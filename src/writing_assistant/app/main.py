"""Main FastAPI application with multi-user support."""

import json
import logging
import os
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from talkpipe.util.config import reset_config as reset_talkpipe_config

from ..core import ai_connection
from ..core import callbacks as cb
from ..core.definitions import Metadata
from .auth import auth_backend, current_active_user, fastapi_users
from .database import create_db_and_tables, get_async_session
from .models import Document, DocumentSnapshot, User
from .schemas import UserCreate, UserRead, UserUpdate

# Lock to prevent race conditions when setting environment variables
_env_var_lock = threading.Lock()

# Configure logging
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize the database on application startup."""
    await create_db_and_tables()
    yield


app = FastAPI(title="Writing Assistant - Multi-User", lifespan=lifespan)

# Get the directory where this module is located
app_dir = Path(__file__).parent


class NoCacheStaticFiles(StaticFiles):
    """Static files handler that disables caching."""

    def file_response(self, *args: Any, **kwargs: Any) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


app.mount(
    "/static", NoCacheStaticFiles(directory=str(app_dir / "static")), name="static"
)
templates = Jinja2Templates(directory=str(app_dir / "templates"))


def _allow_custom_env_vars_default() -> bool:
    """Read the ALLOW_CUSTOM_ENV_VARS environment variable (default: allowed)."""
    return os.getenv("ALLOW_CUSTOM_ENV_VARS", "true").strip().lower() not in (
        "false",
        "0",
        "no",
    )


# Flag to control whether custom environment variables from UI are allowed.
# Configurable via the ALLOW_CUSTOM_ENV_VARS environment variable or the
# --disable-custom-env-vars CLI flag (the flag wins when passed).
ALLOW_CUSTOM_ENV_VARS = _allow_custom_env_vars_default()


def _request_env_vars(
    environment_variables: str, source: str, server_url: str, api_key: str
) -> dict[str, Any]:
    """Environment overrides a request is allowed to apply.

    Both the free-form environment variables and the dedicated connection
    fields (Server URL / API Key, interpreted per AI source) let a user
    redirect where the server connects, so they share the
    ALLOW_CUSTOM_ENV_VARS trust switch. The dedicated fields map to the
    variables the selected source's client reads (see
    ai_connection.SOURCE_CONNECTION_ENV_VARS) so users don't have to know
    the variable names; they win over hand-entered variables of the same
    name.
    """
    env_vars: dict[str, Any] = {}
    if not ALLOW_CUSTOM_ENV_VARS:
        if (
            environment_variables not in ("", "{}")
            or server_url.strip()
            or api_key.strip()
        ):
            logger.info("Custom environment variables disabled by server configuration")
        return env_vars
    if environment_variables:
        try:
            env_vars = json.loads(environment_variables)
            # Log the names only - values may contain API keys.
            logger.debug(
                "Applying custom environment variables: %s",
                sorted(env_vars.keys()),
            )
        except json.JSONDecodeError:
            logger.warning("Could not parse environment_variables as JSON")
            env_vars = {}
    env_vars.update(ai_connection.connection_env_overrides(source, server_url, api_key))
    return env_vars


@contextmanager
def _temporary_env_vars(env_vars: dict[str, Any]) -> Iterator[None]:
    """Apply per-request environment variables, restoring them afterwards.

    Holds a lock for the duration so concurrent requests cannot see each
    other's variables. TalkPipe caches its configuration on first load, so
    the config cache is reset on entry and exit whenever variables change.
    """
    with _env_var_lock:
        original_env = {}
        for key, value in env_vars.items():
            if key in os.environ:
                original_env[key] = os.environ[key]
            os.environ[key] = str(value)
        if env_vars:
            reset_talkpipe_config()
        try:
            yield
        finally:
            for key in env_vars:
                if key in original_env:
                    os.environ[key] = original_env[key]
                else:
                    os.environ.pop(key, None)
            # Drop the per-request values from TalkPipe's config cache
            # so later requests see the server-level configuration again.
            if env_vars:
                reset_talkpipe_config()


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
async def read_root(request: Request) -> HTMLResponse:
    """Homepage - main app interface."""
    empty_document = {"title": "", "sections": []}
    return templates.TemplateResponse(
        request,
        "index.html",
        {"document": empty_document},
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Login page."""
    return templates.TemplateResponse(request, "login.html")


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    """Registration page."""
    return templates.TemplateResponse(request, "register.html")


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    """Serve favicon."""
    favicon_path = app_dir / "static" / "favicon.ico"
    return FileResponse(favicon_path, media_type="image/x-icon")


