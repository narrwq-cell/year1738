import sqlite3
import os
import datetime
from typing import Optional, List, Tuple


DATABASE_PATH = os.getenv("DATABASE_PATH", "bot.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def setup_database() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            message_count INTEGER DEFAULT 0,
            vc_seconds INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        );

        CREATE TABLE IF NOT EXISTS vc_sessions (
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            join_time TEXT NOT NULL,
            PRIMARY KEY (user_id, guild_id)
        );

        CREATE TABLE IF NOT EXISTS moderation_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            timestamp TEXT NOT NULL,
            duration_minutes INTEGER
        );

        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS react_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            role_id INTEGER NOT NULL,
            UNIQUE(message_id, emoji)
        );

        CREATE TABLE IF NOT EXISTS spam_tracking (
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            message_times TEXT DEFAULT '[]',
            last_message TEXT DEFAULT '',
            repeat_count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, guild_id)
        );

        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            creator_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


# ── User Stats ─────────────────────────────────────────────────────────────────

def ensure_user(user_id: int, guild_id: int) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO user_stats (user_id, guild_id) VALUES (?, ?)",
        (user_id, guild_id),
    )
    conn.commit()
    conn.close()


def increment_message_count(user_id: int, guild_id: int) -> None:
    ensure_user(user_id, guild_id)
    conn = get_connection()
    conn.execute(
        "UPDATE user_stats SET message_count = message_count + 1 WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    conn.commit()
    conn.close()


def add_vc_seconds(user_id: int, guild_id: int, seconds: int) -> None:
    ensure_user(user_id, guild_id)
    conn = get_connection()
    conn.execute(
        "UPDATE user_stats SET vc_seconds = vc_seconds + ? WHERE user_id = ? AND guild_id = ?",
        (seconds, user_id, guild_id),
    )
    conn.commit()
    conn.close()


def add_points(user_id: int, guild_id: int, points: int) -> None:
    ensure_user(user_id, guild_id)
    conn = get_connection()
    conn.execute(
        "UPDATE user_stats SET points = points + ? WHERE user_id = ? AND guild_id = ?",
        (points, user_id, guild_id),
    )
    conn.commit()
    conn.close()


def get_user_stats(user_id: int, guild_id: int) -> Optional[sqlite3.Row]:
    ensure_user(user_id, guild_id)
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM user_stats WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    ).fetchone()
    conn.close()
    return row


def get_leaderboard_messages(guild_id: int, limit: int = 10) -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id, message_count FROM user_stats WHERE guild_id = ? ORDER BY message_count DESC LIMIT ?",
        (guild_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_leaderboard_hours(guild_id: int, limit: int = 10) -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id, vc_seconds FROM user_stats WHERE guild_id = ? ORDER BY vc_seconds DESC LIMIT ?",
        (guild_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_leaderboard_points(guild_id: int, limit: int = 10) -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT user_id, points FROM user_stats WHERE guild_id = ? ORDER BY points DESC LIMIT ?",
        (guild_id, limit),
    ).fetchall()
    conn.close()
    return rows


# ── VC Sessions ────────────────────────────────────────────────────────────────

def start_vc_session(user_id: int, guild_id: int) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO vc_sessions (user_id, guild_id, join_time) VALUES (?, ?, ?)",
        (user_id, guild_id, datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def end_vc_session(user_id: int, guild_id: int) -> Optional[int]:
    conn = get_connection()
    row = conn.execute(
        "SELECT join_time FROM vc_sessions WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    ).fetchone()
    if row is None:
        conn.close()
        return None
    join_time = datetime.datetime.fromisoformat(row["join_time"])
    # Ensure both datetimes are comparable (make join_time aware if it isn't)
    now = datetime.datetime.now(datetime.timezone.utc)
    if join_time.tzinfo is None:
        join_time = join_time.replace(tzinfo=datetime.timezone.utc)
    seconds = int((now - join_time).total_seconds())
    conn.execute(
        "DELETE FROM vc_sessions WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    )
    conn.commit()
    conn.close()
    add_vc_seconds(user_id, guild_id, max(seconds, 0))
    return seconds


# ── Moderation Actions ─────────────────────────────────────────────────────────

def log_mod_action(
    guild_id: int,
    user_id: int,
    moderator_id: int,
    action: str,
    reason: Optional[str] = None,
    duration_minutes: Optional[int] = None,
) -> int:
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO moderation_actions
           (guild_id, user_id, moderator_id, action, reason, timestamp, duration_minutes)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (guild_id, user_id, moderator_id, action, reason,
         datetime.datetime.now(datetime.timezone.utc).isoformat(), duration_minutes),
    )
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def get_mod_actions(guild_id: int, user_id: int) -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM moderation_actions WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
        (guild_id, user_id),
    ).fetchall()
    conn.close()
    return rows


# ── Warnings ───────────────────────────────────────────────────────────────────

def add_warning(
    guild_id: int, user_id: int, moderator_id: int, reason: Optional[str] = None
) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
        (guild_id, user_id, moderator_id, reason, datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    log_mod_action(guild_id, user_id, moderator_id, "warn", reason)
    return row_id


def get_warnings(guild_id: int, user_id: int) -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
        (guild_id, user_id),
    ).fetchall()
    conn.close()
    return rows


def get_warning_count(guild_id: int, user_id: int) -> int:
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM warnings WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    ).fetchone()["cnt"]
    conn.close()
    return count


def clear_warnings(guild_id: int, user_id: int) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
        (guild_id, user_id),
    )
    conn.commit()
    conn.close()


