# Live AI Mock Interview Simulator - Project Architecture & State Summary

This document maps the entire codebase structure, design patterns, and application flows to serve as a context bootstrap for future AI agents.

---

## 1. Project Directory Mapping Tree

```
project/
├── backend/
│   ├── app.py                # FastAPI server, API routes, and Socket.io event orchestrator
│   ├── database.py           # Thread-safe local file-based JSON database (db.json CRUD)
│   ├── debrief_verifier.py   # AI post-interview evaluator (JSON structured STAR-method debrief)
│   ├── ideal_answer.py       # Local Ollama planner for ideal whiteboard canvas layout
│   ├── interviewer.py        # Interviewer LLM turn generator (System prompts, rules, nudges)
│   ├── orchestrator.py       # Session status orchestrator, logs candidate transcripts
│   ├── parser.py             # Resume (PDF parser via PyPDF2) and JD qualification parser
│   └── weknora_bank.py       # 34-question scenario seed bank & TF-IDF gap matcher
│
├── vendor/excalidraw-codepair/ (Running Nudge Frontend app)
│   ├── src/
│   │   ├── components/
│   │   │   └── InterviewApp.tsx   # React Client: Setup page, Live timer sidebar, Debrief tabs
│   │   │
│   │   ├── utils/
│   │   │   ├── serializeCanvas.ts  # Serializes whiteboard shapes & arrows to plain text
│   │   │   └── idealCanvas.ts      # Converts backend ideal plans to Nudge shapes
│   │   │
│   │   └── css/
│   │       └── interview.css       # Clean whitish theme styles, badges, & stopwatch layouts
│   │
│   └── tsconfig.json          # Front-end TypeScript configurations
│
├── db.json                   # File storage for Candidates, JobTargets, Sessions, and Debriefs
└── project_architecture_summary.md  # [THIS FILE] Context booster for coding agents
```

---

## 2. Core Pipelines & Data Flow

### A. Setup & Question Retrieval (WeKnora matching)
1. **Resume & JD Upload**: Candidate uploads their resume PDF and pastes the job description.
2. **Parsing**: `parser.py` parses work experiences, tools, and matches them against JD qualifications to build a structured **Candidate Target Gap Profile**.
3. **Question Ranking**: `weknora_bank.py` merges gaps into a text query, ranks the 34-question bank using TF-IDF cosine similarity, and filters questions matching the selected interview type (Coding, System Design, Behavioral, Finance, AI Engineering, or Product Management).
4. **Session Creation**: The orchestrator saves the top 3 ranked questions under `matched_questions` inside `db.json` and loads the first question.

### B. Interactive whiteboard Interview
- **Live Stopwatch**: A timer on the sidebar tracks active minutes and seconds.
- **Auto-Serialization**: Every 2 seconds, the client runs `serializeCanvas.ts` to convert drawings and arrows into plain text bounding boxes.
- **Interviewer Turn**: When the user sends a message, the canvas serialization is appended. The LLM reads what has been drawn and replies contextually.
- **Nudge / Hint**: The background auto-nudger is **disabled**. Nudges are only generated when the candidate clicks the "Nudge / Hint" button.

### C. Multi-Scenario Transition
- When the candidate clicks **Submit & End**, if they have matched target questions remaining (e.g. they completed scenario 1 of 3):
  - The app shows a choice dialog: **Try Next Scenario** or **Go to Feedback**.
  - **Try Next Scenario** triggers the backend `/api/session/next_scenario/{session_id}` route:
    - Clears active transcripts/debrief caches so the next scenario is graded cleanly.
    - Generates a **new 22-character encryption key** which is set on the URL hash.
    - React unmounts and remounts the Nudge canvas component, guaranteeing a completely blank canvas.
    - Starts the next question.

### D. Verified Debrief & Ideal Whiteboard Highlights
- **AI Evaluation**: `debrief_verifier.py` grades the candidate's transcript using local Ollama.
  - **Strict anti-hallucination rule**: Evaluates ONLY what the candidate typed or drew on the canvas. If they only wrote 1-2 words, it is marked as a critical gap.
  - **Citations**: Claims are backed by a `citations` array referring to transcript indices.
- **Ideal Answer Canvas**: `ideal_answer.py` prompts the local LLM to generate a reference whiteboard plan.
  - **Coding questions**: Output is strictly valid programming code snippets.
  - **System Design questions**: Output is structured component systems (DB, API Gateway, Cache blocks).
- **Bidirectional highlights**: Clicking canvas blocks scrolls to matching feedback gaps; clicking feedback badges selects the block in the reference Nudge canvas.

---

## 3. Future Integration Architecture

To transition completely away from the third-party Excalidraw infrastructure, the following community resources must be developed and integrated:
1. **Documentation Platform**: Replace current placeholder alert links with a documentation site mapping Nudge APIs, features, and setup guides.
2. **Blog & Security Disclosures**: Set up Nudge's product engineering blog detailing the end-to-end local encryption mechanisms.
3. **Community Channels & Issue Trackers**: Replace placeholder alerts with Nudge's Discord, Twitter/X, and GitHub issue trackers.
4. **Export & Sharing Hub**: Replace default public shape libraries with Nudge's curated stencil and diagram libraries.

