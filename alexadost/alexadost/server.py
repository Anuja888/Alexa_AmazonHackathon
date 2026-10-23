"""AlexaDost MCP server: a voice-first campus-life agent for Alexa+.

Implements MCP (spec 2025-11-25) over Streamable HTTP using the official Python SDK.
Every tool returns a `spoken` field written to be read aloud by Alexa+.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3

from mcp.server.fastmcp import FastMCP

DB_PATH = os.environ.get("ALEXADOST_DB", "alexadost.db")

mcp = FastMCP(
    "AlexaDost",
    instructions=(
        "AlexaDost helps students manage deadlines, plan study time, revise with "
        "spaced-repetition flashcards and run focus sessions. Replies include a "
        "'spoken' field: read that aloud, keep it short."
    ),
    json_response=True,
    stateless_http=True,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS deadlines(
  id INTEGER PRIMARY KEY, title TEXT, subject TEXT, due TEXT,
  est_hours REAL, done_hours REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS cards(
  id INTEGER PRIMARY KEY, subject TEXT, question TEXT, answer TEXT,
  ease REAL DEFAULT 2.5, interval INTEGER DEFAULT 0, reps INTEGER DEFAULT 0,
  due TEXT);
CREATE TABLE IF NOT EXISTS sessions(
  id INTEGER PRIMARY KEY, task TEXT, minutes INTEGER, started TEXT);
"""


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def today() -> dt.date:
    return dt.date.today()


WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_date(text: str, now: dt.date | None = None) -> dt.date:
    """Parse ISO dates and spoken phrases: tomorrow, friday, in 3 days, next monday."""
    now = now or today()
    t = text.strip().lower()
    if t in ("today", "tonight"):
        return now
    if t == "tomorrow":
        return now + dt.timedelta(days=1)
    m = re.fullmatch(r"in (\d+) days?", t)
    if m:
        return now + dt.timedelta(days=int(m.group(1)))
    m = re.fullmatch(r"(?:next |this |on )?(\w+)", t)
    if m and m.group(1) in WEEKDAYS:
        delta = (WEEKDAYS.index(m.group(1)) - now.weekday()) % 7 or 7
        return now + dt.timedelta(days=delta)
    try:
        return dt.date.fromisoformat(t)
    except ValueError:
        raise ValueError(f"Could not understand the date '{text}'. Try 'friday' or '2026-11-02'.")


def fmt_h(h: float) -> str:
    return f"{h:g} hour" + ("" if h == 1 else "s")


def say_date(d: dt.date) -> str:
    return d.strftime("%A, %B ") + str(d.day)


@mcp.tool()
def add_deadline(title: str, due_date: str, est_hours: float = 2.0, subject: str = "") -> dict:
    """Add an assignment, exam or project deadline. due_date accepts 'friday', 'tomorrow', 'in 3 days' or YYYY-MM-DD."""
    due = parse_date(due_date)
    with db() as con:
        cur = con.execute(
            "INSERT INTO deadlines(title,subject,due,est_hours) VALUES(?,?,?,?)",
            (title, subject, due.isoformat(), est_hours),
        )
    return {
        "id": cur.lastrowid,
        "spoken": f"Added {title}, due {say_date(due)}, about {fmt_h(est_hours)} of work.",
    }


@mcp.tool()
def list_deadlines(days_ahead: int = 14) -> dict:
    """List unfinished deadlines due within the next N days, earliest first."""
    limit = (today() + dt.timedelta(days=days_ahead)).isoformat()
    with db() as con:
        rows = con.execute(
            "SELECT * FROM deadlines WHERE done_hours < est_hours AND due <= ? ORDER BY due", (limit,)
        ).fetchall()
    items = [
        {"id": r["id"], "title": r["title"], "due": r["due"],
         "hours_left": round(r["est_hours"] - r["done_hours"], 2)}
        for r in rows
    ]
    if not items:
        return {"deadlines": [], "spoken": f"Nothing due in the next {days_ahead} days. Enjoy it."}
    first = items[0]
    spoken = (f"You have {len(items)} deadline{'s' if len(items) != 1 else ''}. "
              f"First up: {first['title']}, due {say_date(dt.date.fromisoformat(first['due']))}.")
    return {"deadlines": items, "spoken": spoken}


@mcp.tool()
def log_progress(title: str, hours_done: float) -> dict:
    """Record hours spent on a deadline (matched by title, partial match is fine)."""
    with db() as con:
        r = con.execute(
            "SELECT * FROM deadlines WHERE lower(title) LIKE ? AND done_hours < est_hours ORDER BY due LIMIT 1",
            (f"%{title.lower()}%",),
        ).fetchone()
        if not r:
            return {"ok": False, "spoken": f"I couldn't find an open deadline called {title}."}
        done = min(r["est_hours"], r["done_hours"] + hours_done)
        con.execute("UPDATE deadlines SET done_hours=? WHERE id=?", (done, r["id"]))
    left = r["est_hours"] - done
    msg = "That one is finished. Nice work." if left <= 0 else f"{fmt_h(left)} left on {r['title']}."
    return {"ok": True, "hours_left": max(left, 0), "spoken": msg}


