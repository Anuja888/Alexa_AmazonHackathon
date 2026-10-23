# Devpost submission copy (paste into the form)

## Project name
AlexaDost

## Tagline
Alexa+ study sidekick: deadlines, a study planner and spaced-repetition flashcards, all by voice, via an MCP server.

## Primary track
Alexa+

## Mini challenges
Open Source (tick this). Tick AWS Builder ONLY if you ran the Bedrock path with real credentials.

## Text description
**Inspiration.** Students juggle assignments, exams and revision across five apps, and nothing nudges them by voice at the moment they're deciding what to do next. Alexa+ is the right place for that.

**What it does.** AlexaDost is a self-hosted MCP server that gives Alexa+ nine tools: add and list deadlines, log progress, build an earliest-deadline-first weekly study plan that warns which deadlines won't fit, save flashcards and quiz with the SM-2 spaced-repetition algorithm, start focus sessions, and a one-shot daily briefing. Every tool returns a short `spoken` reply designed to be read aloud, so conversations stay hands-free.

**How we built it.** Python with the official MCP SDK, implementing MCP spec 2025-11-25 over Streamable HTTP (`/mcp`), SQLite for storage, and pytest tests for the date parser, planner, SM-2 scheduling and tool listing. Because the Alexa+ simulated path is allowed, we also built a browser Alexa+ simulator (speech recognition in, speech synthesis out). It is a real MCP client: it runs `tools/list` and `tools/call` against the server and shows every call live. An optional Amazon Bedrock (Converse API with tool use) mode lets a model pick the tools; a rule router keeps the demo working offline.

**Challenges.** MCP SDK 2.x renames FastMCP and changes imports, so we pinned `mcp<2`. We also had to make tool outputs voice-friendly (pluralisation, spoken dates) rather than raw JSON.

**What's next.** Calendar sync, shared study groups, and publishing the server as an Alexa+ skill.

## Code repository
(paste your public GitHub URL; the MIT LICENSE file is in the repo root)

## Open Source mini challenge fields
- Contribution URL: same GitHub repo URL (new open-source repo, MIT licence)
- Project repository URL: same
- GitHub username: (yours)
- What I did / how it works / why it matters: Created a new MIT-licensed MCP server and simulator for students. It exposes nine voice-friendly tools over Streamable HTTP and can be reused by any MCP client. It matters because students get a free, self-hostable study agent.

## Product feedback (edit to match your honest experience)
**Tools used:** MCP open standard (spec 2025-11-25, Streamable HTTP) with the official MCP Python SDK; simulated Alexa+ experience in a web app. Amazon Bedrock Converse API for the optional model-routing mode (only mention if you tested it).
**What worked well:** The Streamable HTTP transport with stateless JSON responses made the server trivial to test with curl and any client. The SDK negotiates protocol version 2025-11-25 out of the box (1.30). Decorator-based tool definitions generate JSON schemas automatically.
**What needs work:** `pip install mcp` now installs 2.x by default, where `FastMCP` moved to `MCPServer`, so older tutorials fail with an import error until you pin `mcp<2`. The hackathon materials don't say how a self-hosted MCP server gets attached to a real Alexa+ device, so we used the allowed simulated path. A public Alexa+ MCP test harness would help.
**Onboarding (zero to hello world):** Under an hour for the server; longer to find which MCP SDK version matched the docs.
**Build again?** Yes, MCP is a clean way to make an assistant capable. We would build more if there was a way to test against a real Alexa+ device.

## Feature requests (optional)
- Official Alexa+ MCP simulator or test harness (Important)
- Documented path to register a self-hosted MCP server with Alexa+ (Critical)

## Friction log (optional, up to 10% bonus)
- Task: install MCP SDK and start a server. Steps: `pip install mcp`, `from mcp.server.fastmcp import FastMCP`. Expected: works. Actual: ModuleNotFoundError, FastMCP renamed in 2.x. Severity: medium. Workaround: `pip install "mcp<2"`. Suggestion: keep a compatibility alias or put the pin in the quickstart.
