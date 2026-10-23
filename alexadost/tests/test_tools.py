import datetime as dt
import pytest

from alexadost import server


@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB_PATH", str(tmp_path / "t.db"))


def test_parse_date():
    base = dt.date(2026, 10, 23)  # Friday
    assert server.parse_date("tomorrow", base) == dt.date(2026, 10, 24)
    assert server.parse_date("in 3 days", base) == dt.date(2026, 10, 26)
    assert server.parse_date("friday", base) == dt.date(2026, 10, 30)
    assert server.parse_date("2026-11-02", base) == dt.date(2026, 11, 2)
    with pytest.raises(ValueError):
        server.parse_date("someday", base)


def test_planner_flags_at_risk():
    server.add_deadline("Big project", "tomorrow", est_hours=20)
    out = server.plan_study_week(hours_per_day=2, days=3)
    assert "Big project" in out["at_risk"]


def test_planner_edf_order():
    server.add_deadline("Later", "in 5 days", est_hours=2)
    server.add_deadline("Sooner", "in 2 days", est_hours=2)
    first = server.plan_study_week(hours_per_day=2, days=1)["plan"][0]["blocks"][0]
    assert first["title"] == "Sooner"


def test_sm2_intervals():
    cid = server.add_flashcard("q", "a")["id"]
    assert server.grade_card(cid, 5)["next_review_days"] == 1
    assert server.grade_card(cid, 5)["next_review_days"] == 6
    assert server.grade_card(cid, 1)["next_review_days"] == 1  # lapse resets


def test_progress_completes():
    server.add_deadline("Essay", "friday", est_hours=2)
    assert server.log_progress("essay", 2)["hours_left"] == 0
    assert server.list_deadlines()["deadlines"] == []


@pytest.mark.asyncio
async def test_mcp_lists_tools():
    tools = await server.mcp.list_tools()
    assert {t.name for t in tools} >= {"add_deadline", "plan_study_week", "quiz_me", "daily_briefing"}
