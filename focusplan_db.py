from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Файл с настройкой и функциями работы с SQLite-базой данных FocusPlan.
# app.py обращается к этим функциям, а сама база хранится в focusplan.db.

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DATA_FILE = os.path.join(DATA_DIR, "store.json")  # оставлен как резервная копия после миграции
DB_FILE = os.path.join(BASE_DIR, "focusplan.db")

DEFAULT_SETTINGS = {"theme": "light", "accent": "purple", "notifications": True}
DEFAULT_FOLDERS = ["Учёба", "Работа", "Личное"]

PRIORITY_LABELS = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}
IMPORTANCE_LABELS = {"low": "Низкая", "medium": "Средняя", "high": "Высокая"}
URGENCY_LABELS = {"not_urgent": "Не срочно", "urgent": "Срочно"}
ESTIMATE_UNIT_LABELS = {"minutes": "мин.", "hours": "ч.", "days": "дн."}

ACHIEVEMENTS = [
    {"code": "first_task", "title": "Первый шаг", "description": "Выполнить первую задачу", "xp": 10, "icon": "✅"},
    {"code": "first_focus", "title": "Фокус включён", "description": "Завершить первую фокус-сессию", "xp": 15, "icon": "⏱️"},
    {"code": "three_day_streak", "title": "3 дня подряд", "description": "Заходить и выполнять действия 3 дня подряд", "xp": 20, "icon": "🔥"},
    {"code": "ten_tasks", "title": "В потоке", "description": "Выполнить 10 задач", "xp": 25, "icon": "🌊"},
    {"code": "new_level", "title": "Новый уровень", "description": "Впервые повысить уровень", "xp": 20, "icon": "⭐"},
    {"code": "productive_day", "title": "День продуктивности", "description": "Выполнить 5 задач за один день", "xp": 15, "icon": "☀️"},
    {"code": "urgent_important", "title": "Срочно и важно", "description": "Выполнить важную и срочную задачу", "xp": 20, "icon": "⚡"},
]

BADGES = [
    {"code": "newbie", "title": "Новичок", "description": "Первые шаги в планировании", "required_level": 2, "icon": "🌱"},
    {"code": "regular_planner", "title": "Планирую регулярно", "description": "Регулярное использование планирования", "required_level": 3, "icon": "📅"},
    {"code": "focus_master", "title": "Фокус-мастер", "description": "Открывается на 5 уровне или после 5 фокус-сессий", "required_level": 5, "focus_sessions": 5, "icon": "🎯"},
    {"code": "stable_progress", "title": "Стабильный прогресс", "description": "Постоянное движение вперёд", "required_level": 7, "icon": "🏆"},
    {"code": "planning_expert", "title": "Эксперт планирования", "description": "Высокий уровень вовлечённости", "required_level": 10, "icon": "💎"},
]


def bool_to_int(value: Any) -> int:
    return 1 if bool(value) else 0


def int_to_bool(value: Any) -> bool:
    return bool(int(value or 0))


def empty_to_none(value: Any) -> Any:
    return None if value == "" else value


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_database() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nickname TEXT NOT NULL UNIQUE,
        password_hash TEXT,
        avatar TEXT,
        theme TEXT DEFAULT 'light',
        accent TEXT DEFAULT 'purple',
        notifications INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1,
        streak INTEGER DEFAULT 0,
        last_activity DATE,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        UNIQUE(user_id, title),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        folder_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        priority TEXT,
        importance TEXT,
        urgency TEXT,
        xp INTEGER DEFAULT 0,
        task_date DATE,
        task_time TEXT,
        is_done INTEGER DEFAULT 0,
        earned_xp INTEGER DEFAULT 0,
        created_at TEXT,
        completed_at TEXT,
        estimate_value TEXT,
        estimate_unit TEXT DEFAULT 'hours',
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (folder_id) REFERENCES folders(id)
    );

    CREATE TABLE IF NOT EXISTS subtasks (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        title TEXT NOT NULL,
        is_done INTEGER DEFAULT 0,
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    );

    CREATE TABLE IF NOT EXISTS focus_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        task_id TEXT,
        duration_minutes INTEGER,
        is_completed INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    );

    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT,
        condition_type TEXT,
        condition_value INTEGER
    );

    CREATE TABLE IF NOT EXISTS user_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        achievement_id INTEGER NOT NULL,
        received_at TEXT,
        UNIQUE(user_id, achievement_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (achievement_id) REFERENCES achievements(id)
    );

    CREATE TABLE IF NOT EXISTS badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT,
        icon TEXT
    );

    CREATE TABLE IF NOT EXISTS user_badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        badge_id INTEGER NOT NULL,
        received_at TEXT,
        is_selected INTEGER DEFAULT 0,
        UNIQUE(user_id, badge_id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (badge_id) REFERENCES badges(id)
    );

    CREATE TABLE IF NOT EXISTS user_streak_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        activity_date DATE NOT NULL,
        UNIQUE(user_id, activity_date),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)

    seed_catalogs(cursor)
    conn.commit()
    conn.close()


