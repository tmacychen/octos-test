#!/usr/bin/env python3
"""
微信 Bot 集成测试

测试 octos 微信 Bot 的核心功能：
  - 会话管理（/new, /switch, /sessions, /back, /delete）
  - 配置命令（/queue, /soul, /status, /adaptive, /reset, /help）
  - 基本 LLM 消息
"""

import logging
import pytest
from test_helpers import inject_and_get_reply
from runner_wechat import WeChatTestRunner

logger = logging.getLogger(__name__)

# ── 超时配置 ──────────────────────────────────────────────────────────────────
TIMEOUT_COMMAND = 50
TIMEOUT_LLM     = 90


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def runner():
    """创建微信测试运行器。"""
    return WeChatTestRunner()


@pytest.fixture(autouse=True)
def clear_before(runner):
    """每个测试前清理 Mock Server 状态。"""
    runner.clear()
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：会话管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeChatSessionCommands:
    """测试微信频道中的会话管理命令 (/new, /s, /back, /sessions, /delete, /clear, /soul)"""

    SENDER = "test_user@im.wechat"

    def test_new_default(self, runner):
        """/new 应该创建默认会话"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        logger.info(f"  Reply: {text}")
        assert text is not None and len(text) > 0, f"Empty reply: {text}"

    def test_new_named(self, runner):
        """/new <name> 应该创建命名会话"""
        text = inject_and_get_reply(runner, "/new work", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        logger.info(f"  Reply: {text}")
        assert "work" in text.lower(), f"Unexpected: {text}"

    def test_sessions_list(self, runner):
        """/sessions 应该列出会话"""
        inject_and_get_reply(runner, "/new list-a", timeout=TIMEOUT_COMMAND,
                             sender=self.SENDER)
        inject_and_get_reply(runner, "/new list-b", timeout=TIMEOUT_COMMAND,
                             sender=self.SENDER)
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        assert text is not None and len(text) > 0, "Empty sessions list"

    def test_delete_session(self, runner):
        """/delete 应该删除当前会话"""
        inject_and_get_reply(runner, "/new delete-me", timeout=TIMEOUT_COMMAND,
                             sender=self.SENDER)
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        assert text is not None and ("deleted" in text.lower() or "已删除" in text), f"Unexpected: {text}"

    def test_soul_set(self, runner):
        """/soul <text> 应该设置 soul"""
        text = inject_and_get_reply(runner, "/soul 你是一个助手", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        assert text is not None and len(text) > 0, f"Empty reply: {text}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：配置命令
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeChatConfigCommands:
    """测试微信频道中的配置命令 (/queue, /status, /adaptive, /reset, /help)"""

    SENDER = "config_user@im.wechat"

    def test_queue_show(self, runner):
        """/queue 应该显示当前模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        assert text is not None and len(text) > 0, f"Empty reply: {text}"

    def test_queue_set(self, runner):
        """/queue followup 应该切换模式"""
        text = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        assert text is not None and len(text) > 0, f"Empty reply: {text}"

    def test_status(self, runner):
        """/status 应该返回状态"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        assert text is not None and len(text) > 0, "Empty status reply"

    def test_help(self, runner):
        """/help 应该返回帮助信息"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND,
                                    sender=self.SENDER)
        assert text is not None and len(text) > 0, "Empty help reply"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：基本 LLM 消息
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeChatLLMMessages:
    """测试微信频道中需要 LLM 回复的消息。"""

    SENDER = "llm_user@im.wechat"

    def test_regular_message(self, runner):
        """普通消息应该触发 LLM 回复"""
        text = inject_and_get_reply(runner, "你好", timeout=TIMEOUT_LLM,
                                    sender=self.SENDER)
        assert text is not None and len(text) > 0, "Bot did not respond"
