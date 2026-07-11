/* eslint-disable prettier/prettier */
import React, { useState, useEffect, useRef } from "react";
import io from "socket.io-client";
import { Excalidraw } from "../packages/excalidraw/index";
import { structuredPlanToCanvasElements } from "../utils/idealCanvas";
import { serializeCanvas } from "../utils/serializeCanvas";
import "../css/interview.css";

function generateRoomKey(): string {
  const bytes = new Uint8Array(16); // 128-bit
  crypto.getRandomValues(bytes);
  return Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("");
}

function arrayBufferToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer), b => b.toString(16).padStart(2, "0")).join("");
}

async function deriveAesKey(roomKey: string, sessionId: string): Promise<CryptoKey> {
  const encoder = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw",
    encoder.encode(roomKey),
    { name: "HKDF" },
    false,
    ["deriveKey"]
  );
  return await crypto.subtle.deriveKey(
    {
      name: "HKDF",
      hash: "SHA-256",
      salt: encoder.encode(sessionId),
      info: encoder.encode("canvas_encryption"),
    },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"]
  );
}

async function encryptCanvas(serialized: string, roomKey: string, sessionId: string): Promise<{ ciphertext: string; iv: string }> {
  const aesKey = await deriveAesKey(roomKey, sessionId);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    aesKey,
    new TextEncoder().encode(serialized)
  );
  return {
    ciphertext: arrayBufferToHex(encrypted),
    iv: arrayBufferToHex(iv.buffer)
  };
}

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:3002";

interface ChatMessage {
  role: "ai" | "user" | "system";
  content: string;
  timestamp: string;
}

interface DebriefSection {
  area: string;
  verdict: string;
  citations: number[];
}

