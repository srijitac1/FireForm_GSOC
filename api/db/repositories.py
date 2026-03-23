from sqlmodel import Session, select
from api.db.models import Template, FormSubmission
from typing import List

# Templates
def create_template(session: Session, template: Template) -> Template:
    session.add(template)
    session.commit()
    session.refresh(template)
    return template

def get_template(session: Session, template_id: int) -> Template | None:
    return session.get(Template, template_id)

def get_template_by_name(session: Session, name: str) -> Template | None:
    return session.exec(select(Template).where(Template.name == name)).first()

def get_templates_by_ids(session: Session, ids: List[int]) -> List[Template]:
    """Fetch multiple templates in a single query."""
    statement = select(Template).where(Template.id.in_(ids))
    return list(session.exec(statement).all())

def get_all_templates(session: Session) -> List[Template]:
    return list(session.exec(select(Template)).all())

# Forms
def create_form(session: Session, form: FormSubmission) -> FormSubmission:
    session.add(form)
    session.commit()
    session.refresh(form)
    return form

def get_form(session: Session, form_id: int) -> FormSubmission | None:
    return session.get(FormSubmission, form_id)
