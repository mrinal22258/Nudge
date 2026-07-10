# Architectural Decisions Log

This document records the architectural and design decisions made during the construction of ResumeExtractBench.

## Initial Decisions

### 1. PowerShell Execution Proxy
- **Context**: The `run_command` tool struggled to locate the `powershell` executable due to environment variable differences.
- **Decision**: Created a `powershell.cmd` script in the workspace directory that proxies execution to `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe %*` and appends Git to the `PATH`. Added it to `.gitignore`.

### 2. PDF Rendering Engine for Windows
- **Context**: Phase 9 requires rendering PDF pages as images. Running on Windows means installing `poppler` for `pdf2image` can be complex/error-prone.
- **Decision**: We will use `pymupdf` (Fitz) or `pdfplumber` for PDF to image rendering, as they are pure python/pip-installable wheels on Windows without external dependencies.

## Vendor repo structure
Below is the directory structure (depth 2) of the cloned vendor repositories, for path referencing in subsequent phases:

- **longextract-bench**:
  - `src/longextract_bench/` (contains `grading.py`, `score.py`, `runner.py`, `cli.py`, etc.)
  - `docs/`
- **hiring-agent**:
  - `prompts/`
  - `config.py`, `evaluator.py`, `github.py`, `llm_utils.py`, `models.py`, `pdf.py`, `prompt.py`, `pymupdf_rag.py`, `score.py`, `transform.py`
- **WeKnora**:
  - `cli/`, `client/`, `cmd/`, `config/`, `dataset/`, `deploy/`, `docker/`, `docreader/`, `docs/`, `examples/`, `frontend/`, `internal/`, `mcp-server/`, `migrations/`, `packages/`, `scripts/`, `skills/`, `tests/`
  - `docker-compose.yml`, `go.mod`, `Makefile`, `rerank_server_demo.py`
- **excalidraw-codepair (branded as Nudge)**:
  - `src/` (contains frontend collaborative Nudge UI)
  - `public/`, `scripts/`, `dev-docs/`, `firebase-project/`
  - `docker-compose.yml`, `package.json`, `vite.config.ts`

## Phase 5 - 8 Optimization Decisions

### 3. VRAM Context Size Optimization
- **Context**: The `hiring-agent` pipeline hardcoded `num_ctx = 32768` (32K tokens). Generating a 32K context window on a 4GB laptop GPU (NVIDIA RTX 3050) forced massive VRAM paging, slowing down generation speed to under 5 tokens/second.
- **Decision**: Monkey-patched `models.OllamaProvider.chat` at runtime inside `extractors/hiring_agent_extractor.py` to intercept and force `num_ctx = 4096`. Set `num_ctx: 4096` in `weknora` and `raw_llm` baseline options. This resulted in a **4.35x speedup** (generation speed rose to ~31.5 tokens/sec).

### 4. Grouped Loops & Model Swapping
- **Context**: Alternating between `qwen2.5:3b` and `qwen2.5:1.5b` per resume (e.g. 1.5b -> 3b -> 1.5b -> 3b) would cause constant model reloading. If `keep_alive` was set to indefinite, both models would load simultaneously, causing VRAM memory contention.
- **Decision**: Restructured `scripts/run_benchmark.py` to loop by **pipeline first**, then by **resume**. This groups all executions using `3b` consecutively, followed by all `1.5b` runs. Added an explicit `subprocess` command to call `ollama stop <old_model>` when switching pipelines to safely free VRAM.

### 5. PDF Pixmap to PIL Image Conversion
- **Context**: `pix.tobytes()` in PyMuPDF defaults to returning compressed PNG byte streams. Passing this directly to PIL's `Image.frombytes("RGB", ...)` threw a `ValueError: not enough image data` since PIL expected raw uncompressed pixel bytes.
- **Decision**: Used `pix.samples` (which returns raw pixel values directly from the buffer) and set the color mode dynamically to `"RGBA" if pix.alpha else "RGB"` inside `overlay/render_overlay.py`.

## Phase 10 - Live Mock Interview Platform Pivot

### 6. Architecture Pivot to Interactive Whiteboard App
- **Context**: User requested pivoting from a static PDF grader benchmark to a fully functional interactive technical whiteboard mock interview platform.
- **Decision**: Restructured the project into a FastAPI/Socket.io backend + React/Vite Nudge frontend. Built a unified backend orchestrating candidate creation, JD parsing, gap profiling, question retrieval, chat generation, stuck detection, and debriefing.

### 7. Unified Socket.io Collaboration & Application Server
- **Context**: Nudge client is collaborative and expects a WebSocket sync server on port 3002. Running a separate Node.js server adds configuration complexity.
- **Decision**: Implemented Socket.io directly on the Python FastAPI backend, allowing it to act as both the WebRTC signaling peer coordinator and the application engine receiving canvas/text events.

### 8. Plaintext Canvas Serialization
- **Context**: Nudge peer-to-peer sync utilizes AES-GCM encryption in the browser, making it hard for the python backend to decrypt and understand what is drawn.
- **Decision**: Hooked into `syncElements` inside the client-side `Collab.tsx` to serialize active shape types, labels, coordinates, and arrow bindings into a clean, plain text layout, emitting it unencrypted via `canvas-update` to the backend.

### 9. Stuck/Idle Detector
- **Context**: Candidates can get stuck during drawing or coding, leading to silent, awkward interview pauses.
- **Decision**: Implemented an asynchronous background thread on the backend tracking session activity. If a candidate performs no whiteboard or dialogue update for 45 seconds, the system automatically triggers a 1-3 sentence hint (nudge) from the interviewer.

### 10. Citation-Backed Verifier
- **Context**: Standard LLM evaluation debriefs can hallucinate positive or negative candidate actions.
- **Decision**: Repurposed the deterministic validation concepts of `longextract-bench`. The generated debrief must specify exact citation indices matching event stamps in the session transcript. The verifier checks index bounds, validates content types, and discards or flags un-grounded claims.


