#!/usr/bin/env python3
"""
跨 Channel 并发测试 — 同一 gateway 上运行多个 channel，验证 session 隔离。

测试流程：
1. 启动 Telegram Mock Server (5000) + Discord Mock Server (5001)
2. 创建包含 telegram + discord 的合并 config
3. 启动单个 octos gateway
4. 向两个 channel 同时注入消息
5. 验证各 channel 的 session 独立隔离

运行方式：
  uv run python -m pytest bot_mock_test/test_cross_channel.py -v
"""

import json
import logging
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import httpx
import pytest

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────────────────────────
TG_PORT = 5000
DC_PORT = 5001
GATEWAY_TIMEOUT = 60
TIMEOUT_COMMAND = 30

BOT_TEST_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = BOT_TEST_DIR.parent
TEST_DIR = Path("/tmp/octos_test")
LOG_DIR = TEST_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Mock Server 启动代码模板 ──────────────────────────────────────────────────

def _mock_code(module: str, port: int, log_file: str) -> str:
    if module == "telegram":
        return f"""
import time, signal, sys, logging
from mock_tg import MockTelegramServer
logging.getLogger("httpx").setLevel(logging.WARNING)
server = MockTelegramServer(port={port})
server.start_background(log_file='{log_file}')
print('ready', flush=True)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
while True:
    time.sleep(1)
"""
    elif module == "discord":
        return f"""
import time, signal, sys, logging
from mock_discord import MockDiscordServer
logging.getLogger("httpx").setLevel(logging.WARNING)
server = MockDiscordServer(port={port})
server.start_background(log_file='{log_file}')
print('ready', flush=True)
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
while True:
    time.sleep(1)
"""
    raise ValueError(f"Unknown module: {module}")


