import os
import re
import math
import json
import pymupdf
from collections import Counter
from typing import Dict, Any, List

class ExtractionFailure(Exception):
    pass

# Helper to chunk text
def chunk_text(text: str, chunk_size: int = 150, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks if chunks else [text]

# Simple TF-based cosine similarity retriever
def get_similarity(chunk: str, query: str) -> float:
    def tokenize(t):
        return re.findall(r'\w+', t.lower())
    chunk_tokens = tokenize(chunk)
    query_tokens = tokenize(query)
    if not chunk_tokens or not query_tokens:
        return 0.0
    chunk_counts = Counter(chunk_tokens)
    query_counts = Counter(query_tokens)
    
    dot_product = sum(chunk_counts[w] * query_counts[w] for w in query_counts if w in chunk_counts)
    chunk_norm = math.sqrt(sum(c**2 for c in chunk_counts.values()))
    query_norm = math.sqrt(sum(c**2 for c in query_counts.values()))
    if chunk_norm == 0 or query_norm == 0:
        return 0.0
    return dot_product / (chunk_norm * query_norm)

def retrieve_context(chunks: List[str], query: str, top_k: int = 2) -> str:
    scored_chunks = [(chunk, get_similarity(chunk, query)) for chunk in chunks]
    scored_chunks.sort(key=lambda x: x[1], reverse=True)
    best_chunks = [c[0] for c in scored_chunks[:top_k]]
    return "\n\n".join(best_chunks)

def call_ollama(model: str, prompt: str) -> Dict[str, Any]:
    """Call the local Ollama API to extract structured JSON."""
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
        
        # Strip <think> tags if present (e.g. for thinking models)
        if "<think>" in content:
            think_end = content.find("</think>")
            if think_end != -1:
                content = content[think_end + 8:].strip()
                
        return json.loads(content)
    except Exception as e:
        # Fallback or propagate
        raise ExtractionFailure(f"Ollama call failed: {str(e)}")

def extract(pdf_path: str, schema: dict, model_name: str = "qwen2.5:3b") -> dict:
    """Retrieves relevant chunks per section and extracts resume data using Ollama."""
    if not os.path.exists(pdf_path):
        raise ExtractionFailure(f"PDF file not found: {pdf_path}")
        
    try:
        # 1. Extract text from PDF
        text_pages = []
        with pymupdf.open(pdf_path) as doc:
            for page in doc:
                text_pages.append(page.get_text())
        full_text = "\n".join(text_pages)
        
        # 2. Chunk text
        chunks = chunk_text(full_text)
        
        # 3. Retrieve and extract section by section
        # Section A: Basics & Contacts
        basics_query = "contact info email phone telephone links website github linkedin name portfolio"
        basics_context = retrieve_context(chunks, basics_query, top_k=2)
        basics_prompt = f"""Extract the candidate's name and contact info from the context.
Return a JSON object conforming strictly to this format:
{{
  "name": "Candidate Full Name",
  "contact": {{
    "email": "email@example.com",
    "phone": "555-0100",
    "links": ["https://github.com/username", "https://linkedin.com/in/username"]
  }}
}}

Context:
{basics_context}"""
        basics_data = call_ollama(model_name, basics_prompt)
        
        # Section B: Education
        edu_query = "education university college school GPA degree bachelor master phd study institution"
        edu_context = retrieve_context(chunks, edu_query, top_k=2)
        edu_prompt = f"""Extract the candidate's education history from the context.
Return a JSON object conforming strictly to this format:
{{
  "education": [
    {{
      "institution": "University Name",
      "degree": "Bachelor of Science",
      "field": "Computer Science",
      "start_date": "September 2018",
      "end_date": "June 2022",
      "gpa": 3.9
    }}
  ]
}}

Context:
{edu_context}"""
        edu_data = call_ollama(model_name, edu_prompt)
        
        # Section C: Experience
        exp_query = "work experience employment history job company title position roles bullets responsibilities"
        exp_context = retrieve_context(chunks, exp_query, top_k=3)
        exp_prompt = f"""Extract the candidate's work experience history from the context.
Return a JSON object conforming strictly to this format:
{{
  "experience": [
    {{
      "company": "Company Name",
      "title": "Job Title",
      "start_date": "July 2022",
      "end_date": "Present",
      "bullets": [
        "Responsibility or achievement bullet point 1",
        "Responsibility or achievement bullet point 2"
      ]
    }}
  ]
}}

Context:
{exp_context}"""
        exp_data = call_ollama(model_name, exp_prompt)
        
        # Section D: Projects
        proj_query = "projects project name description tech stack technologies links github code"
        proj_context = retrieve_context(chunks, proj_query, top_k=2)
        proj_prompt = f"""Extract the candidate's projects from the context.
Return a JSON object conforming strictly to this format:
{{
  "projects": [
    {{
      "name": "Project Name",
      "description": "Short description of the project.",
      "tech_stack": ["Python", "Docker"],
      "links": ["https://github.com/username/project"]
    }}
  ]
}}

Context:
{proj_context}"""
        proj_data = call_ollama(model_name, proj_prompt)
        
        # Section E: Skills
        skills_query = "skills programming languages technologies databases tools frameworks developer"
        skills_context = retrieve_context(chunks, skills_query, top_k=2)
        skills_prompt = f"""Extract the flat list of the candidate's technical skills from the context.
Return a JSON object conforming strictly to this format:
{{
  "skills": ["Skill1", "Skill2", "Skill3"]
}}

Context:
{skills_context}"""
        skills_data = call_ollama(model_name, skills_prompt)
        
        # Section F: Open Source
        os_query = "open source contributions repository pull request merge issues pr link description github"
        os_context = retrieve_context(chunks, os_query, top_k=2)
        os_prompt = f"""Extract the candidate's open source contributions from the context.
Return a JSON object conforming strictly to this format:
{{
  "open_source_contributions": [
    {{
      "repo": "Repository Name",
      "pr_link": "https://github.com/org/repo/pull/1",
      "description": "Description of the pull request contribution."
    }}
  ]
}}

Context:
{os_context}"""
        os_data = call_ollama(model_name, os_prompt)
        
        # Aggregate
        result = {
            "name": basics_data.get("name") or "",
            "contact": basics_data.get("contact") or {"email": "", "phone": "", "links": []},
            "education": edu_data.get("education") or [],
            "experience": exp_data.get("experience") or [],
            "projects": proj_data.get("projects") or [],
            "skills": skills_data.get("skills") or [],
            "open_source_contributions": os_data.get("open_source_contributions") or []
        }
        return result
        
    except Exception as e:
        raise ExtractionFailure(f"WeKnora extraction failed: {str(e)}")
