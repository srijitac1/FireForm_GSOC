from pydantic import BaseModel


class TemplateCreate(BaseModel):
    name: str
    pdf_path: str
    fields: dict


class RegisterTemplate(BaseModel):
    """Schema for registering a PDF already present in src/templates/."""
    filename: str
    name: str
    fields: dict


class TemplateResponse(BaseModel):
    id: int
    name: str
    pdf_path: str
    fields: dict

    class Config:
        from_attributes = True