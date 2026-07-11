# Nudge: AI-Powered Whiteboard Mock Interview Simulator

Nudge is a premium, privacy-focused, local-first mock interview simulator designed to test candidates on whiteboard problem-solving. By leveraging local LLMs (Ollama) and real-time canvas serialization, Nudge provides a high-fidelity mock interview experience across multiple technical and business domains.

---

## 1. Core Product Features

### 🎯 Multi-Scenario Interview Tracks
Nudge moves beyond standard software engineering loops to support multiple career tracks:
- **Coding**: Algorithmic problem-solving with live whiteboard canvas coding.
- **System Design**: Visual block diagram design (Databases, Load Balancers, API Gateways, Caches).
- **Behavioral**: Situational leadership, conflict resolution, and communication mock interviews.
- **Finance**: Quantitative math, capital structures, and portfolio design challenges.
- **AI Engineering**: Neural network architectures, fine-tuning configurations, and model deployment pipelines.
- **Product Management**: Product strategy, wireframing, feature prioritization, and roadmap designs.

### 🔎 Resume & JD Target Matcher (WeKnora Cosine Similarity)
- Candidates upload their resume as a PDF and paste the target job description (JD).
- The backend parses candidate competencies, identifies technical gaps, and queries a curated bank of **34 scenario-based questions** using TF-IDF cosine similarity.
- The top 3 matching scenarios are loaded as a customized interview track.

### 🎨 Live Whiteboard Canvas Integration
- An interactive whiteboard canvas built on a custom React package (`vendor/excalidraw-codepair`).
- Every 2 seconds, the client serializes drawings, text, arrows, and blocks into structural ASCII representations and sends them to the local LLM.
- The AI interviewer actively "reads" your drawings and answers in real-time.

### 📊 Citation-Backed Performance Scorecard
- Evaluates the final transcript across four dimensions: **Problem Solving**, **Communication**, **Correctness**, and **Edge Cases**.
- Generates a STAR-method performance scorecard.
- **Strict Anti-Hallucination Guardrails**: Evaluates *only* what the candidate typed in chat or drew on the whiteboard. Every feedback point features a clickable timeline citation pointing back to the transcript events.

### 💡 Ideal Answer Reference Canvas
- Upon completing a scenario, candidates unlock a split-screen view containing the **Ideal Answer**.
- System Design tracks render database blocks, queues, and gateways. Coding tracks render fully written reference implementations.

---

## 2. Project Architecture Summary

```
project/
├── backend/
│   ├── app.py                # FastAPI server, API routing, and Socket.io events
│   ├── database.py           # Local file-based database controller (db.json CRUD)
│   ├── interviewer.py        # System prompt orchestrator for the AI Interviewer turn loop
│   ├── debrief_verifier.py   # AI STAR-method evaluation verifier with strict grounding
│   ├── ideal_answer.py       # LLM reference canvas structure planner
│   ├── parser.py             # PDF text parser for resume uploads
│   └── weknora_bank.py       # 34-question seed bank with TF-IDFCosine matching
│
├── vendor/excalidraw-codepair/
│   ├── src/
│   │   ├── components/
│   │   │   └── InterviewApp.tsx   # React Frontend: setup, live whiteboard, and scorecard
│   │   └── utils/
│   │       ├── serializeCanvas.ts  # Serializes shapes & lines to plain text
│   │       └── idealCanvas.ts      # Draws reference solutions on the canvas
│   └── index.html             # Main entry page branded with Nudge titles
│
└── db.json                   # Local JSON database for profiles, sessions, and transcripts
```

---

## 3. Setup & Local Installation

### Prerequisites
1. **Python 3.10+**
2. **Node.js 18+**
3. **Ollama**: Download and install [Ollama](https://ollama.com/) locally.

Once Ollama is running, pull the Qwen model weights:
```bash
ollama pull qwen2.5:3b
```

### Installation

1. **Clone the Repository** (ensure submodules are initialized):
   ```bash
   git clone --recursive <repository-url>
   cd project
   ```

2. **Backend Setup**:
   Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Frontend Setup**:
   Install dependencies inside the excalidraw directory:
   ```bash
   npm install --prefix vendor/excalidraw-codepair
   ```

---

## 4. How to Run Locally

1. **Start Ollama**:
   Ensure Ollama is running in the background.
   ```bash
   ollama serve
   ```

2. **Run Backend API Server**:
   ```bash
   python backend/app.py
   ```
   The backend server runs on `http://localhost:3002`.

3. **Run Frontend Web App**:
   ```bash
   npm run start --prefix vendor/excalidraw-codepair
   ```
   The web application will open on `http://localhost:3000`.
   To point the frontend at a non-default backend host/port (e.g. if you set `NUDGE_HOST`), create `vendor/excalidraw-codepair/.env` with `VITE_API_URL=http://<host>:3002`.

---

## 5. Security & Privacy Guidelines
- **Zero Cloud Storage**: All PDF resumes, interview transcripts, and session databases are stored locally inside `db.json` and `uploads/`. No personal data is sent to external servers.
- **Transit Encryption**: Canvas and chat data are encrypted in transit between browser and local backend using AES-GCM with a per-session key derived via HKDF; data at rest in `db.json` remains local, unencrypted plaintext (see Fix 3 for why full at-rest encryption isn't implemented).
- **Local Network Safety**: By default Nudge only accepts connections from localhost. Set `NUDGE_HOST=0.0.0.0` if you need LAN access, e.g. testing from a phone — do this only on trusted networks.
- **Community placeholders**: All community redirected channels (Discord, Twitter/X, GitHub issues) are placeholder dialogs protecting internal workflows.
