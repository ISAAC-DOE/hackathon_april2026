#!/usr/bin/env python3
"""
Discord <-> Claude Code bridge.

Mirrors the Telegram bot architecture: persistent Claude session, long-running
jobs, SLURM monitoring, and full command support.

Env vars:
  DISCORD_BOT_TOKEN      - Bot token from Discord Developer Portal (required)
  DISCORD_ALLOWED_USERS  - Comma-separated Discord user IDs (optional, empty = allow all)
  BOT_NAME               - Display name (default: "Isaac")
  CLAUDE_WORKING_DIR     - Working directory for Claude (default: ~/hackathon_april2026)
  CLAUDE_MAX_BUDGET      - Max spend per message in USD (default: no limit)
  CLAUDE_MODEL           - Model to use (default: CLI default)
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile

import aiohttp
import discord
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

ALLOWED_USER_IDS: set[int] = set()
_raw = os.environ.get("DISCORD_ALLOWED_USERS", "")
if _raw.strip():
    ALLOWED_USER_IDS = {int(uid.strip()) for uid in _raw.split(",") if uid.strip()}

BOT_NAME = os.environ.get("BOT_NAME", "Isaac")

CLAUDE_WORKING_DIR = os.environ.get(
    "CLAUDE_WORKING_DIR", os.path.expanduser("~/hackathon_april2026")
)
MAX_BUDGET = os.environ.get("CLAUDE_MAX_BUDGET", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "")

DISCORD_MAX_LEN = 2000
CLAUDE_TIMEOUT = 7200  # 2 hours

SESSION_FILE = os.path.join(
    os.environ.get("HOME", "/tmp"), ".claude-discord-session"
)

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("claude-discord")

# ---------------------------------------------------------------------------
# Discord client setup
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
client = discord.Client(intents=intents)

# ---------------------------------------------------------------------------
# Session persistence — single shared session across all channels
# ---------------------------------------------------------------------------
_lock = asyncio.Lock()
_session_id: str | None = None
_running_proc: asyncio.subprocess.Process | None = None
_watch_task: asyncio.Task | None = None
_watch_interval: int = 300
_known_jobs: dict[str, str] = {}


def _load_session() -> str | None:
    try:
        with open(SESSION_FILE) as f:
            raw = f.read().strip()
            if not raw:
                return None
            # Handle migration from JSON format
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    for sid in data.values():
                        if sid:
                            logger.info("Migrated session from multi-format: %s", sid)
                            return sid
                    return None
            except json.JSONDecodeError:
                pass
            logger.info("Loaded saved session: %s", raw)
            return raw
    except FileNotFoundError:
        pass
    return None


def _save_session(sid: str):
    with open(SESSION_FILE, "w") as f:
        f.write(sid)
    logger.info("Saved session: %s", sid)


def _clear_session():
    try:
        os.remove(SESSION_FILE)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Text-like file extensions we'll read inline
TEXT_EXTENSIONS = {
    ".txt", ".py", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h", ".hpp",
    ".java", ".rs", ".go", ".rb", ".pl", ".sh", ".bash", ".zsh", ".fish",
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".conf", ".xml",
    ".html", ".css", ".scss", ".less", ".md", ".rst", ".tex", ".csv", ".tsv",
    ".sql", ".r", ".R", ".m", ".f90", ".f", ".dat", ".log", ".env", ".gitignore",
    ".dockerfile", ".makefile", ".cmake", ".slurm", ".sbatch", ".sub",
}

# Max file size we'll read inline (100 KB). Larger files get saved to disk.
MAX_INLINE_SIZE = 100_000


async def _read_attachments(attachments: list[discord.Attachment]) -> tuple[str, list[str]]:
    """Download attachments. Returns (inline_text, list_of_saved_file_paths).

    Text files small enough are returned as inline text to include in the prompt.
    Larger or binary files are saved to CLAUDE_WORKING_DIR/uploads/ and their
    paths are reported so Claude can read them with its tools.
    """
    inline_parts = []
    saved_paths = []
    upload_dir = os.path.join(CLAUDE_WORKING_DIR, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        for att in attachments:
            ext = os.path.splitext(att.filename)[1].lower()
            is_text = ext in TEXT_EXTENSIONS or (att.content_type or "").startswith("text/")

            try:
                async with session.get(att.url) as resp:
                    data = await resp.read()
            except Exception as e:
                inline_parts.append(f"[Failed to download {att.filename}: {e}]")
                continue

            if is_text and len(data) <= MAX_INLINE_SIZE:
                # Small text file — include inline
                text = data.decode("utf-8", errors="replace")
                inline_parts.append(
                    f"--- attached file: {att.filename} ---\n{text}\n--- end of {att.filename} ---"
                )
            else:
                # Save to disk so Claude can access it
                dest = os.path.join(upload_dir, att.filename)
                # Avoid overwriting — append a suffix if needed
                if os.path.exists(dest):
                    base, extension = os.path.splitext(att.filename)
                    dest = tempfile.mktemp(prefix=f"{base}_", suffix=extension, dir=upload_dir)
                with open(dest, "wb") as f:
                    f.write(data)
                saved_paths.append(dest)
                size_kb = len(data) / 1024
                inline_parts.append(
                    f"[Attached file saved to: {dest} ({size_kb:.1f} KB) — "
                    f"use your Read tool to access it]"
                )

    return "\n\n".join(inline_parts), saved_paths


def _chunk(text: str, limit: int = DISCORD_MAX_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


async def _run_claude(message: str) -> str:
    """Run claude -p with streaming JSON. Returns final result text."""
    global _running_proc, _session_id

    cmd = [
        "claude", "-p",
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--verbose",
    ]

    if _session_id:
        cmd.extend(["--resume", _session_id])

    if MAX_BUDGET:
        cmd.extend(["--max-budget-usd", MAX_BUDGET])
    if CLAUDE_MODEL:
        cmd.extend(["--model", CLAUDE_MODEL])
    cmd.append(message)

    logger.info("Running claude (session=%s)...", _session_id or "new")
    print(f"\n{'='*60}")
    print(f"USER: {message}")
    print(f"{'='*60}")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=CLAUDE_WORKING_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _running_proc = proc

    final_result = ""
    session_id = None

    try:
        async def read_stream():
            nonlocal final_result, session_id
            while True:
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=CLAUDE_TIMEOUT
                )
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    event = json.loads(text)
                    etype = event.get("type", "")

                    if etype == "assistant" and "message" in event:
                        msg = event["message"]
                        if msg.get("type") == "tool_use":
                            tool = msg.get("name", "?")
                            print(f"  [TOOL] {tool}")
                        elif msg.get("type") == "text":
                            snippet = msg.get("text", "")[:200]
                            if snippet:
                                print(f"  {snippet}")
                    elif etype == "result":
                        session_id = event.get("session_id", "")
                        final_result = event.get("result", "")
                        cost = event.get("cost_usd", 0)
                        duration = event.get("duration_ms", 0)
                        print(f"\n  [DONE] ${cost:.4f} | {duration/1000:.1f}s")
                    elif etype == "system":
                        smsg = event.get("message", "")
                        if smsg:
                            print(f"  [SYS] {smsg[:100]}")
                    else:
                        if etype not in ("", "ping"):
                            content = str(event)[:150]
                            print(f"  [{etype}] {content[:100]}")
                except json.JSONDecodeError:
                    print(f"  {text[:100]}")

        await read_stream()
        await proc.wait()

    except asyncio.TimeoutError:
        proc.terminate()
        await proc.wait()
        print("  [TIMEOUT]")
        return f"(Claude timed out after {CLAUDE_TIMEOUT}s — try a simpler question or `!new` to reset)"
    finally:
        _running_proc = None
        sys.stdout.flush()

    if session_id:
        _session_id = session_id
        _save_session(session_id)

    if not final_result:
        err = ""
        if proc.stderr:
            err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
        if err:
            final_result = f"[stderr]\n{err}"
        else:
            final_result = "(empty response)"

    print(f"{'─'*60}\n")
    return final_result


# ---------------------------------------------------------------------------
# SLURM job monitoring
# ---------------------------------------------------------------------------
def _get_slurm_snapshot() -> str:
    sections = []
    try:
        r = subprocess.run(
            ["squeue", "-u", os.environ.get("USER", "dsokaras"), "-o",
             "%i|%j|%T|%M|%l|%P|%q|%D|%C|%m|%r|%V", "--noheader"],
            capture_output=True, text=True, timeout=30,
        )
        sections.append(
            f"=== MY JOBS (squeue) ===\n"
            f"JobID|Name|State|Elapsed|TimeLimit|Partition|QoS|Nodes|CPUs|Mem|Reason|SubmitTime\n"
            f"{r.stdout.strip() or '(none)'}"
        )
    except Exception as e:
        sections.append(f"squeue failed: {e}")

    try:
        r = subprocess.run(
            ["sinfo", "-o", "%P|%a|%l|%D|%T|%C", "--noheader"],
            capture_output=True, text=True, timeout=30,
        )
        sections.append(
            f"=== PARTITION STATUS (sinfo) ===\n"
            f"Partition|Avail|TimeLimit|Nodes|State|CPUs(A/I/O/T)\n"
            f"{r.stdout.strip()}"
        )
    except Exception as e:
        sections.append(f"sinfo failed: {e}")

    return "\n\n".join(sections)


def _get_my_jobs() -> dict[str, dict]:
    try:
        r = subprocess.run(
            ["squeue", "-u", os.environ.get("USER", "dsokaras"), "-o",
             "%i|%j|%T|%M|%P|%r", "--noheader"],
            capture_output=True, text=True, timeout=30,
        )
        jobs = {}
        for line in r.stdout.strip().splitlines():
            parts = line.strip().split("|")
            if len(parts) >= 5:
                jobs[parts[0].strip()] = {
                    "name": parts[1].strip(),
                    "state": parts[2].strip(),
                    "time": parts[3].strip(),
                    "partition": parts[4].strip(),
                    "reason": parts[5].strip() if len(parts) > 5 else "",
                }
        return jobs
    except Exception:
        return {}


async def _job_monitor(channel: discord.TextChannel):
    """Periodically check SLURM jobs and report changes."""
    global _known_jobs
    logger.info("Job monitor started (every %ds)", _watch_interval)

    _known_jobs = {jid: info["state"] for jid, info in _get_my_jobs().items()}
    n = len(_known_jobs)
    pending = sum(1 for s in _known_jobs.values() if s == "PENDING")
    await channel.send(
        f"**[{BOT_NAME}]** Watching {n} job(s) ({pending} pending). "
        f"Checking every {_watch_interval // 60} min."
    )

    while True:
        await asyncio.sleep(_watch_interval)
        try:
            current = _get_my_jobs()
            current_states = {jid: info["state"] for jid, info in current.items()}
            notifications = []

            # Jobs that left the queue (finished/failed)
            finished = [jid for jid in _known_jobs if jid not in current_states]
            for jid in finished:
                old_state = _known_jobs[jid]
                async with _lock:
                    response = await _run_claude(
                        f"SLURM job {jid} just left the queue (was {old_state}). "
                        f"Check its output/error files and tell me: did it succeed or fail? "
                        f"Summarize the result. If it failed, diagnose why and suggest a fix.",
                    )
                for chunk in _chunk(f"**[{BOT_NAME}]** Job {jid} finished (was {old_state}).\n\n{response}"):
                    await channel.send(chunk)

            # State changes
            for jid, info in current.items():
                old = _known_jobs.get(jid)
                if old and old != info["state"]:
                    notifications.append(
                        f"Job {jid} ({info['name']}): {old} -> {info['state']}"
                    )

            # New jobs
            for jid in current_states:
                if jid not in _known_jobs:
                    info = current[jid]
                    notifications.append(
                        f"New job: {jid} ({info['name']}) - {info['state']} on {info['partition']}"
                    )

            if notifications:
                await channel.send(f"**[{BOT_NAME}]**\n" + "\n".join(notifications))

            _known_jobs = current_states

        except asyncio.CancelledError:
            logger.info("Job monitor stopped")
            return
        except Exception as e:
            logger.exception("Job monitor error: %s", e)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
async def cmd_start(message: discord.Message):
    session_status = (
        f"Resuming session: `{_session_id[:8]}...`"
        if _session_id
        else "No active session (first message starts one)"
    )
    await message.channel.send(
        f"**{BOT_NAME}** — Claude Code bridge is live.\n\n"
        f"{session_status}\n\n"
        "**Commands:**\n"
        "`!new` — start a fresh conversation\n"
        "`!cancel` — abort a running Claude call\n"
        "`!status` — check if Claude is busy\n"
        "`!jobs` — show current SLURM jobs\n"
        "`!watch [min]` — auto-check jobs every N min (default 5)\n"
        "`!unwatch` — stop auto-checking\n"
    )


async def cmd_new(message: discord.Message):
    global _session_id
    _session_id = None
    _clear_session()
    await message.channel.send(
        "Session cleared. Next message starts a fresh Claude conversation."
    )


async def cmd_cancel(message: discord.Message):
    if _running_proc and _running_proc.returncode is None:
        _running_proc.terminate()
        await message.channel.send("Sent terminate signal to Claude.")
    else:
        await message.channel.send("No Claude process is running.")


async def cmd_status(message: discord.Message):
    busy = _running_proc and _running_proc.returncode is None
    sid = f"\nSession: `{_session_id[:8]}...`" if _session_id else "\nNo active session"
    if busy:
        await message.channel.send(f"**{BOT_NAME}** is processing a message.{sid}")
    else:
        await message.channel.send(f"**{BOT_NAME}** is idle.{sid}")


async def cmd_jobs(message: discord.Message):
    jobs = _get_my_jobs()
    if not jobs:
        await message.channel.send("No SLURM jobs running.")
        return
    lines = [f"{'ID':>10}  {'State':<10}  {'Time':<10}  {'Part':<10}  {'Name'}"]
    for jid, info in jobs.items():
        lines.append(
            f"{jid:>10}  {info['state']:<10}  {info['time']:<10}  "
            f"{info['partition']:<10}  {info['name']}"
        )
    await message.channel.send("```\n" + "\n".join(lines) + "\n```")


async def cmd_watch(message: discord.Message, args: str):
    global _watch_task, _watch_interval

    if args.strip():
        try:
            _watch_interval = int(args.strip()) * 60
        except ValueError:
            await message.channel.send("Usage: `!watch [minutes]`  (default: 5)")
            return

    if _watch_task and not _watch_task.done():
        _watch_task.cancel()
        await asyncio.sleep(0.5)

    _watch_task = asyncio.create_task(_job_monitor(message.channel))


async def cmd_unwatch(message: discord.Message):
    global _watch_task
    if _watch_task and not _watch_task.done():
        _watch_task.cancel()
        _watch_task = None
        await message.channel.send("Job monitor stopped.")
    else:
        await message.channel.send("No job monitor running.")


# Command dispatch table
COMMANDS = {
    "!start": cmd_start,
    "!help": cmd_start,
    "!new": cmd_new,
    "!cancel": cmd_cancel,
    "!status": cmd_status,
    "!jobs": cmd_jobs,
    "!unwatch": cmd_unwatch,
}


# ---------------------------------------------------------------------------
# Discord event handlers
# ---------------------------------------------------------------------------
@client.event
async def on_ready():
    global _session_id
    _session_id = _load_session()

    print(f"Bot is online as {client.user} (ID: {client.user.id})")
    print(f"Connected to {len(client.guilds)} server(s):")
    for guild in client.guilds:
        print(f"  - {guild.name} (ID: {guild.id})")
    print(f"Session: {_session_id or '(none — first message starts one)'}")
    print(f"Working dir: {CLAUDE_WORKING_DIR}")
    print(f"Timeout: {CLAUDE_TIMEOUT}s ({CLAUDE_TIMEOUT//3600}h)")
    print("---")


@client.event
async def on_message(message: discord.Message):
    # Don't respond to ourselves
    if message.author == client.user:
        return

    # Authorization check (if user IDs are configured)
    if ALLOWED_USER_IDS and message.author.id not in ALLOWED_USER_IDS:
        return

    text = message.content.strip()

    # Check if this message is for us: @mention, !command, or has attachments with mention
    is_mentioned = client.user.mentioned_in(message)
    is_command = text.startswith("!")
    is_dm = isinstance(message.channel, discord.DMChannel)
    has_attachments = len(message.attachments) > 0

    if not (is_mentioned or is_command or is_dm):
        return

    # Handle commands
    if is_command:
        cmd_word = text.split()[0].lower()

        if cmd_word == "!watch":
            args = text[len("!watch"):].strip()
            await cmd_watch(message, args)
            return

        if cmd_word in COMMANDS:
            await COMMANDS[cmd_word](message)
            return

    # Strip mention to get the actual message
    content = text
    if is_mentioned:
        content = content.replace(f"<@{client.user.id}>", "").strip()
    # Strip !bot prefix if used
    if content.lower().startswith("!bot"):
        content = content[4:].strip()

    # Process attachments (text files, code, data, etc.)
    attachment_text = ""
    if has_attachments:
        attachment_text, saved_paths = await _read_attachments(message.attachments)

    if not content and not attachment_text:
        await cmd_start(message)
        return

    # Build context-prefixed message (like the Telegram bot does)
    full_content = content
    if attachment_text:
        full_content = f"{content}\n\n{attachment_text}" if content else attachment_text

    if is_dm:
        prompt = f"[DM from {message.author.display_name}]: {full_content}"
    else:
        channel_name = message.channel.name if hasattr(message.channel, "name") else "unknown"
        guild_name = message.guild.name if message.guild else "unknown"
        prompt = (
            f"[Discord #{channel_name} in '{guild_name}', "
            f"from {message.author.display_name}]: {full_content}"
        )

    # Show typing indicator while Claude thinks
    thinking_msg = await message.channel.send(f"**{BOT_NAME}** is thinking...")

    async with _lock:
        try:
            response = await _run_claude(prompt)
        except Exception as e:
            logger.exception("Claude call failed")
            response = f"Error: {e}"

    # Send response in chunks
    chunks = _chunk(response)
    for i, chunk in enumerate(chunks):
        if i == 0:
            try:
                await thinking_msg.edit(content=chunk)
            except Exception:
                await message.channel.send(chunk)
        else:
            await message.channel.send(chunk)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not BOT_TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN not found in .env file")
        sys.exit(1)

    logger.info("Starting %s — Claude-Discord bridge", BOT_NAME)
    logger.info("  Working dir: %s", CLAUDE_WORKING_DIR)
    logger.info("  Allowed users: %s", ALLOWED_USER_IDS or "(all)")
    logger.info("  Timeout: %ds", CLAUDE_TIMEOUT)

    client.run(BOT_TOKEN)
