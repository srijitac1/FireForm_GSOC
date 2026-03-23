import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy.pool import StaticPool

from api.main import app
from api.deps import get_db
from api.db.models import Template, FormSubmission

# In-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def override_get_db():
    with Session(engine) as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def db_session():
    """Provide a clean DB session for each test."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tmp_pdf(tmp_path):
    """
    Create a minimal real fillable PDF on disk so path-validation checks pass
    before any Ollama mock fires.
    """
    from pdfrw import PdfWriter, PdfDict, PdfName, PdfArray, PdfObject, PdfString

    pdf_path = tmp_path / "test_form.pdf"

    writer = PdfWriter()
    page = PdfDict(
        Type=PdfName.Page,
        MediaBox=PdfArray([0, 0, 612, 792]),
        Resources=PdfDict(),
    )

    # Add a simple text widget annotation so the PDF has at least one field
    annot = PdfDict(
        Type=PdfName.Annot,
        Subtype=PdfName.Widget,
        FT=PdfName.Tx,
        T=PdfString("field_0"),
        Rect=PdfArray([100, 700, 300, 720]),
        V=PdfString(""),
    )
    page.Annots = PdfArray([annot])
    writer.addpage(page)
    writer.write(str(pdf_path))

    return str(pdf_path)


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe all rows between tests to prevent state leakage."""
    yield
    with Session(engine) as session:
        for row in session.exec(select(FormSubmission)).all():
            session.delete(row)
        for row in session.exec(select(Template)).all():
            session.delete(row)
        session.commit()
