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


def test_get_cached_sessions(tmp_path):
    """Test getting all cached sessions"""
    db = CacheDB(tmp_path / "cache.db")

    db.cache_session({"id": "s1", "project": "p1", "preview": "First"})
    db.cache_session({"id": "s2", "project": "p2", "preview": "Second"})
    db.cache_session({"id": "s3", "project": "p1", "preview": "Third"})

    all_sessions = db.get_cached_sessions()
    assert len(all_sessions) == 3

    p1_sessions = db.get_cached_sessions(project="p1")
    assert len(p1_sessions) == 2


def test_favorites(tmp_path):
    """Test favorites functionality"""
    db = CacheDB(tmp_path / "cache.db")

    db.cache_session({"id": "fav-session", "project": "p1", "preview": "Favorite"})
    db.add_favorite("fav-session", tags=["important"], notes="My notes")

    favorites = db.get_favorites()
    assert len(favorites) == 1
    assert favorites[0]["session_id"] == "fav-session"


def test_remove_favorite(tmp_path):
    """Test removing a favorite"""
    db = CacheDB(tmp_path / "cache.db")

    db.cache_session({"id": "session-1", "project": "p1", "preview": "Test"})
    db.add_favorite("session-1")

    assert db.is_favorite("session-1") is True

    db.remove_favorite("session-1")
    assert db.is_favorite("session-1") is False

    favorites = db.get_favorites()
    assert len(favorites) == 0


def test_is_favorite_not_exists(tmp_path):
    """Test is_favorite returns False for non-existent favorite"""
    db = CacheDB(tmp_path / "cache.db")

    assert db.is_favorite("non-existent") is False