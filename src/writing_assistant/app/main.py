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

class Section:
    def __init__(self, id: str = None, main_point: str = "", user_text: str = "", order: int = 0):
        self.id = id or str(uuid.uuid4())
        self.main_point = main_point
        self.user_text = user_text
        self.generated_text = ""
        self.order = order
        self._current_task: Optional[asyncio.Task] = None
        self._pending_request: Optional[dict] = None
        self._generation_lock = asyncio.Lock()

        # No automatic generation in constructor - only manual generation via button
    
    def generate_text(self, main_point: str, text: str, metadata: 'Metadata' = None, title: str = "", prev_paragraph: str = "", next_paragraph: str = "") -> str:
        return cb.new_paragraph(main_point=main_point, text=text, metadata=metadata, title=title, prev_paragraph=prev_paragraph, next_paragraph=next_paragraph)
    
    async def _async_generate_text(self, main_point: str, text: str, metadata: 'Metadata' = None, title: str = "", prev_paragraph: str = "", next_paragraph: str = ""):
        """Internal async method to generate text with proper queuing"""
        # Don't generate if main_point is empty or whitespace only
        if not main_point or not main_point.strip():
            print(f"Skipping generation for section {self.id}: empty main_point")
            return self.generated_text

        request_params = {
            'main_point': main_point,
            'text': text,
            'metadata': metadata,
            'title': title,
            'prev_paragraph': prev_paragraph,
            'next_paragraph': next_paragraph
        }

        async with self._generation_lock:
            # Cancel any existing task to prevent queue buildup
            if self._current_task and not self._current_task.done():
                self._current_task.cancel()
                try:
                    await self._current_task
                except asyncio.CancelledError:
                    pass

            # Clear any pending request
            self._pending_request = None

            # Start new generation immediately
            self._current_task = asyncio.create_task(self._process_generation_queue(request_params))

        # Don't await here - let it run in background
        return self.generated_text
    
    async def _process_generation_queue(self, initial_params: dict):
        """Process single generation request"""
        try:
            # Update section state with current request
            self.main_point = initial_params['main_point']
            self.user_text = initial_params['text']

            # Run the actual generation
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self.generate_text,
                initial_params['main_point'],
                initial_params['text'],
                initial_params['metadata'],
                initial_params['title'],
                initial_params['prev_paragraph'],
                initial_params['next_paragraph']
            )
            self.generated_text = result
        except asyncio.CancelledError:
            print("Generation cancelled")
            raise
        except Exception as e:
            print(f"Generation error: {e}")
            # Keep existing text on error
        finally:
            # Clear current task when done
            async with self._generation_lock:
                self._current_task = None

    async def _generate_text_task(self, main_point: str, text: str, metadata: 'Metadata' = None, title: str = "", prev_paragraph: str = "", next_paragraph: str = ""):
        """Legacy method - kept for compatibility"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_text, main_point, text, metadata, title, prev_paragraph, next_paragraph)

    async def update_text(self, main_point: str, user_text: str, metadata: 'Metadata' = None, title: str = "", prev_paragraph: str = "", next_paragraph: str = ""):
        """Update text with atomic state changes"""
        return await self._async_generate_text(main_point, user_text, metadata, title, prev_paragraph, next_paragraph)

    def get_queue_status(self):
        """Get current queue status for debugging"""
        return {
            'has_current_task': self._current_task is not None and not self._current_task.done(),
            'has_pending_request': self._pending_request is not None,
            'main_point': self.main_point,
            'user_text': self.user_text[:50] + '...' if len(self.user_text) > 50 else self.user_text
        }

class Document:
    def __init__(self):
        self.title = ""
        self.sections: List[Section] = []
        self.metadata = Metadata()
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "title": self.title,
            "sections": [
                {
                    "id": section.id,
                    "main_point": section.main_point,
                    "user_text": section.user_text,
                    "generated_text": section.generated_text,
                    "order": section.order
                }
                for section in self.sections
            ],
            "metadata": {
                "writing_style": self.metadata.writing_style,
                "target_audience": self.metadata.target_audience,
                "tone": self.metadata.tone,
                "background_context": self.metadata.background_context,
                "generation_directive": self.metadata.generation_directive,
                "word_limit": self.metadata.word_limit,
                "source": self.metadata.source,
                "model": self.metadata.model
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def from_dict(self, data):
        self.title = data.get("title", "")
        self.created_at = data.get("created_at", datetime.now().isoformat())
        self.updated_at = datetime.now().isoformat()
        
        # Load metadata
        metadata_data = data.get("metadata", {})
        self.metadata.writing_style = metadata_data.get("writing_style", "formal")
        self.metadata.target_audience = metadata_data.get("target_audience", "")
        self.metadata.tone = metadata_data.get("tone", "neutral")
        self.metadata.background_context = metadata_data.get("background_context", "")
        self.metadata.generation_directive = metadata_data.get("generation_directive", "")
        self.metadata.word_limit = metadata_data.get("word_limit", None)
        self.metadata.source = metadata_data.get("source", "")
        self.metadata.model = metadata_data.get("model", "")
        
        # Load sections
        self.sections = []
        for section_data in data.get("sections", []):
            section = Section(
                id=section_data.get("id"),
                main_point="",  # Don't trigger generation during loading
                user_text="",
                order=section_data.get("order", 0)
            )
            # Set the data directly to avoid triggering generation
            section.main_point = section_data.get("main_point", "")
            section.user_text = section_data.get("user_text", "")
            section.generated_text = section_data.get("generated_text", "")
            self.sections.append(section)
        
        self.reorder_sections()
    
    def add_section(self, main_point: str = "", user_text: str = "", position: Optional[int] = None) -> Section:
        if position is None:
            order = len(self.sections)
            section = Section(main_point=main_point, user_text=user_text, order=order)
            self.sections.append(section)
        else:
            section = Section(main_point=main_point, user_text=user_text, order=position)
            self.sections.insert(position, section)
            self.reorder_sections()
        return section
    
    def delete_section(self, section_id: str) -> bool:
        self.sections = [s for s in self.sections if s.id != section_id]
        self.reorder_sections()
        return True
    
    def reorder_sections(self):
        for i, section in enumerate(self.sections):
            section.order = i
    
    def move_section(self, section_id: str, new_position: int):
        section = next((s for s in self.sections if s.id == section_id), None)
        if section:
            self.sections.remove(section)
            self.sections.insert(new_position, section)
            self.reorder_sections()

    def get_section_context(self, section_id: str):
        """Get title, previous paragraph, and next paragraph for a given section"""
        section_index = next((i for i, s in enumerate(self.sections) if s.id == section_id), None)
        if section_index is None:
            return self.title, "", ""

        prev_paragraph = ""
        next_paragraph = ""

        if section_index > 0:
            prev_section = self.sections[section_index - 1]
            prev_paragraph = prev_section.generated_text or prev_section.user_text

        if section_index < len(self.sections) - 1:
            next_section = self.sections[section_index + 1]
            next_paragraph = next_section.generated_text or next_section.user_text

        return self.title, prev_paragraph, next_paragraph

# Helper function to get documents directory
def get_documents_dir():
    home_dir = Path.home()
    docs_dir = home_dir / ".writing_assistant" / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    return docs_dir

document = Document()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "document": document})

@app.get("/favicon.ico")
async def favicon():
    favicon_path = app_dir / "static" / "favicon.ico"
    return FileResponse(favicon_path, media_type="image/x-icon")

@app.get("/metadata")
async def get_metadata():
    return {
        "writing_style": document.metadata.writing_style,
        "target_audience": document.metadata.target_audience,
        "tone": document.metadata.tone,
        "background_context": document.metadata.background_context,
        "generation_directive": document.metadata.generation_directive,
        "word_limit": document.metadata.word_limit,
        "source": document.metadata.source,
        "model": document.metadata.model
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

    document.metadata.writing_style = writing_style
    document.metadata.target_audience = target_audience
    document.metadata.tone = tone
    document.metadata.background_context = background_context
    document.metadata.generation_directive = generation_directive
    document.metadata.word_limit = word_limit
    document.metadata.source = source
    document.metadata.model = model

    print(f"After update - metadata.source: '{document.metadata.source}', metadata.model: '{document.metadata.model}'")
    print("=== End metadata update ===")
    return {"status": "success"}

@app.post("/title")
async def update_title(title: str = Form(...)):
    document.title = title
    return {"status": "success"}

@app.post("/sections")
async def add_section(position: Optional[int] = Form(None)):
    section = document.add_section(position=position)
    return {
        "id": section.id,
        "main_point": section.main_point,
        "user_text": section.user_text,
        "generated_text": section.generated_text,
        "order": section.order
    }

@app.put("/sections/{section_id}")
async def update_section(section_id: str, main_point: str = Form(""), user_text: str = Form("")):
    section = next((s for s in document.sections if s.id == section_id), None)
    if section:
        # Get context information
        title, prev_paragraph, next_paragraph = document.get_section_context(section_id)

        # Use the section's built-in queuing system (max 2 requests)
        await section.update_text(main_point, user_text, document.metadata, title, prev_paragraph, next_paragraph)

        return {
            "id": section.id,
            "main_point": main_point,
            "user_text": user_text,
            "generated_text": section.generated_text,  # Return current text immediately
            "order": section.order
        }
    return {"error": "Section not found"}, 404

@app.patch("/sections/{section_id}")
async def update_section_data_only(section_id: str, main_point: str = Form(""), user_text: str = Form("")):
    """Update section data without triggering text generation"""
    section = next((s for s in document.sections if s.id == section_id), None)
    if section:
        # Update fields directly without triggering generation
        section.main_point = main_point
        section.user_text = user_text

        return {
            "id": section.id,
            "main_point": section.main_point,
            "user_text": section.user_text,
            "generated_text": section.generated_text,
            "order": section.order
        }
    return {"error": "Section not found"}, 404

@app.get("/sections/{section_id}/generated")
async def get_generated_text(section_id: str):
    section = next((s for s in document.sections if s.id == section_id), None)
    if section:
        return {
            "id": section.id,
            "generated_text": section.generated_text,
            "is_generating": section._current_task is not None and not section._current_task.done()
        }
    return {"error": "Section not found"}, 404

@app.get("/sections/{section_id}/debug")
async def get_section_debug_info(section_id: str):
    section = next((s for s in document.sections if s.id == section_id), None)
    if section:
        return {
            "id": section.id,
            "queue_status": section.get_queue_status()
        }
    return {"error": "Section not found"}, 404

@app.delete("/sections/{section_id}")
async def delete_section(section_id: str):
    section = next((s for s in document.sections if s.id == section_id), None)
    if section:
        # Cancel any ongoing generation
        if section._current_task and not section._current_task.done():
            section._current_task.cancel()
        document.delete_section(section_id)
        return {"status": "success"}
    return {"error": "Section not found"}, 404

@app.put("/sections/{section_id}/move")
async def move_section(section_id: str, new_position: int = Form(...)):
    document.move_section(section_id, new_position)
    return {"status": "success"}

@app.post("/documents/save")
async def save_document(filename: str = Form(...)):
    try:
        if not filename.endswith('.json'):
            filename += '.json'
        
        # Sanitize filename
        filename = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_')).strip()
        
        docs_dir = get_documents_dir()
        filepath = docs_dir / filename
        document_data = document.to_dict()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(document_data, f, indent=2, ensure_ascii=False)
        
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

@app.post("/documents/load")
async def load_document(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        document_data = json.loads(contents.decode('utf-8'))
        
        document.from_dict(document_data)
        
        return {"status": "success", "title": document.title}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/documents/load/{filename}")
async def load_document_by_filename(filename: str):
    try:
        docs_dir = get_documents_dir()
        filepath = docs_dir / filename
        
        if not filepath.exists():
            return {"status": "error", "message": "File not found"}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            document_data = json.load(f)
        
        document.from_dict(document_data)
        
        return {"status": "success", "title": document.title}
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

@app.delete("/documents/{filename}")
async def delete_document(filename: str):
    try:
        docs_dir = get_documents_dir()
        filepath = docs_dir / filename
        if filepath.exists():
            filepath.unlink()
            return {"status": "success"}
        else:
            return {"status": "error", "message": "File not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/documents/clear")
async def clear_document():
    """Clear the current document and create a fresh one"""
    global document
    # Cancel any ongoing generation tasks
    for section in document.sections:
        if section._current_task and not section._current_task.done():
            section._current_task.cancel()

    # Create a new document instance
    document = Document()
    return {"status": "success"}

@app.post("/generate-text")
async def generate_text(
    main_point: str = Form(""),
    user_text: str = Form(""),
    title: str = Form(""),
    prev_paragraph: str = Form(""),
    next_paragraph: str = Form(""),
    generation_mode: str = Form("ideas")
):
    """Generate text for a section using the new interface format"""
    try:
        # Use the existing text generation function
        generated_text = cb.new_paragraph(
            main_point=main_point,
            text=user_text,
            metadata=document.metadata,
            title=title,
            prev_paragraph=prev_paragraph,
            next_paragraph=next_paragraph,
            generation_mode=generation_mode
        )

        return {"generated_text": generated_text}
    except Exception as e:
        print(f"Error generating text: {e}")
        return {"error": str(e)}, 500

@app.post("/documents/save-document")
async def save_document_new_format(
    filename: str = Form(...),
    document_data: str = Form(...)
):
    """Save document in the new interface format"""
    try:
        if not filename.endswith('.json'):
            filename += '.json'

        # Sanitize filename
        filename = "".join(c for c in filename if c.isalnum() or c in ('.', '-', '_')).strip()

        docs_dir = get_documents_dir()
        filepath = docs_dir / filename

        # Parse the document data
        document_dict = json.loads(document_data)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(document_dict, f, indent=2, ensure_ascii=False)

        return {"status": "success", "filename": filename, "path": str(filepath)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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