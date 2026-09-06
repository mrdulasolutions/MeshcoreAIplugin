# MeshCore AI plugin

Read `SKILL.md`.

- The human’s MeshCore node is already the participant. Do not post “I am on this channel.”
- Do not take BLE from MeshCore.app.
- Listen with `python3 scripts/meshcore_ai.py watch <channel> --reset --mention Grok` as a **host monitor**. Wake only on @Grok / @[Grok], from anyone.
- Idle watch costs no model tokens. Wake only on `ACTION_REQUIRED:` lines.
- Humans: `README.md` and `COMMON_ISSUES.md`.
