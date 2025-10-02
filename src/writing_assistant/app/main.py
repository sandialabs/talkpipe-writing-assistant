from fastapi import FastAPI, Request, Form, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional
import uuid
import json
import threading
from datetime import datetime
from pathlib import Path
from ..core import callbacks as cb
from ..core.definitions import Metadata

# Lock to prevent race conditions when setting environment variables
# Environment variables are process-wide, so we need to serialize access
_env_var_lock = threading.Lock()

app = FastAPI(title="Writing Assistant")

# Generate a random token for this session (like Jupyter does)
AUTH_TOKEN = str(uuid.uuid4())

# Flag to control whether custom environment variables from UI are allowed
# Can be disabled via --disable-custom-env-vars command line flag
ALLOW_CUSTOM_ENV_VARS = True

# Get the directory where this module is located
app_dir = Path(__file__).parent

class NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app.mount("/static", NoCacheStaticFiles(directory=str(app_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(app_dir / "templates"))

# No server-side state - all metadata sent with requests

# Token validation dependency
def validate_token(request: Request):
    """Validate the authentication token from query parameter"""
    token = request.query_params.get("token")
    if token != AUTH_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing authentication token")
    return token

# Helper function to get documents directory
def get_documents_dir():
    home_dir = Path.home()
    docs_dir = home_dir / ".writing_assistant" / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    return docs_dir

def validate_and_sanitize_filename(filename: str) -> str:
    """
    Validate and sanitize filename to prevent directory traversal attacks.

    Args:
        filename: The filename to validate and sanitize

    Returns:
        str: Sanitized filename

    Raises:
        ValueError: If filename is invalid or contains path traversal attempts
    """
    if not filename or not filename.strip():
        raise ValueError("Filename cannot be empty")

    # Check for path traversal attempts BEFORE path normalization
    if '/' in filename or '\\' in filename:
        raise ValueError("Invalid filename: path traversal not allowed")

    # Check for .. as a path component (but allow .. within filenames like test..json)
    if filename == '..' or filename.startswith('../') or filename.startswith('..\\') or '/..' in filename or '\\..' in filename:
        raise ValueError("Invalid filename: path traversal not allowed")

    # Check for absolute paths or drive letters (Windows)
    if filename.startswith('/') or ':' in filename or filename.startswith('.'):
        raise ValueError("Invalid filename: absolute paths not allowed")

    # Now safely extract just the filename part
    filename = Path(filename).name

    # Sanitize: only allow alphanumeric, dots, hyphens, underscores
    sanitized = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_')).strip()

    if not sanitized:
        raise ValueError("Invalid filename: no valid characters remaining after sanitization")

    # Ensure .json extension
    if not sanitized.endswith('.json'):
        sanitized += '.json'

    # Additional length check
    if len(sanitized) > 255:
        raise ValueError("Filename too long")

    return sanitized

def get_safe_filepath(filename: str) -> Path:
    """
    Get a safe filepath within the documents directory.

    Args:
        filename: The filename to validate

    Returns:
        Path: Safe filepath within documents directory

    Raises:
        ValueError: If filename is invalid
    """
    sanitized_filename = validate_and_sanitize_filename(filename)
    docs_dir = get_documents_dir()
    filepath = docs_dir / sanitized_filename

    # Ensure the resolved path is still within the documents directory
    try:
        filepath.resolve().relative_to(docs_dir.resolve())
    except ValueError:
        raise ValueError("Invalid filename: path traversal detected")

    return filepath

@app.get("/", response_class=HTMLResponse, dependencies=[Depends(validate_token)])
async def read_root(request: Request):
    # Empty document for initial render - all state managed in browser
    empty_document = {"title": "", "sections": []}
    return templates.TemplateResponse("index.html", {"request": request, "document": empty_document, "auth_token": AUTH_TOKEN})

@app.get("/favicon.ico")
async def favicon():
    favicon_path = app_dir / "static" / "favicon.ico"
    return FileResponse(favicon_path, media_type="image/x-icon")

@app.get("/config", dependencies=[Depends(validate_token)])
async def get_config():
    """Get server configuration"""
    return {
        "allow_custom_env_vars": ALLOW_CUSTOM_ENV_VARS
    }

# Metadata endpoints removed - all metadata sent with generation requests

@app.post("/documents/save", dependencies=[Depends(validate_token)])
@app.post("/documents/save-as", dependencies=[Depends(validate_token)])
async def save_document(filename: str = Form(...), document_data: str = Form(...)):
    """Save document data provided by the browser"""
    try:
        filepath = get_safe_filepath(filename)
        sanitized_filename = filepath.name

        # Always use document data from frontend
        data_to_save = json.loads(document_data)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)

        return {"status": "success", "filename": sanitized_filename, "path": str(filepath)}
    except ValueError as e:
        return {"status": "error", "message": f"Invalid filename: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/documents/download/{filename}", dependencies=[Depends(validate_token)])
async def download_document(filename: str):
    try:
        filepath = get_safe_filepath(filename)
        if not filepath.exists():
            return {"error": "File not found"}

        return FileResponse(
            str(filepath),
            media_type='application/json',
            filename=filepath.name
        )
    except ValueError as e:
        return {"error": f"Invalid filename: {str(e)}"}
    except Exception as e:
        return {"error": str(e)}

@app.get("/documents/load/{filename}", dependencies=[Depends(validate_token)])
async def load_document_by_filename(filename: str):
    """Return document data for browser to load"""
    try:
        filepath = get_safe_filepath(filename)

        if not filepath.exists():
            return {"status": "error", "message": "File not found"}

        with open(filepath, 'r', encoding='utf-8') as f:
            document_data = json.load(f)

        return {"status": "success", "document": document_data}
    except ValueError as e:
        return {"status": "error", "message": f"Invalid filename: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/documents/list", dependencies=[Depends(validate_token)])
async def list_documents():
    try:
        docs_dir = get_documents_dir()

        files = []
        for filepath in docs_dir.glob("*.json"):
            stat = filepath.stat()
            files.append({
                "filename": filepath.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

        files.sort(key=lambda x: x["modified"], reverse=True)
        return {"files": files}
    except Exception as e:
        return {"error": str(e)}

@app.post("/generate-text", dependencies=[Depends(validate_token)])
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
    environment_variables: str = Form(default="{}")
):
    """Generate text for a section - fully stateless endpoint"""
    import os

    try:
        # Parse environment variables from request
        env_vars = {}
        if environment_variables and ALLOW_CUSTOM_ENV_VARS:
            try:
                env_vars = json.loads(environment_variables)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse environment_variables: {environment_variables}")
        elif environment_variables and not ALLOW_CUSTOM_ENV_VARS:
            print("Info: Custom environment variables disabled by server configuration")

        # Use a lock to prevent race conditions when modifying process-wide environment variables
        # This ensures that concurrent requests don't interfere with each other's env vars
        with _env_var_lock:
            # Store original environment variables to restore later
            original_env = {}
            for key, value in env_vars.items():
                if key in os.environ:
                    original_env[key] = os.environ[key]
                os.environ[key] = str(value)

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

                generated_text = cb.new_paragraph(
                    text=user_text,
                    metadata=metadata,
                    title=title,
                    prev_paragraph=prev_paragraph,
                    next_paragraph=next_paragraph,
                    generation_mode=generation_mode
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
        print(f"Error generating text: {e}")
        return {"error": str(e)}, 500

def get_snapshots_dir():
    """Get the snapshots directory within documents"""
    docs_dir = get_documents_dir()
    snapshots_dir = docs_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    return snapshots_dir

@app.post("/documents/snapshot/{filename}", dependencies=[Depends(validate_token)])
async def create_snapshot(filename: str):
    """Create a timestamped snapshot of a document and clean up old snapshots"""
    try:
        filepath = get_safe_filepath(filename)

        if not filepath.exists():
            return {"status": "error", "message": "File not found"}

        # Generate timestamp prefix
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_filename = f"{timestamp}_{filename}"

        # Save to snapshots subdirectory
        snapshots_dir = get_snapshots_dir()
        snapshot_filepath = snapshots_dir / snapshot_filename

        # Ensure the snapshot filename doesn't contain path traversal
        try:
            snapshot_filepath.resolve().relative_to(snapshots_dir.resolve())
        except ValueError:
            return {"status": "error", "message": "Invalid snapshot filename"}

        # Read current document and save as snapshot
        with open(filepath, 'r', encoding='utf-8') as f:
            document_data = json.load(f)

        with open(snapshot_filepath, 'w', encoding='utf-8') as f:
            json.dump(document_data, f, indent=2, ensure_ascii=False)

        # Clean up old snapshots - keep only the 10 most recent
        base_filename = filepath.name

        # Find all snapshots for this document (files matching pattern: YYYYMMDD_HHMMSS_filename)
        snapshot_pattern = f"*_{base_filename}"
        snapshots = list(snapshots_dir.glob(snapshot_pattern))

        # Sort by modification time (newest first)
        snapshots.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Delete snapshots beyond the 10 most recent
        for old_snapshot in snapshots[10:]:
            old_snapshot.unlink()

        return {
            "status": "success",
            "message": f"Snapshot created: {snapshot_filename}",
            "snapshot_filename": snapshot_filename
        }
    except ValueError as e:
        return {"status": "error", "message": f"Invalid filename: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/documents/snapshots/{filename}", dependencies=[Depends(validate_token)])
async def list_snapshots(filename: str):
    """List all snapshots for a specific document"""
    try:
        # Validate the base filename
        filepath = get_safe_filepath(filename)
        base_filename = filepath.name

        snapshots_dir = get_snapshots_dir()
        snapshot_pattern = f"*_{base_filename}"
        snapshots = list(snapshots_dir.glob(snapshot_pattern))

        # Sort by modification time (newest first)
        snapshots.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        snapshot_list = []
        for snapshot_path in snapshots:
            stat = snapshot_path.stat()
            snapshot_list.append({
                "filename": snapshot_path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

        return {"status": "success", "snapshots": snapshot_list}
    except ValueError as e:
        return {"status": "error", "message": f"Invalid filename: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/documents/snapshot/load/{snapshot_filename}", dependencies=[Depends(validate_token)])
async def load_snapshot(snapshot_filename: str):
    """Load a specific snapshot's content"""
    try:
        # Validate snapshot filename
        sanitized_filename = validate_and_sanitize_filename(snapshot_filename)
        snapshots_dir = get_snapshots_dir()
        snapshot_filepath = snapshots_dir / sanitized_filename

        # Ensure the resolved path is within snapshots directory
        try:
            snapshot_filepath.resolve().relative_to(snapshots_dir.resolve())
        except ValueError:
            return {"status": "error", "message": "Invalid snapshot filename"}

        if not snapshot_filepath.exists():
            return {"status": "error", "message": "Snapshot not found"}

        with open(snapshot_filepath, 'r', encoding='utf-8') as f:
            document_data = json.load(f)

        return {"status": "success", "document": document_data}
    except ValueError as e:
        return {"status": "error", "message": f"Invalid filename: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/documents/delete/{filename}", dependencies=[Depends(validate_token)])
async def delete_document(filename: str):
    """Delete a saved document"""
    try:
        filepath = get_safe_filepath(filename)

        if not filepath.exists():
            return {"status": "error", "message": "File not found"}

        filepath.unlink()
        return {"status": "success", "message": f"Document {filepath.name} deleted successfully"}
    except ValueError as e:
        return {"status": "error", "message": f"Invalid filename: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8001, reload=True)