# Token Statistics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add token usage statistics (input/output/cache) to conversation viewer UI on both dashboard and conversation pages.

**Architecture:** Extend Message dataclass with token fields, extract usage data from JSONL during parsing, aggregate tokens in API responses, display with breakdown popover in UI.

**Tech Stack:** Python dataclasses, FastAPI, Jinja2 templates, Bootstrap 5, vanilla JS

---

### Task 1: Extend Message Dataclass with Token Fields

**Files:**
- Modify: `src/viewer/parsers/claude.py:10-22`

**Step 1: Add token fields to Message dataclass**

```python
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
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
```

**Step 2: Run tests to verify no breakage**

Run: `cd A:/ai_dev/history-ai-chat && python -m pytest tests/ -v`
Expected: PASS (all existing tests should still work)

**Step 3: Commit**

```bash
git add src/viewer/parsers/claude.py
git commit -m "feat: add token fields to Message dataclass"
```

---

### Task 2: Extract Token Usage from Assistant Messages

**Files:**
- Modify: `src/viewer/parsers/claude.py:122-169`

**Step 1: Update _parse_assistant_message to extract usage**

Modify the method to extract token usage from `data["message"]["usage"]`:

```python
def _parse_assistant_message(self, data: dict) -> Optional[Message]:
    """Parse assistant message with support for thinking and tool_use"""
    message = data.get("message", {})
    content_blocks = message.get("content", [])

    # Extract usage data
    usage = message.get("usage", {})
    input_tokens = usage.get("input_tokens", 0) or 0
    output_tokens = usage.get("output_tokens", 0) or 0
    cache_read_tokens = usage.get("cache_read_input_tokens", 0) or 0
    cache_creation_tokens = usage.get("cache_creation_input_tokens", 0) or 0

    if not isinstance(content_blocks, list):
        return Message(
            role="assistant",
            content=str(content_blocks),
            uuid=data.get("uuid", ""),
            timestamp=self._parse_timestamp(data.get("timestamp")),
            session_id=data.get("sessionId", ""),
            project_path=data.get("cwd", ""),
            message_type="text",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens
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
        thinking_text=thinking_text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens
    )
```

**Step 2: Verify parsing works with real data**

Run: `cd A:/ai_dev/history-ai-chat && python -c "
from src.viewer.parsers import ClaudeParser
from pathlib import Path
import os

parser = ClaudeParser()
projects = parser.get_projects()
if projects:
    sessions = parser.get_sessions(projects[0]['id'])
    if sessions:
        for msg in sessions[0].messages[:5]:
            if msg.input_tokens > 0 or msg.output_tokens > 0:
                print(f'input={msg.input_tokens}, output={msg.output_tokens}, cache_read={msg.cache_read_tokens}')
"`
Expected: Shows token values for some messages

**Step 3: Commit**

```bash
git add src/viewer/parsers/claude.py
git commit -m "feat: extract token usage from assistant messages in JSONL"
```

---

### Task 3: Add Token Fields to API Response

**Files:**
- Modify: `src/viewer/main.py:59-72`

**Step 1: Update message_to_dict to include tokens**

```python
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
        "thinking_text": msg.thinking_text,
        "input_tokens": msg.input_tokens,
        "output_tokens": msg.output_tokens,
        "cache_read_tokens": msg.cache_read_tokens,
        "cache_creation_tokens": msg.cache_creation_tokens
    }
```

**Step 2: Verify API returns tokens**

Run: `cd A:/ai_dev/history-ai-chat && python -c "
import requests
import time
import subprocess
import sys

# Start server in background
proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'viewer.main:app', '--port', '8899'],
                       cwd='A:/ai_dev/history-ai-chat/src')
time.sleep(2)

try:
    # Get projects
    r = requests.get('http://localhost:8899/api/projects?date=all')
    projects = r.json().get('projects', [])
    if projects:
        # Get sessions
        r = requests.get(f'http://localhost:8899/api/sessions/{projects[0][\"id\"]}?platform=claude&date=all')
        sessions = r.json().get('sessions', [])
        if sessions:
            # Get conversation
            r = requests.get(f'http://localhost:8899/api/conversation/{sessions[0][\"id\"]}?project_id={projects[0][\"id\"]}&platform=claude')
            messages = r.json().get('messages', [])
            for msg in messages[:3]:
                if msg.get('input_tokens', 0) > 0:
                    print(f'Tokens: in={msg[\"input_tokens\"]}, out={msg[\"output_tokens\"]}')
                    break
finally:
    proc.terminate()
"`
Expected: Shows token data from API

