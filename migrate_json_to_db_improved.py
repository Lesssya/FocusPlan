import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


# Путь к исходному JSON-файлу и будущей SQLite-базе
JSON_PATH = Path("data/store.json")
DB_PATH = Path("focusplan.db")

# Если True, старая база будет сохранена как резервная копия и создана заново.
# Это удобно для миграции: данные заново переносятся из store.json без дублей.
RESET_DATABASE = True


ACHIEVEMENTS = [
    ("first_task", "Первый шаг", "Пользователь выполнил первую задачу", "completed_tasks", 1),
    ("productive_day", "Продуктивный день", "Пользователь выполнил несколько задач за день", "completed_tasks_day", 5),
    ("new_level", "Новый уровень", "Пользователь достиг нового уровня", "level", 2),
    ("ten_tasks", "10 задач", "Пользователь выполнил 10 задач", "completed_tasks", 10),
    ("urgent_important", "Срочно и важно", "Пользователь выполнил срочную и важную задачу", "urgent_important_task", 1),
    ("first_focus", "Первый фокус", "Пользователь завершил первую фокус-сессию", "focus_sessions", 1),
    ("three_day_streak", "3 дня подряд", "Пользователь был активен 3 дня подряд", "streak", 3),
]


BADGES = [
    ("newbie", "Новичок", "Бейдж за начало работы с приложением", "🌱"),
    ("regular_planner", "Постоянный планировщик", "Бейдж за регулярное выполнение задач", "📅"),
    ("focus_master", "Мастер фокуса", "Бейдж за использование фокус-режима", "🎯"),
]


def empty_to_none(value):
    """Преобразует пустые строки в None, чтобы в БД было NULL."""
    if value == "":
        return None
    return value


def bool_to_int(value):
    """SQLite хранит boolean как 0/1."""
    return 1 if value else 0


