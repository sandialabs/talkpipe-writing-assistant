from fastapi import FastAPI, Request, Form, UploadFile, File, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
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

# Current metadata state for the stateless API
current_metadata = Metadata()

# Helper function to get documents directory
def get_documents_dir():
    home_dir = Path.home()
    docs_dir = home_dir / ".writing_assistant" / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    return docs_dir

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Empty document for initial render - all state managed in browser
    empty_document = {"title": "", "sections": []}
    return templates.TemplateResponse("index.html", {"request": request, "document": empty_document})

@app.get("/favicon.ico")
async def favicon():
    favicon_path = app_dir / "static" / "favicon.ico"
    return FileResponse(favicon_path, media_type="image/x-icon")

@app.get("/metadata")
async def get_metadata():
    return {
        "writing_style": current_metadata.writing_style,
        "target_audience": current_metadata.target_audience,
        "tone": current_metadata.tone,
        "background_context": current_metadata.background_context,
        "generation_directive": current_metadata.generation_directive,
        "word_limit": current_metadata.word_limit,
        "source": current_metadata.source,
        "model": current_metadata.model
    }

@app.post("/metadata")
async def update_metadata(
    writing_style: str = Form("formal"),
    target_audience: str = Form(""),
    tone: str = Form("neutral"),
    background_context: str = Form(""),
    generation_directive: str = Form(""),
    word_limit: Optional[int] = Form(None),
    source: str = Form(""),
    model: str = Form("")
):
    print(f"=== Updating metadata ===")
    print(f"Received source: '{source}', model: '{model}'")
    print(f"Received writing_style: '{writing_style}', target_audience: '{target_audience}'")

    current_metadata.writing_style = writing_style
    current_metadata.target_audience = target_audience
    current_metadata.tone = tone
    current_metadata.background_context = background_context
    current_metadata.generation_directive = generation_directive
    current_metadata.word_limit = word_limit
    current_metadata.source = source
    current_metadata.model = model

    print(f"After update - metadata.source: '{current_metadata.source}', metadata.model: '{current_metadata.model}'")
    print("=== End metadata update ===")
    return {"status": "success"}

@app.post("/documents/save")
async def save_document(filename: str = Form(...), document_data: str = Form(...)):
    """Save document data provided by the browser"""
    try:
        if not filename.endswith('.json'):
            filename += '.json'

        # Sanitize filename
        filename = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_')).strip()

        docs_dir = get_documents_dir()
        filepath = docs_dir / filename

        # Always use document data from frontend
        data_to_save = json.loads(document_data)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)

        return {"status": "success", "filename": filename, "path": str(filepath)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/documents/save-as")
async def save_document_as(filename: str = Form(...), document_data: str = Form(...)):
    """Save document data provided by the browser with new filename"""
    try:
        if not filename.endswith('.json'):
            filename += '.json'

        # Sanitize filename
        filename = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_')).strip()

        docs_dir = get_documents_dir()
        filepath = docs_dir / filename

        # Always use document data from frontend
        data_to_save = json.loads(document_data)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, ensure_ascii=False)

        return {"status": "success", "filename": filename, "path": str(filepath)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/documents/download/{filename}")
async def download_document(filename: str):
    try:
        docs_dir = get_documents_dir()
        filepath = docs_dir / filename
        if not filepath.exists():
            return {"error": "File not found"}

        return FileResponse(
            str(filepath),
            media_type='application/json',
            filename=filename
        )
    except Exception as e:
        return {"error": str(e)}

@app.get("/documents/load/{filename}")
async def load_document_by_filename(filename: str):
    """Return document data for browser to load"""
    try:
        docs_dir = get_documents_dir()
        filepath = docs_dir / filename

        if not filepath.exists():
            return {"status": "error", "message": "File not found"}

        with open(filepath, 'r', encoding='utf-8') as f:
            document_data = json.load(f)

        return {"status": "success", "document": document_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/documents/list")
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

@app.post("/generate-text")
async def generate_text(
    main_point: str = Form(""),
    user_text: str = Form(""),
    title: str = Form(""),
    prev_paragraph: str = Form(""),
    next_paragraph: str = Form(""),
    generation_mode: str = Form("ideas")
):
    """Generate text for a section - stateless endpoint"""
    try:
        # Use current metadata for generation
        generated_text = cb.new_paragraph(
            main_point=main_point,
            text=user_text,
            metadata=current_metadata,
            title=title,
            prev_paragraph=prev_paragraph,
            next_paragraph=next_paragraph,
            generation_mode=generation_mode
        )

        return {"generated_text": generated_text}
    except Exception as e:
        print(f"Error generating text: {e}")
        return {"error": str(e)}, 500

@app.delete("/documents/delete/{filename}")
async def delete_document(filename: str):
    """Delete a saved document"""
    try:
        docs_dir = get_documents_dir()
        filepath = docs_dir / filename

        if not filepath.exists():
            return {"status": "error", "message": "File not found"}

        # Safety check - only delete .json files in the documents directory
        if not filename.endswith('.json') or '..' in filename:
            return {"status": "error", "message": "Invalid filename"}

        filepath.unlink()
        return {"status": "success", "message": f"Document {filename} deleted successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)