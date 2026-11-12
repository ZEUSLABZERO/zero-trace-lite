#!/usr/bin/env python3
"""Zero-Trace Lite — a plain-text leak report for a folder.

Reports these traces in text files: home paths that carry a login name, common secret-key
formats, passwords typed inline (the PGPASSWORD / MYSQL_PWD / REDISCLI_AUTH variables, the password
option of command-line clients, database addresses with a password), secrets left in AI agent settings (.claude/settings*.json), and e-mail addresses. It prints a report and exits with
code 1 when anything is found.

The Lite edition reads plain text only. It does not open ZIP or Office files, does not
read image or PDF metadata, does not check git identity or history, and does not install
commit or push hooks. Those are part of the Full Kit.

Usage:  python3 zero_trace_lite.py [folder]        (default: current folder)
Python 3.9+ standard library only. No network access.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
PLACEHOLDERS = {"you", "yourname", "your-name", "username", "user", "name", "me", "example",
                "shared", "runner", "public", "default"}
OK_DOMAINS = ("users.noreply.github.com", "example.com", "example.org", "example.net")
FILE_EXT_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "js", "css", "md", "json", "py",
                 "sh", "yml", "yaml", "html", "txt", "zip", "pdf"}
HOME_PATH = re.compile(r"(?<![\w.])(?:/Users/|/home/|[A-Za-z]:\\{1,2}Users\\{1,2})([A-Za-z0-9][A-Za-z0-9._-]*)")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+([A-Za-z]{2,}))")
SECRETS = [
    ("secret-key", re.compile(r"\bsk-[A-Za-z0-9_-]{24,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}|\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("aws-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
INLINE = [
    ("inline-password", re.compile(
        r"\b(?:PGPASSWORD|MYSQL_PWD|REDISCLI_AUTH|MSSQL_SA_PASSWORD|SSHPASS)\s*=\s*[\"'\\\\]*([^\s\"'`;&|)\\\\]{3,})")),
    ("inline-password", re.compile(
        r"(?<![\w-])--(?:password|passwd|pass)(?:=|\s+)[\"'\\\\]*([^\s\"'`;&|)\\\\]{3,})")),
    ("db-uri-credential", re.compile(
        r"\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|rediss?|amqps?|mssql|sqlserver)://"
        r"[^\s:/@\"'<>]*:([^\s@/\"'<>]{3,})@")),
]
AI_SETTINGS = re.compile(r"(^|/)\.claude/settings(\.local)?\.json$")
AI_CREDENTIALS = re.compile(r"(^|/)\.claude/\.credentials\.json$")
AI_RULES = [
    re.compile(r"\b[A-Z][A-Z0-9_]*(?:TOKEN|SECRET|KEY|PASSWORD|PASSWD|PWD|AUTH)[A-Z0-9_]*=[\"'\\\\]*([^\s\"'\\\\$)]{6,})"),
    re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{16,})"),
    re.compile(r"(?<![\w-])-u\s+[\"'\\\\]*[^\s:\"'\\\\]+:([^\s\"')\\\\]{3,})"),
]
DUMMY = re.compile(r"(?i)^(?:[$<{%\[].*|x+|\*+|\.+|-+|password|passwd|pass|pwd|secret|changeme|change[-_]?me|example|"
                   r"dummy|test|option|options|flag|value|prompt|argument|string|your[-_a-z0-9]*|my[-_]?password|placeholder|redacted|null|none|todo|foo|bar)$")


def mask(s: str) -> str:
    return s[:1] + "*" * min(max(len(s) - 1, 3), 8)


def scan_text(text: str, name: str = "") -> list[tuple[int, str, str]]:
    found = []

    def line_of(pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    for m in HOME_PATH.finditer(text):
        user = m.group(1).rstrip(".")
        if user.lower() not in PLACEHOLDERS:
            found.append((line_of(m.start()), "home-path", mask(user)))
    for kind, rx in SECRETS:
        for m in rx.finditer(text):
            found.append((line_of(m.start()), kind, m.group(0)[:6] + "…"))
    for kind, rx in INLINE:
        for m in rx.finditer(text):
            if not DUMMY.match(m.group(1)):
                found.append((line_of(m.start()), kind, m.group(1)[:2] + "…"))
    if AI_CREDENTIALS.search(name):
        found.append((1, "ai-credentials-file", "credential store of an AI agent — never publish"))
    if AI_SETTINGS.search(name):
        if name.endswith("settings.local.json"):
            found.append((1, "ai-local-settings", "personal AI agent settings file — keep it out of commits and packages"))
        seen = set()
        for rx in AI_RULES:
            for m in rx.finditer(text):
                if not DUMMY.match(m.group(1)) and m.start() not in seen:
                    seen.add(m.start())
                    found.append((line_of(m.start()), "ai-settings-secret", m.group(1)[:2] + "…"))
    for m in EMAIL.finditer(text):
        addr, domain, tld = m.group(0).lower(), m.group(1).lower(), m.group(2).lower()
        if tld in FILE_EXT_TLDS or addr == "git@github.com":
            continue
        if any(domain == d or domain.endswith("." + d) for d in OK_DOMAINS):
            continue
        found.append((line_of(m.start()), "email", mask(addr.split("@")[0]) + "@" + domain))
    return sorted(found)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    if not root.exists():
        print(f"not found: {root}")
        return 2
    files = [root] if root.is_file() else sorted(
        p for p in root.rglob("*") if p.is_file() and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS))
    found = none = scope = unreadable = total = 0
    for p in files:
        label = p.name if root.is_file() else p.relative_to(root).as_posix()
        try:
            data = p.read_bytes()
        except OSError:
            unreadable += 1
            print(f"  UNREADABLE  {label}")
            continue
        if b"\x00" in data[:8192]:
            scope += 1  # archives, images and documents are outside the Lite edition
            print(f"  OUT OF SCOPE  {label} — not a text file; not inspected")
            continue
        hits = scan_text(data.decode("utf-8", errors="ignore"), "/" + label)
        found += bool(hits)
        none += not hits
        for line, kind, detail in hits:
            total += 1
            print(f"  FOUND  [{kind}] {label}:{line} — {detail}")
    print(f"result: FOUND {found} file(s) · NONE FOUND WITHIN SUPPORTED SCOPE {none} · OUT OF SCOPE {scope} · UNREADABLE {unreadable}")
    print(f"zero-trace lite: {total} finding(s). 'None found' covers text files and the pattern kinds listed at the top of this file only;")
    print("  it says nothing about ZIPs, images or documents, and it is not a proof of safety.")
    return 1 if total or unreadable else 0


if __name__ == "__main__":
    sys.exit(main())