@app.get("/config")
async def get_config() -> dict[str, Any]:
    """Get server configuration."""
    return {
        "allow_custom_env_vars": ALLOW_CUSTOM_ENV_VARS,
        "multi_user_enabled": True,
    }


@app.get("/auth/check")
async def check_auth(user: User = Depends(current_active_user)) -> dict[str, Any]:
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
) -> dict[str, Any]:
    """Get user preferences."""
    try:
        # Refresh user to get latest data
        await db.refresh(user)

        if user.preferences:
            return {"status": "success", "preferences": json.loads(user.preferences)}
        # Return empty preferences if none saved
        return {"status": "success", "preferences": {}}
    except Exception as e:
        logger.exception(f"Error retrieving user preferences: {e}")
        return {"status": "error", "message": "Failed to retrieve user preferences"}


@app.post("/user/preferences")
async def save_user_preferences(
    request: Request,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
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
        logger.exception(f"Error saving user preferences: {e}")
        return {"status": "error", "message": "Failed to save user preferences"}


@app.post("/documents/save")
async def save_document(
    filename: str = Form(...),
    document_data: str = Form(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
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
        logger.exception(f"Invalid JSON in save_document for {filename}: {e}")
        raise HTTPException(
            status_code=400, detail="Invalid JSON in document data"
        ) from e
    except Exception as e:
        await db.rollback()
        logger.exception(f"Error saving document {filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save document") from e


@app.post("/documents/save-as")
async def save_document_as(
    filename: str = Form(...),
    document_data: str = Form(...),
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Save document with a new filename."""
    # Reuse the save_document logic
    return await save_document(filename, document_data, user, db)


@app.get("/documents/download/{filename}")
async def download_document(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> Response:
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
        logger.exception(f"Error downloading document {filename}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to download document"
        ) from e


@app.get("/documents/load/{filename}")
async def load_document_by_filename(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
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
        logger.exception(f"Invalid JSON in document {filename}: {e}")
        return {"status": "error", "message": "Document contains invalid data"}
    except Exception as e:
        logger.exception(f"Error loading document {filename}: {e}")
        return {"status": "error", "message": "Failed to load document"}


@app.get("/documents/list")
async def list_documents(
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
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
        logger.exception(f"Error listing documents: {e}")
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
    word_limit: int | None = Form(default=None),
    source: str = Form(default=""),
    model: str = Form(default=""),
    environment_variables: str = Form(default="{}"),
    server_url: str = Form(default=""),
    api_key: str = Form(default=""),
    user: User = Depends(current_active_user),
) -> dict[str, str]:
    """Generate text for a section - requires authentication."""
    try:
        env_vars = _request_env_vars(environment_variables, source, server_url, api_key)

        with _temporary_env_vars(env_vars):
            # Create metadata from request parameters
            metadata = Metadata()
            metadata.writing_style = writing_style
            metadata.target_audience = target_audience
            metadata.tone = tone
            metadata.background_context = background_context
            metadata.generation_directive = generation_directive
            metadata.word_limit = word_limit
            # Source names are lowercase (openai, anthropic, ollama);
            # normalize so "Ollama" etc. from the UI still works.
            metadata.source = source.strip().lower()
            metadata.model = model.strip()

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

    except Exception as e:
        logger.exception(f"Error generating text: {e}")
        # The exception is classified (missing settings, unknown source,
        # credentials, missing model, unreachable server) and the user gets
        # a message written here from safe inputs - the request's own
        # source/model and the classification - never the exception text,
        # which may carry internal hostnames, paths or SDK internals. The
        # full detail is in the server log above.
        norm_source = source.strip().lower()
        norm_model = model.strip()
        if isinstance(e, ValueError):
            if "Model name and source must be provided" in str(e):
                # TalkPipe could not resolve a model/source: the request
                # supplied neither and the server has no default configured.
                # The library message talks about configuration files and
                # environment variables, which means nothing to a web-UI
                # user - point them at Settings instead.
                missing_source = not norm_source
                missing_model = not norm_model
                if missing_source and missing_model:
                    hint = (
                        "No AI source or model is configured. Open Settings "
                        "→ AI Settings, choose an AI Source and enter a "
                        "Model name (e.g. llama3.1:8b or gpt-4o), or ask the "
                        "server administrator to configure a server default."
                    )
                elif missing_model:
                    hint = (
                        "No model name is set. Open Settings → AI "
                        "Settings and enter a Model name (e.g. llama3.1:8b "
                        "or gpt-4o)."
                    )
                else:
                    hint = (
                        "No AI source is selected. Open Settings → AI "
                        "Settings and choose an AI Source (openai, anthropic, "
                        "or ollama)."
                    )
            elif "Unknown source" in str(e):
                hint = (
                    f"Unknown AI source '{norm_source}'. Valid sources: "
                    "openai, anthropic, ollama"
                )
            else:
                hint = (
                    "Invalid generation settings (ValueError). Details are "
                    "in the server log."
                )
            raise HTTPException(
                status_code=400, detail=f"Failed to generate text: {hint}"
            ) from e

        category = ai_connection.classify_failure(e)
        if category in ("credentials", "missing_model", "connection"):
            # A configuration/backend problem the user can act on: describe
            # it the same way the Test Connection button would, pointing at
            # the dialog fields that were actually in play for this request.
            ui_server_url = server_url.strip() if ALLOW_CUSTOM_ENV_VARS else ""
            ui_api_key = bool(api_key.strip()) and ALLOW_CUSTOM_ENV_VARS
            reason = ai_connection.failure_reason(
                e, norm_source, norm_model, ui_server_url, ui_api_key
            )
            raise HTTPException(
                status_code=502, detail=f"Failed to generate text: {reason}"
            ) from e
        raise HTTPException(status_code=500, detail="Failed to generate text") from e


@app.post("/ai/test-connection")
async def test_ai_connection(
    source: str = Form(default=""),
    model: str = Form(default=""),
    environment_variables: str = Form(default="{}"),
    server_url: str = Form(default=""),
    api_key: str = Form(default=""),
    user: User = Depends(current_active_user),
) -> dict[str, Any]:
    """Test whether the configured AI source/model is reachable.

    Works with any registered AI source (openai, anthropic, ollama, ...):
    runs a minimal token-capped probe through the same TalkPipe adapter the
    generation path uses (workbench-style), under the same per-request
    environment overrides as /generate-text, and reports an actionable
    reason on failure.
    """
    env_vars = _request_env_vars(environment_variables, source, server_url, api_key)
    # Tell the probe which connection values came from the dialog (and were
    # actually applied) so its failure hints can point back at the right
    # field instead of at server-side configuration.
    ui_server_url = server_url.strip() if ALLOW_CUSTOM_ENV_VARS else ""
    ui_api_key = bool(api_key.strip()) and ALLOW_CUSTOM_ENV_VARS
    with _temporary_env_vars(env_vars):
        return ai_connection.test_connection(
            source.strip().lower(),
            model.strip(),
            server_url_override=ui_server_url,
            api_key_supplied=ui_api_key,
        )


@app.post("/documents/snapshot/{filename}")
async def create_snapshot(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
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
        logger.exception(f"Error creating snapshot for {filename}: {e}")
        return {"status": "error", "message": "Failed to create snapshot"}


@app.get("/documents/snapshots/{filename}")
async def list_snapshots(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
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
        logger.exception(f"Error listing snapshots for {filename}: {e}")
        return {"status": "error", "message": "Failed to list snapshots"}


@app.get("/documents/snapshot/load/{snapshot_filename}")
async def load_snapshot(
    snapshot_filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
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
        logger.exception(f"Invalid JSON in snapshot {snapshot_filename}: {e}")
        return {"status": "error", "message": "Snapshot contains invalid data"}
    except Exception as e:
        logger.exception(f"Error loading snapshot {snapshot_filename}: {e}")
        return {"status": "error", "message": "Failed to load snapshot"}


@app.delete("/documents/delete/{filename}")
async def delete_document(
    filename: str,
    user: User = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
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
        logger.exception(f"Error deleting document {filename}: {e}")
        return {"status": "error", "message": "Failed to delete document"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="localhost", port=8001, reload=True)