def _find_binary() -> Path:
    """Find the octos binary."""
    candidates = [
        Path(os.environ.get("OCTOS_BINARY", "")),
        PROJECT_DIR / "target" / "release" / "octos",
        PROJECT_DIR.parent / "octos" / "target" / "release" / "octos",
        Path("/usr/local/bin/octos"),
    ]
    for p in candidates:
        if p and p.exists():
            return p
    raise FileNotFoundError("octos binary not found")


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cross_env():
    """
    启动 tg + dc mock servers + 合并 gateway，测试结束后清理。
    返回 (tg_runner, dc_runner) 元组供测试使用。
    """
    binary = _find_binary()
    venv_python = os.environ.get("UV_PYTHON", sys.executable)

    processes = []
    log_files = []
    cleanup_called = False

    def _log_path(name: str) -> str:
        ts = int(time.time())
        p = str(LOG_DIR / f"{name}_{ts}.log")
        log_files.append(p)
        return p

    def _start_mock(module: str, port: int) -> subprocess.Popen:
        log = _log_path(f"mock_{module}")
        code = _mock_code(module, port, log)
        proc = subprocess.Popen(
            [str(venv_python), "-c", code],
            env={**os.environ, "PYTHONPATH": str(BOT_TEST_DIR),
                 "PYTHONDONTWRITEBYTECODE": "1"},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        processes.append(("mock", module, proc))
        # Wait for ready
        start = time.time()
        while time.time() - start < 10:
            if proc.poll() is not None:
                out, _ = proc.communicate()
                pytest.fail(f"Mock {module} exited early: {out.decode()[:200]}")
            try:
                resp = httpx.get(f"http://127.0.0.1:{port}/health", timeout=2)
                if resp.status_code == 200:
                    logger.info(f"  ✓ Mock {module} ready on port {port}")
                    break
            except Exception:
                pass
            time.sleep(0.5)
        return proc

    def _start_gateway(tg_proc, dc_proc) -> subprocess.Popen:
        # Create combined config
        config = {
            "id": "cross-test",
            "name": "Cross-Channel Test",
            "enabled": True,
            "config": {
                "version": 1,
                "llm": {
                    "family": "openai",
                    "model": "meta/llama-3.3-70b-instruct",
                    "api_key_env": "ANTHROPIC_API_KEY",
                    "base_url": "https://api.nvidia.com/v1/openai/chat/completions",
                },
                "gateway": {
                    "max_history": 50,
                    "max_concurrent_sessions": 10,
                },
                "channels": [
                    {
                        "type": "telegram",
                        "token_env": "TELEGRAM_BOT_TOKEN",
                        "allowed_senders": ["12345:tguser:default"],
                    },
                    {
                        "type": "discord",
                        "token_env": "DISCORD_BOT_TOKEN",
                    },
                ],
            },
        }
        config_dir = TEST_DIR / ".octos"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / "test_cross_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        # Set env vars for mock URLs
        extra_env = {
            "TELOXIDE_API_URL": f"http://127.0.0.1:{TG_PORT}",
            "DISCORD_API_BASE_URL": f"http://127.0.0.1:{DC_PORT}",
            "TELEGRAM_BOT_TOKEN": "fake-tg-token-for-mock",
            "DISCORD_BOT_TOKEN": "fake-dc-token-for-mock",
        }
        bot_env = {**os.environ, **extra_env}
        bot_log = _log_path("gateway_cross")
        log_file = open(bot_log, "w")

        proc = subprocess.Popen(
            [str(binary), "gateway", "--profile", str(config_file), "--data-dir", str(TEST_DIR)],
            env=bot_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        processes.append(("gateway", "cross", proc))

        # Tee output
        def _tee():
            for line in iter(proc.stdout.readline, b""):
                line_str = line.decode("utf-8", errors="replace").rstrip()
                log_file.write(line_str + "\n")
                log_file.flush()
            log_file.close()
        import threading
        t = threading.Thread(target=_tee, daemon=True)
        t.start()

        # Wait for gateway ready
        start = time.time()
        while time.time() - start < GATEWAY_TIMEOUT:
            if proc.poll() is not None:
                break
            try:
                with open(bot_log) as f:
                    content = f.read()
                    if re.search(r"gateway.*ready|Gateway ready|\[gateway\] ready", content):
                        time.sleep(0.5)
                        logger.info("  ✓ Gateway ready")
                        return proc
            except FileNotFoundError:
                pass
            time.sleep(1)

        pytest.fail("Gateway did not become ready")

    def _cleanup():
        nonlocal cleanup_called
        if cleanup_called:
            return
        cleanup_called = True
        logger.info("  Cleaning up...")
        for role, name, proc in reversed(processes):
            try:
                proc.terminate()
            except Exception:
                pass
        time.sleep(1)
        for role, name, proc in processes:
            try:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
            except Exception:
                pass
        # Kill any leftover gateway processes
        subprocess.run(["pkill", "-f", "octos gateway"], capture_output=True, timeout=5)

    # Start mocks
    tg_proc = _start_mock("telegram", TG_PORT)
    dc_proc = _start_mock("discord", DC_PORT)

    # Start gateway
    gw_proc = _start_gateway(tg_proc, dc_proc)

    # Build runners
    from base_runner import BaseMockRunner
    tg_runner = BaseMockRunner(f"http://127.0.0.1:{TG_PORT}")
    dc_runner = BaseMockRunner(f"http://127.0.0.1:{DC_PORT}")

    yield tg_runner, dc_runner

    _cleanup()


# ── 测试用例 ──────────────────────────────────────────────────────────────────

class TestCrossChannelSessionIsolation:
    """跨 channel 会话隔离测试"""

    TG_CHAT_ID = "12345"
    DC_CHANNEL_ID = "1039178386623557754"

    def test_isolated_new_sessions(self, cross_env):
        """两个 channel 各自的 /new 命令应创建独立 session"""
        tg_runner, dc_runner = cross_env

        # Telegram: /new
        tg_before = len(tg_runner.get_sent_messages())
        tg_runner.inject("/new cross-tg-session", chat_id=self.TG_CHAT_ID)
        tg_reply = tg_runner.wait_for_reply(count_before=tg_before, timeout=TIMEOUT_COMMAND,
                                             chat_id=self.TG_CHAT_ID)
        assert tg_reply is not None, "Telegram should reply to /new"
        assert "cross-tg-session" in tg_reply["text"], f"TG session name missing: {tg_reply['text']}"
        logger.info(f"  ✓ TG /new: {tg_reply['text'][:60]}")

        # Discord: /new (different session name)
        dc_before = len(dc_runner.get_sent_messages())
        dc_runner.inject("/new cross-dc-session", channel_id=self.DC_CHANNEL_ID)
        dc_reply = dc_runner.wait_for_reply(count_before=dc_before, timeout=TIMEOUT_COMMAND,
                                             chat_id=self.DC_CHANNEL_ID)
        assert dc_reply is not None, "Discord should reply to /new"
        assert "cross-dc-session" in dc_reply["text"], f"DC session name missing: {dc_reply['text']}"
        logger.info(f"  ✓ DC /new: {dc_reply['text'][:60]}")

        # Verify isolation: each channel only sees its own session
        tg_sessions = tg_runner.get_sent_messages()
        dc_sessions = dc_runner.get_sent_messages()

        tg_has_tg = any("cross-tg-session" in m.get("text", "") for m in tg_sessions)
        tg_no_dc = all("cross-dc-session" not in m.get("text", "") for m in tg_sessions)
        assert tg_has_tg, "TG should have its own session"
        assert tg_no_dc, "TG should NOT see DC session"
        logger.info("  ✓ TG sessions isolated from DC")

        dc_has_dc = any("cross-dc-session" in m.get("text", "") for m in dc_sessions)
        dc_no_tg = all("cross-tg-session" not in m.get("text", "") for m in dc_sessions)
        assert dc_has_dc, "DC should have its own session"
        assert dc_no_tg, "DC should NOT see TG session"
        logger.info("  ✓ DC sessions isolated from TG")

    def test_concurrent_messages(self, cross_env):
        """两个 channel 同时发送消息，验证各自独立响应"""
        tg_runner, dc_runner = cross_env

        # Inject to both simultaneously
        tg_before = len(tg_runner.get_sent_messages())
        dc_before = len(dc_runner.get_sent_messages())

        tg_runner.inject("/sessions", chat_id=self.TG_CHAT_ID)
        dc_runner.inject("/sessions", channel_id=self.DC_CHANNEL_ID)

        tg_reply = tg_runner.wait_for_reply(count_before=tg_before, timeout=TIMEOUT_COMMAND,
                                            chat_id=self.TG_CHAT_ID)
        dc_reply = dc_runner.wait_for_reply(count_before=dc_before, timeout=TIMEOUT_COMMAND,
                                            chat_id=self.DC_CHANNEL_ID)

        assert tg_reply is not None, "TG should respond to /sessions"
        assert dc_reply is not None, "DC should respond to /sessions"
        logger.info(f"  ✓ Concurrent messages: both channels responded")
