"""Simulated Alexa+ experience: web UI + an agent that talks to the MCP server over Streamable HTTP.

The agent is a real MCP *client* (official SDK). It discovers tools with tools/list and runs them
with tools/call against MCP_URL. Intent routing uses Amazon Bedrock (Converse API with tool use)
when AWS credentials are available, otherwise a built-in rule router so the demo works offline.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse

MCP_URL = os.environ.get("MCP_URL", "http://127.0.0.1:8000/mcp")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

_last_card: dict = {}


# ------------------------------------------------------------ rule router (offline)

def route_rules(text: str) -> tuple[str, dict] | None:
    t = text.lower().strip().rstrip(".?!")
    if re.search(r"briefing|my day|good morning|what.?s up today", t):
        return "daily_briefing", {}
    if re.search(r"\bplan\b", t):
        m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)", t)
        return "plan_study_week", {"hours_per_day": float(m.group(1))} if m else {}
    m = re.search(r"focus|pomodoro", t)
    if m:
        mins = re.search(r"(\d+)\s*(?:min|minutes)", t)
        task = re.search(r"\bon\s+(?:my\s+)?(.+?)(?:\s+for\s+\d+\s*(?:min|minutes))?$", text.strip().rstrip(".?!"), re.I)
        args = {"minutes": int(mins.group(1))} if mins else {}
        if task:
            args["task"] = task.group(1).strip()
        return "start_focus_session", args
    m = re.search(r"(?:spent|did|worked|finished)\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\s+(?:on|of)\s+(.+)", t)
    if m:
        return "log_progress", {"hours_done": float(m.group(1)), "title": m.group(2).strip()}
    m = re.search(r"(?:add|create|save|make)\s+(?:a\s+)?(?:flash\s?card|card)[:\s]+(.+?)\s+(?:answer|=|->)\s*(.+)", t)
    if m:
        return "add_flashcard", {"question": m.group(1).strip().rstrip("?") + "?", "answer": m.group(2).strip()}
    if re.search(r"quiz|flash\s?card|test me", t) and not re.search(r"add|save|create", t):
        return "quiz_me", {}
    if _last_card and re.search(r"\b(got it|easy|perfect|knew it|remembered)\b", t):
        return "grade_card", {"card_id": _last_card["id"], "quality": 5}
    if _last_card and re.search(r"\b(hard|barely|struggled)\b", t):
        return "grade_card", {"card_id": _last_card["id"], "quality": 3}
    if _last_card and re.search(r"\b(forgot|no idea|wrong|didn.?t know)\b", t):
        return "grade_card", {"card_id": _last_card["id"], "quality": 1}
    m = re.search(r"(?:add|have|got|new)\s+(?:a\s+|an\s+)?(?:deadline|assignment|exam|test|project)?:?\s*(.+?)\s+(?:due|by)\s+(.+?)(?:\s+(?:about\s+)?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?))?$", text.strip().rstrip(".?!"), re.I)
    if m:
        args = {"title": m.group(1).strip(), "due_date": m.group(2).strip().lower()}
        if m.group(3):
            args["est_hours"] = float(m.group(3))
        return "add_deadline", args
    if re.search(r"deadline|due|upcoming|assignments", t):
        return "list_deadlines", {}
    return None


# ------------------------------------------------------------ Bedrock path

def bedrock_available() -> bool:
    if not BEDROCK_MODEL_ID:
        return False
    try:
        import boto3  # noqa: F401
        return True
    except ImportError:
        return False


async def run_bedrock(session: ClientSession, text: str, calls: list) -> str:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    listed = await session.list_tools()
    tool_config = {"tools": [
        {"toolSpec": {"name": t.name, "description": t.description or "", "inputSchema": {"json": t.inputSchema}}}
        for t in listed.tools
    ]}
    system = [{"text": "You are Alexa+, a warm, concise voice assistant for a student. Use the tools for anything about deadlines, study plans, flashcards, focus sessions. Reply in one or two short spoken sentences."}]
    messages = [{"role": "user", "content": [{"text": text}]}]
    for _ in range(5):
        resp = client.converse(modelId=BEDROCK_MODEL_ID, messages=messages, system=system, toolConfig=tool_config)
        msg = resp["output"]["message"]
        messages.append(msg)
        if resp["stopReason"] != "tool_use":
            return "".join(b.get("text", "") for b in msg["content"]).strip()
        results = []
        for block in msg["content"]:
            if "toolUse" in block:
                tu = block["toolUse"]
                res = await session.call_tool(tu["name"], tu["input"])
                payload = res.structuredContent or json.loads(res.content[0].text)
                calls.append({"name": tu["name"], "args": tu["input"], "result": payload})
                results.append({"toolResult": {"toolUseId": tu["toolUseId"], "content": [{"json": payload}]}})
        messages.append({"role": "user", "content": results})
    return "Sorry, that took too many steps."


# ------------------------------------------------------------ chat endpoint

async def chat(request: Request) -> JSONResponse:
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"reply": "I didn't catch that.", "tool_calls": [], "engine": "none"})
    calls: list = []
    engine = "rules"
    try:
        async with streamablehttp_client(MCP_URL) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if bedrock_available():
                    try:
                        engine = "bedrock:" + BEDROCK_MODEL_ID
                        reply = await run_bedrock(session, text, calls)
                        return JSONResponse({"reply": reply, "tool_calls": calls, "engine": engine})
                    except Exception as exc:  # fall back to rules if Bedrock call fails
                        calls.clear()
                        engine = f"rules (bedrock error: {type(exc).__name__})"
                routed = route_rules(text)
                if not routed:
                    return JSONResponse({
                        "reply": "I can track deadlines, plan your week, quiz you with flashcards, or start a focus session. Try: add a deadline DBMS assignment due friday 4 hours.",
                        "tool_calls": [], "engine": engine})
                name, args = routed
                res = await session.call_tool(name, args)
                if res.isError:
                    msg = res.content[0].text if res.content else "Something went wrong."
                    return JSONResponse({"reply": msg.replace("Error executing tool " + name + ": ", ""),
                                         "tool_calls": [{"name": name, "args": args, "result": {"error": msg}}], "engine": engine})
                payload = res.structuredContent or json.loads(res.content[0].text)
                if name == "quiz_me" and payload.get("card"):
                    _last_card.update(payload["card"])
                calls.append({"name": name, "args": args, "result": payload})
                reply = payload.get("spoken", "Done.")
                return JSONResponse({"reply": reply, "tool_calls": calls, "engine": engine})
    except Exception as exc:
        return JSONResponse({"reply": "I couldn't reach the AlexaDost server.", "tool_calls": [], "engine": f"error: {exc}"}, status_code=502)


async def index(_: Request) -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


def add_routes(app) -> None:
    app.add_route("/api/chat", chat, methods=["POST"])
    app.add_route("/", index, methods=["GET"])
