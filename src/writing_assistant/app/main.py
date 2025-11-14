"""Main FastAPI application with multi-user support."""

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core import callbacks as cb
from ..core.definitions import Metadata
from .auth import auth_backend, current_active_user, fastapi_users
from .database import get_async_session
from .models import Document, DocumentSnapshot, User
from .schemas import UserCreate, UserRead, UserUpdate

# Lock to prevent race conditions when setting environment variables
_env_var_lock = threading.Lock()

# Configure logging
logger = logging.getLogger(__name__)

app = FastAPI(title="Writing Assistant - Multi-User")

# Get the directory where this module is located
app_dir = Path(__file__).parent


class NoCacheStaticFiles(StaticFiles):
    """Static files handler that disables caching."""

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


app.mount(
    "/static", NoCacheStaticFiles(directory=str(app_dir / "static")), name="static"
)
templates = Jinja2Templates(directory=str(app_dir / "templates"))

# Flag to control whether custom environment variables from UI are allowed
ALLOW_CUSTOM_ENV_VARS = True


# Include FastAPI Users authentication routers
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Homepage - main app interface."""
    empty_document = {"title": "", "sections": []}
    return templates.TemplateResponse(
        "index.html", {"request": request, "document": empty_document}
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/favicon.ico")
async def favicon():
    """Serve favicon."""
    favicon_path = app_dir / "static" / "favicon.ico"
    return FileResponse(favicon_path, media_type="image/x-icon")


@app.get("/config")
async def get_config():
    """Get server configuration."""
    return {
        "allow_custom_env_vars": ALLOW_CUSTOM_ENV_VARS,
        "multi_user_enabled": True,
    }


@app.get("/auth/check")
async def check_auth(user: User = Depends(current_active_user)):
    """Check if user is authenticated."""
    return {
        "authenticated": True,
        "email": user.email,
        "user_id": str(user.id),
    }


@app.get("/user/preferences")
async def get_user_preferences(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Get user preferences."""
    try:
        # Refresh user to get latest data
        await db.refresh(user)

        if user.preferences:
            return {"status": "success", "preferences": json.loads(user.preferences)}
        else:
            # Return empty preferences if none saved
            return {"status": "success", "preferences": {}}
    except Exception as e:
        logger.error(f"Error retrieving user preferences: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to retrieve user preferences"}


