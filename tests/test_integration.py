# tests/test_integration.py
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from viewer.main import app, cache_db
from viewer.parsers import Session, Message


client = TestClient(app)


def make_session(session_id: str, days_ago: int) -> Session:
    created_at = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    return Session(
        id=session_id,
        project_path="/tmp/test-project",
        project_name="test-project",
        messages=[],
        created_at=created_at,
    )


def test_dashboard_loads():
    """Test that dashboard page loads"""
    response = client.get("/")
    assert response.status_code == 200
    assert "History AI Chat" in response.text


def test_api_projects():
    """Test projects API endpoint"""
    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert "projects" in data
    assert isinstance(data["projects"], list)


def test_api_search_empty_query():
    """Test search API endpoint with empty query returns empty results"""
    response = client.get("/api/search?q=")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["results"] == []


def test_dashboard_defaults_to_last_7_days():
    """Dashboard should default date filter to last 7 days"""
    response = client.get("/")
    assert response.status_code == 200
    assert "document.getElementById('date-filter').value = 'week';" in response.text


def test_project_page_defaults_to_last_7_days():
    """Project page should default date filter to last 7 days"""
    response = client.get("/project/test-project")
    assert response.status_code == 200
    assert 'const initialDateFilter = "week";' in response.text


def test_conversation_template_has_30_line_tool_threshold():
    """Conversation UI should use line and size thresholds for tool collapse"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'const TOOL_COLLAPSE_LINE_THRESHOLD = 30;' in response.text
    assert 'const TOOL_COLLAPSE_CHAR_THRESHOLD = 4000;' in response.text
    assert 'return lineCount < TOOL_COLLAPSE_LINE_THRESHOLD && normalized.length < TOOL_COLLAPSE_CHAR_THRESHOLD;' in response.text


def test_api_projects_defaults_to_last_7_days(monkeypatch):
    """Projects API should exclude sessions older than 7 days by default"""
    recent_session = make_session("recent", 3)
    old_session = make_session("old", 10)

    class StubClaudeParser:
        def get_projects(self):
            return [{"id": "test-project", "name": "Test Project", "path": "/tmp/test-project"}]

        def get_sessions(self, project_id):
            assert project_id == "test-project"
            return [recent_session, old_session]

    class StubCodexParser:
        def get_sessions(self):
            return []

    monkeypatch.setattr("viewer.main.claude_parser", StubClaudeParser())
    monkeypatch.setattr("viewer.main.codex_parser", StubCodexParser())

    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data["projects"]) == 1
    assert data["projects"][0]["session_count"] == 1


def test_api_sessions_defaults_to_last_7_days(monkeypatch):
    """Sessions API should exclude sessions older than 7 days by default"""
    recent_session = make_session("recent", 2)
    old_session = make_session("old", 9)

    class StubClaudeParser:
        def get_sessions(self, project_id):
            assert project_id == "test-project"
            return [recent_session, old_session]

    monkeypatch.setattr("viewer.main.claude_parser", StubClaudeParser())

    response = client.get("/api/sessions/test-project")
    assert response.status_code == 200
    data = response.json()
    assert [session["id"] for session in data["sessions"]] == ["recent"]


def test_favorites_api():
    """Test favorites API endpoints"""
    session_id = "test-fav-session"

    # Create test session in cache for get_favorites JOIN
    cache_db.cache_session({
        "id": session_id,
        "project": "test-project",
        "platform": "claude",
        "preview": "Test session preview",
        "message_count": 1
    })

    # Add to favorites
    response = client.post(f"/api/favorites/{session_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "added"

    # Check is favorite
    response = client.get(f"/api/favorites/{session_id}/status")
    assert response.status_code == 200
    assert response.json()["is_favorite"] is True

    # Get all favorites
    response = client.get("/api/favorites")
    assert response.status_code == 200
    assert len(response.json()["favorites"]) >= 1

    # Remove from favorites
    response = client.delete(f"/api/favorites/{session_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "removed"

    # Verify removed
    response = client.get(f"/api/favorites/{session_id}/status")
    assert response.json()["is_favorite"] is False


def test_api_conversation_returns_timing_and_tool_metadata(monkeypatch):
    """API should return session timing and tool usage metadata"""
    base = datetime(2026, 4, 10, 12, 0, 0)
    session = Session(
        id="sess-1",
        project_path="/tmp/test-project",
        project_name="test-project",
        created_at=base,
        messages=[
            Message(role="user", content="hi", uuid="1", timestamp=base, session_id="sess-1", project_path="/tmp/test-project"),
            Message(role="assistant", content="", uuid="2", timestamp=base + timedelta(minutes=2), session_id="sess-1", project_path="/tmp/test-project", message_type="tool_use", tool_name="mcp__context7__query-docs"),
            Message(role="assistant", content="", uuid="3", timestamp=base + timedelta(minutes=4), session_id="sess-1", project_path="/tmp/test-project", message_type="tool_use", tool_name="functions.Skill"),
            Message(role="assistant", content="", uuid="4", timestamp=base + timedelta(minutes=5), session_id="sess-1", project_path="/tmp/test-project", message_type="tool_use", tool_name="Read"),
            Message(role="assistant", content="", uuid="5", timestamp=base + timedelta(minutes=6), session_id="sess-1", project_path="/tmp/test-project", message_type="tool_use", tool_name="functions.AskUserQuestion"),
        ],
    )

    class StubClaudeParser:
        def get_sessions(self, project_id):
            assert project_id == "test-project"
            return [session]

    monkeypatch.setattr("viewer.main.claude_parser", StubClaudeParser())

    response = client.get("/api/conversation/sess-1?project_id=test-project&platform=claude")
    assert response.status_code == 200

    payload = response.json()["session"]
    assert payload["created_at"] == "2026-04-10T12:00:00"
    assert payload["ended_at"] == "2026-04-10T12:06:00"
    assert payload["duration_seconds"] == 360
    assert payload["mcps"] == [{"name": "context7", "count": 1}]
    # Skills order is alphabetical
    skills = payload["skills"]
    assert len(skills) == 2
    assert {"name": "Skill", "count": 1} in skills
    assert {"name": "AskUserQuestion", "count": 1} in skills


def test_api_conversation_parses_skills_from_command_name_tags(monkeypatch):
    """Skills should be parsed from <command-name> tags in user message content"""
    base = datetime(2026, 4, 10, 12, 0, 0)
    session = Session(
        id="sess-2",
        project_path="/tmp/test-project",
        project_name="test-project",
        created_at=base,
        messages=[
            Message(
                role="user",
                content="<command-message>superpowers-brainstorming</command-message>\n<command-name>/superpowers-brainstorming</command-name>\n<command-args>Test args</command-args>",
                uuid="1",
                timestamp=base,
                session_id="sess-2",
                project_path="/tmp/test-project",
            ),
            Message(role="assistant", content="", uuid="2", timestamp=base + timedelta(minutes=1), session_id="sess-2", project_path="/tmp/test-project", message_type="tool_use", tool_name="Read"),
        ],
    )

    class StubClaudeParser:
        def get_sessions(self, project_id):
            return [session]

    monkeypatch.setattr("viewer.main.claude_parser", StubClaudeParser())

    response = client.get("/api/conversation/sess-2?project_id=test-project&platform=claude")
    assert response.status_code == 200

    payload = response.json()["session"]
    # Skill should be parsed from <command-name> tag
    skills = payload["skills"]
    assert len(skills) == 1
    assert {"name": "superpowers-brainstorming", "count": 1} in skills


def test_conversation_template_contains_metadata_and_multi_filter_ui():
    """Conversation template should have timing/tool containers and multi-filter JS"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'id="session-timing"' in response.text
    assert 'id="session-tools-summary"' in response.text
    assert 'let activeFilters = new Set();' in response.text
    assert 'function applyFilters()' in response.text
    assert 'function renderToolSummary(session)' in response.text


