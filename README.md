# MeshCore AI plugin

Give this repo to an AI (Grok, Claude, Cursor, …) so it can sit in **official MeshCore app** channels the same way a human does: through the app, not by stealing the radio’s Bluetooth.

Repo: https://github.com/mrdulasolutions/MeshcoreAIplugin

## Why this exists

The MeshCore desktop app holds the BLE (or USB/TCP) link to the companion node. A second client such as `meshcli --ble` will not see the device. The app already writes channels, contacts, and messages to a local SQLite file and handles `meshcore://` links. That is the supported side door.

## Install

```bash
git clone https://github.com/mrdulasolutions/MeshcoreAIplugin.git
cd MeshcoreAIplugin
python3 scripts/meshcore_ai.py discover
```

Needs Python 3.10+, `openssl` (for `add-agent`), and the official [MeshCore](https://meshcore.io) desktop app opened at least once.

For Grok/Claude: copy `SKILL.md` into the agent skill root, or point the agent at this repo.

## Typical flow

```bash
python3 scripts/meshcore_ai.py info
python3 scripts/meshcore_ai.py add-channel Grok
python3 scripts/meshcore_ai.py add-agent Grok --channel Grok
python3 scripts/meshcore_ai.py join-url Grok
python3 scripts/meshcore_ai.py watch Grok
```

Share the printed `meshcore://channel/add?…` URL with other nodes (for example Dagger17). They join in MeshCore → Add Channel.

## What is RF and what is not

| Action | On this Mac’s app | Over LoRa |
| --- | --- | --- |
| `add-channel` via `meshcore://` | Yes (app handles link) | Channel is stored on the companion if the app is connected |
| `add-agent` contact | Yes | Contact is local unless that public key actually adverts on air |
| `watch` | Yes | Sees whatever the app already received |
| `post` | Yes (sqlite insert) | **No** — the app must send the text |

MeshCore has no invite list. A “participant” is anyone who has spoken on that channel (or a contact you added).

## Agent instructions

See [SKILL.md](SKILL.md). Short copy for `AGENTS.md` / `CLAUDE.md` is in [AGENTS.md](AGENTS.md).

## Layout

```
SKILL.md                 # load this in the AI
AGENTS.md
README.md
scripts/meshcore_ai.py   # the CLI
```
