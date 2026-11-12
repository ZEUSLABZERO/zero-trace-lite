#!/usr/bin/env python3
"""Zero-Trace Lite as a local MCP server (stdio, JSON-RPC 2.0).

Lets an MCP client such as Claude Desktop or Cursor ask for a leak report on a folder, a file
or a piece of text before anything is committed or handed out. It reads plain text only and
reports; it does not block a commit. Everything runs on this machine and the server opens no
network connection. It imports nothing outside the Python standard library — which removes
third-party package drift, not supply-chain risk as a whole: verify what you download.

Client configuration (Claude Desktop: claude_desktop_config.json, Cursor: mcp.json):

    {"mcpServers": {"zero-trace-lite": {"command": "python3",
                                         "args": ["/absolute/path/to/mcp_server_lite.py"]}}}

Tools
  scan_path  {"path": "..."}   report on a folder or a text file
  scan_text  {"text": "...", "name": "optional file name"}   report on a snippet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import zero_trace_lite as lite  # noqa: E402

VERSION = "1.2.0"
SCOPE = ("Reads plain text only: home paths with a login name, common secret-key formats, inline passwords, database "
         "URIs with a password, secrets in .claude/settings*.json, e-mail addresses. Read-only.")
TOOLS = [
    {"name": "scan_path", "description": "Report supported leak patterns in a folder or a text file. " + SCOPE,
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "scan_text", "description": "Report supported leak patterns in a piece of text. " + SCOPE,
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}, "name": {"type": "string"}},
                     "required": ["text"]}},
]


def call_tool(name: str, args: dict) -> tuple[str, bool]:
    lines: list[str] = []
    found = none = scope = unreadable = 0
    if name == "scan_text":
        label = str(args.get("name") or "(text)")
        hits = lite.scan_text(str(args.get("text", "")), "/" + label)
        found, none = int(bool(hits)), int(not hits)
        lines += [f"FOUND [{kind}] {label}:{line} — {detail}" for line, kind, detail in hits]
    elif name == "scan_path":
        root = Path(str(args.get("path", ""))).expanduser()
        if not root.exists():
            return f"not found: {root.name}", True
        files = [root] if root.is_file() else sorted(
            p for p in root.rglob("*") if p.is_file() and not (set(p.relative_to(root).parts[:-1]) & lite.SKIP_DIRS))
        for p in files:
            label = p.name if root.is_file() else p.relative_to(root).as_posix()
            try:
                data = p.read_bytes()
            except OSError:
                unreadable += 1
                continue
            if b"\x00" in data[:8192]:
                scope += 1
                continue
            hits = lite.scan_text(data.decode("utf-8", errors="ignore"), "/" + label)
            found += bool(hits)
            none += not hits
            lines += [f"FOUND [{kind}] {label}:{line} — {detail}" for line, kind, detail in hits][:200]
    else:
        return f"unknown tool: {name}", True
    lines.append(f"result: FOUND {found} file(s) · NONE FOUND WITHIN SUPPORTED SCOPE {none} · OUT OF SCOPE {scope} · "
                 f"UNREADABLE {unreadable}")
    lines.append("'None found' means no supported pattern was present in text files. It is not a proof of safety.")
    return "\n".join(lines), False


def handle(msg: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    if mid is None:
        return None
    if method == "initialize":
        version = (msg.get("params") or {}).get("protocolVersion", "2025-06-18")
        result = {"protocolVersion": version, "capabilities": {"tools": {}},
                  "serverInfo": {"name": "zero-trace-lite", "version": VERSION}}
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = msg.get("params") or {}
        try:
            text, is_error = call_tool(params.get("name", ""), params.get("arguments") or {})
        except Exception as exc:
            text, is_error = f"scan failed: {type(exc).__name__}", True
        result = {"content": [{"type": "text", "text": text}], "isError": is_error}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = handle(json.loads(line))
        except json.JSONDecodeError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
