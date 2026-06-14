#!/usr/bin/env python3
"""octos-tui PTY smoke test.

Spawns `octos-tui --mode mock` in a real PTY, captures rendered output,
and asserts the mock-snapshot's seeded text appears in the stream.

This is octos-test's own black-box test, NOT a wrapper for the TUI's
`cargo test` suite (which lives in the TUI repo itself).

Subcommands
-----------
  smoke         build + spawn --mode mock in a PTY, check UI text rendered
  list | --help show help

Environment
-----------
  OCTOS_TUI_DIR       path to sibling octos-tui checkout (default: ../octos-tui)
  OCTOS_TUI_BIN       path to a prebuilt octos-tui binary (skips cargo build)
  CARGO_TARGET_DIR    cargo build target dir (default: /tmp/octos-tui-target)
"""

import argparse
import os
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TUI_DIR = (REPO_ROOT / ".." / "octos-tui").resolve()
TUI_DIR = Path(os.environ.get("OCTOS_TUI_DIR", str(DEFAULT_TUI_DIR)))
DEFAULT_TARGET_DIR = Path("/tmp/octos-tui-target")
TARGET_DIR = Path(os.environ.get("CARGO_TARGET_DIR", str(DEFAULT_TARGET_DIR)))
BIN = Path(os.environ.get("OCTOS_TUI_BIN", str(TARGET_DIR / "release" / "octos-tui")))

ANSI_CSI = re.compile(rb"\x1b\[[0-9;?]*[a-zA-Z]")
ANSI_OSC = re.compile(rb"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def show_help() -> None:
    print(__doc__)


def _ensure_tui() -> Path:
    if not (TUI_DIR / "Cargo.toml").exists():
        raise SystemExit(
            f"octos-tui checkout not found at {TUI_DIR}\n"
            f"Set OCTOS_TUI_DIR or clone the repo next to this one."
        )
    return TUI_DIR


def _run(cmd: List[str], cwd: Path, log_path: Optional[Path] = None,
         timeout: Optional[int] = None) -> Tuple[int, str]:
    print(f"[tui] $ {' '.join(cmd)}  (cwd={cwd})")
    fh = open(log_path, "wb") if log_path else None
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True,
        )
        chunks: List[str] = []
        try:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                chunks.append(line)
                print(line, end="")
                if fh:
                    fh.write(line.encode("utf-8", errors="replace"))
        finally:
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        return proc.returncode, "".join(chunks)
    finally:
        if fh:
            fh.close()


def cmd_build(release: bool = True) -> bool:
    _ensure_tui()
    cmd = ["cargo", "build"]
    if release:
        cmd.append("--release")
    rc, _ = _run(cmd, cwd=TUI_DIR,
                 log_path=Path("/tmp/octos_test/logs/tui_build.log"),
                 timeout=600)
    return rc == 0


def cmd_smoke() -> Tuple[bool, int, int]:
    """PTY smoke: spawn --mode mock, assert rendered text contains markers."""
    if not BIN.exists():
        print(f"[tui] smoke: building octos-tui (no binary at {BIN})")
        if not cmd_build():
            return False, 0, 0
    if not BIN.exists():
        print(f"[tui] smoke FAIL: binary not found at {BIN}")
        return False, 0, 0

    import pty

    pid, fd = pty.fork()
    if pid == 0:
        os.environ["TERM"] = "xterm-256color"
        os.environ["RUST_LOG"] = "off"
        os.execv(str(BIN), [str(BIN), "--mode", "mock", "--theme", "codex"])

    captured = bytearray()
    deadline = time.time() + 5.0
    while time.time() < deadline:
        r, _, _ = select.select([fd], [], [], 0.25)
        if r:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            captured.extend(chunk)
        if len(captured) > 16384:
            break
    try:
        os.write(fd, b"\x03")
    except OSError:
        pass
    time.sleep(0.4)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        os.waitpid(pid, 0)
    except ChildProcessError:
        pass

    log_path = Path("/tmp/octos_test/logs/tui_smoke.pty.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_bytes(bytes(captured))
    raw = ANSI_OSC.sub(b"", ANSI_CSI.sub(b"", bytes(captured))).decode("utf-8", errors="replace")
    text = "".join(c for c in raw if c.isprintable() or c in " \t")
    markers = ["M8", "prototype"]
    missing = [m for m in markers if m not in text]
    ok = not missing
    if ok:
        print(f"[tui] smoke PASS ({len(captured)} bytes): saw {markers}")
    else:
        print(f"[tui] smoke FAIL: missing {missing} in {len(captured)} bytes")
    return ok, len(captured), int(time.time() - (deadline - 5.0))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_tui_tests",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("smoke", help="build + spawn --mode mock PTY, check UI text")
    sub.add_parser("list", help="show help")
    parser.add_argument("--no-build", action="store_true",
                        help="skip cargo build (assume binary is up to date)")
    parser.add_argument("--build-only", action="store_true",
                        help="only build, do not run smoke")
    args, extra = parser.parse_known_args(argv)

    no_build = args.no_build or "--no-build" in extra
    build_only = args.build_only or "--build-only" in extra

    if args.cmd is None or args.cmd == "list":
        show_help()
        return 0

    if not no_build and not build_only:
        if not cmd_build():
            print("[tui] build FAILED")
            return 1
    if build_only:
        return 0 if BIN.exists() else 1

    if args.cmd == "smoke":
        ok, _, _ = cmd_smoke()
        return 0 if ok else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
