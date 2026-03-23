from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from sqlmodel import Session
from api.deps import get_db
from api.schemas.templates import TemplateCreate, RegisterTemplate, TemplateResponse
from api.db.repositories import create_template
from api.db.models import Template
from src.controller import Controller
from src.paths import TEMPLATES_DIR, to_relative

router = APIRouter(prefix="/templates", tags=["templates"])


@router.post("/create", response_model=TemplateResponse)
def create(template: TemplateCreate, db: Session = Depends(get_db)):
    controller = Controller()
    template_path = controller.create_template(template.pdf_path)
    # Ensure stored path is relative
    if Path(template_path).is_absolute():
        template_path = to_relative(template_path)
    tpl = Template(**template.model_dump(exclude={"pdf_path"}), pdf_path=template_path)
    return create_template(db, tpl)


@router.post("/register", response_model=TemplateResponse)
def register(template: RegisterTemplate, db: Session = Depends(get_db)):
    """
    Register a PDF already present in src/templates/ by filename.
    No upload required — the file must exist on disk.
    """
    filename = template.filename

    # Reject path traversal attempts
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename: must not contain '..', '/', or '\\'")

    candidate = TEMPLATES_DIR / filename
    if not candidate.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found in src/templates/"
        )

    pdf_path = f"src/templates/{filename}"
    tpl = Template(name=template.name, pdf_path=pdf_path, fields=template.fields)
    return create_template(db, tpl)
