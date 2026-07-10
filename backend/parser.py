import os
import sys
import json
import pymupdf
from typing import Dict, Any, List

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.extractors.hiring_agent_extractor import extract as extract_resume

def parse_resume_file(pdf_path: str) -> Dict[str, Any]:
    """Parse candidate resume using the hiring-agent wrapper."""
    return extract_resume(pdf_path, schema={})

def parse_jd_text(jd_text: str) -> Dict[str, Any]:
    """Parse Job Description text into a structured JSON schema using Ollama."""
    import ollama
    client = ollama.Client(host="http://localhost:11434")
    
    prompt = f"""You are an expert technical recruiter. Parse the following job description and extract its core structured details.
Return ONLY a valid JSON object matching the following structure:
{{
  "role": "Title of the position (string)",
  "seniority": "Seniority level, e.g., Junior, Mid, Senior, Lead, Staff (string)",
  "required_skills": ["List of key programming languages, frameworks, concepts, or tools required (array of strings)"],
  "context": "Short summary of the team, product, company context or core expectations (string)"
}}

Job Description:
{jd_text}"""
    
    try:
        response = client.chat(
            model="qwen2.5:3b",
            messages=[
                {"role": "system", "content": "You are a precise data parser. Return only valid JSON matching the requested schema."},
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0.0, "num_ctx": 4096},
            format="json"
        )
        content = response["message"]["content"].strip()
        if "<think>" in content:
            think_end = content.find("</think>")
            if think_end != -1:
                content = content[think_end + 8:].strip()
        return json.loads(content)
    except Exception as e:
        # Fallback in case of model issues
        return {
            "role": "Unknown Role",
            "seniority": "Mid",
            "required_skills": [],
            "context": f"Failed to parse JD: {str(e)}"
        }

def build_gap_profile(resume_structured: Dict[str, Any], jd_structured: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Diff candidate resume against target JD to find gaps and target topics for questions."""
    import ollama
    client = ollama.Client(host="http://localhost:11434")
    
    prompt = f"""Compare the candidate's structured resume profile against the target Job Description to identify technical knowledge gaps and areas for interview targeting.
Rank the topics by importance (how critical they are to the JD compared to the candidate's background).

Candidate Resume Profile:
{json.dumps(resume_structured, indent=2)}

Target JD Profile:
{json.dumps(jd_structured, indent=2)}

Return ONLY a valid JSON array of objects, where each object has:
- "topic": Name of the skill or knowledge area (string)
- "importance": "high" or "medium" or "low" (string)
- "resume_evidence": Summary of candidate's experience in this topic or "None" (string)
- "confidence": Float between 0.0 and 1.0 representing your evaluation confidence (number)

Output Format (strict):
[
  {{
    "topic": "topic name",
    "importance": "high",
    "resume_evidence": "none",
    "confidence": 0.9
  }}
]"""
    
    try:
        response = client.chat(
            model="qwen2.5:3b",
            messages=[
                {"role": "system", "content": "You are a precise gap analyst. Return only a valid JSON array of topics matching the requested schema."},
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0.0, "num_ctx": 4096},
            format="json"
        )
        content = response["message"]["content"].strip()
        if "<think>" in content:
            think_end = content.find("</think>")
            if think_end != -1:
                content = content[think_end + 8:].strip()
        return json.loads(content)
    except Exception as e:
        # Fallback gap analysis based on JD skills list
        gaps = []
        resume_skills_lower = [s.lower() for s in resume_structured.get("skills", [])]
        for skill in jd_structured.get("required_skills", []):
            if skill.lower() not in resume_skills_lower:
                gaps.append({
                    "topic": skill,
                    "importance": "high",
                    "resume_evidence": "None found",
                    "confidence": 0.8
                })
            else:
                gaps.append({
                    "topic": skill,
                    "importance": "medium",
                    "resume_evidence": f"Listed in skills: {skill}",
                    "confidence": 0.8
                })
        return gaps
