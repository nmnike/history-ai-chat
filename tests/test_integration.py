# tests/test_integration.py
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from viewer.main import app, cache_db
from viewer.parsers import Session


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