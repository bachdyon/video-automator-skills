"""Cross-platform service installer for the asset-index watcher.

macOS:
    Writes ~/Library/LaunchAgents/com.video-agent.asset-index.plist and runs
    ``launchctl bootstrap gui/<uid>`` to start it. ``KeepAlive`` makes launchd
    relaunch the watcher if it crashes; ``RunAtLoad`` brings it up at login.

Windows:
    Creates a Task Scheduler job ``VideoAgentAssetIndex`` that triggers
    "ONLOGON" for the current user, with a settings block to relaunch on
    failure (5-minute backoff, retry up to 99 times). The CLI uses
    ``schtasks.exe``: it ships with every Windows install since Vista.

Subcommands:
    install     Generate config + start it (idempotent).
    uninstall   Stop + remove config; tolerates missing entries.
    status      Print whether the watcher is running, plus state.json.
    run         Just exec the watcher in the foreground (used as the
                command launchd / schtasks invokes).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
SERVICE_LABEL = "com.video-agent.asset-index"
WIN_TASK_NAME = "VideoAgentAssetIndex"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LOG_DIR = WORKSPACE_ROOT / ".asset_index" / "logs"
STATE_PATH = WORKSPACE_ROOT / ".asset_index" / "state.json"
DB_PATH = WORKSPACE_ROOT / ".asset_index" / "index.db"


def _venv_python() -> Path:
    if sys.platform.startswith("win"):
        candidate = WORKSPACE_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = WORKSPACE_ROOT / ".venv" / "bin" / "python"
    if not candidate.exists():
        raise SystemExit(
            f"Python venv not found at {candidate}.\n"
            "Run the bootstrap installer first (Install.command / Install.bat)."
        )
    return candidate


def _read_state() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# macOS launchd
# ---------------------------------------------------------------------------

def _macos_plist_path() -> Path:
    return LAUNCH_AGENTS_DIR / f"{SERVICE_LABEL}.plist"


def _macos_plist_contents(extra_args: list[str]) -> str:
    python_bin = _venv_python()
    log_dir = LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    args = [
        str(python_bin),
        "-m",
        "tools.asset_index.watcher",
        "--scan-on-start",
        *extra_args,
    ]
    args_xml = "\n        ".join(f"<string>{a}</string>" for a in args)
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
    <key>Label</key>
    <string>{SERVICE_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        {args_xml}
    </array>
    <key>WorkingDirectory</key>
    <string>{WORKSPACE_ROOT}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>LANG</key>
        <string>en_US.UTF-8</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log_dir}/watcher.out.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/watcher.err.log</string>
</dict>
</plist>
"""