**Step 3: Commit**

```bash
git add src/viewer/main.py
git commit -m "feat: include token fields in conversation API response"
```

---

### Task 4: Add Token Statistics to Conversation Page UI

**Files:**
- Modify: `src/viewer/templates/conversation.html:351-385`

**Step 1: Add tokens to updateSessionStats function**

Replace the `updateSessionStats` function:

```javascript
function updateSessionStats(messages) {
    const stats = {
        user: 0,
        assistant: 0,
        tools: {},
        tokens: {
            input: 0,
            output: 0,
            cache_read: 0,
            cache_creation: 0
        }
    };

    messages.forEach(msg => {
        if (msg.role === 'user') {
            stats.user++;
        } else if (msg.role === 'assistant') {
            stats.assistant++;
        }
        if (msg.tool_name) {
            stats.tools[msg.tool_name] = (stats.tools[msg.tool_name] || 0) + 1;
        }
        // Accumulate tokens
        stats.tokens.input += msg.input_tokens || 0;
        stats.tokens.output += msg.output_tokens || 0;
        stats.tokens.cache_read += msg.cache_read_tokens || 0;
        stats.tokens.cache_creation += msg.cache_creation_tokens || 0;
    });

    const container = document.getElementById('session-stats');
    if (!container) return;

    let html = `<span class="badge bg-primary me-1 stat-badge" data-filter="user" onclick="toggleFilter('user')"><i class="bi bi-person"></i> ${stats.user}</span>`;
    html += `<span class="badge bg-secondary me-1 stat-badge" data-filter="assistant" onclick="toggleFilter('assistant')"><i class="bi bi-robot"></i> ${stats.assistant}</span>`;

    const toolNames = Object.keys(stats.tools);
    if (toolNames.length > 0) {
        toolNames
            .sort((a, b) => stats.tools[b] - stats.tools[a])
            .forEach(tool => {
                html += `<span class="badge bg-info text-dark me-1 stat-badge" data-filter="${tool}" onclick="toggleFilter('${tool}')">${tool}: ${stats.tools[tool]}</span>`;
            });
    }

    // Add tokens badge with breakdown
    const totalTokens = stats.tokens.input + stats.tokens.output + stats.tokens.cache_read + stats.tokens.cache_creation;
    if (totalTokens > 0) {
        const inputK = formatTokens(stats.tokens.input);
        const outputK = formatTokens(stats.tokens.output);
        html += `<span class="badge bg-success me-1" style="cursor: pointer;" onclick="toggleTokenBreakdown()" title="Click for details">
            <i class="bi bi-cpu"></i> ${inputK} in / ${outputK} out
        </span>`;
        html += `<span id="token-breakdown" class="badge bg-success me-1" style="display: none;">
            <div class="text-start" style="font-size: 0.75rem; line-height: 1.4;">
                <div>Input: ${stats.tokens.input.toLocaleString()}</div>
                <div>Output: ${stats.tokens.output.toLocaleString()}</div>
                <div>Cache Read: ${stats.tokens.cache_read.toLocaleString()}</div>
                <div>Cache Create: ${stats.tokens.cache_creation.toLocaleString()}</div>
                <hr class="my-1" style="border-color: rgba(255,255,255,0.3);">
                <div><strong>Total: ${totalTokens.toLocaleString()}</strong></div>
            </div>
        </span>`;
    }

    container.innerHTML = html;
}

function formatTokens(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toString();
}

function toggleTokenBreakdown() {
    const el = document.getElementById('token-breakdown');
    if (el) {
        el.style.display = el.style.display === 'none' ? '' : 'none';
    }
}
```

