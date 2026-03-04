#!/usr/bin/env python3
"""
parse_session.py — Parse a Claude Code JSONL session file.

Extracts metadata and conversation content from a session JSONL,
classifying each line by type and extracting meaningful text.

Usage:
    python3 parse_session.py <session.jsonl>
"""

import json
import sys
from pathlib import Path
from typing import Optional


def summarize_tool_input(tool_name: str, input_dict: dict) -> str:
    """Produce a brief human-readable summary of a tool call's input."""
    if tool_name in ("Read", "Write", "Edit"):
        path = input_dict.get("file_path", "")
        return f"`{path}`"
    if tool_name == "Bash":
        cmd = input_dict.get("command", "")
        return f"`{cmd}`" if cmd else ""
    if tool_name == "Glob":
        return f"`{input_dict.get('pattern', '')}`"
    if tool_name == "Grep":
        pattern = input_dict.get("pattern", "")
        path = input_dict.get("path", "")
        return f"`{pattern}`" + (f" in `{path}`" if path else "")
    if tool_name in ("Agent", "Explore", "Plan"):
        return input_dict.get("prompt", "")
    # Generic: show first string value found
    for v in input_dict.values():
        if isinstance(v, str) and v:
            return v
    return json.dumps(input_dict)


def extract_user_text(content) -> Optional[str]:
    """Extract text from a user message content (string or array)."""
    if isinstance(content, str):
        text = content.strip()
        # Skip internal meta messages
        if text.startswith(("<local-command", "<command-name", "<command-message", "<system")):
            return None
        return text or None
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "tool_result":
                    pass  # Skip — API-level tool feedback, not real user content
                elif item.get("type") == "text":
                    t = item.get("text", "").strip()
                    if t and not t.startswith("[Request interrupted by user"):
                        parts.append(t)
        return "\n".join(parts) if parts else None
    return None


def extract_assistant_content(content: list) -> tuple[str, list[str]]:
    """
    Extract text and tool use summaries from an assistant message content array.

    Returns:
        (text, tool_summaries) where text is concatenated text blocks
        and tool_summaries is a list of "ToolName: brief summary" strings.
    """
    texts = []
    tools = []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            t = block.get("text", "").strip()
            if t:
                texts.append(t)
        elif btype == "thinking":
            pass  # skip
        elif btype == "tool_use":
            name = block.get("name", "UnknownTool")
            inp = block.get("input", {})
            summary = summarize_tool_input(name, inp)
            tools.append(f"{name}: {summary}" if summary else name)
    return "\n\n".join(texts), tools


def parse_session(jsonl_path: str) -> dict:
    """
    Parse a session JSONL file.

    Returns a dict with:
        metadata: dict with session-level fields
        messages: list of {role, text, tools} dicts
    """
    path = Path(jsonl_path)
    metadata = {}
    messages = []

    with path.open() as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            msg_type = obj.get("type")

            # Capture session metadata from first user/assistant line
            if not metadata and msg_type in ("user", "assistant"):
                metadata = {
                    "session_id": obj.get("sessionId", ""),
                    "cwd": obj.get("cwd", ""),
                    "git_branch": obj.get("gitBranch", ""),
                    "started_at": obj.get("timestamp", ""),
                    "version": obj.get("version", ""),
                    "permission_mode": obj.get("permissionMode", "default"),
                    "source_jsonl": str(path.resolve()),
                }

            # Track last timestamp for ended_at
            if msg_type in ("user", "assistant") and obj.get("timestamp"):
                metadata["ended_at"] = obj["timestamp"]
                if not metadata.get("started_at"):
                    metadata["started_at"] = obj["timestamp"]

            if msg_type == "user":
                content = obj.get("message", {}).get("content", "")
                # Skip isMeta lines (local command echo, system messages)
                if obj.get("isMeta"):
                    continue
                text = extract_user_text(content)
                if text:
                    messages.append({"role": "user", "text": text, "tools": []})

            elif msg_type == "assistant":
                content = obj.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                text, tools = extract_assistant_content(content)
                if text or tools:
                    messages.append({"role": "assistant", "text": text, "tools": tools})

            # file-history-snapshot, progress, system — skip

    return {"metadata": metadata, "messages": messages}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <session.jsonl>", file=sys.stderr)
        sys.exit(1)

    result = parse_session(sys.argv[1])
    meta = result["metadata"]
    msgs = result["messages"]

    print(f"Session: {meta.get('session_id')}")
    print(f"  cwd:     {meta.get('cwd')}")
    print(f"  branch:  {meta.get('git_branch')}")
    print(f"  started: {meta.get('started_at')}")
    print(f"  ended:   {meta.get('ended_at')}")
    print(f"  version: {meta.get('version')}")
    print(f"  messages: {len(msgs)}")
    print()
    for i, msg in enumerate(msgs):
        role = msg["role"].upper()
        text = msg["text"][:120].replace("\n", " ")
        tools = msg["tools"]
        print(f"[{i+1}] {role}: {text}")
        for t in tools:
            print(f"       > Tool: {t}")