def seed_catalogs(cursor: sqlite3.Cursor) -> None:
    achievement_conditions = {
        "first_task": ("completed_tasks", 1),
        "first_focus": ("focus_sessions", 1),
        "three_day_streak": ("streak", 3),
        "ten_tasks": ("completed_tasks", 10),
        "new_level": ("level", 2),
        "productive_day": ("completed_tasks_day", 5),
        "urgent_important": ("urgent_important_task", 1),
    }
    for achievement in ACHIEVEMENTS:
        condition_type, condition_value = achievement_conditions.get(achievement["code"], (None, None))
        cursor.execute("""
            INSERT OR IGNORE INTO achievements
            (code, title, description, condition_type, condition_value)
            VALUES (?, ?, ?, ?, ?)
        """, (
            achievement["code"], achievement["title"], achievement["description"],
            condition_type, condition_value
        ))

    for badge in BADGES:
        cursor.execute("""
            INSERT OR IGNORE INTO badges
            (code, title, description, icon)
            VALUES (?, ?, ?, ?)
        """, (badge["code"], badge["title"], badge["description"], badge["icon"]))


def create_user(nickname: str, password_hash: str | None = None) -> Dict[str, Any]:
    return {
        "nickname": nickname,
        "password_hash": password_hash,
        "avatar": nickname[:1].upper() if nickname else "F",
        "settings": DEFAULT_SETTINGS.copy(),
        "folders": DEFAULT_FOLDERS.copy(),
        "tasks": [],
        "xp": 0,
        "streak": 0,
        "last_activity": None,
        "achievements": [],
        "focus_sessions": 0,
        "selected_badge": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def user_exists(nickname: str) -> bool:
    ensure_database()
    conn = get_db()
    row = conn.execute("SELECT 1 FROM users WHERE nickname = ?", (nickname,)).fetchone()
    conn.close()
    return row is not None


def get_user_id_by_nickname(cursor: sqlite3.Cursor, nickname: str) -> int | None:
    row = cursor.execute("SELECT id FROM users WHERE nickname = ?", (nickname,)).fetchone()
    return int(row["id"]) if row else None


def get_folder_id(cursor: sqlite3.Cursor, user_id: int, title: str | None) -> int | None:
    if not title:
        return None
    row = cursor.execute(
        "SELECT id FROM folders WHERE user_id = ? AND title = ?",
        (user_id, title)
    ).fetchone()
    return int(row["id"]) if row else None


def get_achievement_id(cursor: sqlite3.Cursor, code: str | None) -> int | None:
    if not code:
        return None
    row = cursor.execute("SELECT id FROM achievements WHERE code = ?", (code,)).fetchone()
    return int(row["id"]) if row else None


def get_badge_id(cursor: sqlite3.Cursor, code: str | None) -> int | None:
    if not code:
        return None
    row = cursor.execute("SELECT id FROM badges WHERE code = ?", (code,)).fetchone()
    return int(row["id"]) if row else None


def reconstruct_streak_days(last_activity: str | None, streak: int) -> List[str]:
    if not last_activity or int(streak or 0) <= 0:
        return []
    try:
        last_day = datetime.strptime(last_activity, "%Y-%m-%d").date()
    except ValueError:
        return []
    return [
        (last_day - timedelta(days=offset)).isoformat()
        for offset in range(int(streak) - 1, -1, -1)
    ]


def normalize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    user.setdefault("password_hash", None)
    user.setdefault("avatar", user.get("nickname", "F")[:1].upper())
    user.setdefault("settings", DEFAULT_SETTINGS.copy())
    user["settings"].setdefault("theme", "light")
    user["settings"].setdefault("accent", "purple")
    user["settings"].setdefault("notifications", True)
    user.setdefault("folders", DEFAULT_FOLDERS.copy())
    for folder in DEFAULT_FOLDERS:
        if folder not in user["folders"]:
            user["folders"].append(folder)
    user.setdefault("tasks", [])
    user.setdefault("xp", 0)
    user.setdefault("streak", 0)
    user.setdefault("last_activity", None)
    user.setdefault("achievements", [])
    user.setdefault("focus_sessions", 0)
    user.setdefault("selected_badge", None)
    user.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    user.setdefault("_streak_days", reconstruct_streak_days(user.get("last_activity"), int(user.get("streak", 0))))

    if user.get("selected_badge") and user["selected_badge"] not in available_badge_codes(user):
        user["selected_badge"] = None

    for task in user.get("tasks", []):
        task.setdefault("id", str(uuid.uuid4()))
        task.setdefault("description", "")
        task.setdefault("subtasks", [])
        task.setdefault("folder", "")
        task.setdefault("importance", "medium")
        task.setdefault("urgency", "not_urgent")
        task["priority"] = calculate_priority(task.get("importance", "medium"), task.get("urgency", "not_urgent"))
        task.setdefault("date", "")
        task.setdefault("time", "")
        task.setdefault("estimate_value", "")
        task.setdefault("estimate_unit", "hours")
        task.setdefault("done", False)
        task["xp"] = calculate_task_xp(task.get("importance", "medium"), task.get("urgency", "not_urgent"), task.get("subtasks", []))
        task.setdefault("earned_xp", task["xp"] if task.get("done") else 0)
        task.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
        task.setdefault("completed_at", None)
    return user


def load_user_from_db(nickname: str) -> Dict[str, Any] | None:
    ensure_database()
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM users WHERE nickname = ?", (nickname,)).fetchone()
    if not row:
        conn.close()
        return None

    user_id = int(row["id"])
    user = {
        "nickname": row["nickname"],
        "password_hash": row["password_hash"],
        "avatar": row["avatar"],
        "settings": {
            "theme": row["theme"] or "light",
            "accent": row["accent"] or "purple",
            "notifications": int_to_bool(row["notifications"]),
        },
        "folders": [item["title"] for item in cursor.execute(
            "SELECT title FROM folders WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()],
        "tasks": [],
        "xp": int(row["xp"] or 0),
        "streak": int(row["streak"] or 0),
        "last_activity": row["last_activity"],
        "achievements": [],
        "focus_sessions": int(cursor.execute(
            "SELECT COUNT(*) AS count FROM focus_sessions WHERE user_id = ?", (user_id,)
        ).fetchone()["count"] or 0),
        "selected_badge": None,
        "created_at": row["created_at"],
        "_streak_days": [item["activity_date"] for item in cursor.execute(
            "SELECT activity_date FROM user_streak_days WHERE user_id = ? ORDER BY activity_date", (user_id,)
        ).fetchall()],
    }

    task_rows = cursor.execute("""
        SELECT tasks.*, folders.title AS folder_title
        FROM tasks
        LEFT JOIN folders ON tasks.folder_id = folders.id
        WHERE tasks.user_id = ?
        ORDER BY tasks.created_at
    """, (user_id,)).fetchall()

    for task_row in task_rows:
        task_id = task_row["id"]
        subtasks = [
            {"id": item["id"], "title": item["title"], "done": int_to_bool(item["is_done"])}
            for item in cursor.execute(
                "SELECT * FROM subtasks WHERE task_id = ? ORDER BY rowid", (task_id,)
            ).fetchall()
        ]
        user["tasks"].append({
            "id": task_id,
            "title": task_row["title"],
            "description": task_row["description"] or "",
            "subtasks": subtasks,
            "priority": task_row["priority"] or "low",
            "importance": task_row["importance"] or "medium",
            "urgency": task_row["urgency"] or "not_urgent",
            "xp": int(task_row["xp"] or 0),
            "date": task_row["task_date"] or "",
            "time": task_row["task_time"] or "",
            "estimate_value": task_row["estimate_value"] or "",
            "estimate_unit": task_row["estimate_unit"] or "hours",
            "folder": task_row["folder_title"] or "",
            "done": int_to_bool(task_row["is_done"]),
            "earned_xp": int(task_row["earned_xp"] or 0),
            "created_at": task_row["created_at"],
            "completed_at": task_row["completed_at"],
        })

    user["achievements"] = [
        {"code": item["code"], "received_at": item["received_at"]}
        for item in cursor.execute("""
            SELECT achievements.code, user_achievements.received_at
            FROM user_achievements
            JOIN achievements ON user_achievements.achievement_id = achievements.id
            WHERE user_achievements.user_id = ?
            ORDER BY user_achievements.received_at
        """, (user_id,)).fetchall()
    ]

    selected_badge = cursor.execute("""
        SELECT badges.code
        FROM user_badges
        JOIN badges ON user_badges.badge_id = badges.id
        WHERE user_badges.user_id = ? AND user_badges.is_selected = 1
        LIMIT 1
    """, (user_id,)).fetchone()
    if selected_badge:
        user["selected_badge"] = selected_badge["code"]

    conn.close()
    return normalize_user(user)


def sync_user_to_db(user: Dict[str, Any], old_nickname: str | None = None) -> None:
    ensure_database()
    user = normalize_user(user)
    conn = get_db()
    cursor = conn.cursor()

    lookup_nickname = old_nickname or user["nickname"]
    user_id = get_user_id_by_nickname(cursor, lookup_nickname)

    if user_id is None:
        cursor.execute("""
            INSERT INTO users
            (nickname, password_hash, avatar, theme, accent, notifications, xp, level, streak, last_activity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user["nickname"], user.get("password_hash"), user.get("avatar"),
            user.get("settings", {}).get("theme", "light"),
            user.get("settings", {}).get("accent", "purple"),
            bool_to_int(user.get("settings", {}).get("notifications", True)),
            int(user.get("xp", 0)), level_from_xp(int(user.get("xp", 0))),
            int(user.get("streak", 0)), user.get("last_activity"), user.get("created_at")
        ))
        user_id = int(cursor.lastrowid)
    else:
        cursor.execute("""
            UPDATE users
            SET nickname = ?, password_hash = ?, avatar = ?, theme = ?, accent = ?, notifications = ?,
                xp = ?, level = ?, streak = ?, last_activity = ?, created_at = ?
            WHERE id = ?
        """, (
            user["nickname"], user.get("password_hash"), user.get("avatar"),
            user.get("settings", {}).get("theme", "light"),
            user.get("settings", {}).get("accent", "purple"),
            bool_to_int(user.get("settings", {}).get("notifications", True)),
            int(user.get("xp", 0)), level_from_xp(int(user.get("xp", 0))),
            int(user.get("streak", 0)), user.get("last_activity"), user.get("created_at"), user_id
        ))

    task_ids = [item["id"] for item in cursor.execute("SELECT id FROM tasks WHERE user_id = ?", (user_id,)).fetchall()]
    if task_ids:
        cursor.executemany("DELETE FROM subtasks WHERE task_id = ?", [(task_id,) for task_id in task_ids])
    cursor.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM folders WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM focus_sessions WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_achievements WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_badges WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_streak_days WHERE user_id = ?", (user_id,))

    for folder_title in user.get("folders", []):
        if folder_title:
            cursor.execute("INSERT OR IGNORE INTO folders (user_id, title) VALUES (?, ?)", (user_id, folder_title))

    for task in user.get("tasks", []):
        folder_id = get_folder_id(cursor, user_id, task.get("folder"))
        cursor.execute("""
            INSERT OR REPLACE INTO tasks
            (id, user_id, folder_id, title, description, priority, importance, urgency,
             xp, task_date, task_time, is_done, earned_xp, created_at, completed_at,
             estimate_value, estimate_unit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task.get("id"), user_id, folder_id, task.get("title"), task.get("description"),
            task.get("priority"), task.get("importance"), task.get("urgency"),
            int(task.get("xp", 0)), empty_to_none(task.get("date")), empty_to_none(task.get("time")),
            bool_to_int(task.get("done", False)), int(task.get("earned_xp", 0)),
            task.get("created_at"), task.get("completed_at"), empty_to_none(task.get("estimate_value")),
            task.get("estimate_unit", "hours")
        ))
        for subtask in task.get("subtasks", []):
            cursor.execute("""
                INSERT OR REPLACE INTO subtasks (id, task_id, title, is_done)
                VALUES (?, ?, ?, ?)
            """, (subtask.get("id"), task.get("id"), subtask.get("title"), bool_to_int(subtask.get("done", False))))

    for achievement in user.get("achievements", []):
        code = achievement.get("code") if isinstance(achievement, dict) else achievement
        achievement_id = get_achievement_id(cursor, code)
        if achievement_id:
            received_at = achievement.get("received_at") if isinstance(achievement, dict) else datetime.now().isoformat(timespec="seconds")
            cursor.execute("""
                INSERT OR IGNORE INTO user_achievements (user_id, achievement_id, received_at)
                VALUES (?, ?, ?)
            """, (user_id, achievement_id, received_at))

    selected_badge = user.get("selected_badge")
    if selected_badge:
        badge_id = get_badge_id(cursor, selected_badge)
        if badge_id:
            cursor.execute("""
                INSERT OR IGNORE INTO user_badges (user_id, badge_id, received_at, is_selected)
                VALUES (?, ?, ?, 1)
            """, (user_id, badge_id, datetime.now().isoformat(timespec="seconds")))
            cursor.execute("UPDATE user_badges SET is_selected = 1 WHERE user_id = ? AND badge_id = ?", (user_id, badge_id))

    streak_days = user.get("_streak_days") or reconstruct_streak_days(user.get("last_activity"), int(user.get("streak", 0)))
    for activity_date in streak_days:
        cursor.execute("""
            INSERT OR IGNORE INTO user_streak_days (user_id, activity_date)
            VALUES (?, ?)
        """, (user_id, activity_date))

    focus_count = int(user.get("focus_sessions", 0))
    for _ in range(focus_count):
        cursor.execute("""
            INSERT INTO focus_sessions (user_id, task_id, duration_minutes, is_completed, created_at)
            VALUES (?, NULL, 25, 1, ?)
        """, (user_id, user.get("last_activity") or datetime.now().isoformat(timespec="seconds")))

    conn.commit()
    conn.close()


def calculate_priority(importance: str, urgency: str) -> str:
    if urgency == "urgent" and importance == "high":
        return "high"
    if urgency == "urgent" or importance == "high":
        return "medium"
    return "low"


def calculate_task_xp(importance: str, urgency: str, subtasks: List[Dict[str, Any]] | None = None) -> int:
    xp = 10
    xp += {"low": 2, "medium": 5, "high": 10}.get(importance, 5)
    xp += 10 if urgency == "urgent" else 0
    xp += 5 if subtasks else 0
    return xp

def level_state_from_xp(xp: int) -> Dict[str, int]:
    level = 1
    remaining = max(0, int(xp))
    required = 100
    total_to_current = 0
    while remaining >= required:
        remaining -= required
        total_to_current += required
        level += 1
        required += 50
    progress = round((remaining / required) * 100) if required else 0
    return {"level": level, "current_xp": remaining, "required_xp": required, "progress": progress, "total_to_current": total_to_current}


def level_from_xp(xp: int) -> int:
    return level_state_from_xp(xp)["level"]


def progress_to_next_level(xp: int) -> int:
    return level_state_from_xp(xp)["progress"]

def available_badge_codes(user: Dict[str, Any]) -> List[str]:
    level = level_from_xp(int(user.get("xp", 0)))
    focus_sessions = int(user.get("focus_sessions", 0))
    codes = []
    for badge in BADGES:
        required_level = int(badge.get("required_level", 999))
        required_focus = badge.get("focus_sessions")
        if level >= required_level or (required_focus and focus_sessions >= int(required_focus)):
            codes.append(badge["code"])
    return codes


