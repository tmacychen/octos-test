#!/usr/bin/env python3
"""Octos TUI test runner.

Wraps `cargo test` and an optional `--mode mock` PTY smoke for the sibling
`octos-tui` Rust crate. The TUI is a standalone repo that depends on
`octos-core` (pinned rev 2afff187) and ships its own test surface:

  * 754 lib unit tests (mock-backed, no server needed)
  * 47 integration tests under tests/*.rs (mock-backed, no server needed)
  * `appui_ux_fixture` (PTY + fixture, no server needed)
  * `--mode mock` PTY smoke (spawns the binary, asserts UI text rendered)

Subcommands
-----------
  smoke         build + spawn --mode mock in a PTY, check welcome markers
  unit          run cargo test --lib (754 unit tests)
  integration   run cargo test --tests (10 tests/*.rs files)
  pty           run cargo test --test appui_ux_fixture
  all           run unit + integration + pty + smoke (default)
  list          list available subcommands
  --help        show help

Environment
-----------
  OCTOS_TUI_DIR       path to sibling octos-tui checkout
                      (default: ../octos-tui relative to this repo)
  OCTOS_TUI_BIN       path to a prebuilt octos-tui binary
                      (skips cargo build for smoke/pty checks)
  CARGO_TARGET_DIR    cargo build target dir (default: /tmp/octos-tui-target)
"""

import argparse
import os
import re
import select
import shutil
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
    """Verify the TUI checkout is present. Returns its path."""
    if not (TUI_DIR / "Cargo.toml").exists():
        raise SystemExit(
            f"octos-tui checkout not found at {TUI_DIR}\n"
            f"Set OCTOS_TUI_DIR or clone the repo next to this one."
        )
    return TUI_DIR


def _run(cmd: List[str], cwd: Path, log_path: Optional[Path] = None,
         timeout: Optional[int] = None) -> Tuple[int, str]:
    """Run a subprocess, stream stdout to log_path (if given), return (rc, text)."""
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
        text = "".join(chunks)
        return proc.returncode, text
    finally:
        if fh:
            fh.close()