@app.post("/user/preferences")
async def save_user_preferences(
    request: Request,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Save user preferences."""
    try:
        # Get JSON data from request body
        data = await request.json()
        preferences = data.get("preferences", {})

        # Update user preferences
        user.preferences = json.dumps(preferences)
        await db.commit()

        return {"status": "success", "message": "Preferences saved"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error saving user preferences: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to save user preferences"}


@app.post("/documents/save")
async def save_document(
    filename: str = Form(...),
    document_data: str = Form(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Save or update a document for the current user."""
    try:
        # Parse document data
        data = json.loads(document_data)
        title = data.get("title", "")

        # Check if document already exists for this user
        result = await db.execute(
            select(Document).where(
                Document.user_id == user.id, Document.filename == filename
            )
        )
        existing_doc = result.scalar_one_or_none()

        if existing_doc:
            # Update existing document
            existing_doc.title = title
            existing_doc.content = document_data
            existing_doc.updated_at = datetime.utcnow()
            await db.commit()
            return {
                "status": "success",
                "filename": filename,
                "message": "Document updated",
            }
        else:
            # Create new document
            new_doc = Document(
                user_id=user.id, filename=filename, title=title, content=document_data
            )
            db.add(new_doc)
            await db.commit()
            return {
                "status": "success",
                "filename": filename,
                "message": "Document created",
            }

    except json.JSONDecodeError as e:
        logger.error(
            f"Invalid JSON in save_document for {filename}: {e}", exc_info=True
        )
        raise HTTPException(status_code=400, detail="Invalid JSON in document data")
    except Exception as e:
        await db.rollback()
        logger.error(f"Error saving document {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save document")


@app.post("/documents/save-as")
async def save_document_as(
    filename: str = Form(...),
    document_data: str = Form(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Save document with a new filename."""
    # Reuse the save_document logic
    return await save_document(filename, document_data, user, db)


@app.get("/documents/download/{filename}")
async def download_document(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Download a document as JSON file."""
    try:
        result = await db.execute(
            select(Document).where(
                Document.user_id == user.id, Document.filename == filename
            )
        )
        doc = result.scalar_one_or_none()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Return content as downloadable JSON
        return Response(
            content=doc.content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document {filename}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to download document")


@app.get("/documents/load/{filename}")
async def load_document_by_filename(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Load a specific document."""
    try:
        result = await db.execute(
            select(Document).where(
                Document.user_id == user.id, Document.filename == filename
            )
        )
        doc = result.scalar_one_or_none()

        if not doc:
            return {"status": "error", "message": "Document not found"}

        # Parse JSON content
        document_data = json.loads(doc.content)

        return {"status": "success", "document": document_data}

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in document {filename}: {e}", exc_info=True)
        return {"status": "error", "message": "Document contains invalid data"}
    except Exception as e:
        logger.error(f"Error loading document {filename}: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to load document"}


@app.get("/documents/list")
async def list_documents(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all documents for the current user."""
    try:
        result = await db.execute(
            select(Document)
            .where(Document.user_id == user.id)
            .order_by(Document.updated_at.desc())
        )
        documents = result.scalars().all()

        files = [
            {
                "filename": doc.filename,
                "title": doc.title,
                "size": len(doc.content),
                "modified": doc.updated_at.isoformat(),
                "created": doc.created_at.isoformat(),
            }
            for doc in documents
        ]

        return {"files": files}

    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        return {"error": "Failed to list documents"}


@app.post("/generate-text")
async def generate_text(
    user_text: str = Form(default=""),
    title: str = Form(default=""),
    prev_paragraph: str = Form(default=""),
    next_paragraph: str = Form(default=""),
    generation_mode: str = Form(default="ideas"),
    writing_style: str = Form(default="formal"),
    target_audience: str = Form(default=""),
    tone: str = Form(default="neutral"),
    background_context: str = Form(default=""),
    generation_directive: str = Form(default=""),
    word_limit: Optional[int] = Form(default=None),
    source: str = Form(default=""),
    model: str = Form(default=""),
    environment_variables: str = Form(default="{}"),
    user: User = Depends(current_active_user),
):
    """Generate text for a section - requires authentication."""
    import os

    try:
        # Parse environment variables from request
        env_vars = {}
        if environment_variables and ALLOW_CUSTOM_ENV_VARS:
            try:
                env_vars = json.loads(environment_variables)
                print(f"DEBUG: Parsed env vars from request: {env_vars}")
            except json.JSONDecodeError:
                print(
                    f"Warning: Could not parse environment_variables: {environment_variables}"
                )
        elif environment_variables and not ALLOW_CUSTOM_ENV_VARS:
            print("Info: Custom environment variables disabled by server configuration")

        # Use a lock to prevent race conditions
        with _env_var_lock:
            # Store original environment variables
            original_env = {}
            for key, value in env_vars.items():
                if key in os.environ:
                    original_env[key] = os.environ[key]
                os.environ[key] = str(value)
                print(f"DEBUG: Set os.environ[{key}] = {value}")

            try:
                # Create metadata from request parameters
                metadata = Metadata()
                metadata.writing_style = writing_style
                metadata.target_audience = target_audience
                metadata.tone = tone
                metadata.background_context = background_context
                metadata.generation_directive = generation_directive
                metadata.word_limit = word_limit
                metadata.source = source
                metadata.model = model

                # Debug: Show current environment
                print(
                    f"DEBUG: OLLAMA_BASE_URL in os.environ: {os.environ.get('OLLAMA_BASE_URL', 'NOT SET')}"
                )
                print(f"DEBUG: Using source={source}, model={model}")

                # Truncate context to 2000 characters
                # prev_paragraph: keep LAST 2000 characters (most recent context)
                if prev_paragraph and len(prev_paragraph) > 2000:
                    prev_paragraph = prev_paragraph[-2000:]

                # next_paragraph: keep FIRST 2000 characters (upcoming context)
                if next_paragraph and len(next_paragraph) > 2000:
                    next_paragraph = next_paragraph[:2000]

                generated_text = cb.new_paragraph(
                    text=user_text,
                    metadata=metadata,
                    title=title,
                    prev_paragraph=prev_paragraph,
                    next_paragraph=next_paragraph,
                    generation_mode=generation_mode,
                )

                return {"generated_text": generated_text}
            finally:
                # Restore original environment variables
                for key in env_vars.keys():
                    if key in original_env:
                        os.environ[key] = original_env[key]
                    else:
                        os.environ.pop(key, None)

    except Exception as e:
        logger.error(f"Error generating text: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate text")


@app.post("/documents/snapshot/{filename}")
async def create_snapshot(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a timestamped snapshot of a document."""
    try:
        # Find the document
        result = await db.execute(
            select(Document).where(
                Document.user_id == user.id, Document.filename == filename
            )
        )
        doc = result.scalar_one_or_none()

        if not doc:
            return {"status": "error", "message": "Document not found"}

        # Generate snapshot name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"{timestamp}_{filename}"

        # Create snapshot
        snapshot = DocumentSnapshot(
            document_id=doc.id, snapshot_name=snapshot_name, content=doc.content
        )
        db.add(snapshot)

        # Clean up old snapshots - keep only 10 most recent
        snapshots_result = await db.execute(
            select(DocumentSnapshot)
            .where(DocumentSnapshot.document_id == doc.id)
            .order_by(DocumentSnapshot.created_at.desc())
        )
        all_snapshots = snapshots_result.scalars().all()

        # Delete old snapshots beyond the 10 most recent
        for old_snapshot in all_snapshots[10:]:
            await db.delete(old_snapshot)

        await db.commit()

        return {
            "status": "success",
            "message": f"Snapshot created: {snapshot_name}",
            "snapshot_filename": snapshot_name,
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating snapshot for {filename}: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to create snapshot"}


@app.get("/documents/snapshots/{filename}")
async def list_snapshots(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """List all snapshots for a specific document."""
    try:
        # Find the document
        result = await db.execute(
            select(Document).where(
                Document.user_id == user.id, Document.filename == filename
            )
        )
        doc = result.scalar_one_or_none()

        if not doc:
            return {"status": "error", "message": "Document not found"}

        # Get snapshots
        snapshots_result = await db.execute(
            select(DocumentSnapshot)
            .where(DocumentSnapshot.document_id == doc.id)
            .order_by(DocumentSnapshot.created_at.desc())
        )
        snapshots = snapshots_result.scalars().all()

        snapshot_list = [
            {
                "filename": snap.snapshot_name,
                "size": len(snap.content),
                "modified": snap.created_at.isoformat(),
            }
            for snap in snapshots
        ]

        return {"status": "success", "snapshots": snapshot_list}

    except Exception as e:
        logger.error(f"Error listing snapshots for {filename}: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to list snapshots"}


@app.get("/documents/snapshot/load/{snapshot_filename}")
async def load_snapshot(
    snapshot_filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Load a specific snapshot's content."""
    try:
        # Find snapshot through document ownership
        result = await db.execute(
            select(DocumentSnapshot)
            .join(Document)
            .where(
                Document.user_id == user.id,
                DocumentSnapshot.snapshot_name == snapshot_filename,
            )
        )
        snapshot = result.scalar_one_or_none()

        if not snapshot:
            return {"status": "error", "message": "Snapshot not found"}

        # Parse JSON content
        document_data = json.loads(snapshot.content)

        return {"status": "success", "document": document_data}

    except json.JSONDecodeError as e:
        logger.error(
            f"Invalid JSON in snapshot {snapshot_filename}: {e}", exc_info=True
        )
        return {"status": "error", "message": "Snapshot contains invalid data"}
    except Exception as e:
        logger.error(f"Error loading snapshot {snapshot_filename}: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to load snapshot"}


@app.delete("/documents/delete/{filename}")
async def delete_document(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Delete a document (and all its snapshots)."""
    try:
        # Find the document
        result = await db.execute(
            select(Document).where(
                Document.user_id == user.id, Document.filename == filename
            )
        )
        doc = result.scalar_one_or_none()

        if not doc:
            return {"status": "error", "message": "Document not found"}

        # Delete document (cascades to snapshots)
        await db.delete(doc)
        await db.commit()

        return {
            "status": "success",
            "message": f"Document {filename} deleted successfully",
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting document {filename}: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to delete document"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8001, reload=True)
