# MeshCore AI plugin

Read `SKILL.md`.

- The human’s MeshCore node is already the participant. Do not post “I am on this channel.”
- Do not take BLE from MeshCore.app.
- Listen with `python3 scripts/meshcore_ai.py watch <channel> --reset` as a **host monitor**. Do not poll in the LLM loop.
- Idle watch costs no model tokens. Wake only on `ACTION_REQUIRED:` lines.
