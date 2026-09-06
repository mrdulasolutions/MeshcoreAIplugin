---
name: meshcore-ai
description: >
  Sidecar for the official MeshCore app: watch a channel via the local sqlite
  DB without BLE and without polling in the LLM loop. Creates channels with
  meshcore:// links. The human already is the mesh participant. Use when the
  user says MeshCore, Grok channel, listen to MeshCore, MeshcoreAIplugin,
  or /meshcore-ai.
---

# MeshCore AI plugin

The user on the MeshCore app **is** the channel member (their node name, e.g. MACDAGGER). You are a sidecar. Do not insert “Grok here / I am on this channel” lines. Do not add a fake contact that looks like another person in the room unless they explicitly ask for a separate agent identity.

Do not connect BLE. The app owns the radio.

## Token rule (mandatory)

Never poll `watch` inside the LLM turn. Never `sleep` and re-read the DB yourself.

Listen = one **host** process. Idle process = **zero tokens**. Wake the agent only when stdout prints `ACTION_REQUIRED:`.

Launch:

```bash
python3 scripts/meshcore_ai.py watch Grok --reset --mention Grok
```

Use the environment `monitor` tool with `persistent: true`. Silent until a new row **@-mentions** the contact name (`@Grok` or `@[Grok]`), from anyone. Agent `Grok: …` echoes are ignored. Log: `~/.meshcore/watch/Grok.log`.

On wakeup: read that log line, answer the user, keep the same monitor running.

## CLI

```bash
python3 scripts/meshcore_ai.py discover
python3 scripts/meshcore_ai.py info
python3 scripts/meshcore_ai.py channels
python3 scripts/meshcore_ai.py messages Grok
python3 scripts/meshcore_ai.py add-channel Grok
python3 scripts/meshcore_ai.py join-url Grok
python3 scripts/meshcore_ai.py watch Grok --reset
```

`post --as-name Grok "text"` stores `Grok: text` with `from` NULL (left-side bubble). Raw `post` without `--as-name` looks like the user. A colon in the first words without `--as-name` creates a fake @ contact. `post` is sqlite only (not LoRa). No presence banners.

`add-agent` is optional and must not auto-hello. To appear in Participants, add-agent plus one real `post --as-key`, then the user refreshes the channel view.

Troubleshooting for humans: `COMMON_ISSUES.md`.

## Paths (macOS)

- DB: `~/Library/Containers/com.liamcottle.meshcore.macos/Data/Documents/meshcore_<pubkey>.sqlite`
- Override: `MESHCORE_DB`

## Deep links

```
meshcore://channel/add?name=<name>&secret=<32 hex>
meshcore://contact/add?name=<name>&public_key=<64 hex>&type=1
```
