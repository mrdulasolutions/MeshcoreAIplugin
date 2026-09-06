# MeshCore AI plugin

Put an AI next to the official [MeshCore](https://meshcore.io) desktop app so it can **see a channel** and **help from the same computer**, without fighting the radio for Bluetooth.

**You** are already on the mesh (your node name, like MACDAGGER). The plugin does not replace you. It is a sidecar: it reads what the app already stored, and it can add a named contact (for example **Grok**) so the AI shows up in Participants.

Repo: https://github.com/mrdulasolutions/MeshcoreAIplugin

Stuck? See **[COMMON_ISSUES.md](COMMON_ISSUES.md)**.

---

## What you get

| You want | What to run |
| --- | --- |
| See if the plugin found your app | `python3 scripts/meshcore_ai.py discover` |
| List channels and contacts | `python3 scripts/meshcore_ai.py info` |
| Make a private channel | `python3 scripts/meshcore_ai.py add-channel Grok` |
| Invite someone else | `python3 scripts/meshcore_ai.py join-url Grok` |
| Show the AI as a participant | `python3 scripts/meshcore_ai.py add-agent Grok` then one `post --as-key …` |
| Listen without burning AI tokens | `python3 scripts/meshcore_ai.py watch Grok --reset` |

---

## Install (about two minutes)

1. Install the official **MeshCore** app and connect your companion radio (BLE is fine).
2. Open a channel once so the app creates its local database.
3. Clone this repo:

```bash
git clone https://github.com/mrdulasolutions/MeshcoreAIplugin.git
cd MeshcoreAIplugin
python3 scripts/meshcore_ai.py discover
```

You need **Python 3.10+**. `add-agent` also needs **openssl**.

If `discover` prints a `db` path, you are done.

### Give this to your AI

Copy `SKILL.md` into the agent’s skill folder (Grok: `~/.grok/skills/meshcore-ai/SKILL.md`). Or paste the repo URL and say: *follow SKILL.md, do not connect BLE.*

---

## Everyday use

**Create a room and share it**

```bash
python3 scripts/meshcore_ai.py add-channel Grok
python3 scripts/meshcore_ai.py join-url Grok
```

Send the `meshcore://channel/add?name=Grok&secret=…` link to the other node. They use **Add Channel** in MeshCore (or open the link).

**Listen (cheap)**

```bash
python3 scripts/meshcore_ai.py watch Grok --reset
```

Leave that running on the computer, not inside the chat. It sits quiet (no model tokens). When someone *else* posts, it prints one line:

```text
ACTION_REQUIRED: MeshCore Grok Dagger17: hello
```

Full log: `~/.meshcore/watch/Grok.log`.

Coding agents should attach a **persistent host monitor** to that command. Do not ask the model to “check every few seconds.”

**Optional: make the AI visible in Participants**

MeshCore lists people who have **spoken** on the channel, plus contacts. After `add-agent Grok`, post one real line as that identity (not “I am on this channel”):

```bash
python3 scripts/meshcore_ai.py post Grok "hi" --as-key <64-char public key from add-agent>
```

Then leave the Grok chat and open it again (or restart MeshCore). The app caches the list in memory.

That `post` is **only on this Mac**. The other radios will not hear it until someone sends the same text from the MeshCore app.

---

## What this is not

- It does **not** take Bluetooth from MeshCore.app. `meshcli --ble` will usually fail while the app is connected. That is expected. See [COMMON_ISSUES.md](COMMON_ISSUES.md).
- `post` does **not** transmit LoRa. The app still owns the radio.
- The AI is **not** a second handheld. Your node is the one on the air.

---

## Commands

```text
discover          Find the MeshCore sqlite DB
info              Node, channels, contacts
channels          Channel list
contacts          Contact list
messages NAME     History for one channel
add-channel NAME  Create/join via meshcore://  (--secret, --hashtag, --no-open)
join-url NAME     Print the invite link
add-agent NAME    Create an Ed25519 identity and add a contact (--hello is optional)
post NAME TEXT    Insert a local channel line (--as-key)
watch NAME        Silent listen (--reset, --verbose, --interval)
```

---

## Files

| File | Who it’s for |
| --- | --- |
| [README.md](README.md) | You |
| [COMMON_ISSUES.md](COMMON_ISSUES.md) | When something looks broken |
| [SKILL.md](SKILL.md) | The AI |
| [AGENTS.md](AGENTS.md) | Short rules for any coding agent |
| [scripts/meshcore_ai.py](scripts/meshcore_ai.py) | The CLI |
