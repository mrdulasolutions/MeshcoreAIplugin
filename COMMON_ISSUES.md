# Common issues

Plain-language fixes from real MeshCore + AI setups (macOS, official Liam Cottle app).

## `meshcli` / BLE: “Couldn't find device”

The MeshCore app is already connected to the companion over Bluetooth. One radio, one BLE client.

**Do this:** use this plugin (`watch`, sqlite, `meshcore://`).  
**Do not:** run `meshcli -a MeshCore-…` while the app is open.

To use `meshcli` on the air, quit MeshCore.app first. You cannot have both at once unless you put a TCP proxy in the middle and reconnect the app over TCP.

## A new @ contact appears every time the AI posts (e.g. “2N 27525 Franklinton NC”)

Incoming MeshCore channel lines are stored as `DisplayName: rest of text` with an empty `from` field. Your own lines use your pubkey and **no** name prefix (they sit on the right as “me”).

If `post` writes `27525 Franklinton NC: Sunday about 82F…`, the app treats **27525 Franklinton NC** as the sender and your @ list changes.

**Fix:** post as a stable name:

```bash
python3 scripts/meshcore_ai.py post Grok "Sunday about 82F in 27525" --as-name Grok
```

That stores `Grok: Sunday about 82F in 27525` with `from` NULL, same as `Dagger17: Pong`. Leave the channel and reopen it.

Do not put a colon in the first words of the body unless it is `Grok:`.

## The AI is not in Participants

Participants are **senders on that channel**, not an invite list.

1. `add-agent Grok` so a **Grok** contact exists.
2. `post Grok "hi" --as-key <Grok public key>` so there is at least one row from that key.
3. Leave the channel and open it again, or quit and reopen MeshCore. The app often keeps an old in-memory list.

Do **not** post “Grok here, I am on this channel.” That looks like a second person claiming the room. You are already in it as your node (MACDAGGER, etc.).

## I removed Grok and Participants went empty for the AI

If you delete Grok’s contact **and** Grok’s messages, the app has nobody left to list. Add the contact and one message again.

## `post` showed up on my Mac but not on the other radio

`post` writes the **local sqlite file** only. It does not go over LoRa.

For the other node (Dagger17, a phone, …) type the same text in MeshCore.app and send.

## `discover` says no sqlite DB

Open MeshCore.app, connect the radio, open any channel once.

macOS path:

`~/Library/Containers/com.liamcottle.meshcore.macos/Data/Documents/meshcore_<64-hex>.sqlite`

Or set:

```bash
export MESHCORE_DB=/full/path/to.sqlite
```

## `add-channel` / `add-agent` did nothing in the UI

The CLI opened a `meshcore://` link. If the app did not come to the front, open MeshCore and tap the link again, or run without `--no-open`.

The CLI also inserts into sqlite. If the UI is stale, leave the screen and come back.

## Channel link does not join on the other device

Both sides need the **same 32-character secret**. `join-url` prints it. Hashtag channels (`--hashtag`) derive the secret from `#name`; a private `Grok` channel uses a random secret. Those are different rooms.

## I @Grok and the AI never answers

`watch` only wakes on an **@ mention of the contact name**, from anyone:

- `@Grok …`
- `@[Grok] …`

Plain channel chat with no @ does not notify (on purpose). Restart:

```bash
python3 scripts/meshcore_ai.py watch Grok --reset --mention Grok
```

`--mention` defaults to names in `~/.meshcore/*-identity.json`. Agent replies stored as `Grok: …` are ignored so they do not loop.

## Watcher never prints anything

That is success while idle. It only prints `ACTION_REQUIRED:` for **new inbound** messages, not your own node and not the agent identity in `~/.meshcore/*-identity.json`.

Check `~/.meshcore/watch/<channel>.log` for every row, including skipped ones.

`--reset` starts from the current last id so old history is not replayed.

## Watcher woke the AI on its own `post`

Older builds only skipped the MeshCore node key. Current `watch` also skips keys in `~/.meshcore/*-identity.json`. Update the repo and restart watch with `--reset`.

## The LLM is burning tokens while “listening”

The model is polling. Stop that.

Run `python3 scripts/meshcore_ai.py watch Grok --reset` as a **host** process (or an agent `monitor` with `persistent: true`). Idle CPU is tiny; idle tokens should be zero.

## `flutter.current_self_info` missing

Some app versions do not keep that plist key. `discover` still finds the DB. `post` without `--as-key` may fail; pass `--as-key` from `info` / the sqlite filename `meshcore_<pubkey>.sqlite`.

## USB plugged in and BLE companion dies (or the reverse)

Companion firmware is usually **one host**: BLE *or* USB serial, not both. If the MeshCore app is on BLE, do not also open the USB serial port from another program.

## Official MeshCore.app blocked on macOS

Desktop builds from files.liamcottle.net are often ad-hoc signed. System Settings → Privacy & Security → Open Anyway. Bluetooth permission must be on for MeshCore.

## I wanted the AI to speak on the air as itself

That needs a **second companion radio** (or exclusive `meshcli` with the app closed). This plugin cannot mint a live LoRa identity on the radio the app is already using.

## Android / iPhone only, no desktop app

This CLI looks for the **desktop** sqlite DB. Phone apps do not expose that file to the plugin. Use the desktop MeshCore app on a Mac/PC that is connected to the companion.
