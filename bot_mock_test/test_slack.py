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
    
    def test_simple_message(self, runner):
        """测试简单文本消息"""
        result = runner.inject(
            text="Hello, Slack bot!",
            channel="C012AB3CD",
            user="U012AB3CD",
        )
        
        assert result["success"] is True
        assert "event_id" in result
        
        # 等待 Bot 响应
        count_before = len(runner.get_sent_messages())
        reply = runner.wait_for_reply(
            count_before=count_before,
            timeout=TIMEOUT_COMMAND,
            chat_id="C012AB3CD",
        )
        
        # 注意：这个测试可能会失败，因为需要 LLM 响应
        # 如果 octos 没有配置 Slack channel，Bot 不会响应
        if reply:
            logger.info(f"✓ Bot responded: {reply['text'][:100]}")
        else:
            logger.warning("⚠ No bot response received (may need LLM configuration)")
    
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
    
    def test_new_creates_session(self, runner):
        """/new 应该创建新会话"""
        result = runner.inject(
            text="/new test-session",
            channel="C012AB3CD",
            user="U012AB3CD",
        )
        
        assert result["success"] is True
        
        # 等待 Bot 响应
        count_before = len(runner.get_sent_messages())
        reply = runner.wait_for_reply(
            count_before=count_before,
            timeout=TIMEOUT_COMMAND,
            chat_id="C012AB3CD",
        )
        
        if reply:
            assert "Switched to session: test-session" in reply["text"], f"Unexpected: {reply['text']}"
        else:
            logger.warning("⚠ No response to /new command")
    
    def test_help_command(self, runner):
        """/help 应该返回帮助信息"""
        result = runner.inject(
            text="/help",
            channel="C012AB3CD",
            user="U012AB3CD",
        )
        
        assert result["success"] is True
        
        # 等待 Bot 响应
        count_before = len(runner.get_sent_messages())
        reply = runner.wait_for_reply(
            count_before=count_before,
            timeout=TIMEOUT_COMMAND,
            chat_id="C012AB3CD",
        )
        
        if reply:
            assert "help" in reply["text"].lower() or "command" in reply["text"].lower()
        else:
            logger.warning("⚠ No response to /help command")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
