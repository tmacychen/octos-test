#!/usr/bin/env python3
"""
Slack Bot 集成测试用例

前置条件（由 test_run.py 自动完成）：
  1. Mock Slack Server 运行在 http://127.0.0.1:5003
  2. octos gateway 已启动并连接到 Mock Server（通过 --features slack）

运行方式：
  uv run python test_run.py --test bot slack    # 完整测试
  pytest test_slack.py -v                        # 直接运行 pytest
"""

import pytest
import time
import logging
from runner_slack import SlackTestRunner

# Configure logger for this module
logger = logging.getLogger(__name__)

# 🔥 Suppress httpx INFO logs to reduce noise in test output
logging.getLogger("httpx").setLevel(logging.WARNING)

# ── 超时配置 ──────────────────────────────────────────────────────────────────
TIMEOUT_COMMAND = 20
TIMEOUT_LLM = 50


# ── Helper Functions ─────────────────────────────────────────────────────────

def inject_and_get_reply(runner, text, timeout=TIMEOUT_COMMAND, channel="C012AB3CD", user="U012AB3CD"):
    """Inject a message and wait for bot reply.
    
    Returns the reply text or None if no reply received.
    """
    # Get message count BEFORE injecting
    count_before = len(runner.get_sent_messages())
    
    # Inject the message
    result = runner.inject(text=text, channel=channel, user=user)
    assert result["success"] is True
    
    # Wait for new message (count_before + 1)
    reply = runner.wait_for_reply(
        count_before=count_before,
        timeout=timeout,
        chat_id=channel,
    )
    
    return reply["text"] if reply else None


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def runner():
    """Create Slack test runner."""
    r = SlackTestRunner()
    assert r.health(), "Slack Mock Server 未运行"
    return r


@pytest.fixture(autouse=True)
def cleanup_state(runner):
    """每个测试前清理 Mock Server 状态"""
    # Health check
    max_health_retries = 5
    health_retry_delay = 2.0
    for attempt in range(max_health_retries):
        try:
            if runner.health():
                break
        except Exception:
            pass
        if attempt < max_health_retries - 1:
            print(f"  ⚠ Mock Server not responding, retry {attempt + 1}/{max_health_retries}...")
            time.sleep(health_retry_delay)
    else:
        pytest.skip("Mock Server 崩溃，无法恢复")
        return
    
    # 清理 Mock Server 状态
    try:
        runner.clear()
    except Exception as e:
        print(f"  ⚠ Failed to clear Mock Server: {e}")
    
    yield


