import json
import os
import sys
from typing import Dict, Any, List
import hmac
from backend.database import _sign_entry

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
    from backend.interviewer import MAX_CANVAS_CHARS

    formatted_transcript = []
    transcript_list = session.get("transcript", [])
    last_canvas_idx = -1
    for i, entry in enumerate(transcript_list):
        if entry.get("type") == "canvas":
            last_canvas_idx = i

    for i, entry in enumerate(transcript_list):
        entry_type = entry.get("type", "")
        content = entry.get("content", "")
        if entry_type == "canvas":
            if i != last_canvas_idx:
                content = "[Canvas state snapshot: Shapes updated (content omitted for readability)]"
            elif len(content) > MAX_CANVAS_CHARS:
                content = (
                    content[:MAX_CANVAS_CHARS]
                    + "\n... [canvas truncated — whiteboard has more content than shown here]"
                )

        formatted_transcript.append(
            f"Index [{entry.get('index')}] - Type: {entry_type} - Timestamp: {entry.get('timestamp')}\n"
            f"Content:\n{content}\n"
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
        
        # 1. Filter out-of-bounds citations and verify signatures (tamper-evidence)
        valid_citations = []
        for c in citations:
            if c in valid_indices:
                entry = next((e for e in transcript if e["index"] == c), None)
                if entry:
                    expected_sig = _sign_entry(session.get("id"), entry)
                    provided_sig = entry.get("signature")
                    if provided_sig and hmac.compare_digest(provided_sig, expected_sig):
                        valid_citations.append(c)
                    else:
                        print(f"[Verification Warning] Signature mismatch or missing for citation index {c}")
        
        # If citations were modified or dropped, we add a verification notice
        if len(valid_citations) < len(citations):
            verdict += " (Note: Some ungrounded citations were removed by the verifier.)"
            
        # 2. Semantic grounding check: verify if the cited entries correspond to the section topic
        # and verify with Ollama
        final_citations = []
        import ollama
        client = ollama.Client(host="http://localhost:11434")
        
        for c in valid_citations:
            entry = next((e for e in transcript if e["index"] == c), None)
            if entry:
                content = entry.get("content") or ""
                content_lower = content.lower()
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
                    # Must be actual candidate dialogue text, not AI text or raw canvas serialization
                    if entry_type == "user":
                        is_valid_semantic = True
                        
                elif area == "problem_solving":
                    # User dialogue showing strategy or canvas
                    if entry_type == "canvas":
                        is_valid_semantic = True
                    elif entry_type == "user":
                        solve_keywords = ["approach", "solve", "design", "idea", "first", "then", "strategy", "complexity", "o(", "big o", "optimize", "improve", "analyse", "breakdown"]
                        if any(kw in content_lower for kw in solve_keywords):
                            is_valid_semantic = True
                
                # Second pass semantic check via Ollama YES/NO call
                if is_valid_semantic:
                    prompt = f"""Does this specific transcript entry support this specific verdict sentence?
Transcript Entry: "{content}"
Verdict: "{verdict}"
Answer only YES or NO."""
                    try:
                        resp = client.chat(
                            model="qwen2.5:3b",
                            messages=[
                                {"role": "system", "content": "You are a binary verification assistant. Reply only with YES or NO."},
                                {"role": "user", "content": prompt}
                            ],
                            options={"temperature": 0.1, "num_ctx": 4096}
                        )
                        ans = resp["message"]["content"].strip().upper()
                        if "<think>" in ans:
                            think_end = ans.find("</think>")
                            if think_end != -1:
                                ans = ans[think_end + 8:].strip().upper()
                        
                        if "YES" in ans:
                            final_citations.append(c)
                        else:
                            print(f"[Verification] Citation index {c} failed semantic verification. Model answer: {ans}")
                    except Exception as e:
                        print(f"[Verification Error] Semantic check failed for citation {c}: {e}")
                        # Fallback
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