def calculate_level(xp):
    """Простой расчет уровня по опыту: 1 уровень на каждые 100 XP."""
    return max(1, int(xp or 0) // 100 + 1)


def make_backup_and_reset_db():
    """Создает резервную копию старой БД и удаляет её перед новой миграцией."""
    if RESET_DATABASE and DB_PATH.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = DB_PATH.with_name(f"{DB_PATH.stem}_backup_{timestamp}{DB_PATH.suffix}")
        shutil.copy2(DB_PATH, backup_path)
        DB_PATH.unlink()
        print(f"Старая база сохранена как {backup_path}")


def create_tables(cursor):
    cursor.execute("PRAGMA foreign_keys = ON;")

    cursor.execute("""
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
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, title)
    );
    """)

    cursor.execute("""
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
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subtasks (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        title TEXT NOT NULL,
        is_done INTEGER DEFAULT 0,
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    );
    """)

    cursor.execute("""
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
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT,
        condition_type TEXT,
        condition_value INTEGER
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        achievement_id INTEGER NOT NULL,
        received_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (achievement_id) REFERENCES achievements(id),
        UNIQUE(user_id, achievement_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        description TEXT,
        icon TEXT
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        badge_id INTEGER NOT NULL,
        received_at TEXT,
        is_selected INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (badge_id) REFERENCES badges(id),
        UNIQUE(user_id, badge_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_streak_days (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        activity_date DATE NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE(user_id, activity_date)
    );
    """)


def seed_achievements(cursor):
    cursor.executemany("""
        INSERT OR IGNORE INTO achievements
        (code, title, description, condition_type, condition_value)
        VALUES (?, ?, ?, ?, ?);
    """, ACHIEVEMENTS)


def seed_badges(cursor):
    cursor.executemany("""
        INSERT OR IGNORE INTO badges
        (code, title, description, icon)
        VALUES (?, ?, ?, ?);
    """, BADGES)


def get_user_id(cursor, nickname):
    cursor.execute("SELECT id FROM users WHERE nickname = ?", (nickname,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_folder_id(cursor, user_id, title):
    if not title:
        return None

    cursor.execute(
        "SELECT id FROM folders WHERE user_id = ? AND title = ?",
        (user_id, title)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def get_achievement_id(cursor, code):
    cursor.execute("SELECT id FROM achievements WHERE code = ?", (code,))
    result = cursor.fetchone()
    return result[0] if result else None


def get_badge_id(cursor, code):
    cursor.execute("SELECT id FROM badges WHERE code = ?", (code,))
    result = cursor.fetchone()
    return result[0] if result else None


def add_reconstructed_streak_days(cursor, user_id, last_activity, streak):
    """
    В store.json хранится только текущий streak и последняя дата активности.
    Полной истории дней там нет, поэтому мы восстанавливаем минимальную историю:
    если streak = 3 и last_activity = 2026-06-01, добавляем 2026-05-30, 2026-05-31, 2026-06-01.
    Это сохраняет текущую серию, но не является полной реальной историей активности.
    """
    if not last_activity or not streak:
        return

    try:
        end_date = datetime.strptime(last_activity, "%Y-%m-%d").date()
    except ValueError:
        return

    streak = int(streak)
    if streak <= 0:
        return

    start_date = end_date - timedelta(days=streak - 1)

    for i in range(streak):
        activity_date = start_date + timedelta(days=i)
        cursor.execute("""
            INSERT OR IGNORE INTO user_streak_days
            (user_id, activity_date)
            VALUES (?, ?);
        """, (user_id, activity_date.isoformat()))


def add_focus_session_placeholders(cursor, user_id, focus_sessions_count, last_activity):
    """
    В store.json хранится только количество фокус-сессий, без времени и длительности.
    Поэтому для сохранения факта этих сессий создаются технические записи-заглушки.
    duration_minutes остается NULL, is_completed = 1.
    """
    try:
        count = int(focus_sessions_count or 0)
    except (TypeError, ValueError):
        count = 0

    for _ in range(count):
        cursor.execute("""
            INSERT INTO focus_sessions
            (user_id, task_id, duration_minutes, is_completed, created_at)
            VALUES (?, ?, ?, ?, ?);
        """, (user_id, None, None, 1, last_activity))


def migrate():
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"Файл {JSON_PATH} не найден")

    make_backup_and_reset_db()

    with open(JSON_PATH, "r", encoding="utf-8") as file:
        data = json.load(file)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    create_tables(cursor)
    seed_achievements(cursor)
    seed_badges(cursor)

    users_data = data.get("users", {})

    for nickname, user_data in users_data.items():
        settings = user_data.get("settings", {})
        user_xp = user_data.get("xp", 0)

        cursor.execute("""
            INSERT OR IGNORE INTO users
            (nickname, password_hash, avatar, theme, accent, notifications, xp, level, streak, last_activity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            user_data.get("nickname", nickname),
            user_data.get("password_hash"),
            user_data.get("avatar"),
            settings.get("theme", "light"),
            settings.get("accent", "purple"),
            bool_to_int(settings.get("notifications", True)),
            user_xp,
            calculate_level(user_xp),
            user_data.get("streak", 0),
            user_data.get("last_activity"),
            user_data.get("created_at")
        ))

        user_id = get_user_id(cursor, user_data.get("nickname", nickname))
        if user_id is None:
            print(f"Не удалось создать пользователя: {nickname}")
            continue

        # Папки пользователя
        for folder_title in user_data.get("folders", []):
            cursor.execute("""
                INSERT OR IGNORE INTO folders
                (user_id, title)
                VALUES (?, ?);
            """, (user_id, folder_title))

        # Задачи и подзадачи
        for task in user_data.get("tasks", []):
            folder_id = get_folder_id(cursor, user_id, task.get("folder"))

            cursor.execute("""
                INSERT OR IGNORE INTO tasks
                (id, user_id, folder_id, title, description, priority, importance, urgency,
                 xp, task_date, task_time, is_done, earned_xp, created_at, completed_at,
                 estimate_value, estimate_unit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                task.get("id"),
                user_id,
                folder_id,
                task.get("title"),
                task.get("description"),
                task.get("priority"),
                task.get("importance"),
                task.get("urgency"),
                task.get("xp", 0),
                empty_to_none(task.get("date")),
                empty_to_none(task.get("time")),
                bool_to_int(task.get("done", False)),
                task.get("earned_xp", 0),
                task.get("created_at"),
                task.get("completed_at"),
                empty_to_none(task.get("estimate_value")),
                task.get("estimate_unit", "hours")
            ))

            for subtask in task.get("subtasks", []):
                cursor.execute("""
                    INSERT OR IGNORE INTO subtasks
                    (id, task_id, title, is_done)
                    VALUES (?, ?, ?, ?);
                """, (
                    subtask.get("id"),
                    task.get("id"),
                    subtask.get("title"),
                    bool_to_int(subtask.get("done", False))
                ))

        # Достижения пользователя
        for achievement in user_data.get("achievements", []):
            achievement_id = get_achievement_id(cursor, achievement.get("code"))

            if achievement_id:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_achievements
                    (user_id, achievement_id, received_at)
                    VALUES (?, ?, ?);
                """, (
                    user_id,
                    achievement_id,
                    achievement.get("received_at")
                ))

        # Выбранный бейдж пользователя
        selected_badge_code = user_data.get("selected_badge")

        if selected_badge_code:
            badge_id = get_badge_id(cursor, selected_badge_code)

            if badge_id:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_badges
                    (user_id, badge_id, received_at, is_selected)
                    VALUES (?, ?, ?, ?);
                """, (
                    user_id,
                    badge_id,
                    user_data.get("last_activity"),
                    1
                ))

        # Восстановление текущей серии streak по last_activity и streak
        add_reconstructed_streak_days(
            cursor,
            user_id,
            user_data.get("last_activity"),
            user_data.get("streak", 0)
        )

        # Перенос количества фокус-сессий в виде технических записей-заглушек
        add_focus_session_placeholders(
            cursor,
            user_id,
            user_data.get("focus_sessions", 0),
            user_data.get("last_activity")
        )

    conn.commit()
    conn.close()

    print(f"Готово! Данные перенесены из {JSON_PATH} в {DB_PATH}")


if __name__ == "__main__":
    migrate()
