import json
import os
import sys

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.database import db
from backend.ideal_answer import IdealAnswerGenerator

def main():
    print("=== Ideal Answer Generator Test ===")
    sessions = db.list_sessions()
    if not sessions:
        print("No active sessions found in db.json. Please run an interview setup first.")
        return

    # Grab the first session
    sess = sessions[0]
    session_id = sess["id"]
    print(f"Testing with Session ID: {session_id}")
    print(f"Question Topic: {sess.get('question_topic')}")
    
    # Generate the verified debrief first if not present
    debrief = db.get_debrief(session_id)
    if not debrief:
        print("Debrief not found in database. Mocking a sample verified debrief...")
        mock_debrief = {
            "sections": [
                {
                    "area": "problem_solving",
                    "verdict": "Candidate demonstrated strong initial decomposition of the system requirements.",
                    "citations": [0]
                },
                {
                    "area": "correctness",
                    "verdict": "There were minor database schema alignment issues during tables configuration.",
                    "citations": [1]
                }
            ]
        }
        db.save_debrief(session_id, mock_debrief)
        debrief = mock_debrief
        
    print(f"Active Gaps Citation Indices: {[c for sec in debrief.get('sections', []) for c in sec.get('citations', [])]}")
    
    print("\nGenerating layout plan via local Ollama (qwen2.5:3b)...")
    plan = IdealAnswerGenerator.generate_plan(session_id)
    
    print("\n=== Generated layout plan ===")
    print(json.dumps(plan, indent=2))
    
    # Verify that plan blocks are valid
    print("\n=== Verification checks ===")
    has_errors = False
    valid_citations = [c for sec in debrief.get("sections", []) for c in sec.get("citations", [])]
    
    for block in plan.get("blocks", []):
        b_id = block.get("id")
        b_type = block.get("type")
        b_gap = block.get("addresses_gap")
        
        if b_type not in ["code", "diagram", "note"]:
            print(f"[-] Block {b_id} has invalid type: {b_type}")
            has_errors = True
        if b_gap is not None and b_gap not in valid_citations:
            print(f"[-] Block {b_id} addresses gap {b_gap} which is not a valid citation in the debrief ({valid_citations})")
            has_errors = True
            
    if not has_errors:
        print("[+] SUCCESS: All generated blocks passed strict verification!")
    else:
        print("[-] FAILED: Some elements failed layout plan verification.")

if __name__ == "__main__":
    main()
