# MeshCore AI plugin

Sidecar for the official [MeshCore](https://meshcore.io) desktop app. The person already on the channel **is** the participant. The AI watches the app’s local database. It does not steal Bluetooth and it does not need to announce itself in the chat.

https://github.com/mrdulasolutions/MeshcoreAIplugin

## Token-cheap listen

`watch` is a tiny host loop (sqlite poll). It prints **nothing** until a new inbound message arrives, then one line:

```text
ACTION_REQUIRED: MeshCore Grok Dagger17: hello
```

Point a coding-agent `monitor` at that command (`persistent: true`). Idle = 0 model tokens. Full history: `~/.meshcore/watch/<channel>.log`.

```bash
python3 scripts/meshcore_ai.py watch Grok --reset
```

Do **not** have the LLM sleep-and-poll.

## Install

```bash
git clone https://github.com/mrdulasolutions/MeshcoreAIplugin.git
cd MeshcoreAIplugin
python3 scripts/meshcore_ai.py discover
```

Python 3.10+, official MeshCore app opened once. Copy `SKILL.md` into the agent skill root.

## Flow

```bash
python3 scripts/meshcore_ai.py info
python3 scripts/meshcore_ai.py add-channel Grok          # once
python3 scripts/meshcore_ai.py join-url Grok             # share with others
python3 scripts/meshcore_ai.py watch Grok --reset        # leave running
```

Others join with the printed `meshcore://channel/add?name=Grok&secret=…` link.

## RF vs local

| Action | App UI | LoRa |
| --- | --- | --- |
| `add-channel` via `meshcore://` | Yes | Stored on companion if the app is connected |
| `watch` | Sees what the app already received | Yes (app already got it) |
| `post` | Local sqlite only | No |

## Why not BLE `meshcli`

The app already holds the companion radio. A second BLE client will not find the device. This plugin reads the app DB instead.
