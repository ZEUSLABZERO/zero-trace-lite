# zero-trace-lite

A free, local leak report for the folder you are about to publish, with a local MCP server.

Clicked "Don't ask again" in Claude Code? Approved commands are saved as literal strings in `.claude/settings.local.json`, including any password or token typed inline. The file is normally excluded from Git, but adding an already tracked file to `.gitignore` does not untrack it.

```sh
python3 zero_trace_lite.py path/to/folder
```

Python 3.9+ standard library only. Nothing to install. The tool opens no network connection.

Prefer the browser? The same checks run in the free in-browser scanner; the files you scan are not uploaded:
https://zero-trace-ship-kit.zeus-lab-global.workers.dev/

## What it reports (plain-text files)

- Secrets inside the permission rules of `.claude/settings.local.json` and `.claude/settings.json`, and the `.claude/.credentials.json` file
- Inline passwords: the `PGPASSWORD` / `MYSQL_PWD` / `REDISCLI_AUTH` variables, the password option of command-line clients, database URIs that carry a password
- Common secret-key formats and private keys
- Home paths with a login name (macOS, Linux, Windows)
- E-mail addresses

Obvious placeholders such as `<password>` or `$DB_PASS` are not reported. It exits with code 1 when anything is found.

## Local MCP server

`mcp_server_lite.py` lets Claude Desktop or Cursor ask for the same report over stdio.

```json
{"mcpServers": {"zero-trace-lite": {"command": "python3", "args": ["/absolute/path/to/mcp_server_lite.py"]}}}
```

Tools: `scan_path` (a folder or a text file) and `scan_text` (a snippet). Read-only.

The server imports nothing outside the Python standard library. That removes third-party package drift; it does not remove supply-chain risk as a whole. Read the two files before you run them — they are short.

## What it does not do

- It reads plain text only. ZIP, Office, PDF and image files are not opened.
- It reports. It does not stop a commit or push.
- "No findings" means no supported pattern was detected; it does not prove that the files contain no secrets.
- A credential that reached Git history or a remote must be revoked at its issuer. Deleting the file does not take it back.

Git hooks that stop the commit or push on supported findings, checks inside ZIPs, photo GPS and document authors, and cleaned distribution ZIPs are in the paid Zero-Trace Ship Kit ($39 individual / $149 team, one-time):
https://zeuslab.gumroad.com/l/zero-trace-ship-kit

## If you find a secret in a settings file

```sh
git ls-files .claude                                   # is it tracked?
git log --oneline --all -- .claude/settings.local.json # was it ever committed?
git rm --cached .claude/settings.local.json            # stop tracking (the file stays on disk)
```

Then revoke the credential and create a new one.

## License

Free for personal projects and for evaluation; see `LICENSE.md`. This is not an open-source license. © 2026 ZEUS LAB

---

日本語：公開しようとしているフォルダの文章ファイルから、Claude Code の設定ファイルに残った秘密情報、インラインのパスワード、秘密キー、ユーザー名入りのパス、メールアドレスを一覧にする無料の道具です。手元で動き、外部へ接続しません。報告のみで、commit / push は止めません。検出0件は「対応パターンが見つからなかった」という結果であり、秘密情報が存在しないことの証明ではありません。
