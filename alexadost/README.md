# AlexaDost – a study sidekick for Alexa+

Built for the **Build, Ship, Shape: Amazon Developer Hackathon** (Alexa+ track, Open Source mini challenge).

AlexaDost is a self-hosted **MCP server** (spec **2025-11-25**, **Streamable HTTP**) that gives Alexa+ the tools a student needs: deadlines, a study planner, spaced-repetition flashcards and focus sessions. Every tool returns a short `spoken` string written to be read aloud.

A browser-based **Alexa+ simulator** (voice in, voice out) talks to the server as a real MCP client, so you can see each `tools/call` as it happens.

## Tools

| Tool | What it does |
|---|---|
| `add_deadline` | Saves an assignment/exam. Accepts spoken dates: "friday", "in 3 days", ISO. |
| `list_deadlines` | Open deadlines in the next N days, earliest first. |
| `log_progress` | Records hours worked; closes the deadline when done. |
| `plan_study_week` | Earliest-deadline-first schedule; warns which deadlines won't fit. |
| `add_flashcard` / `quiz_me` / `grade_card` | Flashcards rescheduled with the SM-2 spaced-repetition algorithm. |
| `start_focus_session` | Starts a pomodoro and says when to stop. |
| `daily_briefing` | One call: next deadline, cards due, today's study blocks. |

## Run it

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m alexadost.server                           # http://127.0.0.1:8000
```

- Simulator UI: http://127.0.0.1:8000/
- MCP endpoint (any MCP client / Alexa+): `http://127.0.0.1:8000/mcp`
- Tests: `pytest`

Try in the simulator: "Add a deadline DBMS assignment due friday 4 hours" → "Plan my week with 2 hours" → "Add flashcard what is normalization answer removing data redundancy" → "Quiz me" → "Got it" → "Give me my briefing".

### Inspect with the MCP Inspector
```bash
npx @modelcontextprotocol/inspector   # transport: Streamable HTTP, URL: http://127.0.0.1:8000/mcp
```

### Optional: Amazon Bedrock for natural language
By default the simulator uses a built-in rule router (works offline). To let a Bedrock model choose tools with the Converse API:
```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=<a Bedrock model id with tool-use support you have access to>
python -m alexadost.server
```
If Bedrock errors, the simulator falls back to the rule router and shows which engine answered.

## How it works
`alexadost/server.py` defines the tools with the official MCP Python SDK (`mcp<2`, FastMCP) and stores data in SQLite. `alexadost/simulator.py` is the simulated Alexa+ layer: it opens an MCP client session to `/mcp`, calls `tools/list` and `tools/call`, and returns the spoken reply plus the raw tool calls to the web UI.

## License
MIT
