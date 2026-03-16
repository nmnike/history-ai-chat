# src/viewer/main.py
"""FastAPI application for Claude Codex Viewer"""
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

from .parsers import ClaudeParser, CodexParser, Session, Message
from .db.cache import CacheDB


# Initialize parsers from environment or defaults
claude_path = os.environ.get("CLAUDE_PROJECTS_PATH")
codex_path = os.environ.get("CODEX_SESSIONS_PATH")

claude_parser = ClaudeParser(claude_path)
codex_parser = CodexParser(codex_path)

# Initialize cache
cache_dir = Path.home() / ".claude-codex-viewer"
cache_dir.mkdir(parents=True, exist_ok=True)
cache_db = CacheDB(cache_dir / "cache.db")

# FastAPI app
app = FastAPI(
    title="Claude Codex Viewer",
    description="Web viewer for Claude Code and Codex CLI conversation history",
    version="0.1.0"
)

# Static files and templates
static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir))


def session_to_dict(session: Session, platform: str) -> dict:
    """Convert Session to dict for JSON response"""
    return {
        "id": session.id,
        "project_name": session.project_name,
        "project_path": session.project_path,
        "platform": platform,
        "first_message": session.first_message,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "message_count": len(session.messages)
    }


def message_to_dict(msg: Message) -> dict:
    """Convert Message to dict for JSON response"""
    return {
        "role": msg.role,
        "content": msg.content,
        "uuid": msg.uuid,
        "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
        "session_id": msg.session_id,
        "project_path": msg.project_path,
        "message_type": msg.message_type,
        "tool_name": msg.tool_name,
        "tool_input": msg.tool_input,
        "thinking_text": msg.thinking_text
    }


