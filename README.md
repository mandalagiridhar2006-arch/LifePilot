# LifePilot — Alexa+ inspired personal assistant

LifePilot is an independent hackathon prototype that simulates a voice-first, multimodal personal assistant in a web interface. It uses a self-hosted MCP server over **Streamable HTTP** and optionally an OpenAI-compatible LLM to plan a day and manage tasks.

> This is not an official Amazon/Alexa+ product and does not connect to Alexa+ itself. Amazon's hackathon FAQ says participants cannot directly integrate with Alexa+ preview tooling; the supported route is a self-hosted MCP server or a simulated experience.

## Features
- Dark, responsive web UI with chat and task overview
- MCP tools: `add_task`, `list_tasks`, `complete_task`, `build_daily_plan`
- MCP server using Streamable HTTP transport at `http://127.0.0.1:8001/mcp`
- Optional LLM function-calling via OpenAI API
- No API key? The task tools still work in deterministic demo mode
- Task data persists locally in `lifepilot_data.json`

## Requirements
- Python 3.11 or newer
- Windows 10/11
- Internet for package installation and LLM requests
- An OpenAI API key is optional. ChatGPT subscription and API billing are separate.

## Run on Windows

Open PowerShell in this folder:

```powershell
py --version
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell blocks activation, run this once for the current terminal:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Optional: enable the LLM
1. Create an API key at https://platform.openai.com/api-keys.
2. Open `.env` in Notepad and set `OPENAI_API_KEY=your_key_here`.
3. Ensure your API account has access/billing for the model in `OPENAI_MODEL`. The default is `gpt-4o-mini`.
4. Never commit `.env` or share your key in screenshots.

### Start the MCP server
Terminal 1 (from the project folder, with `.venv` active):
```powershell
python mcp_server.py
```
Keep this terminal open. It serves Streamable HTTP on port 8001.

### Start the web app
Open Terminal 2 in the same folder and activate the same environment:
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app:app --reload --port 8000
```
Open http://127.0.0.1:8000 in your browser.

## Demo prompts
- `Plan my day for 5 hours: study Java, finish DBMS notes, exercise`
- `Add a high-priority task to finish my DBMS notes`
- `Show my tasks`
- With the LLM enabled: `I have classes until 3pm. Plan a realistic evening with Java practice, dinner, and a short walk.`
- With the LLM enabled: `Mark task 1 complete`

## Verify MCP
Install an MCP client such as MCP Inspector and connect it to:
`http://127.0.0.1:8001/mcp`

You should see the four tools exposed by LifePilot. In the demo video, show a user prompt, the assistant response, and the resulting task list changing. Avoid claiming direct Alexa+ integration.

## Submission checklist
- [ ] Run both processes and test all 4 tools
- [ ] Add screenshots and a demo video (under 3 minutes, public, English)
- [ ] Push all source files to a GitHub repository
- [ ] Include a suitable open-source license if repository is public
- [ ] Add a clear project description and architecture
- [ ] Submit honest product feedback about MCP setup, testing, and what could be improved
- [ ] State that the web UI is a simulation, not a direct Alexa+ integration

## Architecture
Browser UI → FastAPI chat API → OpenAI tool calling (optional) → MCP client → local MCP Streamable HTTP server → persistent JSON task store.

Without a key, a small deterministic fallback keeps the task-management demo usable. With a key, the LLM chooses and invokes MCP tools through function calling.
