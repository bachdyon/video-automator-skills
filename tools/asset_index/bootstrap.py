"""One-shot bootstrap installer for non-technical users.

Goal: a user double-clicks Install.command (macOS) or Install.bat (Windows)
and ends up with a running watcher service without ever opening a terminal.

Steps performed (idempotent, safe to re-run):

1. Detect & verify Python 3.10+; print a clear error otherwise.
2. Verify ``ffmpeg`` + ``ffprobe`` are on PATH (link to install instructions).
3. Create ``.venv`` if missing using ``python -m venv``.
4. ``pip install`` the requirements file.
5. Prompt for ``OPENAI_API_KEY`` / ``GEMINI_API_KEY`` (auto-open browser to the
   key creation pages so the user can copy-paste). Skip prompts if already set.
6. Write ``.env`` (or merge into the existing one).
7. Run ``python -m tools.asset_index.service install`` to register the
   auto-start service on launchd / Task Scheduler.
8. Print a friendly summary and the next-step actions.

The script is purely interactive on stdin/stdout; the wrapper scripts run
it via the OS terminal, which is the only "terminal moment" the user sees.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import textwrap
import webbrowser
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = WORKSPACE_ROOT / ".env"
REQUIREMENTS = WORKSPACE_ROOT / "tools" / "asset_index" / "requirements.txt"
VENV_DIR = WORKSPACE_ROOT / ".venv"

OPENAI_KEY_URL = "https://platform.openai.com/api-keys"
GEMINI_KEY_URL = "https://aistudio.google.com/apikey"


def _venv_python() -> Path:
    if sys.platform.startswith("win"):
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _print_header(title: str) -> None:
    bar = "─" * max(8, min(60, len(title) + 4))
    print()
    print(bar)
    print(f"  {title}")
    print(bar)


def _check_python() -> None:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 10):
        print(
            "Bạn cần Python 3.10 trở lên. Hãy cài từ https://www.python.org/downloads/ rồi chạy lại.",
            file=sys.stderr,
        )
        sys.exit(2)


def _check_ffmpeg() -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if not missing:
        return
    print("ERROR: thiếu công cụ", ", ".join(missing), file=sys.stderr)
    if sys.platform == "darwin":
        print(
            "  Cài bằng Homebrew (https://brew.sh) rồi chạy lại Install:\n"
            "    brew install ffmpeg",
            file=sys.stderr,
        )
    elif sys.platform.startswith("win"):
        print(
            "  Cài Gyan FFmpeg (https://www.gyan.dev/ffmpeg/builds/) hoặc:\n"
            "    winget install Gyan.FFmpeg",
            file=sys.stderr,
        )
    else:
        print("  Cài qua package manager (apt install ffmpeg / dnf install ffmpeg)", file=sys.stderr)
    sys.exit(2)


def _ensure_venv() -> Path:
    py = _venv_python()
    if py.exists():
        return py
    _print_header("Tạo môi trường Python (.venv)")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    return py


def _install_requirements(py: Path) -> None:
    _print_header("Cài thư viện (pip install)")
    subprocess.check_call([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def _read_env() -> dict[str, str]:
    out: dict[str, str] = {}
    if not ENV_PATH.exists():
        return out
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out


def _write_env(values: dict[str, str]) -> None:
    existing: list[str] = []
    seen: set[str] = set()
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                existing.append(line)
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in values:
                existing.append(f"{key}={values[key]}")
                seen.add(key)
            else:
                existing.append(line)
    for key, value in values.items():
        if key not in seen:
            existing.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(existing).rstrip() + "\n", encoding="utf-8")


def _prompt_secret(prompt: str) -> str:
    try:
        import getpass

        value = getpass.getpass(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""
    return value.strip()


def _maybe_open(url: str) -> None:
    try:
        webbrowser.open(url, new=2, autoraise=True)
    except webbrowser.Error:
        pass


def _collect_api_keys(non_interactive: bool = False) -> dict[str, str]:
    env = _read_env()
    updates: dict[str, str] = {}

    def _need(name: str, url: str, label: str) -> None:
        if env.get(name):
            print(f"✓ {name} đã có trong .env (giữ nguyên)")
            return
        if non_interactive:
            print(f"WARN: {name} chưa có và đang ở chế độ tự động — bỏ qua.")
            return
        print(f"\n>>> Cần {label}. Mở trình duyệt để bạn lấy key...")
        _maybe_open(url)
        value = _prompt_secret(f"Dán {name} (rỗng để bỏ qua): ").strip()
        if value:
            updates[name] = value

    _need("OPENAI_API_KEY", OPENAI_KEY_URL, "OpenAI API key")
    _need("GEMINI_API_KEY", GEMINI_KEY_URL, "Google AI Studio key (Gemini)")
    if updates:
        _write_env(updates)
        print(f"✓ ghi key vào {ENV_PATH}")
    return {**env, **updates}


def _install_service(py: Path, include_jobs: bool, polling: bool) -> None:
    _print_header("Đăng ký service tự khởi động cùng máy")
    args = [str(py), "-m", "tools.asset_index.service", "install"]
    if include_jobs:
        args.append("--include-jobs")
    if polling:
        args.append("--polling")
    subprocess.check_call(args)


def _print_done() -> None:
    msg = textwrap.dedent(
        f"""

        ════════════════════════════════════════════════════════════
          Cài đặt xong. Bạn không cần mở terminal lần nào nữa.
        ════════════════════════════════════════════════════════════

          Cách dùng từ giờ:

          • Thả file ảnh / video / audio vào:
              {WORKSPACE_ROOT / 'raw_assets'}
            → hệ thống sẽ tự phân tích & lập chỉ mục trong nền.

          • Tìm kiếm: double-click Search.command (macOS) hoặc Search.bat (Windows).

          • Xem trạng thái: double-click Status.command / Status.bat.

          • Gỡ cài: double-click Uninstall.command / Uninstall.bat.

        Tip: nếu thêm ổ cloud (Drive/OneDrive), cài lại Install và chọn --polling.
        """
    )
    print(msg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap asset-index for non-technical users")
    parser.add_argument("--include-jobs", action="store_true", help="watch jobs/*/input/raw_assets/ too")
    parser.add_argument("--polling", action="store_true", help="use polling (network drives, cloud sync)")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--skip-service", action="store_true", help="install everything but don't register service")
    args = parser.parse_args(argv)

    print(f"Asset-index bootstrap • {platform.platform()} • python {sys.version.split()[0]}")
    print(f"workspace: {WORKSPACE_ROOT}")

    _check_python()
    _check_ffmpeg()
    py = _ensure_venv()
    _install_requirements(py)
    _collect_api_keys(non_interactive=args.non_interactive)

    if not args.skip_service:
        _install_service(py, include_jobs=args.include_jobs, polling=args.polling)

    _print_done()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"\nERROR: bước cài đặt thất bại (exit={exc.returncode}). Hãy thử chạy lại Install hoặc xem .asset_index/logs/.", file=sys.stderr)
        sys.exit(exc.returncode or 1)
    except KeyboardInterrupt:
        print("\n(người dùng huỷ)", file=sys.stderr)
        sys.exit(130)
