# ResumeExtractBench

A deterministic, visually-audited benchmark harness for structured resume/CV extraction pipelines. This benchmark runs locally against Ollama, evaluates pipelines using leaf accuracy and row precision/recall, and produces hand-drawn (Nudge-style) annotated visual overlays of the source PDFs to audit parser errors.

## 1. Project Scaffold

* **`corpus/`**: Contains the evaluation corpus.
  * `raw/`: 15 synthetic PDF resumes generated using ReportLab, covering various layout styles (single-column, double-column, table-based).
  * `ground_truth/`: Schema-conforming ground-truth JSON files for each resume.
  * `manifest.csv`: Lists filename, layout type, and active traps.
* **`schema/`**: Target JSON Schema for resume extraction.
  * `resume_schema.json`: Target data model.
  * `TRAPS.md`: Details the three evaluation traps (overlapping dates, duplicate project entries, and embedded organization links).
* **`extractors/`**: Python modules wrapping the evaluated pipelines.
  * `hiring_agent_extractor.py`: Wrapper for the section-wise `hiring-agent` pipeline.
  * `weknora_extractor.py`: A local section-specific Retrieval-Augmented Generation (RAG) extraction pipeline.
  * `raw_llm_extractor.py`: Direct single-shot prompt baseline comparison for both `qwen2.5:1.5b` and `qwen2.5:3b`.
* **`grading/`**:
  * `grader.py`: Computes deterministic leaf accuracy, precision, and recall, and traces structural differences.
  * `test_grader.py`: Unit tests validating the grading logic.
* **`overlay/`**:
  * `render_overlay.py`: PDF rendering and Excalidraw-style wobbly bounding box overlay annotations.
* **`reports/`**:
  * `results.jsonl`: Detail of all 60 benchmark runs.
  * `predictions/`: Raw JSON files output by each extractor pipeline.
  * `overlays/`: Color-coded PNG visual audits of the resumes.
  * `REPORT.md`: Aggregate summary report and findings.
* **`vendor/`**: Cloned upstream reference repositories (read-only).

---

## 2. Benchmark Findings & Performance

Detailed analysis is available in [reports/REPORT.md](file:///c:/Users/krmri/OneDrive/Desktop/project/reports/REPORT.md). A summary of metrics across 15 resumes:

| Pipeline | Leaf Accuracy | Precision | Recall | Avg Latency |
| --- | --- | --- | --- | --- |
| **hiring-agent** (3b) | 65.83% | 0.8178 | 0.9611 | ~19.1s |
| **weknora** (3b, RAG) | 84.84% | 0.6233 | 1.0000 | ~25.6s |
| **raw_llm_3b** (3b, Single-Shot) | **87.42%** | 0.9478 | 1.0000 | ~14.2s |
| **raw_llm_1.5b** (1.5b, Control) | 78.92% | **1.0000** | 1.0000 | **~7.0s** |

### Key Architectural Findings:
* **The Context Size Bottleneck**: The `hiring-agent` provider defaults to a `32768` context window. On local, memory-constrained hardware (e.g. laptop GPUs like the RTX 3050), this causes massive VRAM paging, slowing inference down by **4.35x**. Limiting `num_ctx` to `4096` (which comfortably fits resumes) restores token generation to ~31.5 tokens/sec.
* **Section-wise Tradeoffs**: Segmenting resumes into 6 sequential sections (done in `hiring-agent` and WeKnora) provides clean prompts but introduces a **6x latency multiplier**.
* **Model Size Impact**: Moving from `1.5b` to `3b` parameters yields a massive leap in leaf accuracy (+8.5%) on direct baseline extraction.

---

## 3. How to Run the Benchmark

Ensure you have a local Ollama instance running. If needed, pull the model weights first:
```powershell
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:3b
```

To run the entire suite from scratch:

1. **Active Virtual Environment**:
   ```powershell
   .venv\Scripts\activate
   ```

2. **Execute Benchmark Runner**:
   This runs all 60 evaluations, sequentially grouping models to prevent VRAM overlapping and freeing VRAM between transitions:
   ```powershell
   python scripts/run_benchmark.py
   ```

3. **Generate Visual Overlays**:
   Renders the wobbly annotated audit pages in `reports/overlays/`:
   ```powershell
   python overlay/render_overlay.py
   ```

4. **Compile Report**:
   Generates the markdown summary:
   ```powershell
   python scripts/generate_report.py
   ```

---

## 4. Play and Test with Individual Extractors

You can inspect or run individual extractors manually on any PDF resume.

### Run WeKnora RAG Extractor:
```python
from extractors.weknora_extractor import extract
import json

# Extract details from any resume PDF
result = extract("corpus/raw/resume_1.pdf", schema={})
print(json.dumps(result, indent=2))
```

### Run direct Raw LLM Baseline:
```python
from extractors.raw_llm_extractor import extract
import json

result = extract("corpus/raw/resume_1.pdf", schema={}, model_name="qwen2.5:3b")
print(json.dumps(result, indent=2))
```