export default function InterviewApp() {
  const [screen, setScreen] = useState<"setup" | "interview" | "debrief">(
    "setup",
  );
  const [sessionId, setSessionId] = useState<string | null>(null);

  // Setup inputs
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [interviewType, setInterviewType] = useState("system_design");

  // Ingestion status messages
  const [loading, setLoading] = useState(false);
  const [statusLog, setStatusLog] = useState<string[]>([]);

  // Live Interview stats
  const [questionTopic, setQuestionTopic] = useState("");
  const [questionPrompt, setQuestionPrompt] = useState("");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [userText, setUserText] = useState("");
  const [isAiTyping, setIsAiTyping] = useState(false);

  // Debrief stats
  const [debriefSections, setDebriefSections] = useState<DebriefSection[]>([]);
  const [fullTranscript, setFullTranscript] = useState<any[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<any | null>(null);
  const [debriefTab, setDebriefTab] = useState<"feedback" | "ideal_answer">(
    "feedback",
  );
  const [idealAnswerPlan, setIdealAnswerPlan] = useState<any>(null);
  const [highlightedGap, setHighlightedGap] = useState<number | null>(null);

  const [_sessionToken, setSessionToken] = useState<string | null>(null);
  const sessionTokenRef = useRef<string | null>(null);

  const updateSessionToken = (token: string | null) => {
    setSessionToken(token);
    sessionTokenRef.current = token;
  };

  const authFetch = (url: string, options: RequestInit = {}) => {
    const token = sessionTokenRef.current;
    if (token) {
      options.headers = {
        ...options.headers,
        "Authorization": `Bearer ${token}`,
      };
    }
    return fetch(url, options);
  };

  const getRoomKeyFromHash = () => {
    const hash = window.location.hash;
    const match = hash.match(/^#room=([^,]+),(.+)$/);
    return match ? match[2] : null;
  };

  // Timer and Multi-Scenario States
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [canvasKey, setCanvasKey] = useState(0);
  const [showNextScenarioOffer, setShowNextScenarioOffer] = useState(false);
  const [hasNextScenario, setHasNextScenario] = useState(false);

  const lastEmittedCanvasRef = useRef<string>("");
  const canvasTimeoutRef = useRef<any>(null);

  const handleCanvasChange = (elements: readonly any[]) => {
    if (screen !== "interview") {
      return;
    }

    if (canvasTimeoutRef.current) {
      clearTimeout(canvasTimeoutRef.current);
    }

    canvasTimeoutRef.current = setTimeout(async () => {
      const serialized = serializeCanvas(elements);
      if (serialized !== lastEmittedCanvasRef.current) {
        lastEmittedCanvasRef.current = serialized;
        if (socketRef.current) {
          const roomKey = getRoomKeyFromHash();
          if (roomKey && sessionId) {
            try {
              const { ciphertext, iv } = await encryptCanvas(serialized, roomKey, sessionId);
              socketRef.current.emit("canvas_update", {
                roomId: sessionId,
                sessionId,
                ciphertext,
                iv,
              });
            } catch (err) {
              console.error("Encryption failed:", err);
            }
          }
        }
      }
    }, 1500);
  };

  const socketRef = useRef<any>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const excalidrawRef = useRef<any>(null);

  // Auto-scroll chat window
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory, isAiTyping]);

  // Set active body class
  useEffect(() => {
    document.body.classList.add("interview-app-active");
    return () => {
      document.body.classList.remove("interview-app-active");
    };
  }, []);

  // Component-unmount socket disconnect cleanup
  useEffect(() => {
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

  // Timer count effect
  useEffect(() => {
    if (screen !== "interview") {
      setElapsedSeconds(0);
      return;
    }
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [screen]);

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    const padMins = String(mins).padStart(2, "0");
    const padSecs = String(secs).padStart(2, "0");
    return `${padMins}:${padSecs}`;
  };

  const handleStartInterview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resumeFile || !jdText.trim()) {
      alert("Please upload a resume and paste the target job description.");
      return;
    }

    setLoading(true);
    setStatusLog([
      "1. Ingesting resume file into parsing pipeline...",
      "2. Parsing resume sections (work history, credentials)...",
    ]);

    const formData = new FormData();
    formData.append("resume", resumeFile);
    formData.append("jd", jdText);
    formData.append("interview_type", interviewType);

    try {
      // 1. Call backend API to parse candidate, target, and retrieve question
      const response = await fetch(`${API_BASE}/api/session/create`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Server failed to parse inputs. Check model logs.");
      }

      setStatusLog((prev) => [
        ...prev,
        "3. Analysing required job qualifications...",
        "4. Conducting candidate target gap profiling...",
        "5. Matching gaps and fetching target scenario question...",
      ]);

      const data = await response.json();
      updateSessionToken(data.session_token);

      const newSessionId = data.id;
      setSessionId(newSessionId);
      setQuestionTopic(data.question_topic);
      setQuestionPrompt(data.question_prompt);

      const matched = data.matched_questions || [];
      const idx = data.current_question_index || 0;
      setHasNextScenario(idx + 1 < matched.length);

      // 2. Set Excalidraw collaboration URL room hash
      const roomKey = generateRoomKey();
      window.location.hash = `room=${newSessionId},${roomKey}`;

      // 3. Setup Socket.io client connection to backend orchestrator
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
      }
      const socket = io(API_BASE);
      socketRef.current = socket;

      socket.on("connect", () => {
        socket.emit("join_room", {
          roomId: newSessionId,
          sessionId: newSessionId,
          token: data.session_token,
          roomKey,
        });
      });

      socket.on("ai-message", (msg: any) => {
        setIsAiTyping(false);
        setChatHistory((prev) => [
          ...prev,
          { role: "ai", content: msg.content, timestamp: msg.timestamp },
        ]);
      });

      socket.on("ai-status", (status: any) => {
        if (status.status === "typing") {
          setIsAiTyping(true);
        }
      });

      socket.on("interview-ended", async () => {
        // Fetch debrief & session transcript using authentication
        const debriefResp = await fetch(
          `${API_BASE}/api/debrief/${newSessionId}`,
          {
            headers: {
              "Authorization": `Bearer ${data.session_token}`
            }
          }
        );
        const debriefData = await debriefResp.json();
        setDebriefSections(debriefData.sections);

        const sessResp = await fetch(
          `${API_BASE}/api/session/${newSessionId}`,
          {
            headers: {
              "Authorization": `Bearer ${data.session_token}`
            }
          }
        );
        const sessData = await sessResp.json();
        setFullTranscript(sessData.transcript);

        try {
          const idealResp = await fetch(
            `${API_BASE}/api/debrief/ideal_answer/${newSessionId}`,
            {
              headers: {
                "Authorization": `Bearer ${data.session_token}`
              }
            }
          );
          if (idealResp.ok) {
            const idealData = await idealResp.json();
            setIdealAnswerPlan(idealData);
          }
        } catch (err) {
          console.error("Failed to load ideal answer plan:", err);
        }

        socket.disconnect();
        if (hasNextScenario) {
          setShowNextScenarioOffer(true);
        } else {
          setScreen("debrief");
        }
      });

      setChatHistory([]);
      setScreen("interview");
    } catch (error) {
      console.error(error);
      alert(
        "Failed to initialize mock session. Ensure local Ollama and the backend server on port 3002 are running.",
      );
    } finally {
      setLoading(false);
      setStatusLog([]);
    }
  };

  const handleSendMessage = () => {
    let messageToSend = userText.trim();
    if (!messageToSend) {
      messageToSend =
        "I have updated my work on the whiteboard. Please review the diagram/code.";
    }

    // Add user message locally
    setChatHistory((prev) => [
      ...prev,
      {
        role: "user",
        content: messageToSend,
        timestamp: new Date().toISOString(),
      },
    ]);

    // Send to backend Socket
    if (socketRef.current) {
      socketRef.current.emit("user_message", {
        roomId: sessionId,
        sessionId,
        content: messageToSend,
      });
    }
    setUserText("");
  };

  const handleRequestNudge = () => {
    if (socketRef.current) {
      socketRef.current.emit("request_nudge", { roomId: sessionId, sessionId });
    }
  };

  const handleEndInterview = () => {
    if (
      window.confirm(
        "Are you sure you want to end this interview session and compile feedback?",
      )
    ) {
      if (socketRef.current) {
        socketRef.current.emit("end_interview", {
          roomId: sessionId,
          sessionId,
        });
      }
    }
  };

  const handleRestart = () => {
    window.location.hash = "";
    setSessionId(null);
    setResumeFile(null);
    setJdText("");
    setScreen("setup");
    setSelectedCitation(null);
  };

  const handleLoadNextScenario = async () => {
    try {
      const resp = await authFetch(
        `${API_BASE}/api/session/next_scenario/${sessionId}`,
        { method: "POST" },
      );
      const data = await resp.json();
      if (data.success) {
        // Update question topic and prompt
        setQuestionTopic(data.session.question_topic);
        setQuestionPrompt(data.session.question_prompt);

        // Reset conversation logs and states
        setChatHistory([]);
        setIsAiTyping(false);
        setDebriefSections([]);
        setFullTranscript([]);
        setSelectedCitation(null);
        setHighlightedGap(null);
        setElapsedSeconds(0);
        setShowNextScenarioOffer(false);

        // Compute if another scenario is left after this one
        const matched = data.session.matched_questions || [];
        const idx = data.session.current_question_index || 0;
        setHasNextScenario(idx + 1 < matched.length);

        // Generate a new cryptographically secure key to clear the canvas
        const nextKey = generateRoomKey();
        window.location.hash = `room=${sessionId},${nextKey}`;

        // Force ExcalidrawApp to unmount and remount fresh
        setCanvasKey((prev) => prev + 1);

        // Setup Socket.io client connection to backend orchestrator for the new scenario
        if (socketRef.current) {
          socketRef.current.disconnect();
          socketRef.current = null;
        }
        const socket = io(API_BASE);
        socketRef.current = socket;

        socket.on("connect", () => {
          socket.emit("join_room", {
            roomId: sessionId,
            sessionId,
            token: sessionTokenRef.current,
            roomKey: nextKey,
          });
        });

        socket.on("ai-message", (msg: any) => {
          setIsAiTyping(false);
          setChatHistory((prev) => [
            ...prev,
            { role: "ai", content: msg.content, timestamp: msg.timestamp },
          ]);
        });

        socket.on("ai-status", (status: any) => {
          if (status.status === "typing") {
            setIsAiTyping(true);
          }
        });

        socket.on("interview-ended", async () => {
          const debriefResp = await authFetch(
            `${API_BASE}/api/debrief/${sessionId}`,
          );
          const debriefData = await debriefResp.json();
          setDebriefSections(debriefData.sections);

          const sessResp = await authFetch(
            `${API_BASE}/api/session/${sessionId}`,
          );
          const sessData = await sessResp.json();
          setFullTranscript(sessData.transcript);

          try {
            const idealResp = await authFetch(
              `${API_BASE}/api/debrief/ideal_answer/${sessionId}`,
            );
            if (idealResp.ok) {
              const idealData = await idealResp.json();
              setIdealAnswerPlan(idealData);
            }
          } catch (err) {
            console.error("Failed to load ideal answer plan:", err);
          }

          socket.disconnect();

          // Re-check next scenario list
          const updatedSessResp = await authFetch(
            `${API_BASE}/api/session/${sessionId}`,
          );
          if (updatedSessResp.ok) {
            const updatedSessData = await updatedSessResp.json();
            const updatedMatched = updatedSessData.matched_questions || [];
            const updatedIdx = updatedSessData.current_question_index || 0;
            if (updatedIdx + 1 < updatedMatched.length) {
              setHasNextScenario(true);
              setShowNextScenarioOffer(true);
            } else {
              setHasNextScenario(false);
              setScreen("debrief");
            }
          } else {
            setScreen("debrief");
          }
        });

        setScreen("interview");
      } else {
        alert(data.message || "No more scenarios available.");
        setScreen("debrief");
      }
    } catch (err) {
      console.error("Failed to load next scenario:", err);
      setScreen("debrief");
    }
  };

  // Render Setup or Interview splits
  if (screen === "setup" || screen === "interview") {
    return (
      <div className="interview-layout">
        {/* Left Side: Excalidraw Whiteboard Canvas (Always active and visible!) */}
        <div className="canvas-panel">
          <Excalidraw
            key={canvasKey}
            ref={excalidrawRef}
            onChange={handleCanvasChange}
            theme="light"
          />
        </div>

        {/* Floating Configuration modal when screen is setup */}
        {screen === "setup" && (
          <div className="excalidraw-dialog-overlay">
            <div className="excalidraw-dialog-container">
              <div className="excalidraw-dialog-header">
                <h3>Configure Nudge AI Mock Interview</h3>
              </div>
              <div className="excalidraw-dialog-body">
                <form
                  onSubmit={handleStartInterview}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "1rem",
                  }}
                >
                  <div className="form-group">
                    <label className="form-label">
                      1. Candidate Resume (PDF)
                    </label>
                    <div className="file-input-wrapper">
                      <input
                        type="file"
                        accept=".pdf"
                        className="file-input-real"
                        onChange={(e) =>
                          setResumeFile(e.target.files?.[0] || null)
                        }
                      />
                      <div className="file-input-label">
                        {resumeFile
                          ? `✓ ${resumeFile.name}`
                          : "Click to select resume PDF..."}
                      </div>
                    </div>
                  </div>

                  <div className="form-group">
                    <label className="form-label">
                      2. Target Job Description (JD)
                    </label>
                    <textarea
                      className="text-area-jd"
                      placeholder="Paste the target JD text here..."
                      value={jdText}
                      onChange={(e) => setJdText(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">3. Scenario Focus</label>
                    <select
                      className="select-type"
                      value={interviewType}
                      onChange={(e) => setInterviewType(e.target.value)}
                    >
                      <option value="system_design">
                        System Architecture Design
                      </option>
                      <option value="coding">
                        Technical Coding / Algorithms
                      </option>
                      <option value="behavioral">
                        Behavioral / Leadership (STAR Method)
                      </option>
                      <option value="finance">
                        Finance / Quantitative Analysis
                      </option>
                      <option value="ai_engineering">
                        AI / Machine Learning Engineering
                      </option>
                      <option value="product_management">
                        Product Management / Strategy
                      </option>
                    </select>
                  </div>

                  <button
                    type="submit"
                    className="btn-primary"
                    disabled={loading}
                  >
                    {loading ? "Analyzing Gap Profile..." : "Start Interview"}
                  </button>
                </form>

                {loading && (
                  <div
                    style={{
                      marginTop: "0.5rem",
                      padding: "0.8rem",
                      background: "rgba(105, 101, 219, 0.08)",
                      border: "1px solid rgba(105, 101, 219, 0.3)",
                      borderRadius: "8px",
                    }}
                  >
                    <div
                      style={{
                        fontSize: "0.8rem",
                        fontWeight: "bold",
                        color: "#a5b4fc",
                        marginBottom: "0.4rem",
                      }}
                    >
                      Gap Analysis Progress:
                    </div>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "0.2rem",
                      }}
                    >
                      {statusLog.map((log, lIdx) => (
                        <div
                          key={lIdx}
                          style={{
                            fontSize: "0.75rem",
                            color: "var(--text-main)",
                          }}
                        >
                          {log}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Right Side Sidebar Panel when interview is active */}
        {screen === "interview" && (
          <div className="dialogue-panel">
            <div
              className="dialogue-header"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h3>{questionTopic}</h3>
              <div className="session-timer-badge">
                ⏱️ {formatTime(elapsedSeconds)}
              </div>
            </div>

            <div className="question-box">
              <strong>Question Prompt:</strong>
              <p>{questionPrompt}</p>
            </div>

            <div className="chat-history">
              {chatHistory.map((msg, idx) => (
                <div key={idx} className={`chat-message ${msg.role}`}>
                  {msg.content}
                </div>
              ))}
              {isAiTyping && (
                <div className="typing-indicator">Interviewer is typing...</div>
              )}
              <div ref={chatEndRef} />
            </div>

            <div className="controls-bar">
              <div className="chat-input-area">
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Type your response..."
                  value={userText}
                  onChange={(e) => setUserText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                />
                <button className="btn-send" onClick={handleSendMessage}>
                  Send
                </button>
              </div>

              <div className="btn-row">
                <button
                  className="btn-control nudge"
                  onClick={handleRequestNudge}
                >
                  Nudge / Hint
                </button>
                <button
                  className="btn-control end"
                  onClick={handleEndInterview}
                >
                  Submit & End
                </button>
              </div>
            </div>
          </div>
        )}
        {showNextScenarioOffer && (
          <div className="excalidraw-dialog-overlay" style={{ zIndex: 9999 }}>
            <div
              className="excalidraw-dialog-container"
              style={{ maxWidth: "480px", textAlign: "center" }}
            >
              <div className="excalidraw-dialog-header">
                <h3>Scenario Complete!</h3>
              </div>
              <div
                className="excalidraw-dialog-body"
                style={{ padding: "1.5rem" }}
              >
                <p
                  style={{
                    marginBottom: "1.5rem",
                    fontSize: "0.95rem",
                    lineHeight: "1.5",
                    color: "var(--text-main)",
                  }}
                >
                  Great job completing this scenario. You have matched target
                  questions remaining for this role. Would you like to tackle
                  the next scenario to further evaluate your skills, or proceed
                  directly to your final Performance Feedback?
                </p>
                <div
                  style={{
                    display: "flex",
                    gap: "1rem",
                    justifyContent: "center",
                  }}
                >
                  <button
                    className="btn-primary"
                    onClick={handleLoadNextScenario}
                    style={{
                      background: "#6965db",
                      border: "none",
                      padding: "0.6rem 1.2rem",
                      borderRadius: "8px",
                      color: "white",
                      cursor: "pointer",
                      fontWeight: "bold",
                    }}
                  >
                    Try Next Scenario
                  </button>
                  <button
                    className="btn-control"
                    onClick={() => {
                      setShowNextScenarioOffer(false);
                      setScreen("debrief");
                    }}
                    style={{
                      background: "transparent",
                      border: "1px solid var(--border-color)",
                      padding: "0.6rem 1.2rem",
                      borderRadius: "8px",
                      color: "var(--text-main)",
                      cursor: "pointer",
                    }}
                  >
                    Go to Feedback
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  if (screen === "debrief") {
    return (
      <div className="debrief-container">
        {/* Tab Selection */}
        <div className="debrief-tabs">
          <button
            className={
              debriefTab === "feedback"
                ? "debrief-tab-btn active"
                : "debrief-tab-btn"
            }
            onClick={() => setDebriefTab("feedback")}
          >
            Your Performance Feedback
          </button>
          <button
            className={
              debriefTab === "ideal_answer"
                ? "debrief-tab-btn active"
                : "debrief-tab-btn"
            }
            onClick={() => setDebriefTab("ideal_answer")}
          >
            What a Strong Answer Looks Like (Ideal Canvas)
          </button>
        </div>

        {debriefTab === "feedback" ? (
          <div
            className="debrief-card"
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "2.5rem",
              padding: "2.5rem",
              background: "#18181b",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              borderRadius: "16px",
              boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.3)",
              fontFamily: "system-ui, -apple-system, sans-serif",
            }}
          >
            {/* Header branding */}
            <div
              className="debrief-header"
              style={{
                borderBottom: "1px solid rgba(255, 255, 255, 0.12)",
                paddingBottom: "1.5rem",
              }}
            >
              <h1
                style={{
                  fontSize: "2.2rem",
                  color: "#ffffff",
                  margin: 0,
                  fontWeight: 800,
                  letterSpacing: "-0.5px",
                }}
              >
                Nudge AI Mock Interview Performance Scorecard
              </h1>
              <p
                style={{
                  margin: "0.5rem 0 0 0",
                  color: "#a1a1aa",
                  fontSize: "1.1rem",
                }}
              >
                Grounded, citation-backed feedback compiled across technical and
                communication dimensions.
              </p>
            </div>

            {/* Overall Fit Scorecard Banner */}
            {(() => {
              const getAreaMatchRating = (verdict: string) => {
                const vLower = (verdict || "").toLowerCase();
                if (
                  vLower.includes("left blank") ||
                  vLower.includes("no code") ||
                  vLower.includes("no diagram") ||
                  vLower.includes("no drawing") ||
                  vLower.includes("nothing to evaluate") ||
                  vLower.includes("nothing to analyze") ||
                  vLower.includes("not present") ||
                  vLower.includes("empty") ||
                  vLower.includes("missing") ||
                  vLower.includes("none provided") ||
                  vLower.includes("did not submit") ||
                  vLower.includes("was not provided") ||
                  vLower.includes("unable to verify") ||
                  vLower.includes("no proof") ||
                  vLower.includes("no evidence") ||
                  vLower.includes("no solution") ||
                  vLower.includes("without a solution") ||
                  vLower.includes("blank") ||
                  vLower.includes("no code was written") ||
                  vLower.includes("did not provide") ||
                  vLower.includes("could not be verified") ||
                  vLower.includes("failed to") ||
                  vLower.includes("did not address")
                ) {
                  return {
                    label: "CRITICAL GAP",
                    color: "#f87171",
                    bg: "rgba(248, 113, 113, 0.15)",
                  };
                }
                if (
                  vLower.includes("minimal") ||
                  vLower.includes("limited") ||
                  vLower.includes("lack of") ||
                  vLower.includes("needs improvement") ||
                  vLower.includes("needs work") ||
                  vLower.includes("some concern") ||
                  vLower.includes("not clear")
                ) {
                  return {
                    label: "NEEDS WORK",
                    color: "#fbbf24",
                    bg: "rgba(251, 191, 36, 0.15)",
                  };
                }
                return {
                  label: "STRONG MATCH",
                  color: "#34d399",
                  bg: "rgba(52, 211, 153, 0.15)",
                };
              };

              const userEntries = fullTranscript.filter(
                (e) => e.type === "user" || e.type === "canvas",
              );
              const totalContentLength = userEntries.reduce(
                (acc, curr) => acc + (curr.content || "").trim().length,
                0,
              );
              const hasCandidateAnswered =
                userEntries.length > 0 && totalContentLength > 10;

              const criticalGapsCount = debriefSections.filter((section) => {
                const rating = getAreaMatchRating(section.verdict);
                return rating.label === "CRITICAL GAP";
              }).length;

              const needsWorkCount = debriefSections.filter((section) => {
                const rating = getAreaMatchRating(section.verdict);
                return rating.label === "NEEDS WORK";
              }).length;

              const passed =
                hasCandidateAnswered &&
                criticalGapsCount === 0 &&
                needsWorkCount <= 1;

              const overallRec = passed
                ? "PASS & FIT FOR ROLE"
                : "PRACTICE RECOMMENDED";
              const recColor = passed ? "#34d399" : "#f87171";
              const recBg = passed
                ? "rgba(52, 211, 153, 0.1)"
                : "rgba(248, 113, 113, 0.1)";

              return (
                <>
                  <div
                    style={{
                      background: "rgba(255, 255, 255, 0.02)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      borderRadius: "12px",
                      padding: "1.5rem",
                      display: "flex",
                      flexDirection: "column",
                      gap: "1.2rem",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        flexWrap: "wrap",
                        gap: "1rem",
                      }}
                    >
                      <div>
                        <div
                          style={{
                            fontSize: "0.85rem",
                            textTransform: "uppercase",
                            color: "#a5b4fc",
                            fontWeight: "bold",
                            letterSpacing: "1px",
                          }}
                        >
                          Scenario Track
                        </div>
                        <div
                          style={{
                            fontSize: "1.3rem",
                            fontWeight: "bold",
                            color: "#ffffff",
                            marginTop: "0.3rem",
                          }}
                        >
                          {questionTopic}
                        </div>
                      </div>
                      <div style={{ textAlign: "right" }}>
                        <div
                          style={{
                            fontSize: "0.85rem",
                            textTransform: "uppercase",
                            color: "#a5b4fc",
                            fontWeight: "bold",
                            letterSpacing: "1px",
                          }}
                        >
                          Overall Recommendation
                        </div>
                        <div
                          style={{
                            fontSize: "1.105rem",
                            fontWeight: "bold",
                            color: recColor,
                            background: recBg,
                            padding: "0.5rem 1rem",
                            borderRadius: "6px",
                            marginTop: "0.3rem",
                            display: "inline-block",
                            border: `1px solid ${recColor}33`,
                          }}
                        >
                          {overallRec}
                        </div>
                      </div>
                    </div>
                    <div
                      style={{
                        fontSize: "1.05rem",
                        color: "#e4e4e7",
                        borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                        paddingTop: "1.2rem",
                        lineHeight: "1.6",
                      }}
                    >
                      <strong style={{ color: "#ffffff" }}>
                        Whiteboard Challenge:
                      </strong>{" "}
                      {questionPrompt}
                    </div>
                  </div>

                  {/* Performance metrics breakdown cards */}
                  <div>
                    <h2
                      style={{
                        fontSize: "1.25rem",
                        color: "#ffffff",
                        marginBottom: "1.2rem",
                        marginTop: 0,
                        fontWeight: 750,
                      }}
                    >
                      📊 Dimensional Verdicts
                    </h2>
                    <div
                      className="debrief-sections"
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr",
                        gap: "1.5rem",
                      }}
                    >
                      {debriefSections.map((section, idx) => {
                        const rating = getAreaMatchRating(section.verdict);
                        return (
                          <div
                            key={idx}
                            className="debrief-section-card"
                            style={{
                              background: "rgba(255, 255, 255, 0.03)",
                              border: "1px solid rgba(255, 255, 255, 0.06)",
                              borderRadius: "12px",
                              padding: "1.5rem",
                              display: "flex",
                              flexDirection: "column",
                              gap: "1rem",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                              }}
                            >
                              <h3
                                style={{
                                  margin: 0,
                                  fontSize: "1.15rem",
                                  color: "#a5b4fc",
                                  textTransform: "capitalize",
                                  fontWeight: 700,
                                }}
                              >
                                {section.area.replace("_", " ")}
                              </h3>
                              <span
                                style={{
                                  fontSize: "0.8rem",
                                  background: rating.bg,
                                  color: rating.color,
                                  padding: "0.3rem 0.7rem",
                                  borderRadius: "6px",
                                  fontWeight: "bold",
                                  border: `1px solid ${rating.color}22`,
                                }}
                              >
                                {rating.label}
                              </span>
                            </div>
                            <div
                              className="debrief-verdict"
                              style={{
                                fontSize: "1.05rem",
                                color: "#f4f4f5",
                                lineHeight: "1.6",
                                margin: 0,
                              }}
                            >
                              {section.verdict}
                              <div
                                style={{
                                  marginTop: "1rem",
                                  display: "flex",
                                  gap: "0.5rem",
                                  flexWrap: "wrap",
                                }}
                              >
                                {section.citations.map((cIdx) => (
                                  <span
                                    key={cIdx}
                                    className="citation-tag"
                                    style={{
                                      background: "rgba(99, 102, 241, 0.25)",
                                      border:
                                        "1px solid rgba(99, 102, 241, 0.4)",
                                      color: "#c7d2fe",
                                      fontSize: "0.85rem",
                                      padding: "0.3rem 0.6rem",
                                      borderRadius: "6px",
                                      cursor: "pointer",
                                      fontWeight: "bold",
                                      transition: "background 0.2s ease",
                                    }}
                                    onClick={() => {
                                      const entry = fullTranscript.find(
                                        (e) => e.index === cIdx,
                                      );
                                      if (entry) {
                                        setSelectedCitation(entry);
                                      }
                                    }}
                                  >
                                    🔎 Cite #{cIdx}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </>
              );
            })()}

            {/* Citation inspect box */}
            {selectedCitation && (
              <div
                style={{
                  padding: "1.5rem",
                  background: "rgba(99, 102, 241, 0.04)",
                  border: "1px solid rgba(99, 102, 241, 0.2)",
                  borderRadius: "12px",
                  boxShadow: "0 4px 12px rgba(99, 102, 241, 0.05)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "0.8rem",
                    alignItems: "center",
                  }}
                >
                  <strong style={{ color: "#a5b4fc", fontSize: "0.95rem" }}>
                    Transcript Citation Event #{selectedCitation.index} (
                    {selectedCitation.type.toUpperCase()})
                  </strong>
                  <button
                    onClick={() => setSelectedCitation(null)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#9ca3af",
                      cursor: "pointer",
                      fontWeight: "bold",
                      fontSize: "0.85rem",
                    }}
                  >
                    ✕ Close
                  </button>
                </div>
                <div
                  style={{
                    background: "rgba(0, 0, 0, 0.25)",
                    padding: "1rem",
                    borderRadius: "8px",
                    maxHeight: "220px",
                    overflowY: "auto",
                    whiteSpace: "pre-wrap",
                    fontFamily:
                      selectedCitation.type === "canvas"
                        ? "monospace"
                        : "inherit",
                    fontSize: "0.85rem",
                    color: "#e5e7eb",
                    lineHeight: "1.4",
                  }}
                >
                  {selectedCitation.content}
                </div>
              </div>
            )}

            {/* Quick Actions (Branded Links as buttons alerting "to be made") */}
            <div
              style={{
                marginTop: "1rem",
                paddingTop: "1.5rem",
                borderTop: "1px solid rgba(255, 255, 255, 0.12)",
              }}
            >
              <h3
                style={{
                  fontSize: "1.1rem",
                  color: "#c7d2fe",
                  marginBottom: "1rem",
                  marginTop: 0,
                  fontWeight: 700,
                }}
              >
                🔗 Nudge Quick Actions
              </h3>
              <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
                <button
                  onClick={() =>
                    alert("Export Nudge Canvas is waiting to be developed!")
                  }
                  style={{
                    background: "rgba(99, 102, 241, 0.15)",
                    border: "1px solid rgba(99, 102, 241, 0.3)",
                    color: "#a5b4fc",
                    padding: "0.8rem 1.6rem",
                    borderRadius: "8px",
                    cursor: "pointer",
                    fontSize: "0.95rem",
                    fontWeight: "bold",
                  }}
                >
                  📥 Export Nudge Canvas
                </button>
                <button
                  onClick={() =>
                    alert(
                      "Share Nudge Interview Report is waiting to be developed!",
                    )
                  }
                  style={{
                    background: "rgba(99, 102, 241, 0.15)",
                    border: "1px solid rgba(99, 102, 241, 0.3)",
                    color: "#a5b4fc",
                    padding: "0.8rem 1.6rem",
                    borderRadius: "8px",
                    cursor: "pointer",
                    fontSize: "0.95rem",
                    fontWeight: "bold",
                  }}
                >
                  🔗 Share Interview Report
                </button>
                <button
                  onClick={() =>
                    alert(
                      "Nudge Feedback & Improvement Hub is waiting to be developed!",
                    )
                  }
                  style={{
                    background: "rgba(99, 102, 241, 0.15)",
                    border: "1px solid rgba(99, 102, 241, 0.3)",
                    color: "#a5b4fc",
                    padding: "0.8rem 1.6rem",
                    borderRadius: "8px",
                    cursor: "pointer",
                    fontSize: "0.95rem",
                    fontWeight: "bold",
                  }}
                >
                  💬 Send Feedback to Nudge
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div
            className="ideal-canvas-split"
            style={{
              display: "flex",
              flexDirection: "row",
              gap: "2rem",
              height: "calc(100vh - 180px)",
              minHeight: "750px",
              padding: "1.5rem",
              boxSizing: "border-box",
              width: "100%",
            }}
          >
            {/* Left Side: Solutions & Performance Gaps Sidebar (45%) */}
            <div
              style={{
                flex: "0 0 45%",
                display: "flex",
                flexDirection: "column",
                gap: "1.5rem",
                overflowY: "auto",
                paddingRight: "0.5rem",
                boxSizing: "border-box",
              }}
            >
              {/* Scenario & Prompt Info */}
              <div
                style={{
                  padding: "1.2rem",
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "12px",
                }}
              >
                <h2
                  style={{
                    fontSize: "1.2rem",
                    color: "#a5b4fc",
                    margin: "0 0 0.5rem 0",
                    fontWeight: 700,
                  }}
                >
                  🎯 Scenario: {questionTopic}
                </h2>
                <p
                  style={{
                    fontSize: "0.85rem",
                    color: "#d1d5db",
                    margin: 0,
                    lineHeight: "1.4",
                  }}
                >
                  <strong>Challenge:</strong> {questionPrompt}
                </p>
              </div>

              {/* Ideal Reference Blocks */}
              {idealAnswerPlan &&
                idealAnswerPlan.blocks &&
                idealAnswerPlan.blocks.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <h3
                      style={{
                        fontSize: "1rem",
                        color: "#c7d2fe",
                        margin: "0.5rem 0 0 0",
                        fontWeight: 700,
                      }}
                    >
                      📖 Ideal Answer Components
                    </h3>
                    {idealAnswerPlan.blocks.map((block: any, bIdx: number) => {
                      const hasGapLink = block.addresses_gap !== null && block.addresses_gap !== undefined;
                      const isHighlighted = highlightedGap === block.addresses_gap;
                      return (
                        <div
                          key={bIdx}
                          onClick={() => {
                            if (hasGapLink) {
                              setHighlightedGap(block.addresses_gap);
                              if (excalidrawRef.current) {
                                const elements = excalidrawRef.current.getSceneElements();
                                const matchingEl = elements.find(
                                  (el: any) => el.customAddressesGap === block.addresses_gap
                                );
                                if (matchingEl) {
                                  excalidrawRef.current.updateScene({
                                    appState: {
                                      selectedElementIds: {
                                        [matchingEl.id]: true
                                      }
                                    }
                                  });
                                }
                              }
                            }
                          }}
                          style={{
                            background: block.type === "code" ? "#1e1e1e" : "rgba(255, 255, 255, 0.02)",
                            border: isHighlighted 
                              ? "2px solid #6965db" 
                              : "1px solid rgba(255, 255, 255, 0.08)",
                            borderRadius: "8px",
                            padding: "1rem",
                            cursor: hasGapLink ? "pointer" : "default",
                            transition: "all 0.2s ease-in-out",
                            transform: isHighlighted ? "scale(1.01)" : "none",
                            boxShadow: isHighlighted ? "0 4px 12px rgba(105, 101, 219, 0.2)" : "none",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "0.5rem",
                            }}
                          >
                            <span style={{ color: "#c7d2fe", fontSize: "0.9rem", fontWeight: "bold" }}>
                              {block.title || `Part ${bIdx + 1}`}
                            </span>
                            <span
                              style={{
                                fontSize: "0.7rem",
                                background: block.type === "code" 
                                  ? "rgba(156, 220, 254, 0.15)" 
                                  : "rgba(105, 101, 219, 0.15)",
                                color: block.type === "code" ? "#9cdcfe" : "#a5b4fc",
                                padding: "0.15rem 0.4rem",
                                borderRadius: "4px",
                                fontWeight: "bold",
                                textTransform: "uppercase",
                              }}
                            >
                              {block.type}
                            </span>
                          </div>

                          {block.type === "code" ? (
                            <pre
                              style={{
                                margin: 0,
                                padding: "0.6rem",
                                background: "#111111",
                                color: "#9cdcfe",
                                borderRadius: "4px",
                                overflowX: "auto",
                                fontSize: "0.8rem",
                                fontFamily: "monospace",
                                border: "1px solid rgba(255, 255, 255, 0.05)",
                              }}
                            >
                              <code>{block.content}</code>
                            </pre>
                          ) : (
                            <p
                              style={{
                                margin: 0,
                                fontSize: "0.85rem",
                                color: "#d1d5db",
                                lineHeight: "1.4",
                                whiteSpace: "pre-wrap",
                              }}
                            >
                              {block.content}
                            </p>
                          )}

                          {hasGapLink && (
                            <div
                              style={{
                                marginTop: "0.5rem",
                                fontSize: "0.75rem",
                                color: "#f87171",
                                display: "flex",
                                alignItems: "center",
                                gap: "0.25rem",
                                fontWeight: "bold",
                              }}
                            >
                              ⚠️ Identifies Gap Cite #{block.addresses_gap} (Click to view)
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

              {/* Linked Gaps List */}
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <h3
                  style={{
                    fontSize: "1rem",
                    color: "#c7d2fe",
                    margin: "0.5rem 0 0 0",
                    fontWeight: 700,
                  }}
                >
                  🔗 Candidate Gap Alignment
                </h3>
                {debriefSections.map((section, idx) => {
                  const hasActiveBadge = section.citations.includes(
                    highlightedGap as number,
                  );
                  return (
                    <div
                      key={idx}
                      onClick={() => {
                        if (section.citations.length > 0) {
                          const targetGap = section.citations[0];
                          setHighlightedGap(targetGap);
                          if (excalidrawRef.current) {
                            const elements = excalidrawRef.current.getSceneElements();
                            const matchingEl = elements.find(
                              (el: any) => el.customAddressesGap === targetGap,
                            );
                            if (matchingEl) {
                              excalidrawRef.current.updateScene({
                                appState: {
                                  selectedElementIds: {
                                    [matchingEl.id]: true,
                                  },
                                },
                              });
                            }
                          }
                        }
                      }}
                      style={{
                        padding: "1rem",
                        background: "rgba(255, 255, 255, 0.02)",
                        border: hasActiveBadge
                          ? "2px solid #fbbf24"
                          : "1px solid rgba(255, 255, 255, 0.08)",
                        borderRadius: "8px",
                        cursor: "pointer",
                        transition: "all 0.2s ease-in-out",
                        boxShadow: hasActiveBadge ? "0 4px 12px rgba(251, 191, 36, 0.15)" : "none",
                      }}
                    >
                      <strong style={{ fontSize: "0.85rem", color: "#c7d2fe", textTransform: "capitalize" }}>
                        {section.area.replace("_", " ")}
                      </strong>
                      <p
                        style={{
                          margin: "0.4rem 0 0 0",
                          fontSize: "0.8rem",
                          color: "#9ca3af",
                          lineHeight: "1.4",
                        }}
                      >
                        {section.verdict}
                      </p>
                      <div
                        style={{
                          display: "flex",
                          gap: "0.4rem",
                          marginTop: "0.5rem",
                          flexWrap: "wrap",
                        }}
                      >
                        {section.citations.map((c) => (
                          <span
                            key={c}
                            id={`citation-card-${c}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              setHighlightedGap(c);
                              if (excalidrawRef.current) {
                                const elements = excalidrawRef.current.getSceneElements();
                                const matchingEl = elements.find(
                                  (el: any) => el.customAddressesGap === c,
                                );
                                if (matchingEl) {
                                  excalidrawRef.current.updateScene({
                                    appState: {
                                      selectedElementIds: {
                                        [matchingEl.id]: true,
                                      },
                                    },
                                  });
                                }
                              }
                            }}
                            style={{
                              fontSize: "0.7rem",
                              padding: "0.15rem 0.4rem",
                              borderRadius: "4px",
                              fontWeight: "bold",
                              background: highlightedGap === c ? "#fbbf24" : "rgba(255, 255, 255, 0.1)",
                              color: highlightedGap === c ? "#18181b" : "#fbbf24",
                              border: "1px solid rgba(251, 191, 36, 0.3)",
                            }}
                          >
                            Cite #{c}
                          </span>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Start new interview button */}
              <button
                className="btn-restart"
                onClick={handleRestart}
                style={{
                  marginTop: "1rem",
                  width: "100%",
                  padding: "0.8rem",
                  borderRadius: "8px",
                  fontWeight: "bold",
                  cursor: "pointer",
                }}
              >
                Start a New Interview
              </button>
            </div>

            {/* Right Side: Interactive Whiteboard Canvas (55%) */}
            <div
              style={{
                flex: "0 0 55%",
                height: "100%",
                border: "1px solid var(--border-color)",
                borderRadius: "12px",
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
                background: "#f8f9fa",
              }}
            >
              <div
                style={{
                  padding: "0.8rem 1.2rem",
                  background: "#ffffff",
                  borderBottom: "1px solid var(--border-color)",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <span style={{ fontSize: "0.85rem", fontWeight: "bold", color: "var(--text-main)" }}>
                  🗺️ Ideal Whiteboard Diagram Model
                </span>
                <span style={{ fontSize: "0.75rem", color: "#6b7280" }}>
                  Interact with shapes or click cite badges to link
                </span>
              </div>
              <div style={{ flex: 1, position: "relative" }}>
                <Excalidraw
                  viewModeEnabled={true}
                  initialData={{
                    elements: structuredPlanToCanvasElements(idealAnswerPlan),
                    appState: {
                      theme: "light",
                      viewBackgroundColor: "#f8f9fa",
                    },
                  }}
                  ref={(api: any) => {
                    excalidrawRef.current = api;
                  }}
                  onChange={(elements, appState) => {
                    const selectedIds = Object.keys(appState.selectedElementIds || {});
                    if (selectedIds.length > 0) {
                      const selectedEl = elements.find((el) => el.id === selectedIds[0]);
                      if (selectedEl && (selectedEl as any).customAddressesGap !== undefined) {
                        const gapIndex = (selectedEl as any).customAddressesGap;
                        setHighlightedGap(gapIndex);
                        const card = document.getElementById(`citation-card-${gapIndex}`);
                        if (card) {
                          card.scrollIntoView({
                            behavior: "smooth",
                            block: "center",
                          });
                        }
                      }
                    }
                  }}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return null;
}
