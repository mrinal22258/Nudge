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

# Create FastAPI app
app = FastAPI(title="Live AI Mock Interview Platform API")

# Configure CORS to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Socket.io Server
sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)

# Local storage for file uploads
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Inactivity tracking: session_id -> datetime of last activity
session_activity = {}

@app.post("/api/session/create")
async def create_session(
    resume: UploadFile = File(...),
    jd: str = Form(...),
    interview_type: str = Form("coding")
):
    """Parses resume + JD, builds target gap profile, selects a question, and creates a session."""
    try:
        # Save resume PDF locally
        resume_filename = f"resume_{uuid_str()}.pdf"
        resume_path = os.path.join(UPLOAD_DIR, resume_filename)
        with open(resume_path, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)

        # Call orchestrator to build session
        session_data = SessionOrchestrator.create_session(resume_path, jd, interview_type)
        return session_data
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
        debrief = generate_and_verify_debrief(session_id)
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
    if not plan:
        plan = IdealAnswerGenerator.generate_plan(session_id)
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
        if sess and sess["status"] == "setup":
            SessionOrchestrator.start_interview(session_id)
            session_activity[session_id] = datetime.now()
            
            # AI introduces itself and asks the initial question
            welcome_text = (
                f"Hello! I am your interviewer today. I have reviewed your profile against the role, "
                f"and selected a technical question for you: \n\n**{sess['question_prompt']}**\n\n"
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
        session_activity[session_id] = datetime.now()
        
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
        session_activity[session_id] = datetime.now()
        SessionOrchestrator.add_transcript_entry(session_id, "user", content)
        
        # Trigger AI interviewer turn
        await sio.emit("ai-status", {"status": "typing"}, room=room_id)
        ai_turn = generate_interviewer_turn(session_id)
        SessionOrchestrator.add_transcript_entry(session_id, "ai", ai_turn)
        await sio.emit("ai-message", {"content": ai_turn, "timestamp": datetime.now().isoformat()}, room=room_id)

@sio.event
async def request_nudge(sid, data):
    """Explicit hint requested by the candidate."""
    room_id = data.get("roomId")
    session_id = data.get("sessionId") or room_id
    
    if session_id:
        session_activity[session_id] = datetime.now()
        await sio.emit("ai-status", {"status": "typing"}, room=room_id)
        nudge_text = generate_interviewer_turn(session_id, is_nudge=True)
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
    """Background loop that nudges candidates when they are inactive for >45 seconds."""
    while True:
        await asyncio.sleep(5)
        now = datetime.now()
        inactive_sessions = []
        
        for sess_id, last_time in list(session_activity.items()):
            # Heuristic: 45 seconds of no activity triggers a nudge
            if (now - last_time).total_seconds() > 45:
                inactive_sessions.append(sess_id)
                
        for sess_id in inactive_sessions:
            print(f"[Idle Detector] Session {sess_id} inactive for >45s. Triggering automatic nudge...")
            # Reset activity timestamp so we don't spam nudges
            session_activity[sess_id] = datetime.now()
            
            # Generate and emit nudge
            nudge = generate_interviewer_turn(sess_id, is_nudge=True)
            SessionOrchestrator.add_transcript_entry(sess_id, "ai", nudge)
            await sio.emit("ai-message", {"content": nudge, "timestamp": datetime.now().isoformat()}, room=sess_id)

@app.on_event("startup")
async def startup_event():
    # Inactivity monitoring loop disabled as requested by candidate
    # asyncio.create_task(monitor_inactivity())
    pass

if __name__ == "__main__":
    uvicorn.run(socket_app, host="0.0.0.0", port=3002)
