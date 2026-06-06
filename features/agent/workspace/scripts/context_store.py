#!/usr/bin/env python3
"""CLI for NV-Disruptron SQLite context store (agent programming skill)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SHARED = ROOT / "platform" / "shared"
sys.path.insert(0, str(SHARED))

from context_store import ContextStore, sync_all_openclaw_sessions  # noqa: E402


def _db() -> ContextStore:
    db = os.environ.get("DISRUPTRON_CONTEXT_DB", str(ROOT / "data" / "disruptron_context.db"))
    return ContextStore(db)


def cmd_record(args: argparse.Namespace) -> int:
    media = json.loads(args.media) if args.media else {}
    if args.image_ref:
        media["image_ref"] = args.image_ref
        args.content_type = "image"
    msg = _db().append_message(
        channel=args.channel,
        external_chat_id=args.chat_id,
        role=args.role,
        content=args.text,
        run_id=args.run_id,
        content_type=args.content_type,
        media=media,
        input_tokens=args.input_tokens,
        output_tokens=args.output_tokens,
        session_key=args.session_key,
        openclaw_session_id=args.openclaw_session_id,
    )
    print(json.dumps({"ok": True, "message_id": msg.id, "conversation_id": msg.conversation_id}))
    return 0


def cmd_recall(args: argparse.Namespace) -> int:
    out = _db().recall(
        channel=args.channel,
        external_chat_id=args.chat_id,
        max_chars=args.max_chars,
        message_limit=args.message_limit,
        fact_limit=args.fact_limit,
    )
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(out["recall_text"])
    return 0


def cmd_fact(args: argparse.Namespace) -> int:
    cid = None
    if args.channel and args.chat_id:
        from context_store import conversation_id

        cid = conversation_id(args.channel, args.chat_id)
    fid = _db().add_fact(
        fact_text=args.text,
        scope=args.scope,
        conversation_id=cid,
        fact_key=args.key,
        source_run_id=args.run_id,
        tags=args.tags.split(",") if args.tags else None,
    )
    print(json.dumps({"ok": True, "fact_id": fid}))
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    if args.openclaw:
        result = sync_all_openclaw_sessions(_db())
    elif args.jsonl:
        result = _db().sync_openclaw_transcript(
            Path(args.jsonl),
            channel=args.channel,
            external_chat_id=args.chat_id,
        )
    else:
        print("Specify --openclaw or --jsonl PATH", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_session_id(args: argparse.Namespace) -> int:
    sid = _db().openclaw_session_id_for(args.channel, args.chat_id)
    print(json.dumps({"openclaw_session_id": sid, "channel": args.channel, "chat_id": args.chat_id}))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="NV-Disruptron context store CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="Append a message")
    r.add_argument("--channel", default="browser")
    r.add_argument("--chat-id", default="main")
    r.add_argument("--role", required=True, choices=["user", "assistant", "system", "tool"])
    r.add_argument("--text", required=True)
    r.add_argument("--run-id")
    r.add_argument("--content-type", default="text")
    r.add_argument("--image-ref")
    r.add_argument("--media", help="JSON object for media metadata")
    r.add_argument("--input-tokens", type=int)
    r.add_argument("--output-tokens", type=int)
    r.add_argument("--session-key")
    r.add_argument("--openclaw-session-id")
    r.set_defaults(func=cmd_record)

    rc = sub.add_parser("recall", help="Build compact recall block for agent prompt")
    rc.add_argument("--channel", default="browser")
    rc.add_argument("--chat-id", default="main")
    rc.add_argument("--max-chars", type=int, default=2800)
    rc.add_argument("--message-limit", type=int, default=12)
    rc.add_argument("--fact-limit", type=int, default=8)
    rc.add_argument("--json", action="store_true")
    rc.set_defaults(func=cmd_recall)

    f = sub.add_parser("fact", help="Store a durable memory fact")
    f.add_argument("--text", required=True)
    f.add_argument("--scope", default="global", choices=["global", "conversation", "user"])
    f.add_argument("--channel")
    f.add_argument("--chat-id")
    f.add_argument("--key")
    f.add_argument("--run-id")
    f.add_argument("--tags")
    f.set_defaults(func=cmd_fact)

    s = sub.add_parser("sync", help="Import OpenClaw session transcripts")
    s.add_argument("--openclaw", action="store_true", help="Sync all ~/.openclaw/disruptron sessions")
    s.add_argument("--jsonl", help="Single session JSONL path")
    s.add_argument("--channel", default="browser")
    s.add_argument("--chat-id", default="main")
    s.set_defaults(func=cmd_sync)

    sid = sub.add_parser("session-id", help="Get/create stable OpenClaw session id")
    sid.add_argument("--channel", default="browser")
    sid.add_argument("--chat-id", default="main")
    sid.set_defaults(func=cmd_session_id)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
