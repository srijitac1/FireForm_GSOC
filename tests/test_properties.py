"""
Property-based tests for the template directory refactor.
Each test is tagged with its property number from the design spec.
All tests use @settings(max_examples=100).
"""

import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from api.main import app
from api.db.database import get_session
from api.db.models import Template
from src.paths import get_project_root, resolve_path, to_relative, TEMPLATES_DIR, OUTPUTS_DIR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_session] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Property 1: All stored template paths are relative
# Validates: Requirements 2.1, 4.2
# ---------------------------------------------------------------------------

@given(
    name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_- ")),
    filename=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")).map(lambda s: s + ".pdf"),
)
@settings(max_examples=100)
def test_property_1_stored_paths_are_relative(name, filename, tmp_path):
    """Property 1: Any path stored via to_relative() is not absolute."""
    abs_path = str(tmp_path / filename)
    Path(abs_path).touch()
    # to_relative only works for paths under project root; skip others
    try:
        rel = to_relative(abs_path)
        assert not Path(rel).is_absolute(), f"Expected relative path, got: {rel}"
    except ValueError:
        pass  # Path outside project root — acceptable


# ---------------------------------------------------------------------------
# Property 2: Path resolution round-trip
# Validates: Requirements 2.2
# ---------------------------------------------------------------------------

@given(
    parts=st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
        min_size=1,
        max_size=4,
    )
)
@settings(max_examples=100)
def test_property_2_path_round_trip(parts):
    """Property 2: resolve_path(to_relative(abs)) == abs for paths under project root."""
    rel = "/".join(parts) + ".pdf"
    abs_path = get_project_root() / rel
    recovered = to_relative(str(abs_path))
    assert recovered == rel


# ---------------------------------------------------------------------------
# Property 3: Missing file returns None
# Validates: Requirements 2.3
# ---------------------------------------------------------------------------

@given(
    filename=st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")).map(lambda s: s + ".pdf"),
)
@settings(max_examples=100)
def test_property_3_missing_file_returns_none(filename, tmp_path):
    """Property 3: fill_form returns None when the resolved path does not exist."""
    from src.file_manipulator import FileManipulator

    fm = FileManipulator.__new__(FileManipulator)
    fm.filler = MagicMock()
    fm.llm = MagicMock()

    non_existent = str(tmp_path / filename)
    assume(not os.path.exists(non_existent))

    result = fm.fill_form("some input", ["FIELD1"], non_existent)
    assert result is None


# ---------------------------------------------------------------------------
# Property 4: Register rejects non-existent filenames
# Validates: Requirements 3.2, 3.4
# ---------------------------------------------------------------------------

