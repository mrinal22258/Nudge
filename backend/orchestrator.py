import uuid
import sys
import os
from datetime import datetime
from typing import Dict, Any, List, Optional

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.database import db
from backend.parser import parse_resume_file, parse_jd_text, build_gap_profile
from backend.weknora_bank import retrieve_top_questions, generate_dynamic_question

class SessionOrchestrator:
    @staticmethod
    def create_session(resume_path: str, jd_text: str, interview_type: str) -> Dict[str, Any]:
        """Creates a candidate, parses the JD, generates a gap profile, retrieves a question, and saves the session."""
        # 1. Parse Resume
        print(f"[Orchestrator] Parsing resume at {resume_path}...")
        resume_structured = parse_resume_file(resume_path)
        candidate_id = str(uuid.uuid4())
        candidate_data = {
            "id": candidate_id,
            "resume_path": resume_path,
            "resume_structured": resume_structured
        }
        db.save_candidate(candidate_id, candidate_data)
        
        # 2. Parse JD
        print("[Orchestrator] Parsing job description...")
        jd_structured = parse_jd_text(jd_text)
        target_id = str(uuid.uuid4())
        
        # 3. Gap Profile Diffing
        print("[Orchestrator] Conducting gap profile analysis...")
        gap_profile = build_gap_profile(resume_structured, jd_structured)
        target_data = {
            "id": target_id,
            "jd_raw": jd_text,
            "jd_structured": jd_structured,
            "gap_profile": gap_profile
        }
        db.save_job_target(target_id, target_data)
        
        # 4. Scenario Question Retrieval (WeKnora matching)
        print(f"[Orchestrator] Retrieving top matching scenario questions for type {interview_type}...")
        matched_questions = retrieve_top_questions(gap_profile, interview_type, limit=3)
        if not matched_questions:
            # Fallback dynamic generation if bank has no match
            dynamic_q = generate_dynamic_question(resume_structured, jd_structured, gap_profile, interview_type)
            matched_questions = [dynamic_q]
            
        question = matched_questions[0]
        
        # 5. Initialize Session
        session_id = str(uuid.uuid4())
        session_data = {
            "id": session_id,
            "candidate_id": candidate_id,
            "job_target_id": target_id,
            "question_id": question["id"],
            "question_topic": question["topic"],
            "question_prompt": question["prompt_text"],
            "question_details": question,
            "matched_questions": matched_questions,
            "current_question_index": 0,
            "status": "setup",
            "transcript": [],
            "started_at": datetime.now().isoformat(),
            "ended_at": None
        }
        db.save_session(session_id, session_data)
        print(f"[Orchestrator] Session {session_id} successfully created.")
        return session_data

    @staticmethod
    def start_interview(session_id: str) -> Optional[Dict[str, Any]]:
        """Starts the active interview state."""
        sess = db.get_session(session_id)
        if sess:
            sess["status"] = "active"
            db.save_session(session_id, sess)
            return sess
        return None

    @staticmethod
    def add_transcript_entry(session_id: str, entry_type: str, content: str) -> Optional[Dict[str, Any]]:
        """Appends a dialogue, nudge, or canvas snapshot to the running transcript."""
        return db.add_session_transcript_entry(session_id, entry_type, content)

    @staticmethod
    def end_interview(session_id: str) -> Optional[Dict[str, Any]]:
        """Sets session status to ended."""
        sess = db.get_session(session_id)
        if sess:
            sess["status"] = "ended"
            sess["ended_at"] = datetime.now().isoformat()
            db.save_session(session_id, sess)
            return sess
        return None
