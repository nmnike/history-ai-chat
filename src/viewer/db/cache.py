"""SQLite cache for session metadata"""
import sqlite3
from pathlib import Path
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
                SELECT s.id as session_id, s.project, s.platform, s.preview,
                       s.message_count, s.cached_at, f.tags, f.notes
                FROM sessions s
                JOIN favorites f ON s.id = f.session_id
                ORDER BY f.created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def remove_favorite(self, session_id: str):
        """Remove session from favorites"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM favorites WHERE session_id = ?", (session_id,)
            )

    def is_favorite(self, session_id: str) -> bool:
        """Check if session is in favorites"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM favorites WHERE session_id = ?", (session_id,)
            )
            return cursor.fetchone() is not None