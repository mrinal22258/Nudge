import os
import sys
from pathlib import Path
from typing import Dict, Any

# Define ExtractionFailure exception
class ExtractionFailure(Exception):
    pass

# Ensure DEFAULT_MODEL is set to qwen2.5:3b before importing hiring-agent
os.environ["DEFAULT_MODEL"] = "qwen2.5:3b"

# Add vendor/hiring-agent to sys.path
vendor_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vendor", "hiring-agent"))
if vendor_path not in sys.path:
    sys.path.append(vendor_path)

import models
def patched_chat(self, model: str, messages, options=None, **kwargs):
    ollama_options = options.copy() if options else {}
    ollama_options.pop("stream", None)
    # Force 4096 context window instead of 32768 to prevent VRAM paging on laptop GPUs
    ollama_options["num_ctx"] = 4096
    chat_params = {
        "model": model,
        "messages": messages,
        "options": ollama_options,
    }
    if "stream" in kwargs:
        chat_params["stream"] = kwargs["stream"]
    if "format" in kwargs:
        chat_params["format"] = kwargs["format"]
    return self.client.chat(**chat_params)

models.OllamaProvider.chat = patched_chat

from pdf import PDFHandler

def map_hiring_agent_to_schema(resume_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Maps the output of hiring-agent (JSONResume format) to our schema structure."""
    basics = resume_dict.get("basics") or {}
    
    # Map contact.links from basics.url + profiles
    links = []
    if basics.get("url"):
        links.append(basics["url"])
    for profile in basics.get("profiles") or []:
        if isinstance(profile, dict) and profile.get("url"):
            links.append(profile["url"])
            
    contact = {
        "email": basics.get("email") or "",
        "phone": basics.get("phone") or "",
        "links": links
    }
    
    # Map education
    education = []
    for edu in resume_dict.get("education") or []:
        if not isinstance(edu, dict):
            continue
        gpa_val = None
        score_str = edu.get("score")
        if score_str:
            try:
                gpa_val = float(score_str)
            except ValueError:
                pass
        education.append({
            "institution": edu.get("institution") or "",
            "degree": edu.get("studyType") or "",
            "field": edu.get("area") or "",
            "start_date": edu.get("startDate") or "",
            "end_date": edu.get("endDate") or "",
            "gpa": gpa_val
        })
        
    # Map experience (work)
    experience = []
    for work in resume_dict.get("work") or []:
        if not isinstance(work, dict):
            continue
        experience.append({
            "company": work.get("name") or "",
            "title": work.get("position") or "",
            "start_date": work.get("startDate") or "",
            "end_date": work.get("endDate") or "",
            "bullets": work.get("highlights") or []
        })
        
    # Map projects
    projects = []
    for proj in resume_dict.get("projects") or []:
        if not isinstance(proj, dict):
            continue
        proj_links = []
        if proj.get("url"):
            proj_links.append(proj["url"])
        projects.append({
            "name": proj.get("name") or "",
            "description": proj.get("description") or "",
            "tech_stack": proj.get("technologies") or proj.get("skills") or [],
            "links": proj_links
        })
        
    # Map skills (flatten keywords from categories)
    skills = []
    for skill_cat in resume_dict.get("skills") or []:
        if not isinstance(skill_cat, dict):
            continue
        if skill_cat.get("keywords"):
            skills.extend(skill_cat["keywords"])
        elif skill_cat.get("name"):
            skills.append(skill_cat["name"])
            
    # Remove duplicates from skills
    skills = list(dict.fromkeys(skills))
    
    # open_source_contributions is not supported by hiring-agent default schema
    open_source = []
    
    return {
        "name": basics.get("name") or "",
        "contact": contact,
        "education": education,
        "experience": experience,
        "projects": projects,
        "skills": skills,
        "open_source_contributions": open_source
    }

def extract(pdf_path: str, schema: dict) -> dict:
    """Extract resume data using the hiring-agent pipeline."""
    try:
        # Temporarily switch directory to vendor path so TemplateManager can load templates relative to its directory
        old_cwd = os.getcwd()
        os.chdir(vendor_path)
        try:
            handler = PDFHandler()
        finally:
            os.chdir(old_cwd)
            
        # Extract from PDF using hiring-agent's built-in routines
        # Resolve pdf_path to absolute since we temporarily change directories or for safety
        abs_pdf_path = os.path.abspath(pdf_path)
        json_resume = handler.extract_json_from_pdf(abs_pdf_path)
        if json_resume is None:
            raise ExtractionFailure("hiring-agent failed to parse the PDF (returned None)")
            
        # Convert Pydantic object to dictionary
        if hasattr(json_resume, "model_dump"):
            resume_dict = json_resume.model_dump()
        else:
            resume_dict = json_resume.dict()
            
        # Map to target schema
        mapped_result = map_hiring_agent_to_schema(resume_dict)
        return mapped_result
    except Exception as e:
        raise ExtractionFailure(f"Error during hiring-agent extraction: {str(e)}")