def _macos_install(extra_args: list[str]) -> None:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    plist_path = _macos_plist_path()
    plist_path.write_text(_macos_plist_contents(extra_args), encoding="utf-8")
    print(f"wrote {plist_path}")
    uid = os.getuid()
    domain = f"gui/{uid}"
    target = f"{domain}/{SERVICE_LABEL}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(plist_path)],
        check=False,
        capture_output=True,
    )
    proc = subprocess.run(
        ["launchctl", "bootstrap", domain, str(plist_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr.strip(), file=sys.stderr)
        raise SystemExit(
            "launchctl bootstrap failed. Try: launchctl bootout gui/$UID && retry."
        )
    subprocess.run(["launchctl", "kickstart", "-k", target], check=False)
    print(f"launchd service {SERVICE_LABEL} loaded at gui/{uid}")


def _macos_uninstall() -> None:
    plist_path = _macos_plist_path()
    uid = os.getuid()
    domain = f"gui/{uid}"
    target = f"{domain}/{SERVICE_LABEL}"
    subprocess.run(["launchctl", "bootout", target], check=False, capture_output=True)
    if plist_path.exists():
        plist_path.unlink()
        print(f"removed {plist_path}")
    else:
        print(f"plist already gone ({plist_path})")


def _macos_status() -> dict[str, Any]:
    """Return parsed launchd status without the noisy raw blob."""
    target = f"gui/{os.getuid()}/{SERVICE_LABEL}"
    proc = subprocess.run(
        ["launchctl", "print", target],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {
            "loaded": False,
            "reason": proc.stderr.strip() or "service not registered",
        }
    raw = proc.stdout
    fields: dict[str, Any] = {"loaded": True, "label": SERVICE_LABEL}
    patterns = {
        "state": r"^\s*state\s*=\s*(\S+)",
        "runs": r"^\s*runs\s*=\s*(\d+)",
        "pid": r"^\s*pid\s*=\s*(\d+)",
        "last_terminating_signal": r"^\s*last terminating signal\s*=\s*(.+)$",
        "last_exit_code": r"^\s*last exit code\s*=\s*(.+)$",
        "path": r"^\s*path\s*=\s*(.+)$",
    }
    for key, pat in patterns.items():
        m = re.search(pat, raw, flags=re.MULTILINE)
        if not m:
            continue
        value = m.group(1).strip()
        if key in ("runs", "pid"):
            try:
                value = int(value)
            except ValueError:
                pass
        fields[key] = value
    return fields


# ---------------------------------------------------------------------------
# Windows Task Scheduler
# ---------------------------------------------------------------------------

def _windows_action_command(extra_args: list[str]) -> str:
    python_bin = _venv_python()
    args = [
        str(python_bin),
        "-m",
        "tools.asset_index.watcher",
        "--scan-on-start",
        *extra_args,
    ]
    quoted = " ".join(f'"{a}"' if " " in a else a for a in args)
    return quoted


def _windows_install(extra_args: list[str]) -> None:
    if not shutil.which("schtasks"):
        raise SystemExit("schtasks.exe not found in PATH (this is Windows-only)")
    cmd_line = _windows_action_command(extra_args)
    subprocess.run(
        ["schtasks", "/Delete", "/TN", WIN_TASK_NAME, "/F"],
        check=False,
        capture_output=True,
    )
    proc = subprocess.run(
        [
            "schtasks",
            "/Create",
            "/TN",
            WIN_TASK_NAME,
            "/SC",
            "ONLOGON",
            "/RL",
            "LIMITED",
            "/RU",
            os.environ.get("USERNAME", ""),
            "/TR",
            cmd_line,
            "/F",
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr.strip(), file=sys.stderr)
        raise SystemExit("schtasks /Create failed")
    subprocess.run(
        ["schtasks", "/Run", "/TN", WIN_TASK_NAME],
        check=False,
        capture_output=True,
    )
    print(f"scheduled task {WIN_TASK_NAME} created and started")


def _windows_uninstall() -> None:
    subprocess.run(
        ["schtasks", "/End", "/TN", WIN_TASK_NAME],
        check=False,
        capture_output=True,
    )
    proc = subprocess.run(
        ["schtasks", "/Delete", "/TN", WIN_TASK_NAME, "/F"],
        capture_output=True,
        text=True,
    )
    if proc.returncode == 0:
        print(f"removed scheduled task {WIN_TASK_NAME}")
    else:
        print(f"task {WIN_TASK_NAME} not present (already uninstalled)")


def _windows_status() -> dict[str, Any]:
    """Return parsed Task Scheduler status without the noisy raw blob."""
    proc = subprocess.run(
        ["schtasks", "/Query", "/TN", WIN_TASK_NAME, "/V", "/FO", "LIST"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return {
            "registered": False,
            "reason": proc.stderr.strip() or "task not registered",
        }
    fields: dict[str, Any] = {"registered": True, "task_name": WIN_TASK_NAME}
    for line in proc.stdout.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "status":
            fields["status"] = value
        elif key == "last run time":
            fields["last_run_time"] = value
        elif key == "last result":
            fields["last_result"] = value
        elif key == "next run time":
            fields["next_run_time"] = value
        elif key == "run as user":
            fields["run_as_user"] = value
    return fields


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _state_summary() -> dict[str, Any]:
    state = _read_state()
    if not state:
        return {"running": False, "reason": "state.json missing"}
    pid = state.get("pid")
    alive = bool(pid) and psutil.pid_exists(int(pid))
    return {
        "running": alive,
        "pid": pid,
        "watched_paths": state.get("watched_paths"),
        "include_jobs": state.get("include_jobs"),
        "polling": state.get("polling"),
        "started_at": state.get("started_at"),
        "stopped_at": state.get("stopped_at"),
        "processed_count": state.get("processed_count"),
        "errors_count": state.get("errors_count"),
        "last_event_at": state.get("last_event_at"),
        "last_error": state.get("last_error"),
    }


def _do_install(args: argparse.Namespace) -> int:
    extra: list[str] = []
    if args.include_jobs:
        extra.append("--include-jobs")
    if args.polling:
        extra.append("--polling")
    if sys.platform == "darwin":
        _macos_install(extra)
    elif sys.platform.startswith("win"):
        _windows_install(extra)
    else:
        raise SystemExit(f"unsupported platform: {sys.platform}")
    time.sleep(2)
    print(json.dumps(_state_summary(), ensure_ascii=False, indent=2))
    return 0


def _do_uninstall(_: argparse.Namespace) -> int:
    if sys.platform == "darwin":
        _macos_uninstall()
    elif sys.platform.startswith("win"):
        _windows_uninstall()
    else:
        raise SystemExit(f"unsupported platform: {sys.platform}")
    state = _read_state()
    if state and psutil.pid_exists(int(state.get("pid") or 0)):
        try:
            psutil.Process(int(state["pid"])).terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    deadline = time.time() + 8.0
    while time.time() < deadline:
        state = _read_state()
        pid = int((state or {}).get("pid") or 0)
        if not pid or not psutil.pid_exists(pid):
            break
        time.sleep(0.5)
    if STATE_PATH.exists():
        STATE_PATH.unlink()
        print(f"removed {STATE_PATH}")
    return 0


def _db_stats() -> dict[str, Any]:
    """Best-effort DB inspection for the status display.

    Returns ``{"available": False}`` when the index file is missing (fresh
    install) or unreadable, so the caller can render a "DB chưa tạo" line
    without crashing.
    """
    if not DB_PATH.exists():
        return {"available": False, "reason": "DB chưa tạo"}
    try:
        import apsw  # local import keeps import time minimal
    except ImportError as exc:
        return {"available": False, "reason": f"apsw missing: {exc}"}
    try:
        conn = apsw.Connection(str(DB_PATH), flags=apsw.SQLITE_OPEN_READONLY)
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"open db: {exc}"}
    try:
        counts: dict[str, int] = {}
        cur = conn.execute("SELECT media_type, COUNT(*) FROM assets GROUP BY media_type")
        for media_type, n in cur:
            counts[media_type] = n
        total = next(conn.execute("SELECT COUNT(*) FROM assets"))[0]
        last_indexed_row = next(
            conn.execute("SELECT file_path, indexed_at FROM assets ORDER BY indexed_at DESC LIMIT 1"),
            (None, None),
        )
        recent_failure_row = next(
            conn.execute(
                "SELECT file_path, error, ran_at FROM process_log "
                "WHERE status = 'failed' ORDER BY id DESC LIMIT 1"
            ),
            (None, None, None),
        )
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"query db: {exc}"}
    finally:
        conn.close()
    return {
        "available": True,
        "total": total,
        "by_media_type": counts,
        "last_indexed": (
            {"file_path": last_indexed_row[0], "indexed_at": last_indexed_row[1]}
            if last_indexed_row[0]
            else None
        ),
        "recent_failure": (
            {
                "file_path": recent_failure_row[0],
                "error": recent_failure_row[1],
                "ran_at": recent_failure_row[2],
            }
            if recent_failure_row[0]
            else None
        ),
    }


def _humanize_iso(value: str | None) -> str:
    """Render an ISO-8601 UTC string as a friendly local-time delta.

    Falls back to the raw string when parsing fails so we never hide
    information from the user.
    """
    if not value:
        return "—"
    try:
        dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return value
    local = dt.astimezone()
    delta = datetime.now(timezone.utc) - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        ago = f"{seconds}s trước"
    elif seconds < 3600:
        ago = f"{seconds // 60}m trước"
    elif seconds < 86400:
        ago = f"{seconds // 3600}h trước"
    else:
        ago = f"{seconds // 86400}d trước"
    return f"{local.strftime('%H:%M:%S %d/%m/%Y')} ({ago})"


def _format_status_pretty(summary: dict[str, Any]) -> str:
    state = summary.get("state") or {}
    service = summary.get("service") or {}
    db = summary.get("db") or {}
    lines: list[str] = []

    def row(label: str, value: Any) -> None:
        lines.append(f"  {label:<20} {value}")

    lines.append("┌─ Asset-index status ──────────────────────────────────────")
    lines.append("│ Service")
    lines.append("│")
    if sys.platform == "darwin":
        loaded = service.get("loaded")
        if loaded:
            mark = "✓ đang chạy" if service.get("state") == "running" else f"⚠ {service.get('state')}"
            row("launchd:", f"loaded ({mark})")
            row("runs:", service.get("runs", "?"))
        else:
            row("launchd:", f"✗ {service.get('reason', 'not loaded')}")
    elif sys.platform.startswith("win"):
        registered = service.get("registered")
        if registered:
            row("Task Scheduler:", f"✓ {service.get('status', 'registered')}")
            row("Last result:", service.get("last_result", "—"))
            row("Last run:", service.get("last_run_time", "—"))
        else:
            row("Task Scheduler:", f"✗ {service.get('reason', 'not registered')}")
    else:
        row("platform:", "không hỗ trợ tự khởi động ngoài macOS / Windows")
    lines.append("│")
    lines.append("│ Watcher")
    lines.append("│")

    running = state.get("running")
    if state.get("reason") == "state.json missing":
        row("trạng thái:", "✗ chưa khởi động lần nào (state.json chưa tạo)")
    else:
        row("trạng thái:", "✓ đang chạy" if running else "✗ không chạy")
        row("PID:", state.get("pid") or "—")
        watched = state.get("watched_paths") or []
        if watched:
            for idx, path in enumerate(watched):
                label = "watching:" if idx == 0 else ""
                row(label, path)
        row("--include-jobs:", "có" if state.get("include_jobs") else "không")
        row("backend:", "polling" if state.get("polling") else "FSEvents/inotify")
        row("đã xử lý:", state.get("processed_count") or 0)
        row("lỗi:", state.get("errors_count") or 0)
        row("started:", _humanize_iso(state.get("started_at")))
        row("last event:", _humanize_iso(state.get("last_event_at")))
        if state.get("last_error"):
            err = str(state["last_error"]).splitlines()[0][:120]
            row("last error:", err)

    lines.append("│")
    lines.append("│ Database (.asset_index/index.db)")
    lines.append("│")
    if not db.get("available"):
        row("DB:", f"— ({db.get('reason', 'không có')})")
    else:
        row("tổng asset:", db.get("total") or 0)
        for mt in ("image", "video", "audio"):
            row(f"  {mt}:", db.get("by_media_type", {}).get(mt, 0))
        last = db.get("last_indexed") or {}
        if last.get("file_path"):
            row("vừa index:", f"{last['file_path']}  ({_humanize_iso(last.get('indexed_at'))})")
        if db.get("recent_failure"):
            f = db["recent_failure"]
            row("lỗi gần nhất:", f"{f['file_path']}: {(f['error'] or '').splitlines()[0][:80]}")

    lines.append("└────────────────────────────────────────────────────────────")
    return "\n".join(lines)


def _do_status(args: argparse.Namespace) -> int:
    summary: dict[str, Any] = {"platform": platform.platform()}
    if sys.platform == "darwin":
        summary["service"] = _macos_status()
    elif sys.platform.startswith("win"):
        summary["service"] = _windows_status()
    else:
        summary["service"] = {"loaded": False, "reason": f"unsupported platform {sys.platform}"}
    summary["state"] = _state_summary()
    summary["db"] = _db_stats()
    if getattr(args, "json", False):
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    else:
        print(_format_status_pretty(summary))
    return 0


def _do_run(args: argparse.Namespace) -> int:
    from tools.asset_index.watcher import main as watcher_main
    forwarded: list[str] = []
    if args.include_jobs:
        forwarded.append("--include-jobs")
    if args.polling:
        forwarded.append("--polling")
    if args.scan_on_start:
        forwarded.append("--scan-on-start")
    return watcher_main(forwarded)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the asset-index background service")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_install = sub.add_parser("install", help="install + start the auto-start service")
    p_install.add_argument("--include-jobs", action="store_true")
    p_install.add_argument("--polling", action="store_true")
    p_install.set_defaults(func=_do_install)

    p_uninstall = sub.add_parser("uninstall", help="stop + remove the service")
    p_uninstall.set_defaults(func=_do_uninstall)

    p_status = sub.add_parser("status", help="print service + watcher state")
    p_status.add_argument("--json", action="store_true", help="emit JSON instead of pretty text")
    p_status.set_defaults(func=_do_status)

    p_run = sub.add_parser("run", help="run the watcher in foreground (for the service entry)")
    p_run.add_argument("--include-jobs", action="store_true")
    p_run.add_argument("--polling", action="store_true")
    p_run.add_argument("--scan-on-start", action="store_true", default=True)
    p_run.set_defaults(func=_do_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