def cmd_build(release: bool = True) -> bool:
    """Build octos-tui via cargo."""
    _ensure_tui()
    profile = "--release" if release else ""
    cmd = ["cargo", "build"]
    if profile:
        cmd.append(profile)
    log_path = Path("/tmp/octos_test/logs/tui_build.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rc, _ = _run(cmd, cwd=TUI_DIR, log_path=log_path, timeout=600)
    return rc == 0


def cmd_unit() -> Tuple[bool, int, int]:
    """Run cargo test --lib. Returns (passed, num_passed, num_failed)."""
    _ensure_tui()
    cmd = ["cargo", "test", "--lib", "--no-fail-fast"]
    log_path = Path("/tmp/octos_test/logs/tui_unit.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rc, text = _run(cmd, cwd=TUI_DIR, log_path=log_path, timeout=600)
    # parse: "test result: ok. 754 passed; 0 failed; 1 ignored"
    passed = 0
    failed = 0
    for line in text.splitlines():
        m = re.search(r"(\d+)\s+passed;\s+(\d+)\s+failed", line)
        if m:
            passed += int(m.group(1))
            failed += int(m.group(2))
    return rc == 0 and failed == 0, passed, failed


def cmd_integration() -> Tuple[bool, int, int]:
    """Run cargo test --tests. Returns (ok, passed, failed)."""
    _ensure_tui()
    cmd = ["cargo", "test", "--tests", "--no-fail-fast"]
    log_path = Path("/tmp/octos_test/logs/tui_integration.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rc, text = _run(cmd, cwd=TUI_DIR, log_path=log_path, timeout=600)
    passed = 0
    failed = 0
    for line in text.splitlines():
        m = re.search(r"(\d+)\s+passed;\s+(\d+)\s+failed", line)
        if m:
            passed += int(m.group(1))
            failed += int(m.group(2))
    return rc == 0 and failed == 0, passed, failed


def cmd_pty() -> Tuple[bool, str, str]:
    """Run cargo test --test appui_ux_fixture (PTY + fixture).

    Returns (ok, log_path, text).
    """
    _ensure_tui()
    cmd = ["cargo", "test", "--test", "appui_ux_fixture", "--", "--nocapture"]
    log_path = "/tmp/octos_test/logs/tui_pty.log"
    log_p = Path(log_path)
    log_p.parent.mkdir(parents=True, exist_ok=True)
    rc, text = _run(cmd, cwd=TUI_DIR, log_path=log_p, timeout=300)
    return rc == 0, log_path, text


def cmd_smoke() -> Tuple[bool, int, int]:
    """PTY smoke: spawn --mode mock, assert the rendered text mentions the
    mock-snapshot's seeded markers. Returns (ok, bytes, sec).

    No required environment. The mock backend is self-contained.
    """
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
    # ratatui writes each cell (character) to its own PTY line, so the final
    # text is split across lines: "M\n8\nr\nu\nn\nt\ni\nm\ne...".  We strip
    # all whitespace/control-chars and search for the markers as substrings
    # of the collapsed form.
    text = "".join(c for c in raw if c.isprintable() or c in " \t")
    # Mock snapshot seeds a system message and one assistant message; see
    # MockAppUiBackend::bootstrap in transport.rs.
    markers = [
        "M8",
        "prototype",
    ]
    missing = [m for m in markers if m not in text]
    ok = not missing
    if ok:
        print(f"[tui] smoke PASS ({len(captured)} bytes): saw {markers}")
    else:
        print(f"[tui] smoke FAIL: missing {missing} in {len(captured)} bytes")
    return ok, len(captured), int(time.time() - (deadline - 5.0))


SUBCOMMANDS = ("smoke", "unit", "integration", "pty", "all", "list")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_tui_tests",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("smoke", help="build + spawn --mode mock PTY, check markers")
    sub.add_parser("unit", help="cargo test --lib (754 unit tests)")
    sub.add_parser("integration", help="cargo test --tests (10 tests/*.rs files)")
    sub.add_parser("pty", help="cargo test --test appui_ux_fixture")
    sub.add_parser("all", help="unit + integration + pty + smoke (default)")
    sub.add_parser("list", help="list available subcommands")
    parser.add_argument("--no-build", action="store_true",
                        help="skip cargo build (assume binary is up to date)")
    parser.add_argument("--build-only", action="store_true",
                        help="only build, do not run any test")
    args, extra = parser.parse_known_args(argv)

    if args.cmd is None or args.cmd == "list":
        show_help()
        return 0

    if not args.no_build and not args.build_only:
        if not cmd_build():
            print("[tui] build FAILED")
            return 1
    if args.build_only:
        return 0 if BIN.exists() else 1

    overall_ok = True
    if args.cmd == "smoke":
        overall_ok, _, _ = cmd_smoke()
    elif args.cmd == "unit":
        ok, p, f = cmd_unit()
        print(f"[tui] unit: passed={p} failed={f}")
        overall_ok = ok
    elif args.cmd == "integration":
        ok, p, f = cmd_integration()
        print(f"[tui] integration: passed={p} failed={f}")
        overall_ok = ok
    elif args.cmd == "pty":
        ok, log_path, _ = cmd_pty()
        print(f"[tui] pty: {'PASS' if ok else 'FAIL'} (log: {log_path})")
        overall_ok = ok
    elif args.cmd == "all":
        results = []
        for name, fn in [
            ("unit", cmd_unit),
            ("integration", cmd_integration),
            ("pty", lambda: cmd_pty()[0:1][0] if isinstance(cmd_pty(), tuple) else cmd_pty()),
            ("smoke", cmd_smoke),
        ]:
            try:
                if name == "pty":
                    ok, _, _ = cmd_pty()
                else:
                    ok = fn()
                results.append((name, ok))
            except Exception as e:  # pragma: no cover
                print(f"[tui] {name} error: {e}")
                results.append((name, False))
        overall_ok = all(ok for _, ok in results)
        print("[tui] all summary:")
        for name, ok in results:
            print(f"  - {name}: {'PASS' if ok else 'FAIL'}")
    else:
        parser.print_help()
        return 2
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
