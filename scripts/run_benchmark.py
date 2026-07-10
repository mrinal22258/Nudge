import os
import sys
import json
import csv
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from grading.grader import grade
from extractors import hiring_agent_extractor
from extractors import weknora_extractor
from extractors import raw_llm_extractor

def run_extraction_with_timeout(extractor_func, pdf_path, schema, **kwargs):
    # Standard function call. On Windows, signal-based timeout is not supported, 
    # so we rely on standard exception handling.
    t0 = time.perf_counter()
    try:
        result = extractor_func(str(pdf_path), schema, **kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return True, None, result, latency_ms
    except Exception as e:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        return False, str(e), None, latency_ms

def main():
    print("=== Starting ResumeExtractBench Run ===")
    
    # 1. Paths
    manifest_path = PROJECT_ROOT / "corpus" / "manifest.csv"
    schema_path = PROJECT_ROOT / "schema" / "resume_schema.json"
    results_path = PROJECT_ROOT / "reports" / "results.jsonl"
    predictions_root = PROJECT_ROOT / "reports" / "predictions"
    
    predictions_root.mkdir(parents=True, exist_ok=True)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Clear previous results
    if results_path.exists():
        os.remove(results_path)

    # 2. Load schema
    with open(schema_path, "r") as f:
        schema = json.load(f)

    # 3. Load manifest
    resumes = []
    with open(manifest_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            resumes.append(row)

    print(f"Loaded {len(resumes)} resumes from manifest.")

    # 4. Define pipelines
    pipelines = [
        {
            "name": "hiring-agent",
            "extract_func": hiring_agent_extractor.extract,
            "args": {}
        },
        {
            "name": "weknora",
            "extract_func": weknora_extractor.extract,
            "args": {"model_name": "qwen2.5:3b"}
        },
        {
            "name": "raw_llm_1.5b",
            "extract_func": raw_llm_extractor.extract,
            "args": {"model_name": "qwen2.5:1.5b"}
        },
        {
            "name": "raw_llm_3b",
            "extract_func": raw_llm_extractor.extract,
            "args": {"model_name": "qwen2.5:3b"}
        }
    ]

    import subprocess
    
    # Open results.jsonl for writing
    current_model = None
    total_runs = len(pipelines) * len(resumes)
    run_idx = 0
    
    with open(results_path, "w", encoding="utf-8") as rf:
        for pipeline in pipelines:
            pipe_name = pipeline["name"]
            model_name = pipeline.get("model_name")
            
            # Manage Ollama model transitions to prevent VRAM memory contention
            if model_name and current_model and model_name != current_model:
                print(f"\n[Ollama] Unloading model '{current_model}' before loading '{model_name}'...")
                try:
                    subprocess.run(["ollama", "stop", current_model], capture_output=True)
                except Exception as e:
                    print(f"  Warning: Failed to stop model: {e}")
            
            if model_name:
                current_model = model_name
                
            print(f"\n=== Pipeline: {pipe_name} (using {model_name}) ===")
            
            # Setup predictions subfolder
            pipe_pred_dir = predictions_root / pipe_name
            pipe_pred_dir.mkdir(parents=True, exist_ok=True)
            
            for resume in resumes:
                run_idx += 1
                filename = resume["filename"]
                base_name = Path(filename).stem
                pdf_path = PROJECT_ROOT / "corpus" / "raw" / filename
                gt_path = PROJECT_ROOT / "corpus" / "ground_truth" / f"{base_name}.json"
                pred_out_path = pipe_pred_dir / f"{base_name}.json"
                
                # Load ground truth
                with open(gt_path, "r") as f:
                    ground_truth = json.load(f)
                    
                print(f"[{run_idx}/{total_runs}] Extracting {filename}...", end="", flush=True)
                
                # Execute extraction
                success, failure_reason, predicted, latency_ms = run_extraction_with_timeout(
                    pipeline["extract_func"],
                    pdf_path,
                    schema,
                    **pipeline["args"]
                )
                
                scores = {}
                field_diffs = []
                completed = False
                
                if success and predicted:
                    # Save predicted JSON
                    with open(pred_out_path, "w", encoding="utf-8") as pf:
                        json.dump(predicted, pf, indent=2)
                        
                    # Grade output
                    grade_res = grade(schema, predicted, ground_truth)
                    completed = grade_res["completed"]
                    failure_reason = grade_res["failure_reason"]
                    
                    if completed:
                        scores = {
                            "leaf_accuracy": grade_res["leaf_accuracy"],
                            "precision": grade_res["precision"],
                            "recall": grade_res["recall"],
                            "leaf_total": grade_res["leaf_total"],
                            "leaf_match": grade_res["leaf_match"]
                        }
                        field_diffs = grade_res["field_diffs"]
                else:
                    # Save error info to predictions directory
                    with open(pred_out_path, "w", encoding="utf-8") as pf:
                        json.dump({"error": failure_reason}, pf, indent=2)

                # Write result line
                result_line = {
                    "resume": filename,
                    "extractor": pipe_name,
                    "completed": completed,
                    "failure_reason": failure_reason,
                    "scores": scores,
                    "field_diffs": field_diffs,
                    "latency_ms": round(latency_ms, 2)
                }
                
                rf.write(json.dumps(result_line, ensure_ascii=False) + "\n")
                rf.flush()
                
                if completed:
                    print(f" Done. Leaf Acc: {scores['leaf_accuracy']}%, P: {scores['precision']}, R: {scores['recall']} ({latency_ms/1000:.1f}s)")
                else:
                    print(f" Failed. Reason: {failure_reason} ({latency_ms/1000:.1f}s)")
                    
        # Unload final model at the end
        if current_model:
            print(f"\n[Ollama] Unloading final model '{current_model}'...")
            try:
                subprocess.run(["ollama", "stop", current_model], capture_output=True)
            except:
                pass

    print("\n=== Benchmark run completed. Results written to reports/results.jsonl ===")

if __name__ == "__main__":
    main()
