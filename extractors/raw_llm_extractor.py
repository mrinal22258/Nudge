import os
import json
import pymupdf
from typing import Dict, Any

class ExtractionFailure(Exception):
    pass

def call_ollama(model: str, prompt: str) -> Dict[str, Any]:
    """Call the local Ollama API to extract structured JSON in a single shot."""
    import ollama
    client = ollama.Client(host="http://localhost:11434")
    try:
        response = client.chat(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a precise data extraction agent. Extract structured information and format it strictly as the requested JSON structure. Return ONLY valid JSON, no explanations or reasoning text."
                },
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0.0, "num_ctx": 4096},
            format="json"
        )
        content = response["message"]["content"].strip()
        
        # Strip <think> tags if present
        if "<think>" in content:
            think_end = content.find("</think>")
            if think_end != -1:
                content = content[think_end + 8:].strip()
                
        return json.loads(content)
    except Exception as e:
        raise ExtractionFailure(f"Ollama call failed: {str(e)}")

def extract(pdf_path: str, schema: dict, model_name: str = "qwen2.5:3b") -> dict:
    """Extracts raw resume data in a single shot prompt from full PDF text."""
    if not os.path.exists(pdf_path):
        raise ExtractionFailure(f"PDF file not found: {pdf_path}")
        
    try:
        # 1. Extract text from PDF
        text_pages = []
        with pymupdf.open(pdf_path) as doc:
            for page in doc:
                text_pages.append(page.get_text())
        full_text = "\n".join(text_pages)
        
        # 2. Build single-shot prompt
        prompt = f"""Extract the candidate's details from the resume text below.
You must return a JSON object conforming strictly to the following schema structure:
{{
  "name": "Candidate Full Name (string)",
  "contact": {{
    "email": "email address (string)",
    "phone": "phone number (string)",
    "links": ["list of website, github, linkedin, or portfolio links (array of strings)"]
  }},
  "education": [
    {{
      "institution": "University/School name (string)",
      "degree": "Degree name (string)",
      "field": "Field of study (string)",
      "start_date": "Start date (string)",
      "end_date": "End date or 'Present' (string)",
      "gpa": 3.9 (number or null)
    }}
  ],
  "experience": [
    {{
      "company": "Company name (string)",
      "title": "Job title (string)",
      "start_date": "Start date (string)",
      "end_date": "End date or 'Present' (string)",
      "bullets": ["list of responsibility or achievement bullet points (array of strings)"]
    }}
  ],
  "projects": [
    {{
      "name": "Project name (string)",
      "description": "Short project description (string)",
      "tech_stack": ["list of technologies used (array of strings)"],
      "links": ["list of project links (array of strings)"]
    }}
  ],
  "skills": ["flat array of professional or technical skills (array of strings)"],
  "open_source_contributions": [
    {{
      "repo": "Open source repository name (string)",
      "pr_link": "PR or issue link (string)",
      "description": "Description of contribution (string)"
    }}
  ]
}}

Resume text:
{full_text}"""
        
        result = call_ollama(model_name, prompt)
        
        # Normalize fields to make sure all schema properties are present
        normalized = {
            "name": result.get("name") or "",
            "contact": result.get("contact") or {"email": "", "phone": "", "links": []},
            "education": result.get("education") or [],
            "experience": result.get("experience") or [],
            "projects": result.get("projects") or [],
            "skills": result.get("skills") or [],
            "open_source_contributions": result.get("open_source_contributions") or []
        }
        return normalized
        
    except Exception as e:
        raise ExtractionFailure(f"Raw LLM extraction failed: {str(e)}")
