import sqlite3
from typing import Optional, Dict, Any, List
from config import DB_PATH


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                total_games INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                creator_id INTEGER NOT NULL,
                opponent_id INTEGER,
                start_article TEXT NOT NULL,
                target_article TEXT NOT NULL,
                creator_current TEXT NOT NULL,
                opponent_current TEXT,
                creator_steps INTEGER DEFAULT 0,
                opponent_steps INTEGER DEFAULT 0,
                status TEXT DEFAULT 'waiting',
                winner_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    finally:
        conn.close()


def get_or_create_user(user_id: int, username: Optional[str], first_name: Optional[str]) -> Dict[str, Any]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username or "", first_name or "")
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
        else:
            cursor.execute(
                "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                (username or "", first_name or "", user_id)
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
        return dict(row)
    finally:
        conn.close()


def get_user_stats(user_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_top_players(limit: int = 10) -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE total_games > 0 ORDER BY wins DESC, total_games ASC LIMIT ?",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def create_match(code: str, creator_id: int, start_article: str, target_article: str) -> Dict[str, Any]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO matches (code, creator_id, start_article, target_article, creator_current, status)
            VALUES (?, ?, ?, ?, ?, 'waiting')
            """,
            (code, creator_id, start_article, target_article, start_article)
        )
        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE code = ?", (code,))
        return dict(cursor.fetchone())
    finally:
        conn.close()


def get_match_by_code(code: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_match_by_id(match_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_active_match(user_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM matches 
            WHERE (creator_id = ? OR opponent_id = ?) 
              AND status IN ('waiting', 'in_progress')
            ORDER BY id DESC LIMIT 1
            """,
            (user_id, user_id)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def join_match(code: str, opponent_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE code = ? AND status = 'waiting'", (code,))
        match = cursor.fetchone()
        if not match:
            return None
        
        start_article = match["start_article"]
        cursor.execute(
            """
            UPDATE matches 
            SET opponent_id = ?, opponent_current = ?, status = 'in_progress'
            WHERE code = ? AND status = 'waiting'
            """,
            (opponent_id, start_article, code)
        )
        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE code = ?", (code,))
        return dict(cursor.fetchone())
    finally:
        conn.close()


def update_player_step(match_id: int, user_id: int, next_article: str) -> Dict[str, Any]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        match = dict(cursor.fetchone())

        if user_id == match["creator_id"]:
            new_steps = match["creator_steps"] + 1
            cursor.execute(
                "UPDATE matches SET creator_current = ?, creator_steps = ? WHERE id = ?",
                (next_article, new_steps, match_id)
            )
        else:
            new_steps = match["opponent_steps"] + 1
            cursor.execute(
                "UPDATE matches SET opponent_current = ?, opponent_steps = ? WHERE id = ?",
                (next_article, new_steps, match_id)
            )
        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        return dict(cursor.fetchone())
    finally:
        conn.close()


def finish_match(match_id: int, winner_id: int) -> Dict[str, Any]:
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        match = dict(cursor.fetchone())

        creator_id = match["creator_id"]
        opponent_id = match["opponent_id"]
        loser_id = opponent_id if winner_id == creator_id else creator_id

        cursor.execute(
            "UPDATE matches SET status = 'finished', winner_id = ? WHERE id = ?",
            (winner_id, match_id)
        )
        cursor.execute(
            "UPDATE users SET wins = wins + 1, total_games = total_games + 1 WHERE user_id = ?",
            (winner_id,)
        )
        if loser_id:
            cursor.execute(
                "UPDATE users SET losses = losses + 1, total_games = total_games + 1 WHERE user_id = ?",
                (loser_id,)
            )

        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        return dict(cursor.fetchone())
    finally:
        conn.close()


def cancel_match(match_id: int):
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE matches SET status = 'cancelled' WHERE id = ?", (match_id,))
        conn.commit()
    finally:
        conn.close()
