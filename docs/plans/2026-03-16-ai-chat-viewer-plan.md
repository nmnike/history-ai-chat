# AI Chat History Viewer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Создать веб-приложение для просмотра истории диалогов с Claude Code и Codex CLI

**Architecture:** Форк AI-Conversation-Viewer с добавлением парсера Codex и улучшенным UI. FastAPI бэкенд парсит JSONL файлы, Jinja2 + Bootstrap фронтенд отображает в стиле мессенджера.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, Bootstrap 5, SQLite, Pygments

---

## Task 1: Клонирование и анализ базового проекта

**Files:**
- Create: `pyproject.toml`
- Create: `src/viewer/__init__.py`

**Step 1: Клонировать AI-Conversation-Viewer**

```bash
cd /tmp && git clone https://github.com/lohasle/AI-Conversation-Viewer.git reference
```

**Step 2: Проанализировать структуру**

```bash
ls -la reference/claude_viewer/
cat reference/pyproject.toml
```

**Step 3: Создать структуру проекта**

```bash
mkdir -p src/viewer/{parsers,db,templates,static/{css,js}}
mkdir -p tests
```

**Step 4: Создать pyproject.toml**

```toml
[project]
name = "claude-codex-viewer"
version = "0.1.0"
description = "Web viewer for Claude Code and Codex CLI conversation history"
requires-python = ">=3.10"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "jinja2>=3.1.0",
    "pygments>=2.17.0",
    "python-dateutil>=2.8.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
]

[project.scripts]
claude-codex-viewer = "viewer.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 5: Commit**

```bash
git add pyproject.toml src/viewer/__init__.py
git commit -m "chore: init project structure"
```

---

## Task 2: Claude Code JSONL Parser

**Files:**
- Create: `src/viewer/parsers/__init__.py`
- Create: `src/viewer/parsers/claude.py`
- Create: `tests/test_claude_parser.py`

**Step 1: Write the failing test**

```python
# tests/test_claude_parser.py
import json
from pathlib import Path
from viewer.parsers.claude import ClaudeParser

