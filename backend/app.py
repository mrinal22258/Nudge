import os
import sys
import shutil
import asyncio
import traceback
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import socketio
import uvicorn
from typing import Dict, Any, List

# Ensure project root is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from backend.database import db
from backend.orchestrator import SessionOrchestrator
from backend.interviewer import generate_interviewer_turn
from backend.debrief_verifier import generate_and_verify_debrief
from backend.ideal_answer import IdealAnswerGenerator

# Configure CORS to allow frontend connections (restrict to localhost dev ports)
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Lifespan event manager to handle inactivity background task
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start inactivity monitor background task
    monitor_task = asyncio.create_task(monitor_inactivity())
    print("[Nudge] Inactivity monitor background task started successfully.")
    yield
    # Cleanup task on shutdown
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    print("[Nudge] Inactivity monitor background task stopped.")

app = FastAPI(title="Live AI Mock Interview Platform API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Socket.io Server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=origins)
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Local storage for file uploads
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Inactivity tracking: session_id -> datetime of last activity
session_activity = {}

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10MB, generous for a resume PDF

@app.post("/api/session/create")
async def create_session(
    resume: UploadFile = File(...),
    jd: str = Form(...),
    interview_type: str = Form("coding")
):
    """Parses resume + JD, builds target gap profile, selects a question, and creates a session."""
    try:
        # Read once, validate, then write — don't trust the client Content-Type header alone
        content = await resume.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Resume file too large (10MB limit).")
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid PDF.")

        resume_filename = f"resume_{uuid_str()}.pdf"
        resume_path = os.path.join(UPLOAD_DIR, resume_filename)
        
        def save_file():
            with open(resume_path, "wb") as buffer:
                buffer.write(content)
                
        await asyncio.to_thread(save_file)

        # Call orchestrator to build session
        session_data = await asyncio.to_thread(
            SessionOrchestrator.create_session, resume_path, jd, interview_type
        )
        return session_data
    except HTTPException as he:
        raise he
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create interview session: {str(e)}")

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess

@app.get("/api/sessions")
async def list_sessions():
    return db.list_sessions()

@app.get("/api/debrief/{session_id}")
async def get_debrief(session_id: str):
    """Generates the verified debrief or returns the cached one."""
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
        
    debrief = db.get_debrief(session_id)
    if not debrief:
        # Trigger debrief generation & verification pass
        sess["status"] = "debriefing"
        db.save_session(session_id, sess)
        debrief = await asyncio.to_thread(generate_and_verify_debrief, session_id)
        sess["status"] = "ready"
        db.save_session(session_id, sess)
        
    return debrief

@app.get("/api/debrief/ideal_answer/{session_id}")
async def get_ideal_answer(session_id: str):
    """Retrieves the ideal answer plan or generates a new verified plan."""
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
        
    plan = sess.get("ideal_answer_plan")
    if not plan or not plan.get("blocks"):
        plan = await asyncio.to_thread(IdealAnswerGenerator.generate_plan, session_id)
        if plan and plan.get("blocks"):
            sess["ideal_answer_plan"] = plan
            db.save_session(session_id, sess)
        
    return plan

@app.post("/api/session/next_scenario/{session_id}")
async def load_next_scenario(session_id: str):
    """Resets conversation transcript and moves to next matched target scenario question."""
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
        
    matched = sess.get("matched_questions", [])
    idx = sess.get("current_question_index", 0)
    
    if idx + 1 < len(matched):
        next_idx = idx + 1
        next_q = matched[next_idx]
        
        # Reset session properties for the next scenario
        sess["current_question_index"] = next_idx
        sess["question_id"] = next_q["id"]
        sess["question_topic"] = next_q["topic"]
        sess["question_prompt"] = next_q["prompt_text"]
        sess["question_details"] = next_q
        sess["transcript"] = []  # Clear transcript for new scenario evaluation
        sess["status"] = "active"
        if "ideal_answer_plan" in sess:
            del sess["ideal_answer_plan"]
        
        # Remove cached debrief from database
        with db.lock:
            database_data = db._read_db()
            if session_id in database_data.get("debriefs", {}):
                del database_data["debriefs"][session_id]
            db._write_db(database_data)
            
        db.save_session(session_id, sess)
        
        # Also notify socket room clients to reload state
        await sio.emit("scenario-changed", {
            "question_topic": next_q["topic"],
            "question_prompt": next_q["prompt_text"]
        }, room=session_id)
        
        return {"success": True, "session": sess}
    else:
        return {"success": False, "message": "No more scenarios available."}

def uuid_str() -> str:
    import uuid
    return str(uuid.uuid4())

# --- Socket.io Event Handlers ---

@sio.event
async def connect(sid, environ):
    print(f"[Socket] Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"[Socket] Client disconnected: {sid}")

@sio.event
async def join_room(sid, data):
    room_id = data.get("roomId")
    session_id = data.get("sessionId") or room_id
    if room_id:
        await sio.enter_room(sid, room_id)
        print(f"[Socket] {sid} joined room: {room_id}")
        
        # Start interview in Orchestrator if it was in setup status
        sess = db.get_session(session_id)
        if sess and sess.get("status") == "setup":
            SessionOrchestrator.start_interview(session_id)
            session_activity[session_id] = {
                "last_active": datetime.now(),
                "room_id": room_id
            }
            
            # AI introduces itself and asks the initial question
            welcome_text = (
                f"Hello! I am your interviewer today. I have reviewed your profile against the role, "
                f"and selected a technical question for you: \n\n**{sess.get('question_prompt', '')}**\n\n"
                f"Please use the Nudge whiteboard to draw out your system design, write your code, "
                f"and explain your thought process."
            )
            SessionOrchestrator.add_transcript_entry(session_id, "ai", welcome_text)
            await sio.emit("ai-message", {"content": welcome_text, "timestamp": datetime.now().isoformat()}, room=room_id)

@sio.event
async def canvas_update(sid, data):
    """Excalidraw canvas serialized state update."""
    room_id = data.get("roomId")
    session_id = data.get("sessionId") or room_id
    serialized_canvas = data.get("serialized", "")
    
    if session_id and serialized_canvas:
        # Update inactivity tracker
        session_activity[session_id] = {
            "last_active": datetime.now(),
            "room_id": room_id or session_id
        }
        
        # Append canvas snapshot to running transcript
        SessionOrchestrator.add_transcript_entry(session_id, "canvas", serialized_canvas)
        print(f"[Socket] Canvas updated for session {session_id} ({len(serialized_canvas)} chars)")

@sio.event
async def user_message(sid, data):
    """Candidate typed chat message."""
    room_id = data.get("roomId")
    session_id = data.get("sessionId") or room_id
    content = data.get("content", "")
    
    if session_id and content:
        session_activity[session_id] = {
            "last_active": datetime.now(),
            "room_id": room_id or session_id
        }
        SessionOrchestrator.add_transcript_entry(session_id, "user", content)
        
        # Trigger AI interviewer turn
        await sio.emit("ai-status", {"status": "typing"}, room=room_id)
        ai_turn = await asyncio.to_thread(generate_interviewer_turn, session_id)
        SessionOrchestrator.add_transcript_entry(session_id, "ai", ai_turn)
        await sio.emit("ai-message", {"content": ai_turn, "timestamp": datetime.now().isoformat()}, room=room_id)

@sio.event
async def request_nudge(sid, data):
    """Explicit hint requested by the candidate."""
    room_id = data.get("roomId")
    session_id = data.get("sessionId") or room_id
    
    if session_id:
        session_activity[session_id] = {
            "last_active": datetime.now(),
            "room_id": room_id or session_id
        }
        await sio.emit("ai-status", {"status": "typing"}, room=room_id)
        nudge_text = await asyncio.to_thread(generate_interviewer_turn, session_id, is_nudge=True)
        SessionOrchestrator.add_transcript_entry(session_id, "ai", nudge_text)
        await sio.emit("ai-message", {"content": nudge_text, "timestamp": datetime.now().isoformat()}, room=room_id)

@sio.event
async def end_interview(sid, data):
    """End the active interview session."""
    room_id = data.get("roomId")
    session_id = data.get("sessionId") or room_id
    
    if session_id:
        SessionOrchestrator.end_interview(session_id)
        if session_id in session_activity:
            del session_activity[session_id]
            
        wrapup_text = (
            "Thank you for completing this mock interview. I will now compile your performance "
            "debrief, checking it for accuracy against our whiteboard session transcript. "
            "Please click 'Go to Debrief' to review the verified feedback."
        )
        SessionOrchestrator.add_transcript_entry(session_id, "ai", wrapup_text)
        await sio.emit("ai-message", {"content": wrapup_text, "timestamp": datetime.now().isoformat()}, room=room_id)
        await sio.emit("interview-ended", {"sessionId": session_id}, room=room_id)

# --- Background Task: Idle/Stuck Detector (Task 7) ---

async def monitor_inactivity():
    """Background loop that nudges candidates when they are inactive for >45 seconds and cleans up old resume uploads."""
    cleanup_counter = 0
    while True:
        await asyncio.sleep(5)
        now = datetime.now()
        inactive_sessions = []
        
        for sess_id, info in list(session_activity.items()):
            last_time = info.get("last_active")
            if last_time and (now - last_time).total_seconds() > 45:
                inactive_sessions.append((sess_id, info.get("room_id", sess_id)))
                
        for sess_id, r_id in inactive_sessions:
            print(f"[Idle Detector] Session {sess_id} inactive for >45s. Triggering automatic nudge...")
            # Reset activity timestamp so we don't spam nudges
            if sess_id in session_activity:
                session_activity[sess_id]["last_active"] = datetime.now()
            
            # Generate and emit nudge
            nudge = await asyncio.to_thread(generate_interviewer_turn, sess_id, is_nudge=True)
            SessionOrchestrator.add_transcript_entry(sess_id, "ai", nudge)
            await sio.emit("ai-message", {"content": nudge, "timestamp": datetime.now().isoformat()}, room=r_id)

        # Cleanup files belonging to sessions older than 2 days (check once every 60 seconds / 12 loops)
        cleanup_counter += 1
        if cleanup_counter >= 12:
            cleanup_counter = 0
            try:
                sessions = db.list_sessions()
                for s in sessions:
                    started_at_str = s.get("started_at")
                    if started_at_str:
                        try:
                            started_at = datetime.fromisoformat(started_at_str)
                        except ValueError:
                            continue
                        if (now - started_at).days >= 2:
                            candidate_id = s.get("candidate_id")
                            if candidate_id:
                                candidate = db.get_candidate(candidate_id)
                                if candidate:
                                    resume_path = candidate.get("resume_path")
                                    if resume_path and os.path.exists(resume_path):
                                        try:
                                            os.remove(resume_path)
                                            print(f"[Cleanup] Deleted old resume file: {resume_path}")
                                        except Exception as e:
                                            print(f"[Cleanup Error] Failed to delete {resume_path}: {e}")
            except Exception as e:
                print(f"[Cleanup Error] {e}")

if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=3002)
