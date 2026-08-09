---
name: morning-briefing
description: How to deliver the user's morning briefing.
---

When the user asks for their morning briefing:

1. Call get_current_time and greet the user according to the time of day.
2. Call search_knowledge with query "daily checklist" and mention any
   routines it returns.
3. Remind the user of at most three things, most important first.
4. Keep the whole briefing under six sentences and end with an
   encouraging note.
