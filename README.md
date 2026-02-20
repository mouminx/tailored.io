# Resume Adjuster (Local)

Local FastAPI app that tailors a resume to a job description using a local Ollama model. It extracts text from a PDF resume, asks the model to make minimal edits, then regenerates a clean PDF.

## Requirements
- Python 3.10+
- Ollama running locally
- macOS: WeasyPrint system deps (via Homebrew)

```bash
brew install pango cairo libffi
```

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
export OLLAMA_MODEL=llama3.1
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Notes
- The model is instructed to use only facts from the original resume and to make minimal edits.
- For pixel-perfect layout, replace `app/templates/resume.html` with your preferred HTML template.