def test_parse_user_message(tmp_path):
    """Test parsing user message from Claude Code JSONL"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "user",
        "message": {"role": "user", "content": "Hello"},
        "uuid": "user-123",
        "timestamp": "2026-03-16T10:00:00.000Z",
        "sessionId": "session-abc",
        "cwd": "/test/project"
    }) + "\n")

    parser = ClaudeParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].role == "user"
    assert messages[0].content == "Hello"
    assert messages[0].session_id == "session-abc"
```

**Step 2: Run test to verify it fails**

```bash
cd /d A:\ai_dev\history_ai_chat && python -m pytest tests/test_claude_parser.py -v
```
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# src/viewer/parsers/__init__.py
from .claude import ClaudeParser

__all__ = ["ClaudeParser"]
```

```python
# src/viewer/parsers/claude.py
"""Parser for Claude Code conversation history"""
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Message:
    """Represents a single message in a conversation"""
    role: str  # user, assistant
    content: str
    uuid: str
    timestamp: datetime
    session_id: str
    project_path: str
    message_type: str = "text"  # text, thinking, tool_use, tool_result
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    thinking_text: Optional[str] = None


@dataclass
class Session:
    """Represents a conversation session"""
    id: str
    project_path: str
    project_name: str
    messages: list[Message]
    first_message: Optional[str] = None
    created_at: Optional[datetime] = None


class ClaudeParser:
    """Parse Claude Code JSONL conversation files"""

    def __init__(self, projects_path: str = None):
        import os
        self.projects_path = Path(projects_path or os.path.expanduser("~/.claude/projects"))

    def parse_session(self, session_file: Path) -> list[Message]:
        """Parse a single session JSONL file"""
        messages = []

        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                msg = self._parse_message(data)
                if msg:
                    messages.append(msg)

        return messages

    def _parse_message(self, data: dict) -> Optional[Message]:
        """Parse a single message from JSONL"""
        msg_type = data.get("type")

        if msg_type == "user":
            return self._parse_user_message(data)
        elif msg_type == "assistant":
            return self._parse_assistant_message(data)

        return None

    def _parse_user_message(self, data: dict) -> Optional[Message]:
        """Parse user message"""
        message = data.get("message", {})
        content = message.get("content", "")

        # Handle string or list content
        if isinstance(content, list):
            # Extract text from content blocks
            texts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        texts.append(f"[Tool Result: {block.get('tool_use_id', 'unknown')}]")
                else:
                    texts.append(str(block))
            content = "\n".join(texts)

        return Message(
            role="user",
            content=str(content),
            uuid=data.get("uuid", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=data.get("sessionId", ""),
            project_path=data.get("cwd", ""),
            message_type="text"
        )

    def _parse_assistant_message(self, data: dict) -> Optional[Message]:
        """Parse assistant message with support for thinking and tool_use"""
        message = data.get("message", {})
        content_blocks = message.get("content", [])

        if not isinstance(content_blocks, list):
            return Message(
                role="assistant",
                content=str(content_blocks),
                uuid=data.get("uuid", ""),
                timestamp=self._parse_timestamp(data.get("timestamp")),
                session_id=data.get("sessionId", ""),
                project_path=data.get("cwd", ""),
                message_type="text"
            )

        # Extract text, thinking, and tool_use from content blocks
        text_parts = []
        thinking_text = None
        tool_name = None
        tool_input = None
        msg_type = "text"

        for block in content_blocks:
            block_type = block.get("type", "")

            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "thinking":
                thinking_text = block.get("thinking", "")
                msg_type = "thinking"
            elif block_type == "tool_use":
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                msg_type = "tool_use"

        return Message(
            role="assistant",
            content="\n".join(text_parts) if text_parts else "",
            uuid=data.get("uuid", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=data.get("sessionId", ""),
            project_path=data.get("cwd", ""),
            message_type=msg_type,
            tool_name=tool_name,
            tool_input=tool_input,
            thinking_text=thinking_text
        )

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse timestamp from various formats"""
        if not ts:
            return None
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts / 1000)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    def get_projects(self) -> list[dict]:
        """Get list of all projects"""
        projects = []

        if not self.projects_path.exists():
            return projects

        for project_dir in self.projects_path.iterdir():
            if not project_dir.is_dir():
                continue

            sessions = list(project_dir.glob("*.jsonl"))
            if sessions:
                # Convert directory name to readable project name
                project_name = project_dir.name.replace("-", "/").replace("_", " ")
                projects.append({
                    "id": project_dir.name,
                    "name": project_name,
                    "path": str(project_dir),
                    "session_count": len(sessions)
                })

        return sorted(projects, key=lambda x: x["name"])

    def get_sessions(self, project_id: str) -> list[Session]:
        """Get all sessions for a project"""
        project_path = self.projects_path / project_id
        sessions = []

        if not project_path.exists():
            return sessions

        for session_file in project_path.glob("*.jsonl"):
            if session_file.name.startswith("agent-"):
                continue  # Skip agent sub-sessions

            messages = self.parse_session(session_file)
            if messages:
                session = Session(
                    id=session_file.stem,
                    project_path=str(project_path),
                    project_name=project_id,
                    messages=messages,
                    first_message=messages[0].content[:100] if messages else None,
                    created_at=messages[0].timestamp if messages else None
                )
                sessions.append(session)

        return sorted(sessions, key=lambda x: x.created_at or datetime.min, reverse=True)
```

**Step 4: Run test to verify it passes**

```bash
cd /d A:\ai_dev\history_ai_chat && python -m pytest tests/test_claude_parser.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add src/viewer/parsers/ tests/test_claude_parser.py
git commit -m "feat: add Claude Code JSONL parser"
```

---

## Task 3: Codex CLI JSONL Parser

**Files:**
- Create: `src/viewer/parsers/codex.py`
- Create: `tests/test_codex_parser.py`

**Step 1: Write the failing test**

```python
# tests/test_codex_parser.py
import json
from pathlib import Path
from viewer.parsers.codex import CodexParser

def test_parse_codex_session(tmp_path):
    """Test parsing Codex CLI rollout JSONL"""
    session_file = tmp_path / "rollout-test.jsonl"
    session_file.write_text(json.dumps({
        "type": "message",
        "role": "user",
        "content": "Write a hello world",
        "timestamp": "2026-03-16T10:00:00Z"
    }) + "\n")

    parser = CodexParser()
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].role == "user"
```

**Step 2: Run test to verify it fails**

```bash
cd /d A:\ai_dev\history_ai_chat && python -m pytest tests/test_codex_parser.py -v
```
Expected: FAIL

**Step 3: Write implementation**

```python
# src/viewer/parsers/codex.py
"""Parser for OpenAI Codex CLI conversation history"""
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from .claude import Message, Session


