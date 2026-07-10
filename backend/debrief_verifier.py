import json
import os
import sys
from typing import Dict, Any, List

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.database import db

def generate_raw_debrief(session: Dict[str, Any]) -> Dict[str, Any]:
    """Generates the raw, structured debrief from the transcript using Ollama."""
    import ollama
    client = ollama.Client(host="http://localhost:11434")
    
    # Format the transcript with indices
    formatted_transcript = []
    for entry in session.get("transcript", []):
        formatted_transcript.append(
            f"Index [{entry['index']}] - Type: {entry['type']} - Timestamp: {entry['timestamp']}\n"
            f"Content:\n{entry['content']}\n"
            f"----------------------------------------"
        )
    transcript_str = "\n".join(formatted_transcript)
    
    prompt = f"""You are an elite software engineering bar raiser writing a structured interview debrief.
You must analyze the full transcript of this whiteboard mock interview and evaluate the candidate across four areas:
1. Problem Solving (approach, logical breakdowns)
2. Communication (explanations, clarity)
3. Technical Correctness (correctness of code, diagram schemas)
4. Edge Case Handling (boundary checks, scale issues)

Hard Rule: Every feedback claim you write MUST reference a specific transcript index in its 'citations' array.
If you cannot point to where in the transcript something happened, do not claim it happened. Vague praise or criticism without a transcript pointer will be rejected.

Strict Grading Rule: Evaluate ONLY what the candidate typed (type: 'user' entries) or drew (type: 'canvas' entries). Do NOT give the candidate credit for any knowledge, design terms, formulas, or solutions that were suggested or introduced by the AI interviewer (type: 'ai' entries). If the candidate did not explicitly draw or explain a concept, mark it as a gap in their feedback, even if the AI brought it up as a hint or nudge. If the candidate was quiet, or only wrote 1-2 words on the canvas (e.g., 'chunking' or 'frame') or in the chat, they did NOT write the code or draw the diagram. Do NOT praise the candidate for correctness or claim they wrote a solution when their transcript entries contain no code. Be critical and document their lack of coverage.


Here is the running transcript:
{transcript_str}

Return ONLY a valid JSON object matching the following structure:
{{
  "sections": [
    {{
      "area": "problem_solving",
      "verdict": "Provide 2-4 sentences of concrete evaluation.",
      "citations": [0, 2]
    }},
    {{
      "area": "communication",
      "verdict": "Provide 2-4 sentences of concrete evaluation.",
      "citations": [1]
    }},
    {{
      "area": "correctness",
      "verdict": "Provide 2-4 sentences of concrete evaluation.",
      "citations": [3]
    }},
    {{
      "area": "edge_cases",
      "verdict": "Provide 2-4 sentences of concrete evaluation.",
      "citations": [4]
    }}
  ]
}}"""

    try:
        response = client.chat(
            model="qwen2.5:3b",
            messages=[
                {"role": "system", "content": "You are a precise, citation-backed evaluator. Return only valid JSON matching the requested schema."},
                {"role": "user", "content": prompt}
            ],
            options={"temperature": 0.1, "num_ctx": 4096},
            format="json"
        )
        content = response["message"]["content"].strip()
        if "<think>" in content:
            think_end = content.find("</think>")
            if think_end != -1:
                content = content[think_end + 8:].strip()
        return json.loads(content)
    except Exception as e:
        print(f"[Debrief Gen Error] {e}")
        return {
            "sections": [
                {"area": "problem_solving", "verdict": "Completed mock session.", "citations": []},
                {"area": "communication", "verdict": "Completed mock session.", "citations": []},
                {"area": "correctness", "verdict": "Completed mock session.", "citations": []},
                {"area": "edge_cases", "verdict": "Completed mock session.", "citations": []}
            ]
        }

def verify_debrief_citations(session: Dict[str, Any], raw_debrief: Dict[str, Any]) -> Dict[str, Any]:
    """Runs a verification pass on the generated debrief to ensure all citations are grounded and valid."""
    transcript = session.get("transcript", [])
    valid_indices = {entry["index"] for entry in transcript}
    
    verified_sections = []
    
    for section in raw_debrief.get("sections", []):
        area = section.get("area")
        verdict = section.get("verdict", "")
        citations = section.get("citations", [])
        
        # 1. Filter out-of-bounds citations (deterministic verifier check)
        valid_citations = [c for c in citations if c in valid_indices]
        
        # If citations were modified or dropped, we add a verification notice
        if len(valid_citations) < len(citations):
            verdict += " (Note: Some ungrounded citations were removed by the verifier.)"
            
        # 2. Semantic grounding check: verify if the cited entries correspond to the section topic
        final_citations = []
        for c in valid_citations:
            entry = next((e for e in transcript if e["index"] == c), None)
            if entry:
                content_lower = (entry.get("content") or "").lower()
                entry_type = entry.get("type")
                is_valid_semantic = False
                
                if area == "correctness":
                    # Must be a canvas sketch or user message showing code
                    if entry_type == "canvas":
                        is_valid_semantic = True
                    elif entry_type == "user":
                        code_keywords = ["def ", "class ", "function", "const ", "let ", "var ", "return", "{", "}", "import", "code", "implement", "js", "ts", "python"]
                        if any(kw in content_lower for kw in code_keywords):
                            is_valid_semantic = True
                            
                elif area == "edge_cases":
                    # Must mention edge case keywords or be canvas drawing
                    if entry_type == "canvas":
                        is_valid_semantic = True
                    elif entry_type == "user":
                        edge_keywords = ["edge", "null", "empty", "bound", "limit", "overflow", "error", "check", "scale", "size", "capacity", "handle", "zero", "negative"]
                        if any(kw in content_lower for kw in edge_keywords):
                            is_valid_semantic = True
                            
                elif area == "communication":
                    # Must be actual dialogue (user or AI text), not raw canvas serialization
                    if entry_type in ["user", "ai"]:
                        is_valid_semantic = True
                        
                elif area == "problem_solving":
                    # User dialogue showing strategy or canvas
                    if entry_type == "canvas":
                        is_valid_semantic = True
                    elif entry_type == "user":
                        solve_keywords = ["approach", "solve", "design", "idea", "first", "then", "strategy", "complexity", "o(", "big o", "optimize", "improve", "analyse", "breakdown"]
                        if any(kw in content_lower for kw in solve_keywords):
                            is_valid_semantic = True
                
                if is_valid_semantic:
                    final_citations.append(c)
                    
        # If a section ends up with NO citations, we flag it as 'unverified'
        if not final_citations and transcript:
            verdict = "Claim could not be verified against the session transcript. " + verdict
            
        verified_sections.append({
            "area": area,
            "verdict": verdict,
            "citations": final_citations
        })
        
    return {"sections": verified_sections}

def generate_and_verify_debrief(session_id: str) -> Dict[str, Any]:
    """Combines debrief generation and verification, saving the verified result to the DB."""
    sess = db.get_session(session_id)
    if not sess:
        return {"sections": []}
        
    raw_debrief = generate_raw_debrief(sess)
    verified_debrief = verify_debrief_citations(sess, raw_debrief)
    
    db.save_debrief(session_id, verified_debrief)
    return verified_debrief
