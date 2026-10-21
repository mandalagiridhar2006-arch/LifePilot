import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

load_dotenv()
MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8001/mcp")
API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

try:
    from openai import AsyncOpenAI
    ai_client = AsyncOpenAI(api_key=API_KEY) if API_KEY else None
except Exception:
    ai_client = None

app = FastAPI(title="LifePilot — Alexa+ style assistant")
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []

async def call_mcp_tool(name: str, arguments: dict):
    """Call a real tool on the local MCP server over Streamable HTTP."""
    async with streamablehttp_client(MCP_URL) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            if getattr(result, "structuredContent", None) is not None:
                return result.structuredContent
            parts = []
            for content in getattr(result, "content", []) or []:
                if getattr(content, "text", None):
                    try:
                        parts.append(json.loads(content.text))
                    except json.JSONDecodeError:
                        parts.append(content.text)
            return parts[0] if len(parts) == 1 else parts

TOOLS = [
    {"type":"function","function":{"name":"add_task","description":"Add a task to the user's task list","parameters":{"type":"object","properties":{"title":{"type":"string"},"priority":{"type":"string","enum":["low","medium","high"]},"due":{"type":"string"}},"required":["title"],"additionalProperties":False}}},
    {"type":"function","function":{"name":"list_tasks","description":"List the user's tasks","parameters":{"type":"object","properties":{"include_completed":{"type":"boolean"}},"required":[],"additionalProperties":False}}},
    {"type":"function","function":{"name":"complete_task","description":"Mark a task complete by ID","parameters":{"type":"object","properties":{"task_id":{"type":"integer"}},"required":["task_id"],"additionalProperties":False}}},
    {"type":"function","function":{"name":"build_daily_plan","description":"Build a daily schedule from available hours and priorities","parameters":{"type":"object","properties":{"available_hours":{"type":"number"},"priorities":{"type":"string"},"start_time":{"type":"string"}},"required":["available_hours","priorities"],"additionalProperties":False}}},
]

SYSTEM = """You are LifePilot, a warm, practical personal assistant inspired by voice-first, multimodal assistants.
Help users plan their day, manage tasks, and stay focused. Use the provided tools whenever the user asks to add/list/complete tasks or create a schedule. Never claim a tool action succeeded unless its result confirms it. Ask a short clarification if required arguments are missing. Keep replies concise, friendly, and actionable. This is a hackathon web simulation, not the actual Alexa+ service. Do not claim to control real Alexa devices or calendars."""

async def demo_reply(message: str):
    """No-key fallback: the app still works and makes actual MCP calls."""
    m = message.lower().strip()
    if any(x in m for x in ["show tasks", "list tasks", "my tasks", "what are my tasks"]):
        result = await call_mcp_tool("list_tasks", {"include_completed": "completed" in m})
        tasks = result.get("tasks", []) if isinstance(result, dict) else []
        if not tasks:
            return "Your task list is empty. Try: “Add a high-priority task to study Java.”"
        return "Here are your tasks:\n" + "\n".join(
            f"• #{t['id']} {'✓' if t.get('done') else '○'} {t['title']} — {t.get('priority','medium')} priority" for t in tasks
        )
    if m.startswith("add ") or "add a task" in m or "remind me to" in m or "remember to" in m:
        title = message
        for prefix in ["add a task to ", "add task ", "add ", "remind me to ", "remember to "]:
            if m.startswith(prefix):
                title = message[len(prefix):].strip()
                break
        priority = "high" if "high priority" in m or "urgent" in m else "medium"
        title = title.replace("high priority", "").replace("urgent", "").strip(" .")
        result = await call_mcp_tool("add_task", {"title": title or "New task", "priority": priority, "due": ""})
        return result.get("message", str(result))
    if "plan" in m or "schedule" in m or "organize my day" in m:
        result = await call_mcp_tool("build_daily_plan", {"available_hours": 6, "priorities": message, "start_time": "09:00"})
        blocks = result.get("schedule", [])
        return "Here's a starter plan (edit it to match your commitments):\n" + "\n".join(f"• {b['start']}–{b['end']}: {b['activity']}" for b in blocks)
    return ("I can help with your schedule and tasks. Try one of these:\n"
            "• “Plan my day for 5 hours: Java, assignment, exercise”\n"
            "• “Add a high-priority task to finish my DBMS notes”\n"
            "• “Show my tasks”\n\n"
            "Tip: add an OpenAI API key to .env to enable the full LLM conversation.")

@app.get("/", response_class=HTMLResponse)
async def home():
    return Path("static/index.html").read_text(encoding="utf-8")

@app.get("/api/status")
async def status():
    return {"llm_enabled": bool(ai_client), "model": MODEL if ai_client else None, "mcp_url": MCP_URL}

@app.get("/api/tasks")
async def tasks():
    return await call_mcp_tool("list_tasks", {"include_completed": True})

@app.post("/api/chat")
async def chat(body: ChatRequest):
    message = body.message.strip()
    if not message:
        return {"reply": "Tell me what you'd like help with.", "tool_calls": []}
    if not ai_client:
        return {"reply": await demo_reply(message), "tool_calls": []}
    try:
        messages = [{"role":"system","content":SYSTEM}]
        for item in body.history[-8:]:
            if item.get("role") in ("user", "assistant") and isinstance(item.get("content"), str):
                messages.append({"role":item["role"], "content":item["content"]})
        messages.append({"role":"user","content":message})
        used = []
        for _ in range(4):
            response = await ai_client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOLS, tool_choice="auto", temperature=0.4
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return {"reply": msg.content or "What would you like to do next?", "tool_calls": used}
            messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    result = await call_mcp_tool(tc.function.name, args)
                    used.append({"name":tc.function.name, "result":result})
                    messages.append({"role":"tool","tool_call_id":tc.id,"content":json.dumps(result, ensure_ascii=False)})
                except Exception as e:
                    messages.append({"role":"tool","tool_call_id":tc.id,"content":json.dumps({"error":str(e)})})
        return {"reply":"I ran the requested tool(s). What would you like to do next?", "tool_calls":used}
    except Exception as e:
        return {"reply":f"The AI request failed ({type(e).__name__}). Check your API key, billing, model name, and internet connection. Your local MCP task tools can still be tested in demo mode.", "tool_calls":[]}

@app.post("/api/complete/{task_id}")
async def complete(task_id: int):
    return await call_mcp_tool("complete_task", {"task_id": task_id})