class CodexParser:
    """Parse Codex CLI rollout JSONL files"""

    def __init__(self, sessions_path: str = None):
        import os
        self.sessions_path = Path(sessions_path or os.path.expanduser("~/.codex/sessions"))

    def parse_session(self, session_file: Path) -> list[Message]:
        """Parse a Codex rollout JSONL file"""
        messages = []

        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                msg = self._parse_message(data, session_file)
                if msg:
                    messages.append(msg)

        return messages

    def _parse_message(self, data: dict, session_file: Path) -> Optional[Message]:
        """Parse a single message from Codex JSONL"""
        msg_type = data.get("type", "")

        if msg_type == "message":
            return self._parse_chat_message(data, session_file)
        elif msg_type == "function_call":
            return self._parse_tool_use(data, session_file)

        return None

    def _parse_chat_message(self, data: dict, session_file: Path) -> Optional[Message]:
        """Parse chat message"""
        role = data.get("role", "")
        content = data.get("content", "")

        if isinstance(content, list):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
            content = "\n".join(texts)

        return Message(
            role=role,
            content=str(content),
            uuid=data.get("id", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=session_file.stem,
            project_path=self._extract_project_from_path(session_file),
            message_type="text"
        )

    def _parse_tool_use(self, data: dict, session_file: Path) -> Optional[Message]:
        """Parse function/tool call"""
        return Message(
            role="assistant",
            content="",
            uuid=data.get("id", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=session_file.stem,
            project_path=self._extract_project_from_path(session_file),
            message_type="tool_use",
            tool_name=data.get("name", ""),
            tool_input=data.get("arguments", {})
        )

    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse timestamp"""
        if not ts:
            return None
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                pass
        return None

    def _extract_project_from_path(self, session_file: Path) -> str:
        """Extract project context from session file path"""
        # Session path: ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl
        parts = session_file.parts
        if len(parts) >= 4:
            return f"codex-{parts[-4]}-{parts[-3]}-{parts[-2]}"
        return "codex"

    def get_sessions(self) -> list[Session]:
        """Get all Codex sessions organized by date"""
        sessions = []

        if not self.sessions_path.exists():
            return sessions

        # Walk through YYYY/MM/DD structure
        for session_file in self.sessions_path.glob("**/rollout-*.jsonl"):
            messages = self.parse_session(session_file)
            if messages:
                session = Session(
                    id=session_file.stem,
                    project_path=str(session_file.parent),
                    project_name=self._extract_project_from_path(session_file),
                    messages=messages,
                    first_message=messages[0].content[:100] if messages else None,
                    created_at=messages[0].timestamp if messages else None
                )
                sessions.append(session)

        return sorted(sessions, key=lambda x: x.created_at or datetime.min, reverse=True)
```

**Step 4: Update parsers/__init__.py**

```python
from .claude import ClaudeParser, Message, Session
from .codex import CodexParser

__all__ = ["ClaudeParser", "CodexParser", "Message", "Session"]
```

**Step 5: Run tests**

```bash
cd /d A:\ai_dev\history_ai_chat && python -m pytest tests/ -v
```
Expected: All PASS

**Step 6: Commit**

```bash
git add src/viewer/parsers/ tests/test_codex_parser.py
git commit -m "feat: add Codex CLI JSONL parser"
```

---

## Task 4: Database Layer (SQLite Cache)

**Files:**
- Create: `src/viewer/db/__init__.py`
- Create: `src/viewer/db/cache.py`
- Create: `tests/test_cache.py`

**Step 1: Write the failing test**

```python
# tests/test_cache.py
from viewer.db.cache import CacheDB

def test_cache_session(tmp_path):
    """Test caching a session"""
    db = CacheDB(tmp_path / "cache.db")

    session_data = {
        "id": "test-session",
        "project": "test-project",
        "preview": "Hello world"
    }
    db.cache_session(session_data)

    cached = db.get_session("test-session")
    assert cached["project"] == "test-project"
```

**Step 2: Run test to verify it fails**

```bash
cd /d A:\ai_dev\history_ai_chat && python -m pytest tests/test_cache.py -v
```

**Step 3: Write implementation**

```python
# src/viewer/db/cache.py
"""SQLite cache for session metadata"""
import sqlite3
from pathlib import Path
from datetime import datetime
import json


class CacheDB:
    """SQLite-based cache for sessions and metadata"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    preview TEXT,
                    message_count INTEGER DEFAULT 0,
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
                CREATE INDEX IF NOT EXISTS idx_sessions_cached ON sessions(cached_at);

                CREATE TABLE IF NOT EXISTS favorites (
                    session_id TEXT PRIMARY KEY,
                    tags TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    def cache_session(self, session: dict):
        """Cache session metadata"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO sessions (id, project, platform, preview, message_count)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session["id"],
                session.get("project", ""),
                session.get("platform", "claude"),
                session.get("preview", "")[:200],
                session.get("message_count", 0)
            ))

    def get_session(self, session_id: str) -> dict | None:
        """Get cached session"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM sessions WHERE id = ?", (session_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_cached_sessions(self, project: str = None) -> list[dict]:
        """Get all cached sessions, optionally filtered by project"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if project:
                cursor = conn.execute(
                    "SELECT * FROM sessions WHERE project = ? ORDER BY cached_at DESC",
                    (project,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM sessions ORDER BY cached_at DESC"
                )
            return [dict(row) for row in cursor.fetchall()]

    def add_favorite(self, session_id: str, tags: list[str] = None, notes: str = ""):
        """Add session to favorites"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO favorites (session_id, tags, notes)
                VALUES (?, ?, ?)
            """, (session_id, json.dumps(tags or []), notes))

    def get_favorites(self) -> list[dict]:
        """Get all favorites"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT s.*, f.tags, f.notes
                FROM sessions s
                JOIN favorites f ON s.id = f.session_id
                ORDER BY f.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
```

**Step 4: Run test**

```bash
cd /d A:\ai_dev\history_ai_chat && python -m pytest tests/test_cache.py -v
```

**Step 5: Commit**

```bash
git add src/viewer/db/ tests/test_cache.py
git commit -m "feat: add SQLite cache layer"
```

---

## Task 5: FastAPI Application

**Files:**
- Create: `src/viewer/main.py`
- Create: `src/viewer/cli.py`

**Step 1: Write main.py**

```python
# src/viewer/main.py
"""FastAPI application for AI Chat History Viewer"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path
from typing import Optional
import os

from .parsers import ClaudeParser, CodexParser, Session
from .db.cache import CacheDB

app = FastAPI(title="Claude & Codex Chat Viewer")

# Paths
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Static files and templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Parsers and cache (initialized on startup)
claude_parser: Optional[ClaudeParser] = None
codex_parser: Optional[CodexParser] = None
cache_db: Optional[CacheDB] = None


@app.on_event("startup")
async def startup():
    global claude_parser, codex_parser, cache_db

    claude_path = os.environ.get("CLAUDE_PROJECTS_PATH")
    codex_path = os.environ.get("CODEX_SESSIONS_PATH")

    claude_parser = ClaudeParser(claude_path)
    codex_parser = CodexParser(codex_path)

    cache_dir = Path.home() / ".claude-codex-viewer"
    cache_db = CacheDB(cache_dir / "cache.db")


# API Routes

@app.get("/", response_class=HTMLResponse)
async def dashboard(request):
    """Dashboard page"""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "title": "AI Chat History Viewer"
    })


@app.get("/api/projects")
async def get_projects():
    """Get all projects from both platforms"""
    claude_projects = claude_parser.get_projects()

    # Add platform marker
    for p in claude_projects:
        p["platform"] = "claude"

    # Codex sessions grouped by date
    codex_sessions = codex_parser.get_sessions()
    codex_projects = {}
    for s in codex_sessions:
        proj = s.project_name
        if proj not in codex_projects:
            codex_projects[proj] = {"id": proj, "name": proj, "session_count": 0, "platform": "codex"}
        codex_projects[proj]["session_count"] += 1

    return {
        "projects": claude_projects + list(codex_projects.values())
    }


@app.get("/api/sessions/{project_id}")
async def get_sessions(project_id: str, platform: str = Query(default="claude")):
    """Get sessions for a project"""
    if platform == "claude":
        sessions = claude_parser.get_sessions(project_id)
    else:
        sessions = codex_parser.get_sessions()
        sessions = [s for s in sessions if s.project_name == project_id]

    return {
        "project_id": project_id,
        "sessions": [
            {
                "id": s.id,
                "preview": s.first_message,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "message_count": len(s.messages)
            }
            for s in sessions
        ]
    }


@app.get("/api/conversation/{session_id}")
async def get_conversation(
    session_id: str,
    project_id: str = Query(default=""),
    platform: str = Query(default="claude")
):
    """Get full conversation for a session"""
    if platform == "claude":
        project_path = claude_parser.projects_path / project_id
        session_file = project_path / f"{session_id}.jsonl"
        if not session_file.exists():
            raise HTTPException(404, "Session not found")
        messages = claude_parser.parse_session(session_file)
    else:
        sessions = codex_parser.get_sessions()
        session = next((s for s in sessions if s.id == session_id), None)
        if not session:
            raise HTTPException(404, "Session not found")
        messages = session.messages

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "type": m.message_type,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "tool_name": m.tool_name,
                "tool_input": m.tool_input,
                "thinking": m.thinking_text
            }
            for m in messages
        ]
    }


@app.get("/api/search")
async def search(q: str = Query(default=""), platform: str = Query(default="all")):
    """Global search across all sessions"""
    results = []

    if platform in ("all", "claude"):
        for project in claude_parser.get_projects():
            for session in claude_parser.get_sessions(project["id"]):
                for msg in session.messages:
                    if q.lower() in msg.content.lower():
                        results.append({
                            "session_id": session.id,
                            "project": project["name"],
                            "platform": "claude",
                            "preview": msg.content[:200],
                            "match": msg.content
                        })
                        break

    if platform in ("all", "codex"):
        for session in codex_parser.get_sessions():
            for msg in session.messages:
                if q.lower() in msg.content.lower():
                    results.append({
                        "session_id": session.id,
                        "project": session.project_name,
                        "platform": "codex",
                        "preview": msg.content[:200],
                        "match": msg.content
                    })
                    break

    return {"query": q, "results": results[:50]}


@app.get("/api/export/{session_id}")
async def export_session(
    session_id: str,
    project_id: str = Query(default=""),
    platform: str = Query(default="claude"),
    format: str = Query(default="md", regex="^(md|html|json)$")
):
    """Export session in various formats"""
    # Get conversation
    if platform == "claude":
        project_path = claude_parser.projects_path / project_id
        session_file = project_path / f"{session_id}.jsonl"
        messages = claude_parser.parse_session(session_file)
    else:
        sessions = codex_parser.get_sessions()
        session = next((s for s in sessions if s.id == session_id), None)
        messages = session.messages if session else []

    if format == "json":
        return {"messages": [
            {"role": m.role, "content": m.content, "type": m.message_type}
            for m in messages
        ]}

    elif format == "md":
        lines = [f"# Session: {session_id}\n"]
        for m in messages:
            lines.append(f"\n## {m.role.title()}\n")
            if m.thinking_text:
                lines.append(f"> Thinking: {m.thinking_text}\n")
            if m.tool_name:
                lines.append(f"**Tool:** {m.tool_name}\n")
            lines.append(f"{m.content}\n")
        return {"content": "\n".join(lines)}

    elif format == "html":
        html = f"<html><head><title>{session_id}</title></head><body>"
        for m in messages:
            html += f"<div class='message {m.role}'><b>{m.role}:</b> {m.content}</div>"
        html += "</body></html>"
        return {"content": html}
```

**Step 2: Write cli.py**

```python
# src/viewer/cli.py
"""CLI entry point"""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="AI Chat History Viewer")
    parser.add_argument("--port", type=int, default=6300, help="Port to run on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind")
    parser.add_argument(
        "--claude-path",
        type=str,
        help="Path to Claude projects directory"
    )
    parser.add_argument(
        "--codex-path",
        type=str,
        help="Path to Codex sessions directory"
    )

    args = parser.parse_args()

    import os
    if args.claude_path:
        os.environ["CLAUDE_PROJECTS_PATH"] = args.claude_path
    if args.codex_path:
        os.environ["CODEX_SESSIONS_PATH"] = args.codex_path

    print(f"Starting AI Chat History Viewer on http://{args.host}:{args.port}")
    uvicorn.run("viewer.main:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
```

**Step 3: Test startup**

```bash
cd /d A:\ai_dev\history_ai_chat && python -c "from viewer.main import app; print('OK')"
```

**Step 4: Commit**

```bash
git add src/viewer/main.py src/viewer/cli.py
git commit -m "feat: add FastAPI application and CLI"
```

---

## Task 6: Jinja2 Templates

**Files:**
- Create: `src/viewer/templates/base.html`
- Create: `src/viewer/templates/dashboard.html`
- Create: `src/viewer/templates/project.html`
- Create: `src/viewer/templates/conversation.html`

**Step 1: Create base.html**

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}AI Chat Viewer{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="/static/css/theme.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand" href="/">AI Chat Viewer</a>
            <div class="navbar-nav">
                <a class="nav-link" href="#" id="theme-toggle">
                    <span id="theme-icon">🌙</span>
                </a>
            </div>
        </div>
    </nav>
    <main class="container py-4">
        {% block content %}{% endblock %}
    </main>
    <script src="/static/js/app.js"></script>
</body>
</html>
```

**Step 2: Create dashboard.html**

```html
{% extends "base.html" %}
{% block content %}
<div class="row mb-4">
    <div class="col-md-4">
        <div class="card stat-card">
            <div class="card-body">
                <h3 id="session-count">--</h3>
                <small class="text-muted">Sessions</small>
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card stat-card">
            <div class="card-body">
                <h3 id="project-count">--</h3>
                <small class="text-muted">Projects</small>
            </div>
        </div>
    </div>
</div>

<div class="mb-4">
    <input type="search" class="form-control" id="global-search"
           placeholder="Search all conversations...">
</div>

<h4>Projects</h4>
<div id="projects-list" class="list-group">
    <div class="text-center py-4">Loading...</div>
</div>
{% endblock %}

{% block scripts %}
<script>
document.addEventListener('DOMContentLoaded', async () => {
    const response = await fetch('/api/projects');
    const data = await response.json();

    document.getElementById('project-count').textContent = data.projects.length;

    const list = document.getElementById('projects-list');
    list.innerHTML = data.projects.map(p => `
        <a href="/project/${p.id}?platform=${p.platform}"
           class="list-group-item list-group-item-action d-flex justify-content-between">
            <span>${p.name}</span>
            <span class="badge bg-secondary">${p.session_count} sessions</span>
        </a>
    `).join('');
});
</script>
{% endblock %}
```

**Step 3: Create conversation.html**

```html
{% extends "base.html" %}
{% block content %}
<div class="conversation-header mb-4">
    <a href="/" class="btn btn-outline-secondary btn-sm">&larr; Back</a>
    <h4 class="mt-2">{{ session_id }}</h4>
    <div class="btn-group">
        <button class="btn btn-outline-primary btn-sm" onclick="exportAs('md')">Export MD</button>
        <button class="btn btn-outline-primary btn-sm" onclick="exportAs('json')">Export JSON</button>
    </div>
</div>

<div id="messages-container" class="messages">
    <div class="text-center py-4">Loading...</div>
</div>
{% endblock %}

{% block scripts %}
<script>
const sessionId = '{{ session_id }}';
const projectId = '{{ project_id }}';
const platform = '{{ platform }}';

document.addEventListener('DOMContentLoaded', async () => {
    const response = await fetch(
        `/api/conversation/${sessionId}?project_id=${projectId}&platform=${platform}`
    );
    const data = await response.json();

    const container = document.getElementById('messages-container');
    container.innerHTML = data.messages.map(m => {
        if (m.role === 'user') {
            return `
                <div class="message user-message">
                    <div class="message-header">👤 You</div>
                    <div class="message-content">${escapeHtml(m.content)}</div>
                </div>
            `;
        } else {
            let html = `<div class="message assistant-message">`;
            html += `<div class="message-header">🤖 ${platform === 'claude' ? 'Claude' : 'Codex'}</div>`;

            if (m.thinking) {
                html += `
                    <div class="thinking-block collapsed">
                        <div class="thinking-header" onclick="this.parentElement.classList.toggle('collapsed')">
                            💭 Thinking...
                        </div>
                        <div class="thinking-content">${escapeHtml(m.thinking)}</div>
                    </div>
                `;
            }

            if (m.type === 'tool_use') {
                html += `
                    <div class="tool-block">
                        <div class="tool-header">🔧 ${m.tool_name}</div>
                        <pre class="tool-input">${JSON.stringify(m.tool_input, null, 2)}</pre>
                    </div>
                `;
            }

            html += `<div class="message-content">${escapeHtml(m.content)}</div>`;
            html += `</div>`;
            return html;
        }
    }).join('');
});

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function exportAs(format) {
    const response = await fetch(
        `/api/export/${sessionId}?project_id=${projectId}&platform=${platform}&format=${format}`
    );
    const data = await response.json();
    const blob = new Blob([data.content || JSON.stringify(data)], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${sessionId}.${format}`;
    a.click();
}
</script>
{% endblock %}
```

**Step 4: Commit**

```bash
git add src/viewer/templates/
git commit -m "feat: add Jinja2 templates for dashboard and conversation"
```

---

## Task 7: CSS Styling (Dark/Light Theme)

**Files:**
- Create: `src/viewer/static/css/theme.css`
- Create: `src/viewer/static/js/app.js`

**Step 1: Create theme.css**

```css
/* src/viewer/static/css/theme.css */

:root {
    --bg-primary: #1e1e2e;
    --bg-secondary: #313244;
    --bg-tertiary: #45475a;
    --text-primary: #cdd6f4;
    --text-secondary: #a6adc8;
    --accent: #a78bfa;
    --user-bg: #313244;
    --assistant-bg: #45475a;
    --thinking-bg: #58372d;
    --tool-bg: #2d4a3e;
    --border-color: #45475a;
}

[data-theme="light"] {
    --bg-primary: #ffffff;
    --bg-secondary: #f5f5f5;
    --bg-tertiary: #e0e0e0;
    --text-primary: #1e1e2e;
    --text-secondary: #6c757d;
    --accent: #7c3aed;
    --user-bg: #e3f2fd;
    --assistant-bg: #f5f5f5;
    --thinking-bg: #fff3e0;
    --tool-bg: #e8f5e9;
    --border-color: #dee2e6;
}

body {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    font-family: system-ui, -apple-system, sans-serif;
}

.navbar {
    background-color: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
}

.card, .list-group-item {
    background-color: var(--bg-secondary);
    border-color: var(--border-color);
}

.stat-card h3 {
    color: var(--accent);
    margin: 0;
}

/* Messages */
.messages {
    max-width: 900px;
    margin: 0 auto;
}

.message {
    margin-bottom: 1rem;
    padding: 1rem;
    border-radius: 12px;
}

.user-message {
    background-color: var(--user-bg);
    margin-left: 2rem;
}

.assistant-message {
    background-color: var(--assistant-bg);
    margin-right: 2rem;
}

.message-header {
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-bottom: 0.5rem;
}

.message-content {
    white-space: pre-wrap;
    word-wrap: break-word;
}

/* Thinking block */
.thinking-block {
    background-color: var(--thinking-bg);
    border-radius: 8px;
    margin-bottom: 0.5rem;
    overflow: hidden;
}

.thinking-header {
    padding: 0.5rem 1rem;
    cursor: pointer;
    font-weight: 500;
}

.thinking-content {
    padding: 0 1rem 1rem;
    font-style: italic;
    color: var(--text-secondary);
}

.thinking-block.collapsed .thinking-content {
    display: none;
}

/* Tool block */
.tool-block {
    background-color: var(--tool-bg);
    border-radius: 8px;
    margin-bottom: 0.5rem;
    overflow: hidden;
}

.tool-header {
    padding: 0.5rem 1rem;
    font-weight: 500;
    font-size: 0.9rem;
}

.tool-input {
    margin: 0;
    padding: 0.5rem 1rem;
    font-size: 0.8rem;
    background: transparent;
    color: var(--text-primary);
    white-space: pre-wrap;
}

/* Forms */
.form-control {
    background-color: var(--bg-tertiary);
    border-color: var(--border-color);
    color: var(--text-primary);
}

.form-control:focus {
    background-color: var(--bg-tertiary);
    border-color: var(--accent);
    color: var(--text-primary);
}

/* Links */
a {
    color: var(--accent);
}

.btn-outline-secondary {
    border-color: var(--border-color);
    color: var(--text-secondary);
}

.btn-outline-secondary:hover {
    background-color: var(--bg-tertiary);
    border-color: var(--border-color);
    color: var(--text-primary);
}

.btn-outline-primary {
    border-color: var(--accent);
    color: var(--accent);
}

.btn-outline-primary:hover {
    background-color: var(--accent);
    color: white;
}
```

**Step 2: Create app.js**

```javascript
// src/viewer/static/js/app.js

// Theme toggle
function initTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    updateThemeIcon(saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    const toggle = document.getElementById('theme-toggle');
    if (toggle) {
        toggle.addEventListener('click', toggleTheme);
    }
});

// Global search
const searchInput = document.getElementById('global-search');
if (searchInput) {
    let debounce;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
            if (e.target.value.length > 2) {
                performSearch(e.target.value);
            }
        }, 300);
    });
}

async function performSearch(query) {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const data = await response.json();
    console.log('Search results:', data.results);
    // TODO: Display search results
}
```

**Step 3: Commit**

```bash
git add src/viewer/static/
git commit -m "feat: add CSS theme and JavaScript app logic"
```

---

## Task 8: Add HTML routes for pages

**Files:**
- Modify: `src/viewer/main.py`

**Step 1: Add page routes**

Add to main.py after existing routes:

```python
@app.get("/project/{project_id}", response_class=HTMLResponse)
async def project_page(request, project_id: str, platform: str = Query(default="claude")):
    """Project sessions page"""
    return templates.TemplateResponse("project.html", {
        "request": request,
        "project_id": project_id,
        "platform": platform
    })


@app.get("/conversation/{session_id}", response_class=HTMLResponse)
async def conversation_page(
    request,
    session_id: str,
    project_id: str = Query(default=""),
    platform: str = Query(default="claude")
):
    """Conversation view page"""
    return templates.TemplateResponse("conversation.html", {
        "request": request,
        "session_id": session_id,
        "project_id": project_id,
        "platform": platform
    })
```

**Step 2: Create project.html**

```html
{% extends "base.html" %}
{% block content %}
<div class="mb-3">
    <a href="/" class="btn btn-outline-secondary btn-sm">&larr; Back to projects</a>
</div>

<h4 class="mb-4">{{ project_id }}</h4>

<div id="sessions-list" class="list-group">
    <div class="text-center py-4">Loading...</div>
</div>
{% endblock %}

{% block scripts %}
<script>
document.addEventListener('DOMContentLoaded', async () => {
    const response = await fetch('/api/sessions/{{ project_id }}?platform={{ platform }}');
    const data = await response.json();

    const list = document.getElementById('sessions-list');
    if (data.sessions.length === 0) {
        list.innerHTML = '<div class="text-center py-4 text-muted">No sessions found</div>';
        return;
    }

    list.innerHTML = data.sessions.map(s => `
        <a href="/conversation/${s.id}?project_id={{ project_id }}&platform={{ platform }}"
           class="list-group-item list-group-item-action">
            <div class="d-flex justify-content-between">
                <span class="text-truncate" style="max-width: 60%">${s.preview || 'No preview'}</span>
                <small class="text-muted">${s.message_count} messages</small>
            </div>
            <small class="text-muted">${s.created_at || ''}</small>
        </a>
    `).join('');
});
</script>
{% endblock %}
```

**Step 3: Commit**

```bash
git add src/viewer/main.py src/viewer/templates/project.html
git commit -m "feat: add project and conversation page routes"
```

---

## Task 9: Integration Testing

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

```python
# tests/test_integration.py
from fastapi.testclient import TestClient
from viewer.main import app

client = TestClient(app)


def test_dashboard_loads():
    """Test that dashboard page loads"""
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Chat Viewer" in response.text


def test_api_projects():
    """Test projects API endpoint"""
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert "projects" in data
    assert isinstance(data["projects"], list)


def test_api_search():
    """Test search API endpoint"""
    response = client.get("/api/search?q=test")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
```

**Step 2: Run tests**

```bash
cd /d A:\ai_dev\history_ai_chat && python -m pytest tests/ -v
```

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration tests"
```

---

## Task 10: Final Setup and Documentation

**Files:**
- Create: `README.md`
- Create: `requirements.txt`

**Step 1: Create README.md**

```markdown
# Claude & Codex Chat History Viewer

Web application for viewing conversation history from Claude Code and OpenAI Codex CLI.

## Features

- Multi-platform support (Claude Code + Codex CLI)
- Global search across all conversations
- Beautiful chat-style UI with dark/light themes
- Export to Markdown, HTML, or JSON
- Thinking blocks visualization
- Tool use formatting

## Installation

```bash
pip install claude-codex-viewer
```

## Usage

```bash
# Start with defaults
claude-codex-viewer

# Custom port
claude-codex-viewer --port 8080

# Custom paths
claude-codex-viewer --claude-path /path/to/.claude/projects --codex-path /path/to/.codex/sessions
```

Open http://localhost:6300 in your browser.

## Data Locations

| Platform | Default Path |
|----------|--------------|
| Claude Code | `~/.claude/projects/` |
| Codex CLI | `~/.codex/sessions/` |

## License

MIT
```

**Step 2: Create requirements.txt**

```
fastapi>=0.109.0
uvicorn>=0.27.0
jinja2>=3.1.0
pygments>=2.17.0
python-dateutil>=2.8.0
```

**Step 3: Final commit**

```bash
git add README.md requirements.txt
git commit -m "docs: add README and requirements"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Project structure | `pyproject.toml` |
| 2 | Claude parser | `src/viewer/parsers/claude.py` |
| 3 | Codex parser | `src/viewer/parsers/codex.py` |
| 4 | Database cache | `src/viewer/db/cache.py` |
| 5 | FastAPI app | `src/viewer/main.py`, `cli.py` |
| 6 | Templates | `src/viewer/templates/*.html` |
| 7 | CSS/JS | `src/viewer/static/*` |
| 8 | Page routes | `main.py` updates |
| 9 | Tests | `tests/test_*.py` |
| 10 | Documentation | `README.md` |