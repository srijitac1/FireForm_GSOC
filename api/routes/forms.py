import os
from fastapi import APIRouter, Depends
from sqlmodel import Session
from api.deps import get_db
from api.schemas.forms import (
    FormFill, FormFillResponse,
    BatchFormFill, BatchResultItem, BatchFormFillResponse,
)
from api.db.repositories import create_form, get_template, get_templates_by_ids
from api.db.models import FormSubmission
from api.errors.base import AppError
from src.controller import Controller
from src.llm import LLM

router = APIRouter(prefix="/forms", tags=["forms"])


@router.post("/fill", response_model=FormFillResponse)
def fill_form(form: FormFill, db: Session = Depends(get_db)):
    template = get_template(db, form.template_id)
    if not template:
        raise AppError("Template not found", status_code=404)

    # PDF path validation — fixes stale path bug (#235)
    if not os.path.exists(template.pdf_path):
        raise AppError(
            f"PDF file not found on disk: {template.pdf_path}. "
            "Re-register the template with a valid path.",
            status_code=404,
        )

    controller = Controller()
    path = controller.fill_form(
        user_input=form.input_text,
        fields=template.fields,
        pdf_form_path=template.pdf_path,
        use_batch_processing=form.use_batch_processing,
    )

    submission = FormSubmission(**form.model_dump(), output_pdf_path=path)
    return create_form(db, submission)


@router.post("/fill/batch", response_model=BatchFormFillResponse)
def fill_batch(form: BatchFormFill, db: Session = Depends(get_db)):
    """
    Fill multiple PDF templates from a single transcript in one request.

    Single-pass extraction strategy:
      1. Validate all templates upfront — fail fast before any LLM work.
      2. Merge ALL fields from ALL templates into one dynamic superset.
      3. ONE LLM call extracts the full superset.
      4. Python splits the extracted JSON per template (deterministic).
      5. Each template is filled and a FormSubmission is saved to the DB.
    """
    # Step 1 — Validate all templates upfront
    fetched = get_templates_by_ids(db, form.template_ids)
    fetched_map = {t.id: t for t in fetched}

    missing = [tid for tid in form.template_ids if tid not in fetched_map]
    if missing:
        raise AppError(
            f"Templates not found: {missing}",
            status_code=404,
        )

    for template in fetched:
        if not os.path.exists(template.pdf_path):
            raise AppError(
                f"PDF file not found on disk for template {template.id}: {template.pdf_path}. "
                "Re-register the template with a valid path.",
                status_code=404,
            )

    # Step 2 — Build superset of all fields across all templates
    superset_fields: dict = {}
    for template in fetched:
        superset_fields.update(template.fields)

    # Step 3 — ONE LLM call for the entire superset
    llm = LLM(
        transcript_text=form.input_text,
        target_fields=superset_fields,
        use_batch_processing=form.use_batch_processing,
    )
    llm.main_loop()
    extracted_json = llm.get_data()

    # Step 4 & 5 — Split extracted data per template, fill each PDF, persist submissions
    from src.filler import Filler
    filler = Filler()
    results = []

    for tid in form.template_ids:
        template = fetched_map[tid]
        try:
            # Extract only the fields relevant to this template
            template_data = {
                field: extracted_json.get(field)
                for field in template.fields
            }

            output_path = filler.fill_form_with_data(
                pdf_form=template.pdf_path,
                data=template_data,
            )

            submission = FormSubmission(
                template_id=tid,
                input_text=form.input_text,
                output_pdf_path=output_path,
            )
            create_form(db, submission)

            results.append(BatchResultItem(
                template_id=tid,
                output_pdf_path=output_path,
            ))

        except Exception as e:
            results.append(BatchResultItem(
                template_id=tid,
                error=str(e),
            ))

    return BatchFormFillResponse(results=results)
