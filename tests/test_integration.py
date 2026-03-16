# tests/test_integration.py
from fastapi.testclient import TestClient
from viewer.main import app

client = TestClient(app)


def test_dashboard_loads():
    """Test that dashboard page loads"""
    response = client.get("/")
    assert response.status_code == 200
    assert "Claude Codex Viewer" in response.text


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