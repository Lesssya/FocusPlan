from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Any, Dict, List

from flask import Flask, redirect, render_template, request, session, url_for, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "focus-plan-demo-secret-key"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DATA_FILE = os.path.join(DATA_DIR, "store.json")

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

MONTH_NAMES = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


def ensure_store() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump({"users": {}}, file, ensure_ascii=False, indent=2)


def load_store() -> Dict[str, Any]:
    ensure_store()
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return {"users": {}}


def save_store(store: Dict[str, Any]) -> None:
    ensure_store()
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(store, file, ensure_ascii=False, indent=2)


def get_today() -> str:
    return date.today().isoformat()


def get_yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def format_date(value: str | None) -> str:
    if not value:
        return "Без даты"
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d.%m.%Y")
    except ValueError:
        return value


def month_label(value: date) -> str:
    return f"{MONTH_NAMES[value.month]} {value.year}"


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


def normalize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    user.setdefault("password_hash", None)
    user.setdefault("settings", DEFAULT_SETTINGS.copy())
    user["settings"]["theme"] = "light"
    user.setdefault("folders", DEFAULT_FOLDERS.copy())
    for folder in DEFAULT_FOLDERS:
        if folder not in user["folders"]:
            user["folders"].append(folder)
    user.setdefault("achievements", [])
    user.setdefault("focus_sessions", 0)
    user.setdefault("selected_badge", None)
    if user.get("selected_badge") and user["selected_badge"] not in available_badge_codes(user):
        user["selected_badge"] = None
    for task in user.get("tasks", []):
        task.setdefault("id", str(uuid.uuid4()))
        task.setdefault("description", "")
        task.setdefault("subtasks", [])
        task.setdefault("attachments", [])
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
    return user


def current_user() -> Dict[str, Any] | None:
    nickname = session.get("nickname")
    if not nickname:
        return None
    store = load_store()
    if nickname not in store["users"]:
        store["users"][nickname] = create_user(nickname)
    user = normalize_user(store["users"][nickname])
    store["users"][nickname] = user
    save_store(store)
    return user


