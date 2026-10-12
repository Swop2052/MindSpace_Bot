"""
FastAPI application for Manovedh Chatbot.
Provides REST API endpoints for chatbot integration.
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import uuid
import logging
import os
import time
import secrets
from collections import defaultdict

from main import ManovedhChatbot, MindSpaceChatbot
from conversation_memory import (
    get_memory,
    clear_memory,
    delete_memory,
    session_exists,
    list_all_session_ids,
    redis_client,
    USE_REDIS,
)
from language_support import detect_language
from config import CONVERSATIONAL_BOT_API_KEY

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# Rate Limiting (Redis-backed with in-memory fallback)
# ============================================================================
class RateLimiter:
    """Distributed Redis-backed rate limiter with in-memory fallback."""
    
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)
    
    def check(self, client_id: str) -> bool:
        """Check if request is allowed."""
        if USE_REDIS and redis_client:
            try:
                key = f"manovedh:ratelimit:{client_id}"
                current = redis_client.incr(key)
                if current == 1:
                    redis_client.expire(key, 60)
                return current <= self.requests_per_minute
            except Exception as e:
                logger.debug(f"Redis rate limit check failed, falling back to local: {e}")

        now = time.time()
        # Clean old requests
        self.requests[client_id] = [t for t in self.requests[client_id] if now - t < 60]
        
        if len(self.requests[client_id]) >= self.requests_per_minute:
            return False
        
        self.requests[client_id].append(now)
        return True

rate_limiter = RateLimiter(requests_per_minute=60)

# API Key Verification (Supports Authorization: Bearer <key> and X-API-Key: <key>)
security = HTTPBearer(auto_error=False)
API_KEY = CONVERSATIONAL_BOT_API_KEY or os.getenv("CONVERSATIONAL_BOT_API_KEY", "").strip()

async def verify_api_key(
    req: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    token = None
    if credentials and credentials.credentials:
        token = credentials.credentials.strip()
    elif "x-api-key" in req.headers:
        token = req.headers.get("x-api-key", "").strip()
    
    # If API_KEY is configured on the server, validate
    if API_KEY and len(API_KEY) >= 8:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key. Provide header 'Authorization: Bearer <your_key>' or 'X-API-Key: <your_key>'."
            )
        if not secrets.compare_digest(token, API_KEY):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or incorrect API key."
            )
        return token
    
    # If no API key configured on server, permit access
    return token or "development"

# ============================================================================
# Pydantic Models for API
# ============================================================================

class ChatRequest(BaseModel):
    message: str = Field(..., description="User's message to the chatbot", min_length=1, max_length=5000)
    session_id: Optional[str] = Field(None, description="Unique session identifier")
    user_id: Optional[str] = Field(None, description="Optional user identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Hello, I'm feeling very stressed today",
                "session_id": "session_20260623_114702",
                "user_id": "user_12345"
            }
        }


class ChatResponse(BaseModel):
    response: str = Field(..., description="Chatbot's response message")
    session_id: str = Field(..., description="Current session identifier")
    message_id: str = Field(..., description="Unique message identifier")
    timestamp: str = Field(..., description="Response timestamp")
    is_crisis: bool = Field(False, description="Whether this was a crisis response")
    is_offensive: bool = Field(False, description="Whether offensive content was blocked")
    language: str = Field("en", description="Detected language of the conversation")
    user_name: Optional[str] = Field(None, description="User's name if known")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "I hear you. Stress can feel really heavy. Can you tell me what's been causing it lately?",
                "session_id": "session_20260623_114702",
                "message_id": "msg_20260623_114702_001",
                "timestamp": "2026-06-23T11:47:17.166510",
                "is_crisis": False,
                "is_offensive": False,
                "language": "en",
                "user_name": "Alex"
            }
        }


class SessionStats(BaseModel):
    session_id: str
    total_messages: int
    history_length: int
    crisis_escalations: int
    off_topic_redirects: int
    offensive_content_blocks: int
    languages_detected: List[str]
    user_name: Optional[str]
    first_seen: Optional[str]
    last_seen: Optional[str]
    name_learned: bool


class SessionCreateRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="Optional user identifier")


class SessionCreateResponse(BaseModel):
    session_id: str
    user_id: Optional[str]
    created_at: str
    message: str = "Session created successfully"


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: str


class HealthCheckResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: str
    services: Dict[str, str]

# ============================================================================
# Session Store
# ============================================================================

_session_store: Dict[str, ManovedhChatbot] = {}
_user_session_map: Dict[str, str] = {}
_session_timestamps: Dict[str, datetime] = {}
SESSION_TIMEOUT_HOURS = 24

# ============================================================================
# FastAPI Application (with Lifespan)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Manovedh Chatbot API starting...")
    logger.info("📚 Documentation available at /docs")
    logger.info("🔍 Health check available at /health")
    logger.info(f"📊 Max sessions: {len(_session_store)}")
    yield
    logger.info("👋 Manovedh Chatbot API shutting down...")
    for session_id, chatbot in _session_store.items():
        try:
            if hasattr(chatbot, 'memory') and chatbot.memory:
                chatbot.memory._save_memory()
                logger.info(f"💾 Saved session: {session_id}")
        except Exception as e:
            logger.error(f"❌ Error saving session {session_id}: {e}")

app = FastAPI(
    title="Manovedh Chatbot API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware - Production ready
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
is_wildcard = ALLOWED_ORIGINS == ["*"] or "*" in ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False if is_wildcard else True,  # Credentials must be false for wildcard *
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    max_age=86400,
)


def cleanup_expired_sessions():
    """Clean up expired sessions."""
    now = datetime.now()
    expired = []
    for session_id, last_active in _session_timestamps.items():
        if now - last_active > timedelta(hours=SESSION_TIMEOUT_HOURS):
            expired.append(session_id)
    
    for session_id in expired:
        if session_id in _session_store:
            del _session_store[session_id]
        if session_id in _session_timestamps:
            del _session_timestamps[session_id]
    
    if expired:
        logger.info(f"Cleaned up {len(expired)} expired sessions")


def get_or_create_chatbot(session_id: Optional[str] = None, user_id: Optional[str] = None, client_ip: Optional[str] = None) -> ManovedhChatbot:
    """Get or create a chatbot instance for a session."""
    # Cleanup expired sessions periodically
    cleanup_expired_sessions()
    
    # If user_id is provided and has an existing session, use that
    if user_id and user_id in _user_session_map:
        session_id = _user_session_map[user_id]
    
    # If session_id is provided, use that
    if session_id and session_id in _session_store:
        _session_timestamps[session_id] = datetime.now()
        return _session_store[session_id]
    
    # Create new session
    if not session_id:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    chatbot = ManovedhChatbot(session_id)
    _session_store[session_id] = chatbot
    _session_timestamps[session_id] = datetime.now()
    
    if user_id:
        _user_session_map[user_id] = session_id
    
    return chatbot

# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/", response_model=Dict[str, str])
async def root():
    return {
        "name": "Manovedh Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "documentation": "/docs",
        "health": "/health",
        "chat_ui": "/chat",
        "chat_api": "/api/chat"
    }


@app.get("/chat", response_class=HTMLResponse)
async def chat_ui():
    """Interactive, clean browser test UI for Manovedh Chatbot."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Manovedh Chatbot — Web Client</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f8fafc;
            --muted: #94a3b8;
            --user-bg: #3b82f6;
            --bot-bg: #334155;
            --accent: #10b981;
            --border: #475569;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; }
        header { background: var(--card); padding: 14px 24px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center; }
        h1 { font-size: 1.15rem; font-weight: 600; display: flex; align-items: center; gap: 8px; }
        .links a { color: var(--muted); text-decoration: none; font-size: 0.85rem; margin-left: 12px; }
        .links a:hover { color: var(--text); }
        #chat-container { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 14px; max-width: 860px; width: 100%; margin: 0 auto; }
        .msg { max-width: 80%; padding: 12px 16px; border-radius: 12px; line-height: 1.5; font-size: 0.95rem; white-space: pre-wrap; word-break: break-word; }
        .msg.user { align-self: flex-end; background: var(--user-bg); color: #fff; border-bottom-right-radius: 2px; }
        .msg.bot { align-self: flex-start; background: var(--bot-bg); color: var(--text); border-bottom-left-radius: 2px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
        .msg .sender { font-size: 0.75rem; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
        #input-area { background: var(--card); border-top: 1px solid var(--border); padding: 16px 20px; }
        .input-box { max-width: 860px; margin: 0 auto; display: flex; gap: 10px; }
        input[type="text"] { flex: 1; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; color: var(--text); font-size: 0.95rem; outline: none; }
        input[type="text"]:focus { border-color: var(--user-bg); }
        button { background: var(--user-bg); border: none; color: white; padding: 12px 20px; border-radius: 8px; cursor: pointer; font-weight: 500; font-size: 0.95rem; }
        button:hover { opacity: 0.9; }
        .meta-bar { max-width: 860px; margin: 0 auto 8px auto; display: flex; gap: 12px; font-size: 0.8rem; color: var(--muted); }
        .meta-bar input { background: transparent; border: 1px solid var(--border); border-radius: 4px; padding: 2px 6px; color: var(--text); font-size: 0.8rem; }
    </style>
</head>
<body>
    <header>
        <h1>🌟 Manovedh Mental Wellness Companion</h1>
        <div class="links">
            <a href="/docs" target="_blank">API Docs</a>
            <a href="/health" target="_blank">Health</a>
        </div>
    </header>
    <div id="chat-container">
        <div class="msg bot">
            <div class="sender">Manovedh</div>
            <div>Hey there! I'm here for you. Whether you want to talk about your day, how you're feeling, or anything on your mind, feel free to share without hesitation. 😊</div>
        </div>
    </div>
    <div id="input-area">
        <div class="meta-bar">
            <span>Auth Key:</span>
            <input type="password" id="api-key" value="jsgnkmunvryriuhpm765074nb" placeholder="API Key" style="width: 220px;" />
            <span id="status-pill" style="margin-left: auto;"></span>
        </div>
        <form class="input-box" id="chat-form" onsubmit="sendMessage(event)">
            <input type="text" id="user-input" placeholder="Type a message in English, Hindi, Marathi, or Hinglish..." autocomplete="off" />
            <button type="submit" id="send-btn">Send</button>
        </form>
    </div>
    <script>
        let sessionId = "session_web_" + Date.now();
        const container = document.getElementById("chat-container");
        const input = document.getElementById("user-input");
        const apiKeyInput = document.getElementById("api-key");
        const sendBtn = document.getElementById("send-btn");

        async function sendMessage(e) {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;

            appendMsg("You", text, "user");
            input.value = "";
            sendBtn.disabled = true;

            const loadingId = appendMsg("Manovedh", "Thinking...", "bot");

            try {
                const headers = { "Content-Type": "application/json" };
                const key = apiKeyInput.value.trim();
                if (key) {
                    headers["Authorization"] = "Bearer " + key;
                }

                const res = await fetch("/api/chat", {
                    method: "POST",
                    headers: headers,
                    body: JSON.stringify({
                        message: text,
                        session_id: sessionId
                    })
                });

                const data = await res.json();
                const loadingElem = document.getElementById(loadingId);

                if (!res.ok) {
                    loadingElem.innerHTML = `<div class="sender">Error (${res.status})</div><div>${data.detail || data.error || 'Request failed'}</div>`;
                } else {
                    sessionId = data.session_id;
                    loadingElem.innerHTML = `<div class="sender">Manovedh</div><div>${escapeHtml(data.response)}</div>`;
                }
            } catch (err) {
                const loadingElem = document.getElementById(loadingId);
                loadingElem.innerHTML = `<div class="sender">Error</div><div>Could not connect to server: ${err.message}</div>`;
            } finally {
                sendBtn.disabled = false;
                container.scrollTop = container.scrollHeight;
            }
        }

        function appendMsg(sender, text, type) {
            const id = "msg_" + Math.random().toString(36).substr(2, 9);
            const div = document.createElement("div");
            div.className = "msg " + type;
            div.id = id;
            div.innerHTML = `<div class="sender">${sender}</div><div>${escapeHtml(text)}</div>`;
            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
            return id;
        }

        function escapeHtml(str) {
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    return HealthCheckResponse(
        status="healthy",
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        services={
            "chatbot": "active",
            "memory": "active",
            "api": "active",
            "sessions": str(len(_session_store))
        }
    )


@app.post("/api/session", response_model=SessionCreateResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_api_key)])
def create_session(request: SessionCreateRequest):
    try:
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        chatbot = ManovedhChatbot(session_id)
        _session_store[session_id] = chatbot
        _session_timestamps[session_id] = datetime.now()
        
        if request.user_id:
            _user_session_map[request.user_id] = session_id
        
        return SessionCreateResponse(
            session_id=session_id,
            user_id=request.user_id,
            created_at=datetime.now().isoformat(),
            message="Session created successfully"
        )
        
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
def chat(request: ChatRequest, req: Request):
    try:
        # Rate limiting
        client_ip = req.client.host if req.client else "unknown"
        if not rate_limiter.check(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait a moment before sending more messages."
            )
        
        # Validate message
        if not request.message or not request.message.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty"
            )
        
        # Get or create chatbot instance
        chatbot = get_or_create_chatbot(request.session_id, request.user_id, client_ip)
        
        # Get stats before response generation to identify triggers
        stats_before = chatbot.get_stats()
        
        # Get response (handles translation, domain check, crisis, and offensive content)
        response_text = chatbot.get_response(request.message)
        
        # Get stats after response generation
        stats_after = chatbot.get_stats()
        
        # Detect if safety triggers were fired based on statistics changes
        is_offensive = stats_after.get("offensive_content_blocks", 0) > stats_before.get("offensive_content_blocks", 0)
        is_crisis = stats_after.get("crisis_escalations", 0) > stats_before.get("crisis_escalations", 0)
        
        # Detect language
        language = detect_language(request.message)
        
        # Get user name if known
        user_name = chatbot.memory.get_user_name()
        
        # Generate message ID
        message_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        
        return ChatResponse(
            response=response_text,
            session_id=chatbot.session_id,
            message_id=message_id,
            timestamp=datetime.now().isoformat(),
            is_crisis=is_crisis,
            is_offensive=is_offensive,
            language=language,
            user_name=user_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process message: {str(e)}"
        )


@app.get("/api/session/{session_id}/stats", response_model=SessionStats, dependencies=[Depends(verify_api_key)])
def get_session_stats(session_id: str):
    try:
        if not session_exists(session_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        chatbot = get_or_create_chatbot(session_id)
        stats = chatbot.get_stats()
        user_info = chatbot.memory.get_user_info()
        
        return SessionStats(
            session_id=session_id,
            total_messages=stats.get("total_messages", 0),
            history_length=stats.get("history_length", 0),
            crisis_escalations=stats.get("crisis_escalations", 0),
            off_topic_redirects=stats.get("off_topic_redirects", 0),
            offensive_content_blocks=stats.get("offensive_content_blocks", 0),
            languages_detected=stats.get("languages_detected", []),
            user_name=stats.get("user_name"),
            first_seen=user_info.get("first_seen"),
            last_seen=user_info.get("last_seen"),
            name_learned=stats.get("name_learned", False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session stats: {str(e)}"
        )


@app.delete("/api/session/{session_id}/clear", dependencies=[Depends(verify_api_key)])
def clear_session_memory(session_id: str):
    try:
        if not session_exists(session_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        chatbot = get_or_create_chatbot(session_id)
        chatbot.clear_memory()
        
        return {
            "status": "success",
            "message": f"Memory cleared for session {session_id}",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing session memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear session memory: {str(e)}"
        )


@app.delete("/api/session/{session_id}/reset", dependencies=[Depends(verify_api_key)])
def reset_session(session_id: str):
    try:
        if not session_exists(session_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        chatbot = get_or_create_chatbot(session_id)
        chatbot.reset_all()
        
        return {
            "status": "success",
            "message": f"Session {session_id} reset completely",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset session: {str(e)}"
        )


@app.delete("/api/session/{session_id}", dependencies=[Depends(verify_api_key)])
def delete_session(session_id: str):
    try:
        if not session_exists(session_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found"
            )
        
        delete_memory(session_id)
        if session_id in _session_store:
            del _session_store[session_id]
        if session_id in _session_timestamps:
            del _session_timestamps[session_id]
        
        for user_id, sess_id in list(_user_session_map.items()):
            if sess_id == session_id:
                del _user_session_map[user_id]
        
        return {
            "status": "success",
            "message": f"Session {session_id} deleted successfully",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


@app.get("/api/sessions", dependencies=[Depends(verify_api_key)])
def list_sessions():
    try:
        session_ids = list_all_session_ids()
        sessions = []
        for session_id in session_ids:
            try:
                chatbot = get_or_create_chatbot(session_id)
                stats = chatbot.get_stats()
                user_name = stats.get("user_name")
                user_info = chatbot.memory.get_user_info()
                sessions.append({
                    "session_id": session_id,
                    "user_name": user_name,
                    "total_messages": stats.get("total_messages", 0),
                    "created_at": user_info.get("first_seen"),
                    "last_active": user_info.get("last_seen")
                })
            except Exception:
                continue
        
        return {
            "total_sessions": len(sessions),
            "active_sessions": len([s for s in sessions if s.get("last_active")]),
            "sessions": sessions,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list sessions: {str(e)}"
        )

# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.detail,
            detail=str(exc.detail),
            timestamp=datetime.now().isoformat()
        ).model_dump()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc),
            timestamp=datetime.now().isoformat()
        ).model_dump()
    )

# ============================================================================
# End of Event Definitions
# ============================================================================


# ============================================================================
# Main entry point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    from config import API_HOST, API_PORT, API_RELOAD, API_WORKERS
    
    print("=" * 60)
    print("🌟 Manovedh Chatbot API Server")
    print("=" * 60)
    print("🚀 Starting server...")
    print(f"💬 Web Client:      http://localhost:{API_PORT}/chat")
    print(f"📚 API Docs:        http://localhost:{API_PORT}/docs")
    print(f"🔍 Health Check:    http://localhost:{API_PORT}/health")
    print(f"📨 REST Endpoint:   POST http://localhost:{API_PORT}/api/chat")
    print("=" * 60)
    
    # On Windows, Uvicorn multi-worker mode causes spawn deadlocks, socket errors, and WinError 10054
    # Multi-worker mode is designed for Linux / container environments
    if os.name == 'nt' or API_RELOAD:
        workers = 1
        if API_WORKERS > 1 and not API_RELOAD:
            print(f"ℹ️ Windows environment: running single worker (multi-worker is enabled on Linux/Docker)")
    else:
        workers = API_WORKERS
    
    uvicorn.run(
        "api:app",
        host=API_HOST,
        port=API_PORT,
        reload=API_RELOAD,
        workers=workers,
        log_level="info"
    )