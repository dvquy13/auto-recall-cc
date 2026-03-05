#!/usr/bin/env python3
"""
session_to_md.py — Convert a Claude Code JSONL session to QMD-compatible markdown.

Usage:
    python3 session_to_md.py --input <session.jsonl> --output <dir/>
    python3 session_to_md.py --input <session.jsonl>   # prints to stdout

Output filename: {date}_{project}_{session_id_short}.md
"""

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Optional

# Import parser from same directory
sys.path.insert(0, str(Path(__file__).parent))
from parse_session import parse_session


def _project_from_cwd(cwd: str) -> str:
    """Derive a short project name from the working directory path."""
    if not cwd:
        return "unknown"
    return Path(cwd).name


def _date_from_ts(ts: str) -> str:
    """Extract YYYY-MM-DD from an ISO timestamp string."""
    if not ts:
        return "unknown"
    return ts[:10]  # "2026-02-04T..."  → "2026-02-04"


def _first_user_text(messages: list) -> str:
    """Return truncated first meaningful user message (for title)."""
    for msg in messages:
        if msg["role"] == "user" and msg["text"]:
            # Strip markdown/special chars for a clean title
            text = msg["text"].replace("\n", " ").strip()
            return text[:80]
    return ""


def _file_checksum(path: str) -> str:
    return hashlib.md5(Path(path).read_bytes()).hexdigest()


def _read_stored_checksum(out_path: Path) -> Optional[str]:
    try:
        for line in out_path.read_text(encoding="utf-8").split("\n"):
            if line.startswith("source_checksum:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def _is_trivial(messages: list) -> bool:
    """Return True if the session has fewer than 2 real user messages."""
    user_count = sum(1 for m in messages if m["role"] == "user")
    return user_count < 2


def render_markdown(parsed: dict) -> str:
    """Render a parsed session dict to markdown string."""
    meta = parsed["metadata"]
    messages = parsed["messages"]

    session_id = meta.get("session_id", "unknown")
    cwd = meta.get("cwd", "")
    project = _project_from_cwd(cwd)
    git_branch = meta.get("git_branch", "")
    started_at = meta.get("started_at", "")
    ended_at = meta.get("ended_at", "")
    source_jsonl = meta.get("source_jsonl", "")
    source_checksum = meta.get("source_checksum", "")
    version = meta.get("version", "")
    permission_mode = meta.get("permission_mode", "default")
    message_count = len(messages)
    date = _date_from_ts(started_at)
    first_msg = _first_user_text(messages)

    # --- Frontmatter ---
    lines = ["---"]
    lines.append(f"session_id: {session_id}")
    lines.append(f"workspace: {cwd}")
    lines.append(f"project: {project}")
    if git_branch:
        lines.append(f"git_branch: {git_branch}")
    lines.append(f"started_at: {started_at}")
    lines.append(f"ended_at: {ended_at}")
    lines.append(f"source_jsonl: {source_jsonl}")
    if source_checksum:
        lines.append(f"source_checksum: {source_checksum}")
    lines.append(f"message_count: {message_count}")
    if version:
        lines.append(f"claude_version: {version}")
    lines.append(f"permission_mode: {permission_mode}")
    lines.append("---")
    lines.append("")

    # --- Title ---
    lines.append(f"# Session: {project} — {date}")
    lines.append("")
    if first_msg:
        lines.append(f"*{first_msg}*")
        lines.append("")

    # --- Conversation ---
    for msg in messages:
        role = msg["role"].capitalize()
        lines.append(f"## {role}")
        lines.append("")
        if msg["text"]:
            lines.append(msg["text"])
            lines.append("")
        for tool in msg["tools"]:
            lines.append(f"> **Tool:** {tool}")
            lines.append("")

    return "\n".join(lines)


def output_filename(meta: dict) -> str:
    """Generate a deterministic output filename for the session."""
    date = _date_from_ts(meta.get("started_at", ""))
    project = _project_from_cwd(meta.get("cwd", ""))
    session_id = meta.get("session_id", "unknown")
    short_id = session_id[:8]
    # Sanitize project name for filesystem
    safe_project = "".join(c if c.isalnum() or c == "-" else "_" for c in project)
    return f"{date}_{safe_project}_{short_id}.md"


def main():
    parser = argparse.ArgumentParser(
        description="Convert Claude Code JSONL session to markdown"
    )
    parser.add_argument("--input", required=True, help="Path to session JSONL file")
    parser.add_argument(
        "--output", default=None, help="Output directory (default: stdout)"
    )
    parser.add_argument(
        "--skip-trivial",
        action="store_true",
        default=True,
        help="Skip sessions with fewer than 2 user messages (default: true)",
    )
    parser.add_argument("--no-skip-trivial", action="store_false", dest="skip_trivial")
    args = parser.parse_args()

    parsed = parse_session(args.input)
    messages = parsed["messages"]
    meta = parsed["metadata"]

    if args.skip_trivial and _is_trivial(messages):
        print(
            f"Skipping trivial session (< 2 user messages): {meta.get('session_id')}",
            file=sys.stderr,
        )
        sys.exit(0)

    checksum = _file_checksum(args.input)
    meta["source_checksum"] = checksum

    md = render_markdown(parsed)

    if args.output:
        date = _date_from_ts(meta.get("started_at", ""))
        out_dir = Path(args.output) / date
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = output_filename(meta)
        out_path = out_dir / fname

        if out_path.exists() and _read_stored_checksum(out_path) == checksum:
            print(f"Already exported (unchanged): {out_path}", file=sys.stderr)
            sys.exit(0)

        out_path.write_text(md, encoding="utf-8")
        print(str(out_path))
    else:
        print(md)


if __name__ == "__main__":
    main()