def test_conversation_template_uses_or_multi_filter_logic():
    """Conversation template should use OR logic for multi-filter"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'activeFilters.has(filter)' in response.text
    assert 'activeFilters.size === 0' in response.text
    # OR logic includes role, tool, mcp, and skill matching
    assert 'matchesRole || matchesTool || matchesMcp || matchesSkill' in response.text


def test_conversation_template_prioritizes_skill_tool_result_scroll_target():
    """Skill badge click should target tool_result launch line, not only tool_use bubble"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert "let lastSkillName = '';" in response.text
    assert "const skillNameForFilter = isToolResult && isLastSkillTool ? lastSkillName : currentSkillNameForFilter;" in response.text
    assert "bubble.dataset.role === 'tool_result'" in response.text
    assert "const scrollContainer = document.getElementById('messages-container');" in response.text
    assert "scrollContainer.scrollTo({" in response.text


def test_conversation_template_renders_timing_and_tool_cards():
    """Conversation template should have timing and tool summary rendering code"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    # Timing is rendered with icons only (no labels like "Started")
    assert 'bi-play-circle' in response.text
    assert 'bi-stop-circle' in response.text
    assert 'bi-clock' in response.text
    # Tool groups
    assert 'MCP Tools' in response.text
    assert 'Skills' in response.text
    assert 'formatDuration(' in response.text


def test_conversation_template_compacts_tool_input_rendering():
    """Conversation template should keep pretty JSON and compact multiline string values"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'function compactMultilineText(text)' in response.text
    assert 'JSON.stringify(normalizedInput, null, 2)' in response.text
    assert 'JSON.stringify(msg.tool_input, null, 2)' not in response.text
    assert 'function normalizeToolInputValue(value)' in response.text
    assert "return text.replace(/\\r\\n/g, '\\n').replace(/\\r/g, '\\n').replace(/\\n{3,}/g, '\\n\\n');" in response.text


