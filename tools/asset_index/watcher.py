"""Filesystem watcher that keeps the asset index in sync with raw_assets/.

Default behaviour:
    Watch ``<workspace>/raw_assets/`` recursively. Any new or modified
    image/video/audio file is debounced, its size is checked for stability
    (so we don't process partial copies), and then routed through
    ``router.process_file``.

Optional flags:
    ``--include-jobs``  also watch every ``jobs/*/input/raw_assets/`` dir.
    ``--watch <path>``  add an arbitrary path; can be repeated.
    ``--scan-on-start`` walk the watched roots on startup so files dropped
                        while the watcher was offline get indexed.
    ``--polling``       use the polling backend (needed on network drives).

Cross-platform notes:
    * Default debounce is 1.5s on macOS and 2.5s on Windows because
      ``ReadDirectoryChangesW`` fires many ``on_modified`` events while a
      large file is still being copied.
    * Console encoding is forced to UTF-8 in ``main()`` so Vietnamese summary
      text doesn't blow up the legacy ``cmd.exe`` console.
    * Single-instance lock lives in ``.asset_index/state.json`` and uses
      ``psutil.pid_exists`` for cross-platform liveness.
    * ``SIGINT`` is registered everywhere; ``SIGBREAK`` is registered only
      on Windows because POSIX doesn't have it.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import queue
import signal
import shutil
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from skills._shared.pipeline_utils import (  # type: ignore
    MEDIA_AUDIO_EXTENSIONS,
    MEDIA_IMAGE_EXTENSIONS,
    MEDIA_VIDEO_EXTENSIONS,
)
from tools.asset_index import store
from tools.asset_index.router import process_file

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = WORKSPACE_ROOT / ".asset_index" / "index.db"
DEFAULT_ENV = WORKSPACE_ROOT / ".env"
STATE_PATH = WORKSPACE_ROOT / ".asset_index" / "state.json"

ALL_EXTS = MEDIA_IMAGE_EXTENSIONS | MEDIA_VIDEO_EXTENSIONS | MEDIA_AUDIO_EXTENSIONS


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_debounce() -> float:
    return 2.5 if sys.platform.startswith("win") else 1.5


def _is_media(path: Path) -> bool:
    return path.suffix.lower() in ALL_EXTS


def _resolve_default_paths(include_jobs: bool, extra: list[Path] | None) -> list[Path]:
    paths: list[Path] = []
    if not extra:
        paths.append(WORKSPACE_ROOT / "raw_assets")
    else:
        paths.extend([Path(p).resolve() for p in extra])
    if include_jobs:
        for raw in sorted((WORKSPACE_ROOT / "jobs").glob("*/input/raw_assets")):
            if raw.is_dir():
                paths.append(raw.resolve())
    cleaned: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        path = Path(path).resolve()
        key = str(path)
        if key in seen:
            continue
        if not path.exists() or not path.is_dir():
            print(f"[watcher] WARNING: skipping missing path {path}", file=sys.stderr)
            continue
        seen.add(key)
        cleaned.append(path)
    return cleaned


def _check_ffmpeg() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if not missing:
        return
    where = "brew install ffmpeg" if sys.platform == "darwin" else "winget install Gyan.FFmpeg"
    print(
        f"[watcher] ERROR: missing {', '.join(missing)} in PATH. Install via: {where}",
        file=sys.stderr,
    )
    sys.exit(2)


def _force_utf8_console() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (LookupError, ValueError, OSError):
            pass


def _read_state() -> dict[str, Any] | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_state(payload: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _acquire_lock(allow_takeover: bool = False) -> None:
    state = _read_state()
    if not state:
        return
    pid = state.get("pid")
    if not pid or not psutil.pid_exists(int(pid)):
        return
    if allow_takeover:
        print(f"[watcher] taking over from stale state with pid={pid}", file=sys.stderr)
        return
    raise SystemExit(
        f"another asset-index watcher is already running (pid={pid}).\n"
        "Stop it first with: python -m tools.asset_index.service uninstall\n"
        f"or kill the process directly: kill {pid}"
    )


class _Debouncer:
    """Per-path debouncer. Process a path only after ``delay`` seconds of
    quiet AND a stable file size between two probes."""

    def __init__(self, delay: float, queue_obj: "queue.Queue[Path]") -> None:
        self.delay = delay
        self.queue = queue_obj
        self._last_seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._timer: threading.Thread | None = None

    def schedule(self, path: Path) -> None:
        with self._lock:
            self._last_seen[str(path)] = time.time()
        if self._timer is None or not self._timer.is_alive():
            self._timer = threading.Thread(target=self._sweep, daemon=True)
            self._timer.start()

    def _sweep(self) -> None:
        while not self._stop.is_set():
            now = time.time()
            ready: list[Path] = []
            with self._lock:
                for key, ts in list(self._last_seen.items()):
                    if now - ts >= self.delay:
                        ready.append(Path(key))
                        del self._last_seen[key]
                empty = not self._last_seen
            for path in ready:
                if self._is_size_stable(path):
                    self.queue.put(path)
                else:
                    with self._lock:
                        self._last_seen[str(path)] = time.time()
            if empty and not ready:
                return
            time.sleep(0.4)

    @staticmethod
    def _is_size_stable(path: Path) -> bool:
        try:
            first = path.stat().st_size
        except (FileNotFoundError, PermissionError):
            return False
        time.sleep(0.5)
        try:
            second = path.stat().st_size
        except (FileNotFoundError, PermissionError):
            return False
        return first == second and first > 0

    def stop(self) -> None:
        self._stop.set()


class _MediaEventHandler(FileSystemEventHandler):
    def __init__(self, debouncer: _Debouncer, delete_queue: "queue.Queue[Path]") -> None:
        self._debouncer = debouncer
        self._delete_queue = delete_queue

    def _maybe_enqueue(self, raw_path: str) -> None:
        path = Path(raw_path)
        if not _is_media(path):
            return
        self._debouncer.schedule(path)

    def on_created(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        self._maybe_enqueue(event.src_path)

    def on_modified(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        self._maybe_enqueue(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        old_path = Path(event.src_path)
        if _is_media(old_path):
            self._delete_queue.put(old_path)
        self._maybe_enqueue(event.dest_path)

    def on_deleted(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        path = Path(event.src_path)
        if _is_media(path):
            self._delete_queue.put(path)


def _scan_existing(roots: list[Path], work_queue: "queue.Queue[Path]") -> int:
    count = 0
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and _is_media(path):
                work_queue.put(path)
                count += 1
    return count


def _process_loop(
    *,
    db_path: Path,
    env_file: Path,
    work_queue: "queue.Queue[Path]",
    delete_queue: "queue.Queue[Path]",
    state: dict[str, Any],
    stop_event: threading.Event,
) -> None:
    conn = store.open_db(db_path)
    try:
        while not stop_event.is_set():
            try:
                path = work_queue.get(timeout=0.5)
            except queue.Empty:
                while not delete_queue.empty():
                    deleted = delete_queue.get_nowait()
                    try:
                        store.delete_by_path(conn, str(deleted))
                        print(f"[watcher] deleted {deleted}", flush=True)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[watcher] delete failed {deleted}: {exc}", file=sys.stderr)
                continue
            try:
                result = process_file(path, conn=conn, env_file=env_file)
            except Exception as exc:  # noqa: BLE001
                tb = traceback.format_exc(limit=4)
                state["errors_count"] += 1
                state["last_error"] = f"{path}: {exc}\n{tb}"
                _write_state(state)
                print(f"[watcher] FAIL {path}: {exc}", file=sys.stderr, flush=True)
                continue
            if result["status"] == "ok":
                state["processed_count"] += 1
            elif result["status"] == "failed":
                state["errors_count"] += 1
                state["last_error"] = f"{path}: {result.get('reason')}"
            state["last_event_at"] = _now_iso()
            _write_state(state)
            print(f"[watcher] {result['status']} {result['file_path']}", flush=True)
    finally:
        conn.close()


def _signal_handlers(stop_event: threading.Event) -> None:
    def _handler(signum, frame):  # noqa: ARG001
        print(f"\n[watcher] received signal {signum}, shutting down...", file=sys.stderr)
        stop_event.set()

    signal.signal(signal.SIGINT, _handler)
    if sys.platform.startswith("win"):
        sigbreak = getattr(signal, "SIGBREAK", None)
        if sigbreak is not None:
            signal.signal(sigbreak, _handler)
    else:
        signal.signal(signal.SIGTERM, _handler)


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    parser = argparse.ArgumentParser(description="Asset index filesystem watcher")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--watch", type=Path, action="append", default=[], help="path to watch (repeatable)")
    parser.add_argument("--include-jobs", action="store_true", help="also watch jobs/*/input/raw_assets/")
    parser.add_argument("--scan-on-start", action="store_true", help="walk the watched roots on startup")
    parser.add_argument("--debounce-seconds", type=float, default=_default_debounce())
    parser.add_argument("--polling", action="store_true", help="use polling backend (network drives)")
    parser.add_argument("--allow-takeover", action="store_true", help="ignore stale state lock")
    args = parser.parse_args(argv)

    _check_ffmpeg()
    _acquire_lock(allow_takeover=args.allow_takeover)

    roots = _resolve_default_paths(args.include_jobs, args.watch)
    if not roots:
        print("[watcher] no valid paths to watch (raw_assets/ missing?)", file=sys.stderr)
        return 2

    args.db.parent.mkdir(parents=True, exist_ok=True)

    state: dict[str, Any] = {
        "pid": os.getpid(),
        "platform": platform.platform(),
        "started_at": _now_iso(),
        "watched_paths": [str(p) for p in roots],
        "include_jobs": args.include_jobs,
        "polling": args.polling,
        "debounce_seconds": args.debounce_seconds,
        "processed_count": 0,
        "errors_count": 0,
        "last_event_at": None,
        "last_error": None,
        "db": str(args.db),
    }
    _write_state(state)

    work_queue: "queue.Queue[Path]" = queue.Queue()
    delete_queue: "queue.Queue[Path]" = queue.Queue()
    debouncer = _Debouncer(args.debounce_seconds, work_queue)

    handler = _MediaEventHandler(debouncer, delete_queue)
    use_polling = args.polling
    observer = (PollingObserver if use_polling else Observer)()
    for root in roots:
        observer.schedule(handler, str(root), recursive=True)
    observer.start()
    if not use_polling:
        time.sleep(1.0)
        emitters = list(getattr(observer, "emitters", []))
        if emitters and any(not e.is_alive() for e in emitters):
            print(
                "[watcher] native FS events backend failed (likely macOS FSEvents permission/sandbox). "
                "Falling back to polling backend.",
                file=sys.stderr,
                flush=True,
            )
            try:
                observer.stop()
                observer.join(timeout=3)
            except Exception:  # noqa: BLE001
                pass
            use_polling = True
            observer = PollingObserver()
            for root in roots:
                observer.schedule(handler, str(root), recursive=True)
            observer.start()
    state["polling"] = use_polling
    _write_state(state)

    stop_event = threading.Event()
    _signal_handlers(stop_event)

    if args.scan_on_start:
        scanned = _scan_existing(roots, work_queue)
        print(f"[watcher] scan-on-start enqueued {scanned} files", flush=True)

    print(
        f"[watcher] started pid={os.getpid()} watching {len(roots)} path(s):",
        flush=True,
    )
    for root in roots:
        print(f"          - {root}", flush=True)

    worker = threading.Thread(
        target=_process_loop,
        kwargs=dict(
            db_path=args.db,
            env_file=args.env_file,
            work_queue=work_queue,
            delete_queue=delete_queue,
            state=state,
            stop_event=stop_event,
        ),
        daemon=True,
    )
    worker.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.5)
    finally:
        observer.stop()
        debouncer.stop()
        stop_event.set()
        observer.join(timeout=5)
        worker.join(timeout=15)
        _write_state({**state, "stopped_at": _now_iso()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