**Step 2: Test conversation page shows tokens**

Manual test: Open a conversation in browser, verify token badge appears with breakdown.

**Step 3: Commit**

```bash
git add src/viewer/templates/conversation.html
git commit -m "feat: add token statistics to conversation page UI"
```

---

### Task 5: Add Aggregate Token Stats to Projects API

**Files:**
- Modify: `src/viewer/main.py:118-195`

**Step 1: Add token aggregation to list_projects endpoint**

Update the `list_projects` function to aggregate tokens per project:

```python
@app.get("/api/projects")
async def list_projects(date: str = Query(default="today")):
    """List all projects from both platforms with optional date filter"""
    from datetime import datetime, date as date_type, timedelta

    projects = []

    # Parse date filter
    filter_mode = "all"
    filter_date = None
    filter_date_start = None

    if date == "today":
        filter_mode = "single"
        filter_date = date_type.today()
    elif date == "yesterday":
        filter_mode = "single"
        filter_date = date_type.today() - timedelta(days=1)
    elif date == "week":
        filter_mode = "range"
        filter_date_start = date_type.today() - timedelta(days=7)
    elif date and date != "all":
        try:
            filter_mode = "single"
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            filter_mode = "all"

    def matches_date(session_created_at) -> bool:
        """Check if session date matches the filter"""
        if filter_mode == "all":
            return True
        if not session_created_at:
            return False

        session_date = session_created_at.date() if hasattr(session_created_at, 'date') else session_created_at
        if hasattr(session_date, 'date'):
            session_date = session_date.date()

        if filter_mode == "single":
            return session_date == filter_date
        elif filter_mode == "range":
            return session_date >= filter_date_start
        return True

    # Claude projects
    for project in claude_parser.get_projects():
        sessions = [s for s in claude_parser.get_sessions(project["id"]) if matches_date(s.created_at)]
        session_count = len(sessions)

        # Aggregate tokens
        total_input = sum(
            msg.input_tokens
            for s in sessions
            for msg in s.messages
        )
        total_output = sum(
            msg.output_tokens
            for s in sessions
            for msg in s.messages
        )
        total_cache_read = sum(
            msg.cache_read_tokens
            for s in sessions
            for msg in s.messages
        )
        total_cache_creation = sum(
            msg.cache_creation_tokens
            for s in sessions
            for msg in s.messages
        )

        if session_count > 0 or filter_mode == "all":
            projects.append({
                **project,
                "session_count": session_count,
                "platform": "claude",
                "total_input_tokens": total_input,
                "total_output_tokens": total_output,
                "total_cache_read_tokens": total_cache_read,
                "total_cache_creation_tokens": total_cache_creation
            })

    # Codex sessions grouped by project
    codex_sessions = codex_parser.get_sessions()
    codex_projects = {}
    for session in codex_sessions:
        if not matches_date(session.created_at):
            continue
        project_name = session.project_name
        if project_name not in codex_projects:
            codex_projects[project_name] = {
                "id": project_name,
                "name": project_name,
                "path": session.project_path,
                "session_count": 0,
                "platform": "codex",
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "total_cache_read_tokens": 0,
                "total_cache_creation_tokens": 0
            }

        # Aggregate tokens for codex session
        codex_projects[project_name]["session_count"] += 1
        codex_projects[project_name]["total_input_tokens"] += sum(
            msg.input_tokens for msg in session.messages
        )
        codex_projects[project_name]["total_output_tokens"] += sum(
            msg.output_tokens for msg in session.messages
        )
        codex_projects[project_name]["total_cache_read_tokens"] += sum(
            msg.cache_read_tokens for msg in session.messages
        )
        codex_projects[project_name]["total_cache_creation_tokens"] += sum(
            msg.cache_creation_tokens for msg in session.messages
        )

    projects.extend(codex_projects.values())

    # Calculate total tokens for dashboard
    total_input = sum(p.get("total_input_tokens", 0) for p in projects)
    total_output = sum(p.get("total_output_tokens", 0) for p in projects)
    total_cache_read = sum(p.get("total_cache_read_tokens", 0) for p in projects)
    total_cache_creation = sum(p.get("total_cache_creation_tokens", 0) for p in projects)

    return {
        "projects": sorted(projects, key=lambda x: x["name"]),
        "token_stats": {
            "input": total_input,
            "output": total_output,
            "cache_read": total_cache_read,
            "cache_creation": total_cache_creation
        }
    }
```

