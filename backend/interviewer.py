import json
import os
import sys
from typing import Dict, Any, List, Optional

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.database import db
from backend.weknora_bank import QUESTION_BANK

def generate_interviewer_turn(session_id: str, is_nudge: bool = False) -> str:
    """Generates the next technical interviewer response (question or nudge) using local Ollama."""
    sess = db.get_session(session_id)
    if not sess:
        return "I'm sorry, I couldn't resolve our current session."
        
    cand = db.get_candidate(sess["candidate_id"]) or {}
    target = db.get_job_target(sess["job_target_id"]) or {}
    
    # 1. Fetch expected approach notes
    question = sess.get("question_details")
    if not question:
        question = next((q for q in QUESTION_BANK if q["id"] == sess["question_id"]), None)
    expected_notes = question["expected_approach_notes"] if question else "Demonstrate problem-solving rigor."
    
    # 2. Re-construct running transcript & latest canvas state
    canvas_transcript = "No elements drawn yet."
    chat_history = []
    
    for entry in sess.get("transcript", []):
        if entry.get("type") == "canvas":
            canvas_transcript = entry.get("content", "")
        elif entry.get("type") == "ai":
            chat_history.append(f"Interviewer: {entry.get('content', '')}")
        elif entry.get("type") == "user":
            chat_history.append(f"Candidate: {entry.get('content', '')}")
            
    # Keep context window under budget by using a sliding window for active chat dialogue
    if len(chat_history) > 10:
        chat_history = ["... [Earlier dialogue truncated for context window efficiency] ..."] + chat_history[-10:]
        
    history_str = "\n".join(chat_history)
    
    # 3. System Prompt
    system_prompt = f"""You are a technical interviewer conducting a real mock interview. You have:
- The candidate's background: {json.dumps(cand.get('resume_structured'), indent=2)}
- The target role: {json.dumps(target.get('jd_structured'), indent=2)}
- The current question: {sess.get('question_prompt')}
- What a strong answer typically covers: {expected_notes}
- The candidate's whiteboard so far (serialized):
{canvas_transcript}

Your job each turn:
1. Read what's actually on the whiteboard now — not what you expect to see.
2. If they've made real progress since your last turn, ask ONE focused follow-up that probes the next weak point or untested edge case — grounded in what's literally drawn/written, not a generic textbook follow-up.
3. If they're stuck (no meaningful change across turns) or if a nudge is requested, give ONE small nudge — not the answer.
4. If they've covered the core of the expected approach, say so plainly and move toward wrapping the question rather than fishing for more.
5. Never invent claims about what's on the canvas — only reference what's actually there.
6. Keep your turn short — 1-3 sentences. This is a live interview, not an essay."""

    # 4. User Prompt
    if is_nudge:
        user_prompt = f"The candidate is stuck and has requested a nudge/hint. Current chat history:\n{history_str}\n\nProvide a supportive, brief nudge/hint to guide them in the right direction."
    else:
        user_prompt = f"Review the canvas state and candidate progress. Provide the next interviewer response. Current chat history:\n{history_str}"
        
    # 5. Local Inference Call
    import ollama
    client = ollama.Client(host="http://localhost:11434")
    try:
        response = client.chat(
            model="qwen2.5:3b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            options={"temperature": 0.2, "num_ctx": 4096}
        )
        content = response["message"]["content"].strip()
        
        # Clean thinking blocks
        if "<think>" in content:
            think_end = content.find("</think>")
            if think_end != -1:
                content = content[think_end + 8:].strip()
                
        return content
    except Exception as e:
        print(f"[Interviewer Error] {e}")
        return "Could you walk me through your thoughts on the whiteboard so far?"
