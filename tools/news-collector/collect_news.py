#!/usr/bin/env python3
"""World/KCME Discord announcement relay collector.

Reads followed announcement copies from relay channels on a Discord server the
user controls and writes World data/news/feed.json.  Uses only Python stdlib.
The bot token is read from DISCORD_BOT_TOKEN and is never written to disk.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://discord.com/api/v10"
USER_AGENT = "KCME-World-NewsCollector/1.0"
URL_RE = re.compile(r"https?://[^\s<>]+")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def api_get(path: str, token: str, retry: bool = True) -> Any:
    req = urllib.request.Request(
        API + path,
        headers={
            "Authorization": f"Bot {token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 429 and retry:
            try:
                delay = float(json.loads(body).get("retry_after", 1.0))
            except Exception:
                delay = 1.0
            time.sleep(max(0.25, min(delay, 10.0)))
            return api_get(path, token, retry=False)
        if e.code == 401:
            raise RuntimeError("Discord rejected the bot token (401). Check DISCORD_BOT_TOKEN.") from e
        if e.code == 403:
            raise RuntimeError("Discord denied access (403). Give the bot View Channel + Read Message History in the relay channel.") from e
        raise RuntimeError(f"Discord API HTTP {e.code}: {body[:400]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach Discord API: {e.reason}") from e


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    s = value.replace("\r", "").strip()
    return re.sub(r"\n{3,}", "\n\n", s)


def first_line(text: str, max_len: int = 120) -> str:
    for raw in text.splitlines():
        line = raw.strip().lstrip("#>*- ").strip()
        if line:
            return line if len(line) <= max_len else line[: max_len - 1].rstrip() + "…"
    return ""


def snapshot_message(message: dict[str, Any]) -> dict[str, Any]:
    # Forwarded/crossposted messages may expose the original payload as a snapshot.
    snaps = message.get("message_snapshots") or []
    if isinstance(snaps, list) and snaps:
        snap = snaps[0]
        if isinstance(snap, dict) and isinstance(snap.get("message"), dict):
            return snap["message"]
    return message


def embed_data(message: dict[str, Any]) -> tuple[str, str, str, str]:
    embeds = message.get("embeds") or []
    if not isinstance(embeds, list):
        return "", "", "", ""
    for emb in embeds:
        if not isinstance(emb, dict):
            continue
        title = clean_text(emb.get("title"))
        desc = clean_text(emb.get("description"))
        url = clean_text(emb.get("url"))
        image = ""
        for key in ("image", "thumbnail"):
            node = emb.get(key)
            if isinstance(node, dict):
                image = clean_text(node.get("url") or node.get("proxy_url"))
                if image:
                    break
        if title or desc or url or image:
            return title, desc, url, image
    return "", "", "", ""


def first_attachment_url(message: dict[str, Any]) -> tuple[str, str]:
    atts = message.get("attachments") or []
    if not isinstance(atts, list):
        return "", ""
    for att in atts:
        if not isinstance(att, dict):
            continue
        url = clean_text(att.get("url"))
        name = clean_text(att.get("filename"))
        ctype = clean_text(att.get("content_type"))
        if url:
            if ctype.startswith("image/"):
                return url, name
            return "", name
    return "", ""


def discord_reference_url(message: dict[str, Any], source: dict[str, Any]) -> str:
    ref = message.get("message_reference")
    if isinstance(ref, dict):
        mid = str(ref.get("message_id") or "").strip()
        cid = str(ref.get("channel_id") or source.get("origin_channel_id") or "").strip()
        gid = str(ref.get("guild_id") or source.get("origin_guild_id") or "").strip()
        if mid and cid and gid:
            return f"https://discord.com/channels/{gid}/{cid}/{mid}"
    return ""


def normalize(message: dict[str, Any], source: dict[str, Any]) -> dict[str, Any] | None:
    payload = snapshot_message(message)
    content = clean_text(payload.get("content") or message.get("content"))
    etitle, edesc, eurl, eimage = embed_data(payload)
    if not any((etitle, edesc, eurl, eimage)):
        etitle, edesc, eurl, eimage = embed_data(message)
    aimage, aname = first_attachment_url(payload)
    if not aimage and not aname:
        aimage, aname = first_attachment_url(message)

    title = etitle or first_line(content) or first_line(edesc) or aname or "New announcement"
    summary = edesc or content
    if summary and summary.startswith(title):
        summary = summary[len(title):].lstrip(" \n:-—")
    if len(summary) > 600:
        summary = summary[:599].rstrip() + "…"

    # Prefer an original Discord reference, then an embed URL, then any URL in text.
    url = discord_reference_url(message, source) or eurl
    if not url:
        m = URL_RE.search(content + "\n" + edesc)
        if m:
            url = m.group(0).rstrip(".,);]")

    published = clean_text(payload.get("timestamp") or message.get("timestamp"))
    if not published:
        published = utc_now()

    mid = str(message.get("id") or "").strip()
    if not mid:
        return None

    relay_channel = str(source.get("relay_channel_id") or "")
    relay_url = f"https://discord.com/channels/@me/{relay_channel}/{mid}" if relay_channel else ""

    item = {
        "id": mid,
        "source_id": source["id"],
        "source_name": source["name"],
        "section": source.get("section") or "News",
        "title": title,
        "summary": summary,
        "published": published,
        "url": url,
        "image": eimage or aimage,
        "relay_channel_id": relay_channel,
        "relay_message_id": mid,
    }
    # Keep relay_url only as diagnostics; distributed World clients should use url.
    if relay_url:
        item["relay_url"] = relay_url
    return item


def collect(config_path: pathlib.Path, output_path: pathlib.Path, token: str, limit_per_channel: int, max_items: int) -> dict[str, Any]:
    config = load_json(config_path)
    sources = config.get("sources") or []
    if not sources:
        raise RuntimeError(f"No sources configured in {config_path}")

    all_items: list[dict[str, Any]] = []
    status: list[dict[str, Any]] = []
    for source in sources:
        cid = str(source.get("relay_channel_id") or "").strip()
        if not cid:
            status.append({"source_id": source.get("id"), "ok": False, "error": "missing relay_channel_id"})
            continue
        try:
            encoded = urllib.parse.urlencode({"limit": max(1, min(limit_per_channel, 100))})
            messages = api_get(f"/channels/{cid}/messages?{encoded}", token)
            count = 0
            for message in messages if isinstance(messages, list) else []:
                if not isinstance(message, dict):
                    continue
                item = normalize(message, source)
                if item:
                    all_items.append(item)
                    count += 1
            status.append({"source_id": source.get("id"), "ok": True, "messages": count})
        except Exception as exc:
            status.append({"source_id": source.get("id"), "ok": False, "error": str(exc)})

    # Relay channels are independent, so de-dupe by source+message id and order newest first.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in all_items:
        unique[(item["source_id"], item["id"])] = item
    items = list(unique.values())
    items.sort(key=lambda x: x.get("published", ""), reverse=True)
    items = items[:max_items]

    good = sum(1 for s in status if s.get("ok"))
    feed = {
        "version": 1,
        "updated": utc_now(),
        "collector": {
            "sources_ok": good,
            "sources_total": len(status),
            "status": status,
        },
        "items": items,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(output_path)
    return feed


def main() -> int:
    here = pathlib.Path(__file__).resolve().parent
    root = here.parent.parent
    parser = argparse.ArgumentParser(description="Collect Discord relay announcements for World/KCME")
    parser.add_argument("--config", type=pathlib.Path, default=root / "data" / "news" / "sources.json")
    parser.add_argument("--output", type=pathlib.Path, default=root / "data" / "news" / "feed.json")
    parser.add_argument("--limit", type=int, default=50, help="messages fetched per relay channel (1..100)")
    parser.add_argument("--max-items", type=int, default=60, help="maximum normalized items kept in feed")
    parser.add_argument("--watch", type=int, default=0, metavar="SECONDS", help="repeat every N seconds (minimum 60)")
    args = parser.parse_args()

    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("ERROR: DISCORD_BOT_TOKEN is not set.", file=sys.stderr)
        print("PowerShell example for this terminal only:", file=sys.stderr)
        print("  $env:DISCORD_BOT_TOKEN='PASTE_TOKEN_LOCALLY_HERE'", file=sys.stderr)
        return 2

    interval = max(60, args.watch) if args.watch else 0
    while True:
        try:
            feed = collect(args.config, args.output, token, args.limit, args.max_items)
            c = feed["collector"]
            print(f"[{feed['updated']}] wrote {len(feed['items'])} items; sources {c['sources_ok']}/{c['sources_total']} OK -> {args.output}")
            for s in c["status"]:
                if not s.get("ok"):
                    print(f"  WARN {s.get('source_id')}: {s.get('error')}", file=sys.stderr)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            if not interval:
                return 1
        if not interval:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