**Step 2: Verify API returns token stats**

Run: `cd A:/ai_dev/history-ai-chat && python -c "
import requests
import time
import subprocess
import sys

proc = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'viewer.main:app', '--port', '8899'],
                       cwd='A:/ai_dev/history-ai-chat/src')
time.sleep(2)

try:
    r = requests.get('http://localhost:8899/api/projects?date=all')
    data = r.json()
    stats = data.get('token_stats', {})
    print(f'Input: {stats.get(\"input\", 0):,}')
    print(f'Output: {stats.get(\"output\", 0):,}')
    print(f'Cache Read: {stats.get(\"cache_read\", 0):,}')
finally:
    proc.terminate()
"`
Expected: Shows aggregated token stats

**Step 3: Commit**

```bash
git add src/viewer/main.py
git commit -m "feat: add aggregate token stats to projects API"
```

---

### Task 6: Add Token Statistics Card to Dashboard

**Files:**
- Modify: `src/viewer/templates/dashboard.html:10-28`
- Modify: `src/viewer/templates/dashboard.html:97-139`

**Step 1: Add token stats card HTML**

Add after the Projects stat card (around line 28):

```html
            <div class="stat-card">
                <div class="stat-icon tokens">
                    <i class="bi bi-cpu"></i>
                </div>
                <div class="stat-info">
                    <span class="stat-value" id="tokens-count">-</span>
                    <span class="stat-label">Tokens</span>
                </div>
            </div>
```

**Step 2: Update loadProjects to display tokens**

Modify the `loadProjects` function to update tokens display:

```javascript
function loadProjects() {
    const dateFilter = getDateFilter();
    fetch(`/api/projects?date=${dateFilter}`)
        .then(response => response.json())
        .then(data => {
            const projects = data.projects || [];
            const tokenStats = data.token_stats || {};
            let totalSessions = 0;

            document.getElementById('projects-count').textContent = projects.length;

            // Update tokens display
            const inputK = formatTokens(tokenStats.input || 0);
            const outputK = formatTokens(tokenStats.output || 0);
            document.getElementById('tokens-count').textContent = `${inputK} / ${outputK}`;
            document.getElementById('tokens-count').title =
                `Input: ${(tokenStats.input || 0).toLocaleString()}\n` +
                `Output: ${(tokenStats.output || 0).toLocaleString()}\n` +
                `Cache Read: ${(tokenStats.cache_read || 0).toLocaleString()}\n` +
                `Cache Create: ${(tokenStats.cache_creation || 0).toLocaleString()}`;

            const listEl = document.getElementById('projects-list');

            if (projects.length === 0) {
                listEl.innerHTML = '<div class="text-center py-4 text-muted">No projects found for selected date</div>';
                document.getElementById('sessions-count').textContent = '0';
                return;
            }

            listEl.innerHTML = projects.map(p => {
                totalSessions += p.session_count || 0;
                const platformBadge = p.platform === 'codex'
                    ? '<span class="badge bg-info">Codex</span>'
                    : '<span class="badge bg-warning text-dark">Claude</span>';
                const tokensBadge = (p.total_input_tokens || p.total_output_tokens)
                    ? `<span class="badge bg-success ms-1">${formatTokens(p.total_input_tokens || 0)}/${formatTokens(p.total_output_tokens || 0)}</span>`
                    : '';
                return `
                    <a href="/project/${encodeURIComponent(p.id)}?platform=${p.platform}&date=${dateFilter}" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                        <div>
                            <i class="bi bi-folder me-2"></i>
                            ${escapeHtml(p.name)}
                            ${platformBadge}
                            ${tokensBadge}
                        </div>
                        <span class="badge bg-secondary rounded-pill">${p.session_count || 0} sessions</span>
                    </a>
                `;
            }).join('');

            document.getElementById('sessions-count').textContent = totalSessions;
        })
        .catch(err => {
            console.error('Failed to load projects:', err);
            document.getElementById('projects-list').innerHTML =
                '<div class="alert alert-danger">Failed to load projects</div>';
        });
}

function formatTokens(n) {
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return n.toString();
}
```

