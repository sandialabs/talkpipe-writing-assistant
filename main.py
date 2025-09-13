from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
import uuid
import json
from datetime import datetime
from pathlib import Path
import callbacks as cb

app = FastAPI(title="Writing Assistant")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class Section:
    def __init__(self, id: str = None, main_point: str = "", user_text: str = "", order: int = 0):
        self.id = id or str(uuid.uuid4())
        self.main_point = main_point
        self.user_text = user_text
        self.generated_text = self.generate_text(main_point=main_point, text=user_text)
        self.order = order
    
    def generate_text(self, main_point: str, text: str, metadata: 'Metadata' = None) -> str:

        # if not text.strip():
        #     return ""
        
        # if metadata is None:
        #     return text.upper()
        
        # enhanced_text = ""
        
        # # Add source and model info if provided
        # if metadata.source or metadata.model:
        #     source_info = []
        #     if metadata.source:
        #         source_info.append(f"SOURCE: {metadata.source.upper()}")
        #     if metadata.model:
        #         source_info.append(f"MODEL: {metadata.model.upper()}")
        #     enhanced_text += f"[{', '.join(source_info)}] "
        
        # # Add style and tone info
        # style_info = f"[{metadata.writing_style.upper()} STYLE"
        # if metadata.tone != "neutral":
        #     style_info += f", {metadata.tone.upper()} TONE"
        # if metadata.target_audience:
        #     style_info += f", FOR: {metadata.target_audience.upper()}"
        # style_info += f"] "
        # enhanced_text += style_info
        
        # # Add the main text
        # enhanced_text += text.upper()
        
        # # Add directive if provided
        # if metadata.generation_directive:
        #     enhanced_text += f" [DIRECTIVE: {metadata.generation_directive.upper()}]"
        
        # # Add word limit if specified
        # if metadata.word_limit:
        #     enhanced_text += f" [LIMIT: {metadata.word_limit} WORDS]"
        
        # return enhanced_text

        return cb.new_paragraph(main_point=main_point, text=text)

    def update_text(self, main_point: str, user_text: str, metadata: 'Metadata' = None):
        self.user_text = user_text
        self.generated_text = self.generate_text(main_point=main_point, text=user_text, metadata=metadata)

class Metadata:
    def __init__(self):
        self.writing_style = "formal"
        self.target_audience = ""
        self.tone = "neutral"
        self.background_context = ""
        self.generation_directive = ""
        self.word_limit = None
        self.source = ""
        self.model = ""

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
                main_point=section_data.get("main_point", ""),
                user_text=section_data.get("user_text", ""),
                order=section_data.get("order", 0)
            )
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
    document.metadata.writing_style = writing_style
    document.metadata.target_audience = target_audience
    document.metadata.tone = tone
    document.metadata.background_context = background_context
    document.metadata.generation_directive = generation_directive
    document.metadata.word_limit = word_limit
    document.metadata.source = source
    document.metadata.model = model
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
        section.main_point = main_point
        section.update_text(main_point, user_text, document.metadata)
        return {
            "id": section.id,
            "main_point": section.main_point,
            "user_text": section.user_text,
            "generated_text": section.generated_text,
            "order": section.order
        }
    return {"error": "Section not found"}, 404

@app.delete("/sections/{section_id}")
async def delete_section(section_id: str):
    if document.delete_section(section_id):
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8001)