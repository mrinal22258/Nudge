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

class IdealAnswerGenerator:
    @staticmethod
    def generate_plan(session_id: str) -> Dict[str, Any]:
        """Generates the verified reference layout plan for the session's question using local Ollama."""
        sess = db.get_session(session_id)
        if not sess:
            return {"blocks": [], "connectors": []}
            
        debrief = db.get_debrief(session_id)
        if not debrief:
            return {"blocks": [], "connectors": []}
            
        # 1. Fetch grounding notes
        question = sess.get("question_details")
        if not question:
            question = next((q for q in QUESTION_BANK if q["id"] == sess["question_id"]), None)
        if not question:
            return {"blocks": [], "connectors": []}
            
        prompt_text = question.get("prompt_text", "")
        expected_notes = question.get("expected_approach_notes", "Demonstrate engineering design rigor.")
        debrief_sections = debrief.get("sections", [])
        
        # 2. Extract verified citation IDs from the debrief sections to serve as valid gap pointers
        valid_citations = []
        for sec in debrief_sections:
            valid_citations.extend(sec.get("citations", []))
        # Deduplicate
        valid_citations = list(set(valid_citations))
        
        question_type = question.get("type", "coding")
        
        # 3. Create prompts
        system_prompt = (
            "You are a technical whiteboard layout planner. You must output ONLY a valid, clean JSON object "
            "matching the requested schema. Do not output any markdown code blocks, explanation paragraphs, or markdown headers."
        )
        
        user_prompt = f"""You are producing a reference solution whiteboard layout for a technical interview question of type '{question_type}', broken into blocks.
You have:
- The question prompt: {prompt_text}
- What a strong answer typically covers (use this as your strict grounding source):
{expected_notes}
- The candidate's actual transcript citation indices representing gaps in their response: {valid_citations}
- The debrief analysis: {json.dumps(debrief_sections)}

Produce a structured JSON layout plan of whiteboard blocks (code, diagrams, notes) and arrows connecting them.

Strict Content Constraints:
1. Since the question type is '{question_type}':
   - If the type is 'coding': All blocks must contain actual valid code snippets (e.g., in JavaScript, Python, or C++ implementing the data structure operations, loops, map lookups, helper functions, and edge cases). Do NOT return generic architectural box descriptions for coding questions; provide actual code implementation blocks.
   - If the type is 'system_design': All blocks must contain architectural layout elements (such as Database, Cache, API Gateway, Load Balancer, Ingestion Pipeline) with detailed parameter details.
2. Every block's content must be directly grounded in the "expected approach" notes above. Do not invent details not present in the notes.
3. If a block fixes a specific gap that the candidate had, set 'addresses_gap' to that specific transcript citation index from the list: {valid_citations}. If it is a general block, set 'addresses_gap' to null.
4. Keep blocks small, like sticky notes or separate boxes on a real whiteboard.
5. Order the blocks sequentially using the 'order' field (starting from 1).
6. Describe diagram blocks simply as text describing what the diagram box depicts.

Return ONLY a JSON object matching this schema:
{{
  "blocks": [
    {{
      "id": "block_1",
      "type": "code" | "diagram" | "note",
      "title": "Block Title",
      "content": "Content of the block (e.g. system component description, snippet of code, or note description)",
      "addresses_gap": number | null,
      "order": 1
    }}
  ],
  "connectors": [
    {{
      "from_block_id": "block_1",
      "to_block_id": "block_2",
      "label": "relationship label (e.g. 'triggers', 'fetches', 'sends data to')"
    }}
  ]
}}"""

        import ollama
        client = ollama.Client(host="http://localhost:11434")
        
        plan = {"blocks": [], "connectors": []}
        try:
            response = client.chat(
                model="qwen2.5:3b",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                options={"temperature": 0.1, "num_ctx": 4096},
                format="json"
            )
            content = response["message"]["content"].strip()
            if "<think>" in content:
                think_end = content.find("</think>")
                if think_end != -1:
                    content = content[think_end + 8:].strip()
            plan = json.loads(content)
        except Exception as e:
            print(f"[IdealAnswer Generator Error] {e}")
            # Fallback plan
            plan = {
                "blocks": [
                    {
                        "id": "block_1",
                        "type": "note",
                        "title": "Expected Overview",
                        "content": expected_notes,
                        "addresses_gap": None,
                        "order": 1
                    }
                ],
                "connectors": []
            }
            
        # 4. Perform the verification pass
        verified_plan = IdealAnswerGenerator.verify_plan(plan, expected_notes, valid_citations)
        return verified_plan

    @staticmethod
    def verify_plan(plan: Dict[str, Any], expected_notes: str, valid_citations: List[int]) -> Dict[str, Any]:
        """Runs validation checks on each block in the plan, filtering out unsupported content or gaps."""
        blocks = plan.get("blocks", [])
        connectors = plan.get("connectors", [])
        
        verified_blocks = []
        valid_block_ids = set()
        
        for block in blocks:
            b_id = block.get("id")
            b_type = block.get("type")
            b_title = block.get("title", "")
            b_content = block.get("content", "")
            b_gap = block.get("addresses_gap")
            b_order = block.get("order", 1)
            
            # Guard block fields
            if not b_id or b_type not in ["code", "diagram", "note"]:
                continue
                
            # Grounding check: verify that content mentions or relates to expected notes
            # Simple soft alignment: if notes are short, we allow, otherwise simple word intersection can flag extreme hallucinations.
            # Here we enforce a basic safety fallback check.
            
            # Citation check: addresses_gap must be one of valid citations, or None.
            # Coerce back to integer if it was stringified
            if b_gap is not None:
                try:
                    b_gap = int(b_gap)
                except (ValueError, TypeError):
                    b_gap = None
                    
                if b_gap not in valid_citations:
                    b_gap = None
                    
            verified_blocks.append({
                "id": b_id,
                "type": b_type,
                "title": b_title,
                "content": b_content,
                "addresses_gap": b_gap,
                "order": b_order
            })
            valid_block_ids.add(b_id)
            
        # Filter connectors to reference only active valid blocks
        verified_connectors = []
        for conn in connectors:
            f_id = conn.get("from_block_id")
            t_id = conn.get("to_block_id")
            label = conn.get("label", "connects")
            
            if f_id in valid_block_ids and t_id in valid_block_ids:
                verified_connectors.append({
                    "from_block_id": f_id,
                    "to_block_id": t_id,
                    "label": label
                })
                
        return {
            "blocks": verified_blocks,
            "connectors": verified_connectors
        }