# ══════════════════════════════════════════════════════════════════════════════
# 基础消息测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackBasicMessages:
    """验证 Slack 基础消息处理"""
    
    # 🔥 固定 channel_id，确保测试隔离
    CHANNEL = "C012AB3CD"
    USER = "U012AB3CD"
    
    def test_simple_message(self, runner):
        """测试简单文本消息"""
        reply = inject_and_get_reply(runner, "Hello, Slack bot!", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        
        if reply:
            logger.info(f"✓ Bot responded: {reply[:100]}")
        else:
            logger.warning("⚠ No bot response received (may need LLM configuration)")
    
    def test_empty_message(self, runner):
        """测试空消息"""
        result = runner.inject(text="", channel=self.CHANNEL, user=self.USER)
        assert result["success"] is True
        
        # Empty messages may not trigger a response
        count_before = len(runner.get_sent_messages())
        time.sleep(2)
        count_after = len(runner.get_sent_messages())
        
        # Bot should not respond to empty messages
        assert count_after == count_before, "Bot should not respond to empty messages"
    
    def test_very_long_message(self, runner):
        """测试长消息"""
        long_text = "A" * 1000
        reply = inject_and_get_reply(runner, long_text, timeout=TIMEOUT_LLM, channel=self.CHANNEL)
        
        if reply:
            logger.info(f"✓ Long message handled, reply length: {len(reply)}")
    
    def test_special_characters(self, runner):
        """测试特殊字符"""
        special_text = "Test with special chars: @#$%^&*()!@#$%"
        reply = inject_and_get_reply(runner, special_text, timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        
        if reply:
            logger.info(f"✓ Special characters handled: {reply[:50]}")
    
    def test_unicode_emoji(self, runner):
        """测试 Unicode 和 emoji"""
        unicode_text = "Test with unicode: 你好世界 🌍🎉🚀"
        reply = inject_and_get_reply(runner, unicode_text, timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        
        if reply:
            logger.info(f"✓ Unicode handled: {reply[:50]}")
    
    def test_mock_server_health(self, runner):
        """测试 Mock Server 健康检查"""
        assert runner.health() is True
        
        stats = runner.get_stats()
        assert "sent_messages" in stats
        assert "injected_events" in stats
        assert "transactions" in stats


# ══════════════════════════════════════════════════════════════════════════════
# 会话管理命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackSessionCommands:
    """验证 GatewayDispatcher 处理的命令（不依赖 LLM）"""
    
    # 🔥 固定 channel_id，确保测试隔离
    CHANNEL = "C012AB3CD"
    USER = "U012AB3CD"
    
    def test_new_default(self, runner):
        """/new → 'Session cleared.'"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Session cleared.", f"实际回复: {text}"
    
    def test_new_named(self, runner):
        """/new work → 'Switched to session: work'"""
        text = inject_and_get_reply(runner, "/new work", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Switched to session: work", f"实际回复: {text}"
    
    def test_new_invalid_name(self, runner):
        """/new bad:name（含冒号）→ 'Invalid session name: ...'"""
        text = inject_and_get_reply(runner, "/new bad:name", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text.startswith("Invalid session name:"), f"实际回复: {text}"
    
    def test_switch_to_existing(self, runner):
        """/s <name> → 'Switched to session: <name>'"""
        inject_and_get_reply(runner, "/new research", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        text = inject_and_get_reply(runner, "/s research", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text.startswith("Switched to session: research"), f"实际回复: {text}"
    
    def test_switch_to_default(self, runner):
        """/s（无参数）→ 'Switched to default session.'"""
        text = inject_and_get_reply(runner, "/s", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Switched to default session.", f"实际回复: {text}"
    
    def test_sessions_list(self, runner):
        """/sessions → bot replies with session list"""
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert len(text) > 0, "Empty reply"
        logger.info(f"\n  /sessions → {text[:100]}")
    
    def test_back_returns_session(self, runner):
        """/back → session-related reply"""
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert "session" in text.lower(), f"Unexpected reply: {text}"
        logger.info(f"\n  /back → {text}")
    
    def test_back_with_history(self, runner):
        """/back（有历史）→ 'Switched back to session: <name>'"""
        inject_and_get_reply(runner, "/new alpha", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        inject_and_get_reply(runner, "/new beta", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text.startswith("Switched back to session:"), f"实际回复: {text}"
    
    def test_delete_session(self, runner):
        """/delete <name> → 'Deleted session: <name>'"""
        inject_and_get_reply(runner, "/new to-delete", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        text = inject_and_get_reply(runner, "/delete to-delete", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Deleted session: to-delete", f"实际回复: {text}"
    
    def test_soul_show_default(self, runner):
        """/soul → 显示当前 soul 或默认提示"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert len(text) > 0, "回复为空"
        logger.info(f"\n  /soul → {text[:80]}")
    
    def test_soul_set(self, runner):
        """/soul <text> → 'Soul updated. Takes effect in new sessions.'"""
        text = inject_and_get_reply(runner, "/soul You are a helpful assistant.", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Soul updated. Takes effect in new sessions.", f"实际回复: {text}"
    
    def test_soul_reset(self, runner):
        """/soul reset → 'Soul reset to default. Takes effect in new sessions.'"""
        text = inject_and_get_reply(runner, "/soul reset", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Soul reset to default. Takes effect in new sessions.", f"实际回复: {text}"


# ══════════════════════════════════════════════════════════════════════════════
# 会话内控制命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackSessionActorCommands:
    """会话内控制命令 — 本地处理，无需 LLM"""
    
    # 🔥 固定 channel_id，确保测试隔离
    CHANNEL = "C012AB3CD"
    USER = "U012AB3CD"
    
    def test_adaptive_no_router(self, runner):
        """/adaptive（未启用自适应路由）→ 'Adaptive routing is not enabled.'"""
        text = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Adaptive routing is not enabled.", f"实际回复: {text}"
    
    def test_queue_show(self, runner):
        """/queue → 'Queue mode: Collect'（默认模式）"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text.startswith("Queue mode:"), f"实际回复: {text}"
    
    def test_queue_set_followup(self, runner):
        """/queue followup → 'Queue mode set to: Followup'"""
        text = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert "Followup" in text, f"实际回复: {text}"
    
    def test_queue_set_invalid(self, runner):
        """/queue badmode → 'Unknown mode: ...'"""
        text = inject_and_get_reply(runner, "/queue badmode", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert "Unknown mode" in text, f"实际回复: {text}"
    
    def test_status_show(self, runner):
        """/status → 显示 Status Config"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert "Status Config" in text, f"实际回复: {text}"
    
    def test_reset_command(self, runner):
        """/reset → 'Reset: queue=collect, adaptive=off, history cleared.'"""
        text = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Reset: queue=collect, adaptive=off, history cleared.", \
            f"实际回复: {text}"
    
    def test_unknown_command_help(self, runner):
        """未知命令 → 帮助文本，包含所有已知命令"""
        text = inject_and_get_reply(runner, "/unknowncmd", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text.startswith("Unknown command."), f"实际回复: {text}"
        for cmd in ["/new", "/s", "/sessions", "/back", "/delete", "/soul",
                    "/status", "/adaptive", "/reset"]:
            assert cmd in text, f"帮助文本缺少 {cmd}: {text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