# ── React Roles ────────────────────────────────────────────────────────────────

def add_react_role(
    guild_id: int, channel_id: int, message_id: int, emoji: str, role_id: int
) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO react_roles
           (guild_id, channel_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?, ?)""",
        (guild_id, channel_id, message_id, emoji, role_id),
    )
    conn.commit()
    conn.close()


def get_react_role(message_id: int, emoji: str) -> Optional[sqlite3.Row]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM react_roles WHERE message_id = ? AND emoji = ?",
        (message_id, emoji),
    ).fetchone()
    conn.close()
    return row


def get_react_roles_for_message(message_id: int) -> List[sqlite3.Row]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM react_roles WHERE message_id = ?",
        (message_id,),
    ).fetchall()
    conn.close()
    return rows


def remove_react_role(message_id: int, emoji: str) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM react_roles WHERE message_id = ? AND emoji = ?",
        (message_id, emoji),
    )
    conn.commit()
    conn.close()


# ── Spam Tracking ──────────────────────────────────────────────────────────────

def get_spam_data(user_id: int, guild_id: int) -> sqlite3.Row:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM spam_tracking WHERE user_id = ? AND guild_id = ?",
        (user_id, guild_id),
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO spam_tracking (user_id, guild_id) VALUES (?, ?)",
            (user_id, guild_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM spam_tracking WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        ).fetchone()
    conn.close()
    return row


def update_spam_data(
    user_id: int, guild_id: int, message_times: str, last_message: str, repeat_count: int
) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO spam_tracking (user_id, guild_id, message_times, last_message, repeat_count)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, guild_id, message_times, last_message, repeat_count),
    )
    conn.commit()
    conn.close()


# ── Polls ──────────────────────────────────────────────────────────────────────

def log_poll(
    guild_id: int, channel_id: int, message_id: int, question: str, creator_id: int
) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO polls (guild_id, channel_id, message_id, question, creator_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (guild_id, channel_id, message_id, question, creator_id,
         datetime.datetime.now(datetime.timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


# ── Rank queries ───────────────────────────────────────────────────────────────

def get_user_rank_messages(guild_id: int, user_id: int) -> int:
    """Return 1-based rank for message_count. Returns total+1 if user has no data."""
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) + 1 AS rank FROM user_stats
           WHERE guild_id = ? AND message_count > COALESCE(
               (SELECT message_count FROM user_stats WHERE guild_id = ? AND user_id = ?), -1
           )""",
        (guild_id, guild_id, user_id),
    ).fetchone()
    conn.close()
    return row["rank"] if row else 1


def get_user_rank_hours(guild_id: int, user_id: int) -> int:
    """Return 1-based rank for vc_seconds."""
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) + 1 AS rank FROM user_stats
           WHERE guild_id = ? AND vc_seconds > COALESCE(
               (SELECT vc_seconds FROM user_stats WHERE guild_id = ? AND user_id = ?), -1
           )""",
        (guild_id, guild_id, user_id),
    ).fetchone()
    conn.close()
    return row["rank"] if row else 1


def get_user_rank_points(guild_id: int, user_id: int) -> int:
    """Return 1-based rank for points."""
    conn = get_connection()
    row = conn.execute(
        """SELECT COUNT(*) + 1 AS rank FROM user_stats
           WHERE guild_id = ? AND points > COALESCE(
               (SELECT points FROM user_stats WHERE guild_id = ? AND user_id = ?), -1
           )""",
        (guild_id, guild_id, user_id),
    ).fetchone()
    conn.close()
    return row["rank"] if row else 1


def get_leaderboard_top_values(guild_id: int) -> dict:
    """Return the top values for each leaderboard category in a single query."""
    conn = get_connection()
    row = conn.execute(
        """SELECT MAX(message_count) as top_messages,
                  MAX(vc_seconds) as top_seconds,
                  MAX(points) as top_points
           FROM user_stats WHERE guild_id = ?""",
        (guild_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return {"top_messages": 0, "top_seconds": 0, "top_points": 0}
    return {
        "top_messages": row["top_messages"] or 0,
        "top_seconds": row["top_seconds"] or 0,
        "top_points": row["top_points"] or 0,
    }

