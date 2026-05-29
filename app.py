from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta
from functools import wraps
from typing import Any, Dict, List

from flask import Flask, redirect, render_template, request, session, url_for, send_from_directory
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


def create_user(nickname: str) -> Dict[str, Any]:
    return {
        "nickname": nickname,
        "avatar": nickname[:1].upper() if nickname else "F",
        "settings": DEFAULT_SETTINGS.copy(),
        "folders": DEFAULT_FOLDERS.copy(),
        "tasks": [],
        "xp": 0,
        "streak": 0,
        "last_activity": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def normalize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    user.setdefault("settings", DEFAULT_SETTINGS.copy())
    user["settings"]["theme"] = "light"
    user.setdefault("folders", DEFAULT_FOLDERS.copy())
    for folder in DEFAULT_FOLDERS:
        if folder not in user["folders"]:
            user["folders"].append(folder)
    for task in user.get("tasks", []):
        task.setdefault("id", str(uuid.uuid4()))
        task.setdefault("description", "")
        task.setdefault("subtasks", [])
        task.setdefault("attachments", [])
        task.setdefault("folder", "Учёба")
        task.setdefault("priority", "medium")
        task.setdefault("importance", "medium")
        task.setdefault("urgency", "not_urgent")
        task.setdefault("date", "")
        task.setdefault("time", "")
        task.setdefault("done", False)
        task["xp"] = calculate_task_xp(task.get("priority", "medium"), task.get("importance", "medium"), task.get("urgency", "not_urgent"))
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


def calculate_task_xp(priority: str, importance: str, urgency: str) -> int:
    xp = 10
    xp += {"low": 0, "medium": 10, "high": 20}.get(priority, 10)
    xp += {"low": 0, "medium": 10, "high": 25}.get(importance, 10)
    xp += 15 if urgency == "urgent" else 0
    return xp


def register_activity(user: Dict[str, Any], xp: int = 5) -> Dict[str, Any]:
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
    user["xp"] = max(0, int(user.get("xp", 0)) + xp)
    return user


def level_from_xp(xp: int) -> int:
    return max(1, xp // 100 + 1)


def progress_to_next_level(xp: int) -> int:
    return xp % 100


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


@app.context_processor
def inject_user_data():
    user = current_user()
    base = {"current_endpoint": request.endpoint, "format_date": format_date}
    if not user:
        return base
    settings = user.get("settings", DEFAULT_SETTINGS)
    settings["theme"] = "light"
    base.update({
        "user": user,
        "settings": settings,
        "level": level_from_xp(int(user.get("xp", 0))),
        "level_progress": progress_to_next_level(int(user.get("xp", 0))),
        "priority_labels": PRIORITY_LABELS,
        "importance_labels": IMPORTANCE_LABELS,
        "urgency_labels": URGENCY_LABELS,
        "confetti": session.pop("confetti", None),
    })
    return base


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        if not nickname:
            return render_template("login.html", error="Введите никнейм для входа")
        store = load_store()
        if nickname not in store["users"]:
            store["users"][nickname] = create_user(nickname)
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
    visible_tasks = [t for t in user.get("tasks", []) if t.get("date") in [today, "", None]]
    visible_tasks = sorted(visible_tasks, key=lambda task: (task.get("done", False), 0 if task.get("date") == today else 1, task.get("time") or "99:99"))
    today_tasks = [t for t in visible_tasks if t.get("date") == today]
    no_date_tasks = [t for t in visible_tasks if not t.get("date")]
    return render_template("dashboard.html", tasks=visible_tasks, today_tasks=today_tasks, no_date_tasks=no_date_tasks, stats=task_stats(visible_tasks), today=today)


@app.route("/tasks")
@login_required
def tasks_page():
    user = current_user()
    active_filter = request.args.get("filter", "all")
    active_folder = request.args.get("folder", "all")
    tasks = sorted(user.get("tasks", []), key=lambda task: (task.get("done", False), task.get("date") or "9999-99-99", task.get("time") or "99:99"))
    if active_filter == "dated":
        tasks = [t for t in tasks if t.get("date")]
    elif active_filter == "nodate":
        tasks = [t for t in tasks if not t.get("date")]
    if active_folder != "all":
        tasks = [t for t in tasks if t.get("folder") == active_folder]
    return render_template("tasks.html", tasks=tasks, active_filter=active_filter, active_folder=active_folder, folders=user.get("folders", []))


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
    priority = request.form.get("priority", "medium")
    importance = request.form.get("importance", "medium")
    urgency = request.form.get("urgency", "not_urgent")
    attachments = list((existing or {}).get("attachments", []))
    file_attachment = save_uploaded_file(request.files.get("attachment"), task_id, "file")
    if file_attachment:
        attachments.append(file_attachment)
    return {
        "id": task_id,
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "subtasks": get_subtasks_from_form((existing or {}).get("subtasks", [])),
        "priority": priority,
        "importance": importance,
        "urgency": urgency,
        "xp": calculate_task_xp(priority, importance, urgency),
        "date": request.form.get("date") or "",
        "time": request.form.get("time") or "",
        "folder": request.form.get("new_folder", "").strip() or request.form.get("folder", "Учёба") or "Учёба",
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
        user = register_activity(user, xp=5)
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
                earned = int(task.get("xp", 10))
                task["earned_xp"] = earned
                task["completed_at"] = datetime.now().isoformat(timespec="seconds")
                user = register_activity(user, xp=earned)
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
    tasks = sorted([t for t in user.get("tasks", []) if t.get("date")], key=lambda task: (task.get("date"), task.get("time") or "99:99"))
    no_date_tasks = [t for t in user.get("tasks", []) if not t.get("date")]
    selected_view = request.args.get("view", "week")
    today = date.today()
    try:
        selected_month = datetime.strptime(request.args.get("month", today.strftime("%Y-%m")), "%Y-%m").date().replace(day=1)
    except ValueError:
        selected_month = today.replace(day=1)
    previous_month = (selected_month - timedelta(days=1)).replace(day=1)
    next_month = (selected_month.replace(day=28) + timedelta(days=4)).replace(day=1)
    start_of_week = today - timedelta(days=today.weekday())
    week_days = [(start_of_week + timedelta(days=i)).isoformat() for i in range(7)]
    month_days_count = (next_month - selected_month).days
    month_days = [(selected_month + timedelta(days=i)).isoformat() for i in range(month_days_count)]
    hours = list(range(8, 23))
    now = datetime.now()
    return render_template(
        "calendar.html", tasks=tasks, no_date_tasks=no_date_tasks, week_days=week_days, month_days=month_days,
        hours=hours, today=today.isoformat(), selected_view=selected_view, current_hour=now.hour, current_minute=now.minute,
        month_title=month_label(selected_month), selected_month=selected_month.strftime("%Y-%m"),
        previous_month=previous_month.strftime("%Y-%m"), next_month=next_month.strftime("%Y-%m")
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
    user = register_activity(user, xp=25)
    update_current_user(user)
    session["confetti"] = {"earned": 25}
    return redirect(url_for("focus"))


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
