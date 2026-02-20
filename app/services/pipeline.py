from __future__ import annotations

import json
from app.models import Resume
from app.services.ollama import chat_json

SYSTEM_PROMPT = """You are a resume assistant. You MUST only use facts that already exist in the resume text. Do not invent employers, titles, dates, degrees, or achievements. Make minimal edits needed to better match the job description, preserving the original tone and details. Output JSON only, conforming to the schema provided."""

SCHEMA = {
    "name": "string",
    "contact": ["string"],
    "summary": "string",
    "skills": ["string"],
    "experience": [
        {
            "role": "string",
            "company": "string",
            "location": "string",
            "dates": "string",
            "bullets": ["string"],
        }
    ],
    "education": [
        {
            "school": "string",
            "degree": "string",
            "dates": "string",
            "details": ["string"],
        }
    ],
    "projects": [
        {
            "name": "string",
            "details": ["string"],
        }
    ],
}

CONSTRAINT_RULES = {
    "one_page": "Keep overall length to about one page; prefer trimming or tightening over adding content.",
    "no_new_facts": "Do not add any facts that are not already in the resume text.",
    "preserve_format": "Preserve the existing section order and headings.",
    "tight_bullets": "Keep bullets short; avoid wrapping to more than ~2 lines.",
    "quantify_when_present": "Emphasize or surface metrics that already exist; do not invent numbers.",
}


def build_prompt(resume_text: str, job_text: str, constraints: list[str]) -> str:
    constraints_text = ", ".join(constraints) if constraints else "none"
    constraints_rules = "\n".join(
        f"- {CONSTRAINT_RULES[key]}" for key in constraints if key in CONSTRAINT_RULES
    )
    if not constraints_rules:
        constraints_rules = "- None."
    return (
        "Resume text:\n"
        + resume_text
        + "\n\nJob description:\n"
        + job_text
        + "\n\nConstraints (keys):\n"
        + constraints_text
        + "\n\nConstraint rules:\n"
        + constraints_rules
        + "\n\nReturn JSON with this schema:\n"
        + json.dumps(SCHEMA, indent=2)
        + "\n\nRules:\n"
        + "- Preserve all facts; do not add new ones.\n"
        + "- Make minimal edits, only where relevant to the job.\n"
        + "- Keep bullets concise and measurable if already present.\n"
    )


def generate_resume(resume_text: str, job_text: str, constraints: list[str]) -> Resume:
    prompt = build_prompt(resume_text, job_text, constraints)
    data = chat_json(SYSTEM_PROMPT, prompt)
    return Resume.model_validate(data)
