---
name: meshcore-ai
description: >
  Add an AI agent to official MeshCore app channels without stealing the
  radio's BLE connection. Reads the MeshCore desktop sqlite DB, creates
  channels and contacts via meshcore:// deep links, watches channel
  history, and posts local participant messages. Use when the user says
  MeshCore, Grok channel, add an AI to MeshCore, monitor MeshCore app
  sqlite, meshcore://, MeshcoreAIplugin, or /meshcore-ai.
---

# MeshCore AI plugin

Work **through the official MeshCore app**, not over BLE to the companion radio.

The app holds Bluetooth to the node. A second BLE client will fail to find the device. Do not run `meshcli -a …` / `meshcli --ble` against a radio the app is already using.

## Model

| Piece | Role |
| --- | --- |
| MeshCore.app | Owns BLE/USB/TCP to the companion. Transmits LoRa. |
| App sqlite | Local cache of channels, contacts, messages. |
| `meshcore://` | Deep links the running app handles (`channel/add`, `contact/add`). |
| This CLI | Discover DB, open deep links, watch/post **local** rows. |

Local sqlite inserts show up in this copy of the app. They **do not go over LoRa**. Over-the-air send still requires the app (or exclusive `meshcli` with the app disconnected).

## Paths (macOS, verified)

- DB: `~/Library/Containers/com.liamcottle.meshcore.macos/Data/Documents/meshcore_<64-hex-pubkey>.sqlite`
- Prefs: `…/Preferences/com.liamcottle.meshcore.macos.plist` key `flutter.current_self_info`
- Override: `MESHCORE_DB=/path/to.sqlite`

Tables that matter: `channels` (`channel_idx`, `name`, `secret` blob 16 bytes), `contacts` (`adv_name`, `public_key` 32-byte blob, `type=1` companion), `channel_messages` (`channel_secret`, `from` hex pubkey text, `text`, `timestamp` ms, `sender_timestamp` seconds).

Channel participants are not a roster. Anyone with the secret who has a message in `channel_messages` is a participant.

## CLI

From this repo:

```bash
python3 scripts/meshcore_ai.py discover
python3 scripts/meshcore_ai.py info
python3 scripts/meshcore_ai.py channels
python3 scripts/meshcore_ai.py contacts
python3 scripts/meshcore_ai.py messages Grok
```

### Create a channel

Private (random secret):

```bash
python3 scripts/meshcore_ai.py add-channel Grok
```

Hashtag (secret = first 16 bytes of SHA-256 of `#name`):

```bash
python3 scripts/meshcore_ai.py add-channel grok --hashtag
```

Share with others:

```bash
python3 scripts/meshcore_ai.py join-url Grok
```

Prints `meshcore://channel/add?name=Grok&secret=<32 hex>`.

### Add the AI as a participant

```bash
python3 scripts/meshcore_ai.py add-agent Grok --channel Grok
```

Generates Ed25519 under `~/.meshcore/`, opens `meshcore://contact/add?name=Grok&public_key=…&type=1`, inserts the contact if the app did not, and posts a local hello on the channel.

Do **not** commit `*-identity.json` or `*.pem`.

### Watch (do this instead of BLE meshcli)

```bash
python3 scripts/meshcore_ai.py watch Grok --interval 2
```

Prints new `channel_messages` rows. When the user wants the agent in the room, keep this running and reply with `post` (local) or tell them to send from the app (RF).

### Local reply

```bash
python3 scripts/meshcore_ai.py post Grok "hello from the agent"
```

Always tell the user that `post` is local-only unless they send the same text in the MeshCore app.

## Agent procedure

1. `discover` / `info`. If no DB, tell the user to open MeshCore.app once.
2. If they want a named room, `add-channel` then `join-url`.
3. If they want the agent listed, `add-agent <Name> --channel <Room>`.
4. `watch` that channel. Do not connect BLE.
5. On new rows, answer in the user chat and `post` locally when they want the agent line in the app transcript.
6. If they insist on RF from the agent, say the app must send it, or they must quit MeshCore.app and use `meshcli` exclusively.

## Deep links (only two)

```
meshcore://channel/add?name=<name>&secret=<32 hex>
meshcore://contact/add?name=<name>&public_key=<64 hex>&type=1
```

`type`: 1 companion, 2 repeater, 3 room server, 4 sensor.

On macOS: `open '<url>'`.