def test_conversation_template_renders_multiline_tool_fields_separately():
    """Conversation template should add readable blocks for multiline JSON fields"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'function renderToolInput(toolName, input, collapsedStyle)' in response.text
    assert 'function collectMultilineToolInputFields(value, path = [])' in response.text
    assert 'tool-input-multiline-fields' in response.text
    assert 'tool-input-field-label' in response.text



def test_conversation_template_hides_raw_json_only_for_custom_tool_views():
    """Conversation template should hide raw JSON only when a custom readable view exists"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'function parseLibraryListToolView(input)' in response.text
    assert 'function renderLibraryListToolView(parsed)' in response.text
    assert 'const hasCustomView = Boolean(readableViewHtml);' in response.text
    assert 'hasCustomView ?' in response.text
    assert 'tool-input-raw-toggle' in response.text
    assert 'style="display: none"' in response.text
    assert 'tool-input-readable-view' in response.text
    assert "${hasCustomView ? '<button type=\"button\" class=\"tool-input-raw-toggle\" onclick=\"toggleToolRaw(this)\">Show raw JSON</button>' : ''}" in response.text



def test_conversation_template_supports_compact_skill_preview():
    """Conversation template should provide compact readable preview for Skill tool input"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'function parseSkillToolView(toolName, input)' in response.text
    assert 'function renderSkillToolView(parsed)' in response.text
    assert 'Base directory for this skill:' in response.text
    assert 'skill-readable-preview' in response.text
    assert 'skill-readable-body' in response.text



def test_conversation_template_supports_compact_skill_dump_content_preview():
    """Conversation template should compact skill dump text in regular message content"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'function parseSkillDumpContent(content)' in response.text
    assert 'function renderSkillDumpContent(parsed)' in response.text
    assert 'message-content skill-dump-preview collapse-content' in response.text
    assert 'skill-dump-raw-toggle' in response.text
    assert 'skill-dump-body' in response.text



def test_conversation_template_supports_compact_tool_result_library_preview():
    """Conversation template should render library list tool results as readable cards with raw toggle"""
    response = client.get("/conversation/test-session?project_id=test-project&platform=claude")
    assert response.status_code == 200
    assert 'function parseToolResultLibraryContent(content)' in response.text
    assert 'function renderToolResultContent(content)' in response.text
    assert 'tool-result-readable-view' in response.text
    assert 'tool-result-raw-toggle' in response.text
    assert 'Show raw result' in response.text
    assert 'function compactLibraryDescription(text, maxLength = 220)' in response.text
    assert 'tool-library-list compact' in response.text
    assert 'const headerChunk = firstLibraryStart >= 0 ? firstChunk.slice(0, firstLibraryStart).trim() : firstChunk;' in response.text
    assert "const firstLibraryChunk = firstLibraryStart >= 0 ? firstChunk.slice(firstLibraryStart + 1).trim() : '';" in response.text
    assert 'const libraryChunks = [firstLibraryChunk, ...chunks.slice(1)].filter(Boolean);' in response.text
    css_text = Path("src/viewer/static/css/theme.css").read_text(encoding="utf-8")
    assert '.tool-result-readable-view {' in css_text
    assert 'white-space: normal;' in css_text