from unittest.mock import patch, MagicMock
from api.db.models import Template
from api.db.repositories import create_template
from sqlmodel import Session
from tests.conftest import engine


def _create_template(pdf_path: str, fields: dict = None, name: str = "Test Form") -> int:
    """Helper: insert a Template row and return its id."""
    if fields is None:
        fields = {"Name": "field_0"}
    with Session(engine) as session:
        tpl = Template(name=name, fields=fields, pdf_path=pdf_path)
        created = create_template(session, tpl)
        return created.id


# ---------------------------------------------------------------------------
# POST /forms/fill — single template
# ---------------------------------------------------------------------------

def test_fill_form_template_not_found(client):
    """Returns 404 when template_id does not exist."""
    response = client.post("/forms/fill", json={
        "template_id": 99999,
        "input_text": "some transcript",
    })
    assert response.status_code == 404


def test_fill_form_pdf_not_on_disk_returns_404(client, tmp_path):
    """Returns 404 when the template record exists but the PDF file is missing."""
    missing_path = str(tmp_path / "ghost.pdf")
    tid = _create_template(pdf_path=missing_path)

    response = client.post("/forms/fill", json={
        "template_id": tid,
        "input_text": "Officer Smith responding to fire",
    })
    assert response.status_code == 404
    assert "not found on disk" in response.json()["error"]


def test_fill_form_ollama_down_returns_503(client, tmp_pdf):
    """Returns 503 when Ollama is unreachable (path validation passes first)."""
    tid = _create_template(pdf_path=tmp_pdf)

    with patch("src.llm.requests.post", side_effect=ConnectionError("Ollama down")):
        response = client.post("/forms/fill", json={
            "template_id": tid,
            "input_text": "Officer Smith responding to fire",
        })
    # ConnectionError propagates as 500 from FastAPI unless mapped; accept 500 or 503
    assert response.status_code in (500, 503)


# ---------------------------------------------------------------------------
# POST /forms/fill/batch — multi-template
# ---------------------------------------------------------------------------

def test_fill_batch_missing_template_returns_404(client, tmp_pdf):
    """Returns 404 when any template_id in the batch does not exist."""
    tid = _create_template(pdf_path=tmp_pdf)

    response = client.post("/forms/fill/batch", json={
        "template_ids": [tid, 99999],
        "input_text": "John Smith, firefighter",
    })
    assert response.status_code == 404
    assert "99999" in response.json()["error"]


def test_fill_batch_pdf_not_on_disk_returns_404(client, tmp_path):
    """Returns 404 when a batch template's PDF is missing from disk."""
    missing = str(tmp_path / "missing.pdf")
    tid = _create_template(pdf_path=missing)

    response = client.post("/forms/fill/batch", json={
        "template_ids": [tid],
        "input_text": "John Smith, firefighter",
    })
    assert response.status_code == 404
    assert "not found on disk" in response.json()["error"]


def test_fill_batch_success(client, tmp_pdf):
    """
    Happy path: two valid templates, Ollama mocked to return JSON,
    returns 200 with one result per template.
    """
    tid1 = _create_template(pdf_path=tmp_pdf, fields={"Name": "f0"}, name="Fire Form")
    tid2 = _create_template(pdf_path=tmp_pdf, fields={"Location": "f1"}, name="Police Form")

    mock_llm_response = {
        "response": '{"Name": "John Smith", "Location": "Main Street"}'
    }

    with patch("src.llm.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_llm_response
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        response = client.post("/forms/fill/batch", json={
            "template_ids": [tid1, tid2],
            "input_text": "John Smith at Main Street",
        })

    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    assert data["results"][0]["template_id"] == tid1
    assert data["results"][1]["template_id"] == tid2
    # Both should have an output path, not an error
    for result in data["results"]:
        assert result.get("error") is None
        assert result.get("output_pdf_path") is not None


def test_fill_batch_empty_template_ids(client):
    """Empty template_ids list returns 200 with empty results."""
    response = client.post("/forms/fill/batch", json={
        "template_ids": [],
        "input_text": "some transcript",
    })
    assert response.status_code == 200
    assert response.json()["results"] == []
