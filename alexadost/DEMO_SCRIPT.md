# 3-minute demo video script (screen record the simulator, upload to YouTube as Public/Unlisted-public)

0:00-0:20  Say: "Students juggle deadlines and revision. AlexaDost is an MCP server that gives Alexa+ a study sidekick." Show the repo page with the MIT license and the running terminal (`python -m alexadost.server`).
0:20-0:50  Open http://127.0.0.1:8000. Click the Speak button and say: "Add a deadline DBMS assignment due Friday, 4 hours." Point at the tool-call panel (tools/call add_deadline).
0:50-1:20  Add a second deadline (AIML report due in 3 days 6 hours). Say "Plan my week with 2 hours." Point out the at-risk warning.
1:20-2:00  "Add flashcard what is normalization answer removing data redundancy." Then "Quiz me", then "Got it". Mention SM-2 schedules the next review.
2:00-2:25  "Start a focus session for 25 minutes on DBMS." Then "Give me my briefing."
2:25-2:50  Show MCP Inspector or curl `tools/list` hitting /mcp with protocol 2025-11-25 to prove it is a real MCP server. Run `pytest` (6 passed).
2:50-3:00  "Open source, MIT, link below. Thanks!"
Note: no copyrighted music, no Amazon logos in the video.