def update_current_user(user: Dict[str, Any]) -> None:
    nickname = session.get("nickname")
    if not nickname:
        return
    store = load_store()
    store["users"][nickname] = normalize_user(user)
    save_store(store)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("nickname"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


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


def register_activity(user: Dict[str, Any]) -> Dict[str, Any]:
    today = get_today()
    yesterday = get_yesterday()
    last_activity = user.get("last_activity")
    if last_activity == today:
        pass
    elif last_activity == yesterday:
        user["streak"] = int(user.get("streak", 0)) + 1
    else:
        user["streak"] = 1
    user["last_activity"] = today
    return user


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


def add_xp(user: Dict[str, Any], xp: int) -> bool:
    old_level = level_from_xp(int(user.get("xp", 0)))
    user["xp"] = max(0, int(user.get("xp", 0)) + int(xp))
    new_level = level_from_xp(int(user.get("xp", 0)))
    return new_level > old_level


def achievement_by_code(code: str) -> Dict[str, Any] | None:
    return next((item for item in ACHIEVEMENTS if item["code"] == code), None)


def badge_by_code(code: str) -> Dict[str, Any] | None:
    return next((item for item in BADGES if item["code"] == code), None)


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


def unlocked_achievement_codes(user: Dict[str, Any]) -> List[str]:
    return [item.get("code") if isinstance(item, dict) else item for item in user.get("achievements", [])]


def unlock_achievement(user: Dict[str, Any], code: str) -> int:
    achievement = achievement_by_code(code)
    if not achievement or code in unlocked_achievement_codes(user):
        return 0
    user.setdefault("achievements", []).append({"code": code, "received_at": datetime.now().isoformat(timespec="seconds")})
    add_xp(user, int(achievement.get("xp", 0)))
    session.setdefault("toasts", []).append(f"Достижение открыто: {achievement['title']} (+{achievement['xp']} XP)")
    return int(achievement.get("xp", 0))


def check_level_achievement(user: Dict[str, Any], level_up: bool) -> int:
    if level_up:
        return unlock_achievement(user, "new_level")
    return 0


def check_task_achievements(user: Dict[str, Any], task: Dict[str, Any]) -> int:
    bonus = 0
    completed_tasks = [item for item in user.get("tasks", []) if item.get("done")]
    completed_today = [item for item in completed_tasks if str(item.get("completed_at", "")).startswith(get_today())]
    if len(completed_tasks) >= 1:
        bonus += unlock_achievement(user, "first_task")
    if len(completed_tasks) >= 10:
        bonus += unlock_achievement(user, "ten_tasks")
    if len(completed_today) >= 5:
        bonus += unlock_achievement(user, "productive_day")
    if int(user.get("streak", 0)) >= 3:
        bonus += unlock_achievement(user, "three_day_streak")
    if task.get("urgency") == "urgent" and task.get("importance") == "high":
        bonus += unlock_achievement(user, "urgent_important")
    return bonus


def check_focus_achievements(user: Dict[str, Any]) -> int:
    bonus = 0
    if int(user.get("focus_sessions", 0)) >= 1:
        bonus += unlock_achievement(user, "first_focus")
    if int(user.get("streak", 0)) >= 3:
        bonus += unlock_achievement(user, "three_day_streak")
    return bonus


def task_stats(tasks: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(tasks)
    done = len([task for task in tasks if task.get("done")])
    progress = round((done / total) * 100) if total else 0
    return {"total": total, "done": done, "active": total - done, "progress": progress}


def split_eisenhower(tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    matrix = {"urgent_important": [], "not_urgent_important": [], "urgent_not_important": [], "not_urgent_not_important": []}
    for task in tasks:
        important = task.get("importance") in ["medium", "high"]
        urgent = task.get("urgency") == "urgent"
        if important and urgent:
            matrix["urgent_important"].append(task)
        elif important and not urgent:
            matrix["not_urgent_important"].append(task)
        elif not important and urgent:
            matrix["urgent_not_important"].append(task)
        else:
            matrix["not_urgent_not_important"].append(task)
    return matrix


def save_uploaded_file(file_storage, task_id: str, kind: str = "file") -> Dict[str, str] | None:
    if not file_storage or not file_storage.filename:
        return None
    safe_name = secure_filename(file_storage.filename)
    if not safe_name:
        return None
    folder = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(folder, exist_ok=True)
    stored_name = f"{kind}_{uuid.uuid4().hex[:8]}_{safe_name}"
    file_storage.save(os.path.join(folder, stored_name))
    return {"name": file_storage.filename, "stored": stored_name, "kind": kind}


def get_subtasks_from_form(existing: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    existing_by_title = {item.get("title", "").strip(): item for item in (existing or []) if item.get("title")}
    titles = [x.strip() for x in request.form.getlist("subtask_items") if x.strip()]
    if not titles:
        raw = request.form.get("subtasks", "")
        titles = [x.strip() for x in raw.replace(";", "\n").splitlines() if x.strip()]
    subtasks = []
    for title in titles:
        old = existing_by_title.get(title)
        subtasks.append({"id": old.get("id") if old else str(uuid.uuid4()), "title": title, "done": bool(old.get("done")) if old else False})
    return subtasks


def find_task(user: Dict[str, Any], task_id: str) -> Dict[str, Any] | None:
    for task in user.get("tasks", []):
        if task.get("id") == task_id:
            return task
    return None



def build_reminder_tasks(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    reminder_tasks = []

    for task in user.get("tasks", []):
        if task.get("done") or not task.get("date"):
            continue

        reminder_tasks.append({
            "id": task.get("id"),
            "title": task.get("title", "Задача"),
            "date": task.get("date", ""),
            "time": task.get("time", ""),
            "estimate_value": task.get("estimate_value", ""),
            "estimate_unit": task.get("estimate_unit", "hours"),
        })

    return reminder_tasks

def complete_task_with_rewards(user: Dict[str, Any], task: Dict[str, Any]) -> int:
    if not task or task.get("done"):
        return 0

    task["done"] = True
    earned = int(task.get("xp", 10))
    task["earned_xp"] = earned
    task["completed_at"] = datetime.now().isoformat(timespec="seconds")

    add_xp(user, earned)
    earned += check_task_achievements(user, task)

    return earned


@app.context_processor
def inject_user_data():
    user = current_user()
    base = {"current_endpoint": request.endpoint, "format_date": format_date, "estimate_unit_labels": ESTIMATE_UNIT_LABELS}
    if not user:
        return base
    settings = user.get("settings", DEFAULT_SETTINGS)
    settings["theme"] = "light"
    level_state = level_state_from_xp(int(user.get("xp", 0)))
    unlocked_codes = unlocked_achievement_codes(user)
    available_badges = available_badge_codes(user)
    active_badge = badge_by_code(user.get("selected_badge")) if user.get("selected_badge") in available_badges else None
    base.update({
        "user": user,
        "settings": settings,
        "level": level_state["level"],
        "level_current_xp": level_state["current_xp"],
        "level_required_xp": level_state["required_xp"],
        "level_progress": level_state["progress"],
        "priority_labels": PRIORITY_LABELS,
        "importance_labels": IMPORTANCE_LABELS,
        "urgency_labels": URGENCY_LABELS,
        "achievements_catalog": ACHIEVEMENTS,
        "badges_catalog": BADGES,
        "unlocked_achievement_codes": unlocked_codes,
        "available_badge_codes": available_badges,
        "active_badge": active_badge,
        "profile_avatar": active_badge["icon"] if active_badge else user.get("avatar", "F"),
        "confetti": session.pop("confetti", None),
        "toasts": session.pop("toasts", []),
        "reminder_tasks": build_reminder_tasks(user) if settings.get("notifications", True) else [],
        "notifications_enabled": bool(settings.get("notifications", True)),
    })
    return base


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        password = request.form.get("password", "")

        if not nickname:
            return render_template("login.html", error="Введите никнейм для входа")
        if not password:
            return render_template("login.html", error="Введите пароль")

        store = load_store()
        user = store["users"].get(nickname)

        if not user:
            store["users"][nickname] = create_user(
                nickname,
                password_hash=generate_password_hash(password)
            )
            save_store(store)
            session["nickname"] = nickname
            return redirect(url_for("dashboard"))

        user = normalize_user(user)
        saved_hash = user.get("password_hash")

        # Для старых профилей без пароля: первый введённый пароль становится паролем профиля.
        if not saved_hash:
            user["password_hash"] = generate_password_hash(password)
            store["users"][nickname] = user
            save_store(store)
            session["nickname"] = nickname
            return redirect(url_for("dashboard"))

        if not check_password_hash(saved_hash, password):
            return render_template("login.html", error="Неверный пароль")

        store["users"][nickname] = user
        save_store(store)
        session["nickname"] = nickname
        return redirect(url_for("dashboard"))

    if session.get("nickname"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    today = get_today()

    # На главной показываем:
    # 1) задачи на сегодня;
    # 2) задачи без даты, но только если они ещё не выполнены.
    visible_tasks = [
        t for t in user.get("tasks", [])
        if (
            t.get("date") == today
            or (not t.get("date") and not t.get("done", False))
        )
    ]

    visible_tasks = sorted(
        visible_tasks,
        key=lambda task: (
            task.get("done", False),
            0 if task.get("date") == today else 1,
            task.get("time") or "99:99"
        )
    )

    today_tasks = [t for t in visible_tasks if t.get("date") == today]
    no_date_tasks = [
        t for t in visible_tasks
        if not t.get("date") and not t.get("done", False)
    ]

    return render_template(
        "dashboard.html",
        tasks=visible_tasks,
        today_tasks=today_tasks,
        no_date_tasks=no_date_tasks,
        stats=task_stats(visible_tasks),
        today=today
    )

@app.route("/tasks")
@login_required
def tasks_page():
    user = current_user()
    active_filter = request.args.get("filter", "all")
    active_folder = request.args.get("folder", "all")

    tasks = list(user.get("tasks", []))

    if active_filter == "dated":
        tasks = [t for t in tasks if t.get("date")]
    elif active_filter == "nodate":
        tasks = [t for t in tasks if not t.get("date")]

    if active_folder != "all":
        tasks = [t for t in tasks if t.get("folder") == active_folder]

    active_tasks = sorted(
        [t for t in tasks if not t.get("done")],
        key=lambda task: (task.get("date") or "9999-99-99", task.get("time") or "99:99")
    )
    completed_tasks = sorted(
        [t for t in tasks if t.get("done")],
        key=lambda task: (task.get("completed_at") or task.get("date") or "", task.get("time") or ""),
        reverse=True
    )

    return render_template(
        "tasks.html",
        tasks=tasks,
        active_tasks=active_tasks,
        completed_tasks=completed_tasks,
        active_filter=active_filter,
        active_folder=active_folder,
        folders=user.get("folders", [])
    )


@app.route("/folders/add", methods=["POST"])
@login_required
def add_folder():
    user = current_user()
    folder = request.form.get("folder", "").strip()
    if folder and folder not in user.get("folders", []):
        user.setdefault("folders", []).append(folder)
        update_current_user(user)
    return redirect(url_for("tasks_page"))


def task_from_form(task_id: str, existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
    importance = request.form.get("importance", "medium")
    urgency = request.form.get("urgency", "not_urgent")
    priority = calculate_priority(importance, urgency)
    subtasks = get_subtasks_from_form((existing or {}).get("subtasks", []))
    attachments = []
    return {
        "id": task_id,
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "subtasks": subtasks,
        "priority": priority,
        "importance": importance,
        "urgency": urgency,
        "xp": calculate_task_xp(importance, urgency, subtasks),
        "date": request.form.get("date") or "",
        "time": request.form.get("time") or "",
        "estimate_value": request.form.get("estimate_value", "").strip(),
        "estimate_unit": request.form.get("estimate_unit", "hours"),
        "folder": request.form.get("new_folder", "").strip() or request.form.get("folder", "").strip(),
        "attachments": attachments,
        "done": bool((existing or {}).get("done", False)),
        "earned_xp": int((existing or {}).get("earned_xp", 0)),
        "created_at": (existing or {}).get("created_at", datetime.now().isoformat(timespec="seconds")),
        "completed_at": (existing or {}).get("completed_at"),
    }


@app.route("/tasks/add", methods=["POST"])
@login_required
def add_task():
    user = current_user()
    task_id = str(uuid.uuid4())
    task = task_from_form(task_id)
    if task["title"]:
        if task.get("folder") and task["folder"] not in user.get("folders", []):
            user.setdefault("folders", []).append(task["folder"])
        user.setdefault("tasks", []).append(task)
        update_current_user(user)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/tasks/<task_id>/edit", methods=["POST"])
@login_required
def edit_task(task_id: str):
    user = current_user()
    task = find_task(user, task_id)
    if not task:
        return redirect(url_for("tasks_page"))
    old_earned = int(task.get("earned_xp", 0))
    updated = task_from_form(task_id, existing=task)
    if updated.get("folder") and updated["folder"] not in user.get("folders", []):
        user.setdefault("folders", []).append(updated["folder"])
    # Если выполненная задача изменила ценность XP, корректируем уже начисленный опыт.
    if updated.get("done"):
        diff = int(updated.get("xp", 0)) - old_earned
        updated["earned_xp"] = int(updated.get("xp", 0))
        user["xp"] = max(0, int(user.get("xp", 0)) + diff)
    for idx, item in enumerate(user.get("tasks", [])):
        if item.get("id") == task_id:
            user["tasks"][idx] = updated
            break
    update_current_user(user)
    return redirect(request.referrer or url_for("tasks_page"))


@app.route("/tasks/<task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(task_id: str):
    user = current_user()
    earned = 0
    for task in user.get("tasks", []):
        if task.get("id") == task_id:
            was_done = bool(task.get("done", False))
            task["done"] = not was_done
            if task["done"]:
                old_level = level_from_xp(int(user.get("xp", 0)))
                earned = int(task.get("xp", 10))
                task["earned_xp"] = earned
                task["completed_at"] = datetime.now().isoformat(timespec="seconds")
                user = register_activity(user)
                add_xp(user, earned)
                earned += check_task_achievements(user, task)
                earned += check_level_achievement(user, level_from_xp(int(user.get("xp", 0))) > old_level)
            else:
                lost = int(task.get("earned_xp", 0))
                user["xp"] = max(0, int(user.get("xp", 0)) - lost)
                task["earned_xp"] = 0
                task.pop("completed_at", None)
            break
    update_current_user(user)
    if earned:
        session["confetti"] = {"earned": earned}
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/tasks/<task_id>/subtasks/<subtask_id>/toggle", methods=["POST"])
@login_required
def toggle_subtask(task_id: str, subtask_id: str):
    user = current_user()
    task = find_task(user, task_id)
    if task:
        for subtask in task.get("subtasks", []):
            if subtask.get("id") == subtask_id:
                subtask["done"] = not subtask.get("done", False)
                break
    update_current_user(user)
    return redirect(request.referrer or url_for("tasks_page"))


@app.route("/tasks/<task_id>/delete", methods=["POST"])
@login_required
def delete_task(task_id: str):
    user = current_user()
    task = find_task(user, task_id)
    if task and task.get("done"):
        user["xp"] = max(0, int(user.get("xp", 0)) - int(task.get("earned_xp", 0)))
    user["tasks"] = [task for task in user.get("tasks", []) if task.get("id") != task_id]
    update_current_user(user)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/calendar")
@login_required
def calendar():
    user = current_user()
    tasks = sorted(
        [t for t in user.get("tasks", []) if t.get("date")],
        key=lambda task: (task.get("date"), task.get("time") or "99:99")
    )
    no_date_tasks = [t for t in user.get("tasks", []) if not t.get("date")]

    selected_view = request.args.get("view", "week")
    if selected_view not in ["day", "week", "month"]:
        selected_view = "week"

    today = date.today()

    # Основная дата календаря. Именно она переключается стрелками в режимах
    # "День" и "Неделя". Для месяца используется первый день выбранного месяца.
    raw_date = request.args.get("date")
    raw_month = request.args.get("month")
    selected_date = today
    if raw_date:
        try:
            selected_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today
    elif raw_month:
        try:
            selected_date = datetime.strptime(raw_month, "%Y-%m").date()
        except ValueError:
            selected_date = today

    selected_month = selected_date.replace(day=1)
    previous_month = (selected_month - timedelta(days=1)).replace(day=1)
    next_month = (selected_month.replace(day=28) + timedelta(days=4)).replace(day=1)

    if selected_view == "day":
        previous_date = selected_date - timedelta(days=1)
        next_date = selected_date + timedelta(days=1)
    elif selected_view == "week":
        previous_date = selected_date - timedelta(days=7)
        next_date = selected_date + timedelta(days=7)
    else:
        previous_date = previous_month
        next_date = next_month

    start_of_week = selected_date - timedelta(days=selected_date.weekday())
    week_days = [(start_of_week + timedelta(days=i)).isoformat() for i in range(7)]

    month_days_count = (next_month - selected_month).days
    month_days = [(selected_month + timedelta(days=i)).isoformat() for i in range(month_days_count)]
    month_leading_blanks = selected_month.weekday()

    early_hours = list(range(0, 8))
    hours = list(range(8, 20))
    late_hours = list(range(20, 24))

    selected_day = selected_date.isoformat()
    today_iso = today.isoformat()
    now = datetime.now()

    def count_timed_tasks(day_list: List[str], hour_list: List[int]) -> int:
        return len([
            task for task in tasks
            if task.get("date") in day_list
            and task.get("time")
            and int(str(task.get("time", "00:00"))[:2]) in hour_list
        ])

    early_count = count_timed_tasks([selected_day] if selected_view == "day" else week_days, early_hours)
    late_count = count_timed_tasks([selected_day] if selected_view == "day" else week_days, late_hours)

    if selected_view == "month":
        period_title = month_label(selected_month)
    elif selected_view == "day":
        period_title = format_date(selected_day)
    else:
        period_title = f"{format_date(week_days[0])} — {format_date(week_days[6])}"

    return render_template(
        "calendar.html",
        tasks=tasks,
        no_date_tasks=no_date_tasks,
        week_days=week_days,
        month_days=month_days,
        month_leading_blanks=month_leading_blanks,
        early_hours=early_hours,
        hours=hours,
        late_hours=late_hours,
        early_count=early_count,
        late_count=late_count,
        today=today_iso,
        selected_day=selected_day,
        selected_view=selected_view,
        current_hour=now.hour,
        current_minute=now.minute,
        month_title=month_label(selected_month),
        period_title=period_title,
        selected_month=selected_month.strftime("%Y-%m"),
        selected_date=selected_day,
        previous_date=previous_date.isoformat(),
        next_date=next_date.isoformat(),
        today_date=today_iso,
        previous_month=previous_month.strftime("%Y-%m"),
        next_month=next_month.strftime("%Y-%m")
    )


@app.route("/matrix")
@login_required
def matrix():
    user = current_user()
    tasks = [task for task in user.get("tasks", []) if not task.get("done")]
    return render_template("matrix.html", matrix=split_eisenhower(tasks))


@app.route("/focus")
@login_required
def focus():
    user = current_user()
    active_tasks = [task for task in user.get("tasks", []) if not task.get("done")]
    return render_template("focus.html", active_tasks=active_tasks)


@app.route("/focus/complete", methods=["POST"])
@login_required
def complete_focus():
    user = current_user()
    old_level = level_from_xp(int(user.get("xp", 0)))

    focus_task_id = request.form.get("focus_task_id", "").strip()
    complete_selected_task = request.form.get("complete_task") == "1"

    user = register_activity(user)
    user["focus_sessions"] = int(user.get("focus_sessions", 0)) + 1

    add_xp(user, 25)
    earned = 25
    earned += check_focus_achievements(user)

    completed_task_title = None
    if complete_selected_task and focus_task_id:
        task = find_task(user, focus_task_id)
        if task and not task.get("done"):
            completed_task_title = task.get("title")
            earned += complete_task_with_rewards(user, task)

    earned += check_level_achievement(user, level_from_xp(int(user.get("xp", 0))) > old_level)

    update_current_user(user)

    message = f"Фокус-сессия завершена! +{earned} XP"
    if completed_task_title:
        message = f"Фокус-сессия завершена, задача «{completed_task_title}» выполнена! +{earned} XP"

    session["confetti"] = {"earned": earned, "message": message}
    return redirect(url_for("focus"))


@app.route("/achievements")
@login_required
def achievements_page():
    user = current_user()
    return render_template("achievements.html", focus_sessions=int(user.get("focus_sessions", 0)))


@app.route("/badges/select", methods=["POST"])
@login_required
def select_badge():
    user = current_user()
    badge_code = request.form.get("badge_code") or None
    if not badge_code or badge_code == "none":
        user["selected_badge"] = None
    elif badge_code in available_badge_codes(user):
        user["selected_badge"] = badge_code
        badge = badge_by_code(badge_code)
        if badge:
            session.setdefault("toasts", []).append(f"Бейдж «{badge['title']}» установлен в профиль")
    update_current_user(user)
    return redirect(request.referrer or url_for("achievements_page"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        old_nickname = session.get("nickname")
        new_nickname = request.form.get("nickname", old_nickname).strip() or old_nickname
        store = load_store()
        if new_nickname != old_nickname and new_nickname in store["users"]:
            return render_template("profile.html", error="Такой никнейм уже используется. Попробуйте другой вариант.")
        user["nickname"] = new_nickname
        selected_badge = request.form.get("selected_badge") or None
        if selected_badge and selected_badge not in available_badge_codes(user):
            selected_badge = user.get("selected_badge")
        user["selected_badge"] = selected_badge
        user["avatar"] = request.form.get("avatar", "").strip()[:2].upper() or new_nickname[:1].upper()
        user["settings"] = {"theme": "light", "accent": request.form.get("accent", "purple"), "notifications": bool(request.form.get("notifications"))}
        if new_nickname != old_nickname:
            store["users"].pop(old_nickname, None)
            session["nickname"] = new_nickname
        store["users"][new_nickname] = normalize_user(user)
        save_store(store)
        return redirect(url_for("profile"))
    return render_template("profile.html")


@app.route("/uploads/<task_id>/<filename>")
@login_required
def uploaded_file(task_id: str, filename: str):
    return send_from_directory(os.path.join(UPLOAD_DIR, task_id), filename, as_attachment=True)


if __name__ == "__main__":
    ensure_store()
    app.run(debug=True)