# HTML Pages

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page with overview of all projects"""
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/project/{project_id}", response_class=HTMLResponse)
async def project_page(
    request: Request,
    project_id: str,
    platform: str = Query(default="claude")
):
    """Project page showing sessions"""
    return templates.TemplateResponse(
        "project.html",
        {"request": request, "project_id": project_id, "platform": platform}
    )


@app.get("/conversation/{session_id}", response_class=HTMLResponse)
async def conversation_page(
    request: Request,
    session_id: str,
    project_id: str = Query(default=""),
    platform: str = Query(default="claude")
):
    """Conversation page showing full session"""
    return templates.TemplateResponse(
        "conversation.html",
        {
            "request": request,
            "session_id": session_id,
            "project_id": project_id,
            "platform": platform
        }
    )


# API Endpoints

@app.get("/api/projects")
async def list_projects():
    """List all projects from both platforms"""
    projects = []

    # Claude projects
    for project in claude_parser.get_projects():
        projects.append({
            **project,
            "platform": "claude"
        })

    # Codex sessions grouped by project
    codex_sessions = codex_parser.get_sessions()
    codex_projects = {}
    for session in codex_sessions:
        project_name = session.project_name
        if project_name not in codex_projects:
            codex_projects[project_name] = {
                "id": project_name,
                "name": project_name,
                "path": session.project_path,
                "session_count": 0,
                "platform": "codex"
            }
        codex_projects[project_name]["session_count"] += 1

    projects.extend(codex_projects.values())

    return {"projects": sorted(projects, key=lambda x: x["name"])}


@app.get("/api/sessions/{project_id}")
async def list_sessions(
    project_id: str,
    platform: str = Query(default="claude")
):
    """List sessions for a project"""
    sessions = []

    if platform == "claude":
        for session in claude_parser.get_sessions(project_id):
            sessions.append(session_to_dict(session, "claude"))
    elif platform == "codex":
        # For Codex, project_id is the project_name
        for session in codex_parser.get_sessions():
            if session.project_name == project_id:
                sessions.append(session_to_dict(session, "codex"))
    else:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'claude' or 'codex'")

    return {"sessions": sessions}


@app.get("/api/conversation/{session_id}")
async def get_conversation(
    session_id: str,
    project_id: str = Query(default=""),
    platform: str = Query(default="claude")
):
    """Get full conversation for a session"""
    session: Optional[Session] = None

    if platform == "claude":
        sessions = claude_parser.get_sessions(project_id)
        for s in sessions:
            if s.id == session_id:
                session = s
                break
    elif platform == "codex":
        for s in codex_parser.get_sessions():
            if s.id == session_id:
                session = s
                break
    else:
        raise HTTPException(status_code=400, detail="Invalid platform. Use 'claude' or 'codex'")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session": session_to_dict(session, platform),
        "messages": [message_to_dict(m) for m in session.messages]
    }


@app.get("/api/search")
async def search(
    q: str = Query(default=""),
    platform: str = Query(default="all")
):
    """Global search across all sessions"""
    results = []
    query = q.lower()

    if not query:
        return {"results": []}

    def search_in_session(session: Session, platform_name: str) -> list[dict]:
        """Search in session messages"""
        matches = []
        for msg in session.messages:
            if query in msg.content.lower():
                matches.append({
                    "session_id": session.id,
                    "project_name": session.project_name,
                    "platform": platform_name,
                    "role": msg.role,
                    "content_preview": msg.content[:200] + "..." if len(msg.content) > 200 else msg.content,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
                })
        return matches

    # Search in Claude
    if platform in ("all", "claude"):
        for project in claude_parser.get_projects():
            for session in claude_parser.get_sessions(project["id"]):
                results.extend(search_in_session(session, "claude"))

    # Search in Codex
    if platform in ("all", "codex"):
        for session in codex_parser.get_sessions():
            results.extend(search_in_session(session, "codex"))

    return {"results": results[:100]}  # Limit to 100 results


@app.get("/api/export/{session_id}")
async def export_session(
    session_id: str,
    project_id: str = Query(default=""),
    platform: str = Query(default="claude"),
    format: str = Query(default="md")
):
    """Export session in various formats"""
    session: Optional[Session] = None

    if platform == "claude":
        sessions = claude_parser.get_sessions(project_id)
        for s in sessions:
            if s.id == session_id:
                session = s
                break
    elif platform == "codex":
        for s in codex_parser.get_sessions():
            if s.id == session_id:
                session = s
                break
    else:
        raise HTTPException(status_code=400, detail="Invalid platform")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if format == "md":
        content = export_to_markdown(session)
        media_type = "text/markdown"
    elif format == "html":
        content = export_to_html(session)
        media_type = "text/html"
    elif format == "json":
        content = export_to_json(session)
        media_type = "application/json"
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'md', 'html', or 'json'")

    return JSONResponse(
        content={"content": content, "format": format, "media_type": media_type}
    )


def export_to_markdown(session: Session) -> str:
    """Export session to Markdown format"""
    lines = [
        f"# Conversation: {session.id}",
        f"\n**Project:** {session.project_name}",
        f"**Created:** {session.created_at.isoformat() if session.created_at else 'Unknown'}",
        "\n---\n"
    ]

    for msg in session.messages:
        role = "**User**" if msg.role == "user" else "**Assistant**"
        lines.append(f"\n### {role}\n")
        if msg.content:
            lines.append(msg.content)
        if msg.thinking_text:
            lines.append(f"\n*Thinking:*\n```\n{msg.thinking_text}\n```")
        if msg.tool_name:
            lines.append(f"\n*Tool: {msg.tool_name}*")
        lines.append("")

    return "\n".join(lines)


def export_to_html(session: Session) -> str:
    """Export session to HTML format"""
    lines = [
        "<!DOCTYPE html>",
        "<html><head>",
        f"<title>Conversation: {session.id}</title>",
        "<style>",
        "body { font-family: system-ui, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }",
        ".message { margin: 20px 0; padding: 15px; border-radius: 8px; }",
        ".user { background: #e3f2fd; }",
        ".assistant { background: #f5f5f5; }",
        ".role { font-weight: bold; margin-bottom: 10px; }",
        "pre { background: #263238; color: #eceff1; padding: 15px; border-radius: 4px; overflow-x: auto; }",
        "</style></head><body>",
        f"<h1>Conversation: {session.id}</h1>",
        f"<p><strong>Project:</strong> {session.project_name}</p>",
        f"<p><strong>Created:</strong> {session.created_at.isoformat() if session.created_at else 'Unknown'}</p>",
        "<hr>"
    ]

    for msg in session.messages:
        role = "User" if msg.role == "user" else "Assistant"
        lines.append(f'<div class="message {msg.role}">')
        lines.append(f'<div class="role">{role}</div>')
        if msg.content:
            lines.append(f'<div class="content">{msg.content}</div>')
        if msg.thinking_text:
            lines.append(f'<pre>{msg.thinking_text}</pre>')
        lines.append("</div>")

    lines.append("</body></html>")
    return "\n".join(lines)


def export_to_json(session: Session) -> dict:
    """Export session to JSON format"""
    return {
        "id": session.id,
        "project_name": session.project_name,
        "project_path": session.project_path,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "messages": [message_to_dict(m) for m in session.messages]
    }