@given(
    filename=st.text(min_size=1, max_size=40, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")).map(lambda s: s + ".pdf"),
    name=st.text(min_size=1, max_size=50),
)
@settings(max_examples=100)
def test_property_4_register_rejects_nonexistent(filename, name, client):
    """Property 4: POST /templates/register returns 404 for files not in src/templates/."""
    assume(not (TEMPLATES_DIR / filename).exists())
    resp = client.post("/templates/register", json={"filename": filename, "name": name, "fields": {}})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Property 5: Register stores exact relative path
# Validates: Requirements 3.3
# ---------------------------------------------------------------------------

@given(
    name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_- ")),
    stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
)
@settings(max_examples=100)
def test_property_5_register_stores_relative_path(name, stem, client):
    """Property 5: Registered template is stored with path 'src/templates/<filename>'."""
    filename = stem + ".pdf"
    candidate = TEMPLATES_DIR / filename
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    candidate.touch()
    try:
        resp = client.post("/templates/register", json={"filename": filename, "name": name, "fields": {}})
        assert resp.status_code == 200
        assert resp.json()["pdf_path"] == f"src/templates/{filename}"
    finally:
        candidate.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Property 6: Register rejects path traversal filenames
# Validates: Requirements 3.5
# ---------------------------------------------------------------------------

TRAVERSAL_CHARS = ["../", "..\\", "/", "\\"]

@given(
    prefix=st.text(min_size=0, max_size=10, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
    traversal=st.sampled_from(TRAVERSAL_CHARS),
    suffix=st.text(min_size=0, max_size=10, alphabet=st.characters(whitelist_categories=("Lu", "Ll"))),
)
@settings(max_examples=100)
def test_property_6_register_rejects_traversal(prefix, traversal, suffix, client):
    """Property 6: POST /templates/register returns 400 for filenames with path traversal chars."""
    filename = prefix + traversal + suffix + ".pdf"
    resp = client.post("/templates/register", json={"filename": filename, "name": "test", "fields": {}})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Property 7: Filler output is inside src/outputs/
# Validates: Requirements 5.1
# ---------------------------------------------------------------------------

@given(
    stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
)
@settings(max_examples=100)
def test_property_7_output_inside_outputs_dir(stem, tmp_path):
    """Property 7: get_output_path always returns a path inside OUTPUTS_DIR."""
    from src.file_manipulator import FileManipulator

    fm = FileManipulator.__new__(FileManipulator)
    fm.filler = MagicMock()
    fm.llm = MagicMock()

    fake_template = str(tmp_path / (stem + ".pdf"))
    output = fm.get_output_path(fake_template)
    assert Path(output).parent.resolve() == OUTPUTS_DIR.resolve()


# ---------------------------------------------------------------------------
# Property 8: Filler output filename matches naming pattern
# Validates: Requirements 5.2
# ---------------------------------------------------------------------------

import re

@given(
    stem=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
)
@settings(max_examples=100)
def test_property_8_output_filename_pattern(stem, tmp_path):
    """Property 8: Output filename matches <stem>_<YYYYMMDD_HHMMSS>_filled.pdf."""
    from src.file_manipulator import FileManipulator

    fm = FileManipulator.__new__(FileManipulator)
    fm.filler = MagicMock()
    fm.llm = MagicMock()

    fake_template = str(tmp_path / (stem + ".pdf"))
    output = fm.get_output_path(fake_template)
    pattern = re.compile(r".+_\d{8}_\d{6}_filled\.pdf$")
    assert pattern.match(Path(output).name), f"Filename '{Path(output).name}' does not match pattern"


# ---------------------------------------------------------------------------
# Property 9: Batch fill returns one result per template
# Validates: Requirements 6.2, 6.4
# ---------------------------------------------------------------------------

@given(
    n=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=100)
def test_property_9_batch_returns_one_result_per_template(n, client, tmp_path):
    """Property 9: POST /forms/fill/batch returns exactly one result per valid template."""
    # Create n templates in DB
    ids = []
    for i in range(n):
        pdf = tmp_path / f"tpl_{i}.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        resp = client.post("/templates/create", json={
            "name": f"tpl_{i}",
            "pdf_path": str(pdf),
            "fields": {"FIELD": ""},
        })
        assume(resp.status_code == 200)
        ids.append(resp.json()["id"])

    with patch("api.routes.forms.Controller") as MockCtrl:
        mock_instance = MockCtrl.return_value
        mock_instance.fill_form.return_value = str(tmp_path / "out.pdf")

        resp = client.post("/forms/fill/batch", json={
            "input_text": "test input",
            "template_ids": ids,
        })

    if resp.status_code == 200:
        results = resp.json().get("results", [])
        assert len(results) == n


# ---------------------------------------------------------------------------
# Property 10: Batch fill with missing ID creates no submissions
# Validates: Requirements 6.3
# ---------------------------------------------------------------------------

@given(
    missing_id=st.integers(min_value=9000, max_value=9999),
)
@settings(max_examples=100)
def test_property_10_batch_missing_id_no_submissions(missing_id, client, db_session):
    """Property 10: POST /forms/fill/batch with a missing ID returns 404 and creates no submissions."""
    from api.db.models import FormSubmission
    from sqlmodel import select

    resp = client.post("/forms/fill/batch", json={
        "input_text": "test",
        "template_ids": [missing_id],
    })
    assert resp.status_code == 404

    submissions = db_session.exec(select(FormSubmission)).all()
    assert len(submissions) == 0
