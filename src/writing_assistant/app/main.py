from fastapi import FastAPI, Request, Form, UploadFile, File, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json
from datetime import datetime
from pathlib import Path
import asyncio
from ..core import callbacks as cb
from ..core.definitions import Metadata

app = FastAPI(title="Writing Assistant")

# Generate a random token for this session (like Jupyter does)
AUTH_TOKEN = str(uuid.uuid4())

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

# Metadata endpoints removed - all metadata sent with generation requests

@app.post("/documents/save", dependencies=[Depends(validate_token)])
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

@app.post("/documents/save-as", dependencies=[Depends(validate_token)])
async def save_document_as(filename: str = Form(...), document_data: str = Form(...)):
    """Save document data provided by the browser with new filename"""
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
    user_text: str = Form(""),
    title: str = Form(""),
    prev_paragraph: str = Form(""),
    next_paragraph: str = Form(""),
    generation_mode: str = Form("ideas"),
    writing_style: str = Form("formal"),
    target_audience: str = Form(""),
    tone: str = Form("neutral"),
    background_context: str = Form(""),
    generation_directive: str = Form(""),
    word_limit: Optional[int] = Form(None),
    source: str = Form(""),
    model: str = Form("")
):
    """Generate text for a section - fully stateless endpoint"""
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
    except Exception as e:
        print(f"Error generating text: {e}")
        return {"error": str(e)}, 500

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