---
name: disruptron-context-memory
description: >-
  Persist and recall chat context across browser, Telegram, and CLI using the
  SQLite context database. Use when continuing a conversation, remembering prior
  investigations, storing run_id/chat_id, or avoiding 16k context overflow.
---

# NV-Disruptron context memory (SQLite)

Durable chat state lives in **`data/disruptron_context.db`** — not in the live LLM window.

## When to activate

- User returns to a browser/Telegram chat and expects continuity
- After a long tool-heavy turn — store facts, recall summary next turn
- Before answering "what did we discuss?" or "continue from last time"
- After compaction or `/new` — reload facts from DB instead of full history

## MCP tools (preferred)

| Tool | Use |
|------|-----|
| `disruptron_ops__recall_conversation_context` | Compact recall block (`channel`, `chat_id`, default `browser`/`main`) |
| `disruptron_ops__store_memory_fact` | Save durable fact (line names, stress scores, decisions) |

## CLI (programming skill)

```bash
cd /home/nvidia/NV-Disruptron-Gyana/features/agent/workspace

# Import OpenClaw Control UI / CLI sessions into SQLite
python3 scripts/sync_openclaw_context.py
# or: disruptron context sync

# Recall for injection (stay under ~2800 chars)
python3 scripts/context_store.py recall --channel browser --chat-id main

# Record a turn manually
python3 scripts/context_store.py record --channel browser --chat-id main \
  --role user --text "Check Jubilee line" --run-id run-abc

# Store a fact
python3 scripts/context_store.py fact --text "Stress score was 62; Jubilee delayed" \
  --key stress --channel browser --chat-id main
```

## REST API (outputs-api :8010)

| Endpoint | Action |
|----------|--------|
| `GET /v1/context/recall?channel=browser&chat_id=main` | Compact recall |
| `POST /v1/context/messages` | Append message + run_id |
| `POST /v1/context/facts` | Store memory fact |
| `POST /v1/context/sync/openclaw` | Import OpenClaw JSONL sessions |
| `GET /v1/context/session-id?channel=browser&chat_id=main` | Stable session id |

## IDs

| Field | Example | Meaning |
|-------|---------|---------|
| `channel` | `browser`, `telegram`, `cli` | Surface |
| `chat_id` | `main`, `8734062810` | Conversation key within channel |
| `conversation_id` | `browser:main` | DB primary key |
| `run_id` | OpenClaw turn / message id | Tie tool results to a turn |
| `openclaw_session_id` | `disruptron-a1b2…` | Stable `--session-id` for continuity |

## Agent loop

1. **`recall_conversation_context`** (or CLI recall) at start of interactive turns
2. Answer using live MCP tools — summarize in chat, don't dump JSON
3. **`store_memory_fact`** for anything the user will need next session
4. Run **`disruptron context sync`** after long browser sessions (imports JSONL + compaction summaries)

Images: store `[image attached]` + optional `image_ref` path in `record --image-ref`; vision stays in OpenClaw transcript, DB keeps reference only.
