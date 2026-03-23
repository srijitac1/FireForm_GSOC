# FireForm Setup Guide

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) running locally with the `mistral` model pulled
- `pip install -r requirements.txt`

## Running the API

```bash
uvicorn api.main:app --reload
```

## Adding Your Own PDF Templates

FireForm stores fillable PDF templates in `src/templates/`. Any PDF placed here can be registered once and reused indefinitely — no re-upload needed.

### Step 1 — Copy your fillable PDF

```bash
cp /path/to/your_form.pdf src/templates/your_form.pdf
```

### Step 2 — Register it via the API

```bash
curl -X POST http://localhost:8000/templates/register \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "your_form.pdf",
    "name": "My Department Form",
    "fields": {"FIELD_1": "", "FIELD_2": ""}
  }'
```

The `fields` dict should map each PDF field name to an empty string. FireForm uses this to know which fields to extract from the incident transcript.

### Step 3 — Fill the form

```bash
curl -X POST http://localhost:8000/forms/fill \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "John Smith responded to a structure fire at 123 Main St...",
    "template_id": 1
  }'
```

### Batch filling (multiple agencies at once)

```bash
curl -X POST http://localhost:8000/forms/fill/batch \
  -H "Content-Type: application/json" \
  -d '{
    "input_text": "John Smith, firefighter, responded to...",
    "template_ids": [1, 2, 3]
  }'
```

## Output Files

Filled PDFs are saved to `src/outputs/` with the naming pattern:

```
<template_stem>_<YYYYMMDD_HHMMSS>_filled.pdf
```

This directory is gitignored — outputs are never committed.

## Running Tests

```bash
pytest tests/ -v
```
