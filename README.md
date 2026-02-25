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

## Deploy On Render (Docker)
This repo includes `Dockerfile` and `render.yaml` for deployment.

1. Push this repo to GitHub.
2. In Render, create a new Blueprint and select this repo.
3. Set `OLLAMA_BASE_URL` in Render environment variables.
4. Set `OLLAMA_API_KEY` if your Ollama endpoint requires auth.
5. Optionally set `OLLAMA_MODEL` (default: `llama3.1`).
6. Deploy.

Your app will run with:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 10000
```

Important:
- `OLLAMA_BASE_URL` must be reachable from Render (not `localhost` on your laptop).
- If you self-host Ollama, expose it on a public/private network URL that Render can access.

## Best No-GPU Option
If you do not want to host your own model server, use a managed Ollama endpoint.

Recommended setup:
- `OLLAMA_BASE_URL=https://ollama.com`
- `OLLAMA_API_KEY=<your_api_key>`
- `OLLAMA_MODEL=<a hosted model name available to your account>`

Then deploy to Render using the same Docker/Blueprint flow above.
