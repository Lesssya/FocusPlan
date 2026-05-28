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

PRIORITY_LABELS = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}
IMPORTANCE_LABELS = {"low": "Низкая", "medium": "Средняя", "high": "Высокая"}
URGENCY_LABELS = {"not_urgent": "Не срочно", "urgent": "Срочно"}


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


def create_user(nickname: str) -> Dict[str, Any]:
    return {
        "nickname": nickname,
        "avatar": nickname[:1].upper() if nickname else "F",
        "settings": DEFAULT_SETTINGS.copy(),
        "tasks": [],
        "xp": 0,
        "streak": 0,
        "last_activity": None,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def current_user() -> Dict[str, Any] | None:
    nickname = session.get("nickname")
    if not nickname:
        return None
    store = load_store()
    if nickname not in store["users"]:
        store["users"][nickname] = create_user(nickname)
        save_store(store)
    return store["users"].get(nickname)


def update_current_user(user: Dict[str, Any]) -> None:
    nickname = session.get("nickname")
    if not nickname:
        return
    store = load_store()
    store["users"][nickname] = user
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
    user["xp"] = int(user.get("xp", 0)) + xp
    return user


def level_from_xp(xp: int) -> int:
    return max(1, xp // 100 + 1)


def progress_to_next_level(xp: int) -> int:
    return xp % 100


def task_stats(tasks: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(tasks)
    done = len([task for task in tasks if task.get("done")])
    active = total - done
    progress = round((done / total) * 100) if total else 0
    return {"total": total, "done": done, "active": active, "progress": progress}


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


def save_uploaded_file(file_storage, task_id: str, kind: str) -> Dict[str, str] | None:
    if not file_storage or not file_storage.filename:
        return None
    safe_name = secure_filename(file_storage.filename)
    if not safe_name:
        return None
    folder = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(folder, exist_ok=True)
    stored_name = f"{kind}_{safe_name}"
    file_storage.save(os.path.join(folder, stored_name))
    return {"name": file_storage.filename, "stored": stored_name, "kind": kind}


def get_subtasks_from_form() -> List[Dict[str, Any]]:
    subtasks_raw = request.form.get("subtasks", "")
    subtasks = []
    for item in subtasks_raw.replace(";", "\n").splitlines():
        title = item.strip()
        if title:
            subtasks.append({"id": str(uuid.uuid4()), "title": title, "done": False})
    return subtasks


@app.context_processor
def inject_user_data():
    user = current_user()
    if not user:
        return {"current_endpoint": request.endpoint}
    settings = user.get("settings", DEFAULT_SETTINGS)
    return {
        "user": user,
        "settings": settings,
        "level": level_from_xp(int(user.get("xp", 0))),
        "level_progress": progress_to_next_level(int(user.get("xp", 0))),
        "current_endpoint": request.endpoint,
        "priority_labels": PRIORITY_LABELS,
        "importance_labels": IMPORTANCE_LABELS,
        "urgency_labels": URGENCY_LABELS,
        "confetti": session.pop("confetti", None),
    }


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
    tasks = sorted(user.get("tasks", []), key=lambda task: (task.get("done", False), task.get("date") or "9999-99-99", task.get("time") or "99:99"))
    return render_template("dashboard.html", tasks=tasks, stats=task_stats(tasks), today=get_today())


@app.route("/tasks")
@login_required
def tasks_page():
    user = current_user()
    tasks = sorted(user.get("tasks", []), key=lambda task: (task.get("done", False), task.get("date") or "9999-99-99", task.get("time") or "99:99"))
    dated_tasks = [t for t in tasks if t.get("date")]
    no_date_tasks = [t for t in tasks if not t.get("date")]
    return render_template("tasks.html", tasks=tasks, dated_tasks=dated_tasks, no_date_tasks=no_date_tasks)


@app.route("/tasks/add", methods=["POST"])
@login_required
def add_task():
    user = current_user()
    title = request.form.get("title", "").strip()
    if title:
        task_id = str(uuid.uuid4())
        priority = request.form.get("priority", "medium")
        importance = request.form.get("importance", "medium")
        urgency = request.form.get("urgency", "not_urgent")
        xp_value = calculate_task_xp(priority, importance, urgency)
        attachments = []
        file_attachment = save_uploaded_file(request.files.get("attachment"), task_id, "file")
        audio_attachment = save_uploaded_file(request.files.get("audio"), task_id, "audio")
        if file_attachment:
            attachments.append(file_attachment)
        if audio_attachment:
            attachments.append(audio_attachment)
        task = {
            "id": task_id,
            "title": title,
            "description": request.form.get("description", "").strip(),
            "subtasks": get_subtasks_from_form(),
            "priority": priority,
            "importance": importance,
            "urgency": urgency,
            "xp": xp_value,
            "date": request.form.get("date") or "",
            "time": request.form.get("time") or "",
            "attachments": attachments,
            "done": False,
            "earned_xp": 0,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        user.setdefault("tasks", []).append(task)
        user = register_activity(user, xp=5)
        update_current_user(user)
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/tasks/<task_id>/toggle", methods=["POST"])
@login_required
def toggle_task(task_id: str):
    user = current_user()
    earned = 0
    for task in user.get("tasks", []):
        if task.get("id") == task_id:
            was_done = task.get("done", False)
            task["done"] = not was_done
            if task["done"]:
                earned = int(task.get("xp", 10))
                task["earned_xp"] = earned
                task["completed_at"] = datetime.now().isoformat(timespec="seconds")
                user = register_activity(user, xp=earned)
            else:
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
    for task in user.get("tasks", []):
        if task.get("id") == task_id:
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
    start_of_week = today - timedelta(days=today.weekday())
    week_days = [(start_of_week + timedelta(days=i)).isoformat() for i in range(7)]
    month_start = today.replace(day=1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_days_count = (next_month - month_start).days
    month_days = [(month_start + timedelta(days=i)).isoformat() for i in range(month_days_count)]
    hours = list(range(8, 23))
    now = datetime.now()
    return render_template("calendar.html", tasks=tasks, no_date_tasks=no_date_tasks, week_days=week_days, month_days=month_days, hours=hours, today=today.isoformat(), selected_view=selected_view, current_hour=now.hour, current_minute=now.minute, month_title=today.strftime("%m.%Y"))


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
        user["nickname"] = new_nickname
        user["avatar"] = request.form.get("avatar", "").strip()[:2].upper() or new_nickname[:1].upper()
        user["settings"] = {"theme": request.form.get("theme", "light"), "accent": request.form.get("accent", "purple"), "notifications": bool(request.form.get("notifications"))}
        store = load_store()
        if new_nickname != old_nickname:
            store["users"].pop(old_nickname, None)
            session["nickname"] = new_nickname
        store["users"][new_nickname] = user
        save_store(store)
        return redirect(url_for("profile"))
    return render_template("profile.html")


@app.route("/uploads/<task_id>/<filename>")
@login_required
def uploaded_file(task_id: str, filename: str):
    return send_from_directory(os.path.join(UPLOAD_DIR, task_id), filename, as_attachment=True)


@app.after_request
def add_confetti_header(response):
    return response


if __name__ == "__main__":
    ensure_store()
    app.run(debug=True)
