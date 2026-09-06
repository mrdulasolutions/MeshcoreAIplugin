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
    if args.channel:
        post_local(con, args.channel, ident["public_key"], args.hello or f"{ident['name']} here.")


def post_local(con: sqlite3.Connection, channel: str, sender_hex: str, text: str) -> None:
    secret = channel_secret_for(con, channel)
    now = int(time.time())
    now_ms = now * 1000
    con.execute(
        """INSERT INTO channel_messages
           (channel_secret, "from", path_len, txt_type, sender_timestamp, text, timestamp, repeats_heard_count)
           VALUES (?, ?, 0, 0, ?, ?, ?, 0)""",
        (secret, sender_hex.lower(), now, text, now_ms),
    )
    con.execute(
        "UPDATE channels SET last_message_sent_or_received_at = ? WHERE secret = ?",
        (now_ms, secret),
    )
    con.commit()
    print(f"posted locally to {channel}: {text}")


def cmd_post(args: argparse.Namespace) -> None:
    info = plist_self_info() or {}
    sender = args.as_key or info.get("public_key")
    if not sender:
        raise SystemExit("pass --as-key (64 hex) or open MeshCore so flutter.current_self_info exists")
    con = connect(find_db())
    post_local(con, args.channel, sender, args.text)
    print("note: this is a local app-DB insert. It does not transmit over LoRa.")


def cmd_watch(args: argparse.Namespace) -> None:
    con = connect(find_db())
    secret = channel_secret_for(con, args.channel)
    last = con.execute(
        "SELECT COALESCE(MAX(id), 0) FROM channel_messages WHERE channel_secret = ?",
        (secret,),
    ).fetchone()[0]
    print(f"watching {args.channel} from id {last}", flush=True)
    while True:
        time.sleep(args.interval)
        con = connect(find_db())
        rows = con.execute(
            """SELECT id, timestamp, "from" AS sender, text
               FROM channel_messages
               WHERE channel_secret = ? AND id > ?
               ORDER BY id""",
            (secret, last),
        ).fetchall()
        for r in rows:
            last = r["id"]
            print(f"{r['id']}\t{r['timestamp']}\t{r['sender'] or ''}\t{r['text']}", flush=True)


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
    ag.add_argument("--channel", help="also post a local hello on this channel")
    ag.add_argument("--hello")
    ag.add_argument("--store", default="~/.meshcore")
    ag.add_argument("--no-open", action="store_true")
    ag.set_defaults(func=cmd_add_agent)

    po = sub.add_parser("post", help="insert a local channel message (not LoRa)")
    po.add_argument("channel")
    po.add_argument("text")
    po.add_argument("--as-key", help="sender public key hex")
    po.set_defaults(func=cmd_post)

    w = sub.add_parser("watch", help="poll channel_messages and print new rows")
    w.add_argument("channel")
    w.add_argument("--interval", type=float, default=2.0)
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