**Step 3: Add CSS for tokens stat icon**

Add to `src/viewer/static/style.css` (if exists) or inline in the template:

```css
.stat-icon.tokens {
    background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
}
```

**Step 4: Test dashboard shows tokens**

Manual test: Open dashboard, verify tokens card shows aggregated stats and project list shows per-project tokens.

**Step 5: Commit**

```bash
git add src/viewer/templates/dashboard.html
git commit -m "feat: add token statistics card to dashboard"
```

---

### Task 7: Write Unit Tests for Token Parsing

**Files:**
- Create: `tests/test_token_parsing.py`

**Step 1: Write tests**

```python
# tests/test_token_parsing.py
import json
from pathlib import Path
from viewer.parsers.claude import ClaudeParser


def test_parse_assistant_message_with_tokens(tmp_path):
    """Test that token usage is extracted from assistant messages"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello"}],
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 50,
                "cache_read_input_tokens": 200,
                "cache_creation_input_tokens": 10
            }
        },
        "uuid": "test-uuid",
        "timestamp": "2026-03-17T10:00:00Z",
        "sessionId": "test-session",
        "cwd": "/test"
    }) + "\n")

    parser = ClaudeParser(str(tmp_path))
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].input_tokens == 1000
    assert messages[0].output_tokens == 50
    assert messages[0].cache_read_tokens == 200
    assert messages[0].cache_creation_tokens == 10


def test_parse_message_without_usage(tmp_path):
    """Test that messages without usage default to 0 tokens"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": "Hello"
        },
        "uuid": "test-uuid",
        "timestamp": "2026-03-17T10:00:00Z",
        "sessionId": "test-session",
        "cwd": "/test"
    }) + "\n")

    parser = ClaudeParser(str(tmp_path))
    messages = parser.parse_session(session_file)

    assert len(messages) == 1
    assert messages[0].input_tokens == 0
    assert messages[0].output_tokens == 0


def test_parse_message_with_missing_usage_fields(tmp_path):
    """Test partial usage data"""
    session_file = tmp_path / "test-session.jsonl"
    session_file.write_text(json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello"}],
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 50
                # cache fields missing
            }
        },
        "uuid": "test-uuid",
        "timestamp": "2026-03-17T10:00:00Z",
        "sessionId": "test-session",
        "cwd": "/test"
    }) + "\n")

    parser = ClaudeParser(str(tmp_path))
    messages = parser.parse_session(session_file)

    assert messages[0].input_tokens == 1000
    assert messages[0].output_tokens == 50
    assert messages[0].cache_read_tokens == 0
    assert messages[0].cache_creation_tokens == 0
```

**Step 2: Run tests**

Run: `cd A:/ai_dev/history-ai-chat && python -m pytest tests/test_token_parsing.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/test_token_parsing.py
git commit -m "test: add unit tests for token parsing"
```

---

### Task 8: Final Verification

**Step 1: Run all tests**

Run: `cd A:/ai_dev/history-ai-chat && python -m pytest tests/ -v`
Expected: All tests PASS

**Step 2: Manual integration test**

1. Start the server: `cd src && python -m uvicorn viewer.main:app --reload`
2. Open dashboard in browser
3. Verify tokens card shows aggregated stats
4. Navigate to a conversation
5. Verify token badge appears with breakdown on click
6. Test with different date filters

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: any remaining issues from integration testing"
```