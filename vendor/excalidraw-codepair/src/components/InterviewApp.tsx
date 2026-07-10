import React, { useState, useEffect, useRef } from "react";
import io from "socket.io-client";
import { Excalidraw } from "../packages/excalidraw/index";
import { structuredPlanToCanvasElements } from "../utils/idealCanvas";
import { serializeCanvas } from "../utils/serializeCanvas";
import "../css/interview.css";

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

  // Timer and Multi-Scenario States
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [canvasKey, setCanvasKey] = useState(0);
  const [showNextScenarioOffer, setShowNextScenarioOffer] = useState(false);
  const [hasNextScenario, setHasNextScenario] = useState(false);

  const lastEmittedCanvasRef = useRef<string>("");
  const canvasTimeoutRef = useRef<any>(null);

  const handleCanvasChange = (elements: readonly any[]) => {
    if (screen !== "interview") return;

    if (canvasTimeoutRef.current) {
      clearTimeout(canvasTimeoutRef.current);
    }

    canvasTimeoutRef.current = setTimeout(() => {
      const serialized = serializeCanvas(elements);
      if (serialized !== lastEmittedCanvasRef.current) {
        lastEmittedCanvasRef.current = serialized;
        if (socketRef.current) {
          socketRef.current.emit("canvas_update", {
            roomId: sessionId,
            sessionId: sessionId,
            serialized: serialized,
          });
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
      const response = await fetch("http://localhost:3002/api/session/create", {
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

      const newSessionId = data.id;
      setSessionId(newSessionId);
      setQuestionTopic(data.question_topic);
      setQuestionPrompt(data.question_prompt);

      const matched = data.matched_questions || [];
      const idx = data.current_question_index || 0;
      setHasNextScenario(idx + 1 < matched.length);

      // 2. Set Excalidraw collaboration URL room hash
      const roomKey = "1234567890123456789012"; // 22-char key
      window.location.hash = `room=${newSessionId},${roomKey}`;

      // 3. Setup Socket.io client connection to backend orchestrator
      const socket = io("http://localhost:3002");
      socketRef.current = socket;

      socket.on("connect", () => {
        socket.emit("join_room", {
          roomId: newSessionId,
          sessionId: newSessionId,
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
        // Fetch debrief & session transcript
        const debriefResp = await fetch(
          `http://localhost:3002/api/debrief/${newSessionId}`,
        );
        const debriefData = await debriefResp.json();
        setDebriefSections(debriefData.sections);

        const sessResp = await fetch(
          `http://localhost:3002/api/session/${newSessionId}`,
        );
        const sessData = await sessResp.json();
        setFullTranscript(sessData.transcript);

        try {
          const idealResp = await fetch(
            `http://localhost:3002/api/debrief/ideal_answer/${newSessionId}`,
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
      const resp = await fetch(
        `http://localhost:3002/api/session/next_scenario/${sessionId}`,
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

        // Generate a new 22-char encryption key to clear the canvas
        const nextKey =
          Math.random().toString(36).substring(2, 13) +
          Math.random().toString(36).substring(2, 13);
        window.location.hash = `room=${sessionId},${nextKey}`;

        // Force ExcalidrawApp to unmount and remount fresh
        setCanvasKey((prev) => prev + 1);

        // Setup Socket.io client connection to backend orchestrator for the new scenario
        const socket = io("http://localhost:3002");
        socketRef.current = socket;

        socket.on("connect", () => {
          socket.emit("join_room", {
            roomId: sessionId,
            sessionId,
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
          const debriefResp = await fetch(
            `http://localhost:3002/api/debrief/${sessionId}`,
          );
          const debriefData = await debriefResp.json();
          setDebriefSections(debriefData.sections);

          const sessResp = await fetch(
            `http://localhost:3002/api/session/${sessionId}`,
          );
          const sessData = await sessResp.json();
          setFullTranscript(sessData.transcript);

          try {
            const idealResp = await fetch(
              `http://localhost:3002/api/debrief/ideal_answer/${sessionId}`,
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
          const updatedSessResp = await fetch(
            `http://localhost:3002/api/session/${sessionId}`,
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
            ref={excalidrawRef}
            onChange={handleCanvasChange}
            theme="dark"
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
                  vLower.includes("no code was written") ||
                  vLower.includes("did not provide") ||
                  vLower.includes("could not be verified") ||
                  vLower.includes("failed to") ||
                  vLower.includes("did not address") ||
                  vLower.includes("no solution") ||
                  vLower.includes("without a solution") ||
                  vLower.includes("blank")
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
              flexDirection: "column",
              gap: "1.5rem",
              height: "100%",
              overflowY: "auto",
              padding: "1.5rem",
              width: "100%",
              boxSizing: "border-box",
            }}
          >
            {/* Top Section: Scenario Question and Reference Solution Overview */}
            <div
              style={{
                padding: "1.5rem",
                background: "rgba(255, 255, 255, 0.03)",
                border: "1px solid var(--border-color)",
                borderRadius: "12px",
              }}
            >
              <h2
                style={{
                  fontSize: "1.3rem",
                  color: "#a5b4fc",
                  marginBottom: "0.5rem",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  marginTop: 0,
                }}
              >
                🎯 Scenario Challenge: {questionTopic}
              </h2>
              <div
                style={{
                  fontSize: "0.95rem",
                  color: "#d1d5db",
                  background: "rgba(0, 0, 0, 0.25)",
                  padding: "1rem",
                  borderRadius: "8px",
                  lineHeight: "1.5",
                  marginBottom: "1.5rem",
                }}
              >
                <strong>Whiteboard Prompt:</strong> {questionPrompt}
              </div>
              {idealAnswerPlan &&
                idealAnswerPlan.blocks &&
                idealAnswerPlan.blocks.length > 0 && (
                  <div>
                    <h3
                      style={{
                        fontSize: "1.05rem",
                        color: "#c7d2fe",
                        marginBottom: "0.8rem",
                        marginTop: 0,
                      }}
                    >
                      📖 Ideal Answer Reference Solutions
                    </h3>
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: "1rem",
                      }}
                    >
                      {idealAnswerPlan.blocks.map(
                        (block: any, bIdx: number) => (
                          <div
                            key={bIdx}
                            style={{
                              background: "rgba(255, 255, 255, 0.02)",
                              border: "1px solid rgba(255, 255, 255, 0.05)",
                              borderRadius: "8px",
                              padding: "1rem",
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
                              <strong
                                style={{
                                  color: "#c7d2fe",
                                  fontSize: "0.95rem",
                                }}
                              >
                                {block.title || `Block #${bIdx + 1}`}
                              </strong>
                              <span
                                style={{
                                  fontSize: "0.75rem",
                                  background: "rgba(105, 101, 219, 0.2)",
                                  color: "#a5b4fc",
                                  padding: "0.2rem 0.5rem",
                                  borderRadius: "4px",
                                  fontWeight: "bold",
                                }}
                              >
                                {block.type.toUpperCase()}
                              </span>
                            </div>
                            {block.type === "code" ? (
                              <pre
                                style={{
                                  margin: 0,
                                  padding: "0.8rem",
                                  background: "#1e1e1e",
                                  color: "#9cdcfe",
                                  borderRadius: "6px",
                                  overflowX: "auto",
                                  fontSize: "0.85rem",
                                  fontFamily: "monospace",
                                }}
                              >
                                <code>{block.content}</code>
                              </pre>
                            ) : (
                              <p
                                style={{
                                  margin: 0,
                                  fontSize: "0.9rem",
                                  color: "#e5e7eb",
                                  lineHeight: "1.4",
                                  whiteSpace: "pre-wrap",
                                }}
                              >
                                {block.content}
                              </p>
                            )}
                            {block.addresses_gap !== null &&
                              block.addresses_gap !== undefined && (
                                <div
                                  style={{
                                    marginTop: "0.5rem",
                                    fontSize: "0.8rem",
                                    color: "#f87171",
                                    fontWeight: "bold",
                                  }}
                                >
                                  ⚠️ Addresses Citation Gap #
                                  {block.addresses_gap}
                                </div>
                              )}
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
            </div>

            {/* Split Section: Interactive Whiteboard Canvas & Performance Gaps Sidebar */}
            <div
              style={{
                display: "flex",
                gap: "1.5rem",
                flex: 1,
                minHeight: "600px",
                width: "100%",
              }}
            >
              <div
                className="ideal-canvas-container"
                style={{
                  flex: 2,
                  height: "100%",
                  minHeight: "600px",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  overflow: "hidden",
                }}
              >
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
                    const selectedIds = Object.keys(
                      appState.selectedElementIds || {},
                    );
                    if (selectedIds.length > 0) {
                      const selectedEl = elements.find(
                        (el) => el.id === selectedIds[0],
                      );
                      if (
                        selectedEl &&
                        (selectedEl as any).customAddressesGap !== undefined
                      ) {
                        const gapIndex = (selectedEl as any).customAddressesGap;
                        setHighlightedGap(gapIndex);
                        const card = document.getElementById(
                          `citation-card-${gapIndex}`,
                        );
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

              <div
                className="ideal-canvas-sidebar"
                style={{
                  flex: 1,
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                }}
              >
                <h3>Linked Performance Gaps</h3>
                <p className="sidebar-instructions">
                  Select a highlighted element on the canvas to view the
                  matching transcript gap, or click on a badge below to locate
                  it on the canvas.
                </p>
                <div
                  className="linked-gaps-list"
                  style={{ flex: 1, overflowY: "auto" }}
                >
                  {debriefSections.map((section, idx) => {
                    const hasActiveBadge = section.citations.includes(
                      highlightedGap as number,
                    );
                    return (
                      <div
                        key={idx}
                        className={
                          hasActiveBadge
                            ? "linked-gap-card highlighted"
                            : "linked-gap-card"
                        }
                        onClick={() => {
                          if (section.citations.length > 0) {
                            const targetGap = section.citations[0];
                            setHighlightedGap(targetGap);
                            if (excalidrawRef.current) {
                              const elements =
                                excalidrawRef.current.getSceneElements();
                              const matchingEl = elements.find(
                                (el: any) =>
                                  el.customAddressesGap === targetGap,
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
                      >
                        <strong>{section.area.replace("_", " ")}</strong>
                        <p>{section.verdict}</p>
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
                              className={
                                highlightedGap === c
                                  ? "gap-badge active"
                                  : "gap-badge"
                              }
                              onClick={(e) => {
                                e.stopPropagation();
                                setHighlightedGap(c);
                                if (excalidrawRef.current) {
                                  const elements =
                                    excalidrawRef.current.getSceneElements();
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
                            >
                              Cite #{c}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div
                  style={{
                    marginTop: "auto",
                    paddingTop: "1rem",
                    display: "flex",
                    justifyContent: "center",
                  }}
                >
                  <button
                    className="btn-restart"
                    style={{ width: "100%" }}
                    onClick={handleRestart}
                  >
                    Start a New Interview
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return null;
}