@mcp.tool()
def plan_study_week(hours_per_day: float = 3.0, days: int = 7) -> dict:
    """Build a day-by-day study plan using earliest-deadline-first scheduling and flag deadlines at risk."""
    with db() as con:
        rows = con.execute("SELECT * FROM deadlines WHERE done_hours < est_hours ORDER BY due").fetchall()
    remaining = {r["id"]: r["est_hours"] - r["done_hours"] for r in rows}
    by_id = {r["id"]: r for r in rows}
    plan, start = [], today()
    for offset in range(days):
        day = start + dt.timedelta(days=offset)
        cap, blocks = hours_per_day, []
        for r in rows:
            if cap <= 0:
                break
            if remaining[r["id"]] <= 0 or dt.date.fromisoformat(r["due"]) < day:
                continue
            chunk = min(2.0, cap, remaining[r["id"]])
            remaining[r["id"]] -= chunk
            cap -= chunk
            blocks.append({"title": r["title"], "hours": chunk})
        plan.append({"date": day.isoformat(), "blocks": blocks})
    at_risk = [by_id[i]["title"] for i, h in remaining.items() if h > 0]
    first = next((p for p in plan if p["blocks"]), None)
    if not rows:
        spoken = "You have no open deadlines, so there's nothing to plan."
    else:
        first_txt = ", ".join(f"{fmt_h(b['hours'])} of {b['title']}" for b in first["blocks"]) if first else ""
        spoken = f"Plan ready. Today: {first_txt}." if first else "Plan ready."
        if at_risk:
            spoken += f" Heads up: {', '.join(at_risk)} won't fit at {hours_per_day:g} hours a day. Try more hours or an extension."
    return {"plan": plan, "at_risk": at_risk, "spoken": spoken}


@mcp.tool()
def add_flashcard(question: str, answer: str, subject: str = "general") -> dict:
    """Save a flashcard for spaced-repetition revision."""
    with db() as con:
        cur = con.execute(
            "INSERT INTO cards(subject,question,answer,due) VALUES(?,?,?,?)",
            (subject, question, answer, today().isoformat()),
        )
    return {"id": cur.lastrowid, "spoken": "Saved. I'll quiz you on it."}


@mcp.tool()
def quiz_me(subject: str = "") -> dict:
    """Return the next flashcard that is due. Ask the question aloud; answer is returned for grading."""
    with db() as con:
        q = "SELECT * FROM cards WHERE due <= ?"
        args: list = [today().isoformat()]
        if subject:
            q += " AND lower(subject)=?"
            args.append(subject.lower())
        r = con.execute(q + " ORDER BY due, id LIMIT 1", args).fetchone()
        total = con.execute("SELECT COUNT(*) c FROM cards WHERE due <= ?", (today().isoformat(),)).fetchone()["c"]
    if not r:
        return {"card": None, "spoken": "No cards due. You're all caught up."}
    return {
        "card": {"id": r["id"], "question": r["question"], "answer": r["answer"], "subject": r["subject"]},
        "cards_due": total,
        "spoken": r["question"],
    }


@mcp.tool()
def grade_card(card_id: int, quality: int) -> dict:
    """Grade recall 0-5 (0 blackout, 3 hard, 5 perfect). Reschedules the card with the SM-2 algorithm."""
    q = max(0, min(5, quality))
    with db() as con:
        r = con.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not r:
            return {"ok": False, "spoken": "I couldn't find that card."}
        ease, reps, interval = r["ease"], r["reps"], r["interval"]
        if q < 3:
            reps, interval = 0, 1
        else:
            reps += 1
            interval = 1 if reps == 1 else 6 if reps == 2 else round(interval * ease)
        ease = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        due = today() + dt.timedelta(days=interval)
        con.execute("UPDATE cards SET ease=?, reps=?, interval=?, due=? WHERE id=?",
                    (ease, reps, interval, due.isoformat(), card_id))
    when = "tomorrow" if interval == 1 else f"in {interval} days"
    return {"ok": True, "next_review_days": interval, "spoken": f"Got it. You'll see this again {when}."}


@mcp.tool()
def start_focus_session(minutes: int = 25, task: str = "studying") -> dict:
    """Start a focus (pomodoro) session and return when it ends."""
    minutes = max(1, min(180, minutes))
    now = dt.datetime.now()
    with db() as con:
        con.execute("INSERT INTO sessions(task,minutes,started) VALUES(?,?,?)", (task, minutes, now.isoformat()))
    end = now + dt.timedelta(minutes=minutes)
    return {
        "ends_at": end.isoformat(timespec="minutes"),
        "spoken": f"Focus mode on for {minutes} minutes: {task}. I'll tell you when it's time to stop at {end.strftime('%I:%M %p').lstrip('0')}.",
    }


@mcp.tool()
def daily_briefing() -> dict:
    """One-shot morning briefing: next deadline, cards due, and today's study blocks."""
    dl = list_deadlines(7)
    quiz = quiz_me()
    plan = plan_study_week(days=1)
    parts = [dl["spoken"]]
    parts.append(f"{quiz.get('cards_due', 0)} flashcards due." if quiz["card"] else "No flashcards due.")
    if plan["plan"][0]["blocks"]:
        parts.append("Today's plan: " + ", ".join(f"{fmt_h(b['hours'])} of {b['title']}" for b in plan["plan"][0]["blocks"]) + ".")
    return {"deadlines": dl["deadlines"], "cards_due": quiz.get("cards_due", 0),
            "plan_today": plan["plan"][0], "spoken": " ".join(parts)}


def build_app():
    """Streamable HTTP app: MCP at /mcp, plus simulator routes (see simulator.py)."""
    from .simulator import add_routes

    app = mcp.streamable_http_app()
    add_routes(app)
    return app


def main() -> None:
    import uvicorn

    uvicorn.run(build_app(), host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
