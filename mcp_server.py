"""LifePilot MCP tools. Uses MCP Streamable HTTP transport."""
from datetime import datetime
from pathlib import Path
import json
from mcp.server.fastmcp import FastMCP

DATA_FILE = Path(__file__).with_name("lifepilot_data.json")
mcp = FastMCP("LifePilot", host="127.0.0.1", port=8001)

def _load():
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("tasks"), list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"tasks": []}

def _save(data):
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

@mcp.tool()
def add_task(title: str, priority: str = "medium", due: str = "") -> dict:
    """Add a task to the user's LifePilot task list. Priority must be low, medium, or high."""
    priority = priority.lower().strip()
    if priority not in {"low", "medium", "high"}:
        priority = "medium"
    title = title.strip()
    if not title:
        return {"ok": False, "message": "Task title cannot be empty."}
    data = _load()
    task = {
        "id": max([t.get("id", 0) for t in data["tasks"]], default=0) + 1,
        "title": title[:180],
        "priority": priority,
        "due": due.strip()[:80],
        "done": False,
        "created_at": datetime.now().isoformat(timespec="minutes"),
    }
    data["tasks"].append(task)
    _save(data)
    return {"ok": True, "task": task, "message": f"Added: {task['title']}"}

@mcp.tool()
def list_tasks(include_completed: bool = False) -> dict:
    """List tasks. Set include_completed true to include completed tasks."""
    tasks = _load()["tasks"]
    if not include_completed:
        tasks = [t for t in tasks if not t.get("done")]
    tasks = sorted(tasks, key=lambda t: (t.get("done", False), {"high": 0, "medium": 1, "low": 2}.get(t.get("priority"), 1), t.get("id", 0)))
    return {"tasks": tasks, "count": len(tasks)}

@mcp.tool()
def complete_task(task_id: int) -> dict:
    """Mark a task complete using its numeric task ID."""
    data = _load()
    for task in data["tasks"]:
        if task.get("id") == task_id:
            task["done"] = True
            _save(data)
            return {"ok": True, "task": task, "message": f"Completed: {task['title']}"}
    return {"ok": False, "message": f"No task found with ID {task_id}."}

@mcp.tool()
def build_daily_plan(available_hours: float, priorities: str, start_time: str = "09:00") -> dict:
    """Create a practical suggested schedule from the user's available hours and priorities."""
    hours = max(1.0, min(float(available_hours), 16.0))
    items = [x.strip() for x in priorities.replace("\n", ",").split(",") if x.strip()]
    if not items:
        items = ["Choose your most important task"]
    # A simple deterministic plan, intentionally editable by the user.
    blocks = []
    start_hour, start_min = 9, 0
    try:
        start_hour, start_min = map(int, start_time.split(":"))
        if not (0 <= start_hour <= 23 and 0 <= start_min <= 59):
            raise ValueError
    except (ValueError, TypeError):
        start_hour, start_min = 9, 0
    cursor = start_hour * 60 + start_min
    remaining = int(hours * 60)
    for i, item in enumerate(items[:8]):
        if remaining <= 0:
            break
        duration = min(60 if i == 0 else 45, remaining)
        end = cursor + duration
        fmt = lambda m: f"{(m // 60) % 24:02d}:{m % 60:02d}"
        blocks.append({"start": fmt(cursor), "end": fmt(end), "activity": item, "minutes": duration})
        cursor = end + 10
        remaining -= duration + (10 if remaining > duration + 10 else 0)
    return {"available_hours": hours, "schedule": blocks, "note": "Suggested plan — adjust it to your real commitments and energy."}

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
