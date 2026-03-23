from pydantic import BaseModel
from typing import Optional, List


class FormFill(BaseModel):
    template_id: int
    input_text: str
    use_batch_processing: Optional[bool] = True


class FormFillResponse(BaseModel):
    id: int
    template_id: int
    input_text: str
    output_pdf_path: str

    class Config:
        from_attributes = True


class BatchFormFill(BaseModel):
    template_ids: List[int]
    input_text: str
    use_batch_processing: Optional[bool] = True


class BatchResultItem(BaseModel):
    template_id: int
    output_pdf_path: Optional[str] = None
    error: Optional[str] = None


class BatchFormFillResponse(BaseModel):
    results: List[BatchResultItem]
