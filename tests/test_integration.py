# tests/test_integration.py
from fastapi.testclient import TestClient
from viewer.main import app, cache_db


client = TestClient(app)


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