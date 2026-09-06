#!/usr/bin/env python3
"""Talk to the official MeshCore desktop app through its local SQLite DB.

Does not connect over BLE. The MeshCore app keeps the radio. This CLI
reads/writes the app database and opens meshcore:// deep links so the
running app can join channels and add contacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


def home() -> Path:
    return Path.home()


def candidate_db_dirs() -> list[Path]:
    h = home()
    return [
        h / "Library/Containers/com.liamcottle.meshcore.macos/Data/Documents",
        h / "Library/Application Support/com.liamcottle.meshcore.macos",
        h / "Library/Application Support/MeshCore",
        h / ".local/share/com.liamcottle.meshcore",
        Path(os.environ.get("APPDATA", "")) / "com.liamcottle.meshcore" if os.environ.get("APPDATA") else Path(),
    ]


def find_db() -> Path:
    env = os.environ.get("MESHCORE_DB")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return p
        raise SystemExit(f"MESHCORE_DB not a file: {p}")
    found: list[Path] = []
    for d in candidate_db_dirs():
        if not d or not d.is_dir():
            continue
        found.extend(sorted(d.glob("meshcore_*.sqlite")))
        found.extend(sorted(d.glob("*.sqlite")))
    # Prefer meshcore_<64hex>.sqlite
    named = [p for p in found if p.name.startswith("meshcore_") and p.suffix == ".sqlite"]
    pick = named or found
    if not pick:
        raise SystemExit(
            "No MeshCore sqlite DB found. Open the official MeshCore app once, "
            "or set MESHCORE_DB to the sqlite path."
        )
    return pick[0]


def connect(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    return con


def plist_self_info() -> dict | None:
    plist = (
        home()
        / "Library/Containers/com.liamcottle.meshcore.macos/Data/Library/Preferences/com.liamcottle.meshcore.macos.plist"
    )
    if not plist.is_file():
        return None
    try:
        raw = subprocess.check_output(
            ["plutil", "-extract", "flutter.current_self_info", "raw", str(plist)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return json.loads(raw)
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError, OSError):
        return None


def hexblob(b: bytes | None) -> str:
    if b is None:
        return ""
    if isinstance(b, str):
        return b
    return b.hex()


def parse_secret(s: str) -> bytes:
    s = s.strip().lower().replace("0x", "")
    if len(s) != 32:
        raise SystemExit("channel secret must be 32 hex chars (16 bytes)")
    return bytes.fromhex(s)


def hashtag_secret(name: str) -> bytes:
    n = name.strip()
    if n.startswith("#"):
        n = n[1:]
    return hashlib.sha256(("#" + n).encode("utf-8")).digest()[:16]


def open_url(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.check_call(["open", url])
    elif sys.platform == "win32":
        os.startfile(url)  # type: ignore[attr-defined]
    else:
        subprocess.check_call(["xdg-open", url])


def cmd_discover(_args: argparse.Namespace) -> None:
    db = find_db()
    print(f"db\t{db}")
    info = plist_self_info()
    if info:
        print(f"name\t{info.get('name')}")
        print(f"public_key\t{info.get('public_key')}")
        print(f"freq_hz\t{info.get('radio_freq')}")
        print(f"sf\t{info.get('radio_sf')}")
        print(f"bw\t{info.get('radio_bw')}")
        print(f"cr\t{info.get('radio_cr')}")


def cmd_info(args: argparse.Namespace) -> None:
    cmd_discover(args)
    con = connect(find_db())
    print("\nchannels")
    for r in con.execute("SELECT channel_idx, name, hex(secret) AS secret FROM channels WHERE name != '' ORDER BY channel_idx"):
        print(f"  {r['channel_idx']}\t{r['name']}\t{r['secret']}")
    print("contacts")
    for r in con.execute("SELECT id, adv_name, hex(public_key) AS pk FROM contacts ORDER BY id"):
        print(f"  {r['id']}\t{r['adv_name']}\t{r['pk']}")


def cmd_channels(_args: argparse.Namespace) -> None:
    con = connect(find_db())
    for r in con.execute(
        "SELECT channel_idx, name, hex(secret) AS secret, last_message_sent_or_received_at AS last "
        "FROM channels WHERE name != '' ORDER BY channel_idx"
    ):
        print(f"{r['channel_idx']}\t{r['name']}\t{r['secret']}\t{r['last'] or ''}")


def cmd_contacts(_args: argparse.Namespace) -> None:
    con = connect(find_db())
    for r in con.execute("SELECT id, adv_name, type, hex(public_key) AS pk FROM contacts ORDER BY id"):
        print(f"{r['id']}\t{r['adv_name']}\t{r['type']}\t{r['pk']}")


def channel_secret_for(con: sqlite3.Connection, name: str) -> bytes:
    row = con.execute("SELECT secret FROM channels WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if not row:
        raise SystemExit(f"no channel named {name!r}")
    secret = row["secret"]
    if isinstance(secret, str):
        return bytes.fromhex(secret)
    return bytes(secret)


def cmd_messages(args: argparse.Namespace) -> None:
    con = connect(find_db())
    secret = channel_secret_for(con, args.channel)
    q = """
      SELECT id, timestamp, sender_timestamp, "from" AS sender, text
      FROM channel_messages
      WHERE channel_secret = ?
      ORDER BY id
    """
    for r in con.execute(q, (secret,)):
        print(f"{r['id']}\t{r['timestamp']}\t{r['sender'] or ''}\t{r['text']}")


def cmd_add_channel(args: argparse.Namespace) -> None:
    name = args.name
    if args.hashtag:
        secret = hashtag_secret(name)
        if not name.startswith("#"):
            name = "#" + name
    elif args.secret:
        secret = parse_secret(args.secret)
    else:
        secret = os.urandom(16)
    url = f"meshcore://channel/add?name={name}&secret={secret.hex()}"
    print(url)
    if not args.no_open:
        open_url(url)
        time.sleep(1.5)
    # Record locally if the app already wrote it; otherwise insert a row so watchers work.
    db = find_db()
    con = connect(db)
    existing = con.execute("SELECT 1 FROM channels WHERE hex(secret) = ?", (secret.hex().upper(),)).fetchone()
    if not existing:
        nxt = con.execute("SELECT COALESCE(MAX(channel_idx), -1) + 1 FROM channels").fetchone()[0]
        con.execute(
            "INSERT INTO channels (channel_idx, name, secret) VALUES (?, ?, ?)",
            (nxt, name.lstrip("#") if not args.hashtag else name, secret),
        )
        con.commit()
        print(f"local slot {nxt}")
    else:
        print("app already has this channel")


def generate_identity(name: str, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    ident_path = dest / f"{name.lower().replace(' ', '-')}-identity.json"
    if ident_path.exists():
        return json.loads(ident_path.read_text())
    pem = dest / f"{name.lower().replace(' ', '-')}-ed25519.pem"
    subprocess.check_call(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(pem)], stdout=subprocess.DEVNULL)
    pub_pem = subprocess.check_output(["openssl", "pkey", "-in", str(pem), "-pubout"], text=True)
    import base64

    b64 = "".join(line for line in pub_pem.splitlines() if not line.startswith("-----"))
    pk = base64.b64decode(b64)[-32:].hex()
    ident = {"name": name, "public_key": pk, "pem": str(pem)}
    ident_path.write_text(json.dumps(ident, indent=2) + "\n")
    os.chmod(ident_path, 0o600)
    os.chmod(pem, 0o600)
    return ident


def cmd_add_agent(args: argparse.Namespace) -> None:
    store = Path(args.store).expanduser()
    ident = generate_identity(args.name, store)
    url = f"meshcore://contact/add?name={ident['name']}&public_key={ident['public_key']}&type=1"
    print(url)
    print(f"public_key\t{ident['public_key']}")
    if not args.no_open:
        open_url(url)
        time.sleep(1.5)
    con = connect(find_db())
    pk = bytes.fromhex(ident["public_key"])
    now = int(time.time())
    if not con.execute("SELECT 1 FROM contacts WHERE public_key = ?", (pk,)).fetchone():
        con.execute(
            """INSERT INTO contacts
               (public_key, type, flags, out_path_len, out_path, adv_name, last_advert, adv_lat, adv_lon, last_mod)
               VALUES (?, 1, 0, 0, ?, ?, ?, 0, 0, ?)""",
            (pk, bytes(64), ident["name"], now, now),
        )
        con.commit()
        print("contact inserted")
    else:
        print("contact already present")
    if args.hello:
        if not args.channel:
            raise SystemExit("--hello requires --channel")
        post_local(con, args.channel, args.hello, as_name=ident["name"])


def post_local(
    con: sqlite3.Connection,
    channel: str,
    text: str,
    *,
    as_name: str | None = None,
    as_key: str | None = None,
) -> None:
    """Insert a channel line in the same shape the MeshCore app uses.

    Own messages: from=<self pubkey>, text=<body>
    Everyone else (left-side bubbles): from=NULL, text='Name: body'

    A colon in the body without the Name: prefix makes the app invent a
    new @ contact from the words before the colon.
    """
    secret = channel_secret_for(con, channel)
    now = int(time.time())
    now_ms = now * 1000
    body = text.strip()
    if as_name:
        prefix = f"{as_name}: "
        if not body.startswith(prefix):
            body = prefix + body
        from_val = None
        path_len = 0
    else:
        from_val = (as_key or "").lower() or None
        path_len = None
    con.execute(
        """INSERT INTO channel_messages
           (channel_secret, "from", path_len, txt_type, sender_timestamp, text, timestamp, repeats_heard_count)
           VALUES (?, ?, ?, 0, ?, ?, ?, 0)""",
        (secret, from_val, path_len, now, body, now_ms),
    )
    con.execute(
        "UPDATE channels SET last_message_sent_or_received_at = ? WHERE secret = ?",
        (now_ms, secret),
    )
    con.commit()
    print(f"posted locally to {channel}: {body}")


def cmd_post(args: argparse.Namespace) -> None:
    con = connect(find_db())
    name = args.as_name
    key = args.as_key
    if not name and key:
        row = con.execute(
            "SELECT adv_name FROM contacts WHERE lower(hex(public_key)) = ?",
            (key.lower(),),
        ).fetchone()
        if row and row["adv_name"]:
            name = row["adv_name"]
    if name:
        post_local(con, args.channel, args.text, as_name=name, as_key=key)
    else:
        info = plist_self_info() or {}
        sender = key or info.get("public_key")
        if not sender:
            raise SystemExit("pass --as-name Grok (other people) or --as-key for self")
        post_local(con, args.channel, args.text, as_key=sender)
    print("note: this is a local app-DB insert. It does not transmit over LoRa.")


def state_dir() -> Path:
    d = home() / ".meshcore" / "watch"
    d.mkdir(parents=True, exist_ok=True)
    return d


def agent_identities() -> list[dict]:
    out: list[dict] = []
    ident_dir = home() / ".meshcore"
    if not ident_dir.is_dir():
        return out
    for p in ident_dir.glob("*-identity.json"):
        try:
            out.append(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def is_agent_line(text: str | None) -> bool:
    if not text:
        return False
    for ident in agent_identities():
        name = ident.get("name")
        if name and text.startswith(f"{name}: "):
            return True
    return False


def agent_pubkeys_only() -> set[str]:
    keys: set[str] = set()
    for ident in agent_identities():
        pk = ident.get("public_key")
        if pk:
            keys.add(str(pk).lower())
    return keys


def mention_names(explicit: list[str] | None) -> list[str]:
    names = [n.strip() for n in (explicit or []) if n and n.strip()]
    if names:
        return names
    return [str(i["name"]) for i in agent_identities() if i.get("name")]


def is_contact_mention(text: str | None, names: list[str]) -> bool:
    """True if the MeshCore line @-mentions one of the agent contact names.

    App chips look like @[Grok] or @Grok. Older chips used @[Grok here. …].
    """
    if not text or not names:
        return False
    for name in names:
        n = re.escape(name)
        if re.search(rf"@\[\s*{n}(?:\s|[\].,!?:;]|$)", text, re.I):
            return True
        if re.search(rf"@{n}\b", text, re.I):
            return True
    return False


def sender_name(con: sqlite3.Connection, sender: str | None) -> str:
    if not sender:
        return "unknown"
    row = con.execute(
        "SELECT adv_name FROM contacts WHERE lower(hex(public_key)) = ?",
        (sender.lower(),),
    ).fetchone()
    if row and row["adv_name"]:
        return row["adv_name"]
    return sender[:12]


def cmd_watch(args: argparse.Namespace) -> None:
    """Host-side poll. Idle is silent. New inbound rows emit one ACTION_REQUIRED line.

    Agents must run this as a background monitor, not inside the LLM loop.
    """
    db = find_db()
    con = connect(db)
    secret = channel_secret_for(con, args.channel)
    st = state_dir() / f"{args.channel.lower()}.last_id"
    log = state_dir() / f"{args.channel.lower()}.log"
    if args.reset or not st.exists():
        last = con.execute(
            "SELECT COALESCE(MAX(id), 0) FROM channel_messages WHERE channel_secret = ?",
            (secret,),
        ).fetchone()[0]
        st.write_text(str(last))
    else:
        last = int(st.read_text().strip() or "0")
    names = mention_names(args.mention)
    if not names and not args.verbose:
        raise SystemExit("watch needs --mention NAME (or ~/.meshcore/*-identity.json)")
    if args.verbose:
        print(
            f"watching {args.channel} from id {last} mention={names}",
            flush=True,
        )
    while True:
        time.sleep(args.interval)
        con = connect(db)
        rows = con.execute(
            """SELECT id, timestamp, "from" AS sender, text
               FROM channel_messages
               WHERE channel_secret = ? AND id > ?
               ORDER BY id""",
            (secret, last),
        ).fetchall()
        for r in rows:
            last = r["id"]
            st.write_text(str(last))
            sender = (r["sender"] or "").lower()
            name = sender_name(con, r["sender"])
            line = f"{r['id']}\t{name}\t{r['text']}\n"
            with log.open("a") as f:
                f.write(line)
            if is_agent_line(r["text"]) or sender in agent_pubkeys_only():
                continue
            if not args.verbose and not is_contact_mention(r["text"], names):
                continue
            if args.verbose:
                print(line, end="", flush=True)
            else:
                text = (r["text"] or "").replace("\n", " ")
                print(f"ACTION_REQUIRED: MeshCore {args.channel} {name}: {text}", flush=True)


def cmd_join_url(args: argparse.Namespace) -> None:
    con = connect(find_db())
    row = con.execute("SELECT name, hex(secret) AS secret FROM channels WHERE name = ? COLLATE NOCASE", (args.channel,)).fetchone()
    if not row:
        raise SystemExit(f"no channel named {args.channel!r}")
    print(f"meshcore://channel/add?name={row['name']}&secret={row['secret'].lower()}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("discover", help="find MeshCore sqlite DB and node info").set_defaults(func=cmd_discover)
    sub.add_parser("info", help="node + channels + contacts").set_defaults(func=cmd_info)
    sub.add_parser("channels", help="list channels").set_defaults(func=cmd_channels)
    sub.add_parser("contacts", help="list contacts").set_defaults(func=cmd_contacts)

    m = sub.add_parser("messages", help="print channel history")
    m.add_argument("channel")
    m.set_defaults(func=cmd_messages)

    ac = sub.add_parser("add-channel", help="create/join a channel via meshcore://")
    ac.add_argument("name")
    ac.add_argument("--secret", help="32 hex chars; random if omitted")
    ac.add_argument("--hashtag", action="store_true", help="derive secret from #name")
    ac.add_argument("--no-open", action="store_true")
    ac.set_defaults(func=cmd_add_channel)

    ag = sub.add_parser("add-agent", help="create Ed25519 identity and add as MeshCore contact")
    ag.add_argument("name")
    ag.add_argument("--channel", help="only used with --hello")
    ag.add_argument("--hello", help="optional local DB line; do not use a 'I am here' banner")
    ag.add_argument("--store", default="~/.meshcore")
    ag.add_argument("--no-open", action="store_true")
    ag.set_defaults(func=cmd_add_agent)

    po = sub.add_parser("post", help="insert a local channel message (not LoRa)")
    po.add_argument("channel")
    po.add_argument("text")
    po.add_argument("--as-name", help="left-side sender, e.g. Grok (stores 'Name: text', from NULL)")
    po.add_argument("--as-key", help="self pubkey for right-side 'me' bubbles")
    po.set_defaults(func=cmd_post)

    w = sub.add_parser("watch", help="silent host poll; stdout only on new inbound messages")
    w.add_argument("channel")
    w.add_argument("--interval", type=float, default=2.0)
    w.add_argument("--verbose", action="store_true", help="print every new row, including self")
    w.add_argument("--reset", action="store_true", help="start from current max id")
    w.add_argument(
        "--mention",
        action="append",
        default=[],
        help="contact name that must be @-mentioned to wake (repeatable). Default: names in ~/.meshcore/*-identity.json",
    )
    w.set_defaults(func=cmd_watch)

    j = sub.add_parser("join-url", help="print meshcore:// join URL for a channel")
    j.add_argument("channel")
    j.set_defaults(func=cmd_join_url)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
