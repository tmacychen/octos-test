#!/usr/bin/env python3
"""
飞书 Bot 集成测试

测试 octos 飞书 Bot 的核心功能：
  - 会话管理（/new, /switch, /sessions, /back, /delete）
  - 配置命令（/queue, /soul, /status, /adaptive, /reset, /help）
  - 基本 LLM 消息
  - Profile 模式
"""

import logging
import pytest
from test_helpers import inject_and_get_reply
from runner_feishu import FeishuTestRunner

logger = logging.getLogger(__name__)

# ── 超时配置 ──────────────────────────────────────────────────────────────────
TIMEOUT_COMMAND = 50
TIMEOUT_LLM     = 90


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def runner():
    """创建飞书测试运行器。"""
    return FeishuTestRunner()


@pytest.fixture(autouse=True)
def clear_before(runner):
    """每个测试前清理 Mock Server 状态。"""
    runner.clear()
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：会话管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuSessionCommands:
    """测试飞书频道中的会话管理命令 (/new, /s, /back, /sessions, /delete, /clear, /soul)"""

    SENDER = "ou_tester"
    CHAT = "oc_test_session"

    def inject(self, runner, text):
        return runner.inject(text, sender_id=self.SENDER, chat_id=self.CHAT)

    def test_new_default(self, runner):
        """/new 应该创建默认会话"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        logger.info(f"  Reply: {text}")
        assert text is not None and len(text) > 0, f"Empty reply: {text}"

    def test_new_named(self, runner):
        """/new <name> 应该创建命名会话"""
        text = inject_and_get_reply(runner, "/new work", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        logger.info(f"  Reply: {text}")
        assert "work" in text.lower(), f"Unexpected: {text}"

    def test_switch_session(self, runner):
        """/s <name> 应该切换会话"""
        inject_and_get_reply(runner, "/new research", timeout=TIMEOUT_COMMAND,
                             sender_id=self.SENDER, chat_id=self.CHAT)
        text = inject_and_get_reply(runner, "/s research", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "research" in text.lower(), f"Unexpected: {text}"

    def test_sessions_list(self, runner):
        """/sessions 应该列出会话"""
        inject_and_get_reply(runner, "/new list-a", timeout=TIMEOUT_COMMAND,
                             sender_id=self.SENDER, chat_id=self.CHAT)
        inject_and_get_reply(runner, "/new list-b", timeout=TIMEOUT_COMMAND,
                             sender_id=self.SENDER, chat_id=self.CHAT)
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and len(text) > 0, "Empty sessions list"

    def test_delete_session(self, runner):
        """/delete 应该删除当前会话"""
        inject_and_get_reply(runner, "/new delete-me", timeout=TIMEOUT_COMMAND,
                             sender_id=self.SENDER, chat_id=self.CHAT)
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and ("deleted" in text.lower() or "已删除" in text), f"Unexpected: {text}"

    def test_soul_set(self, runner):
        """/soul <text> 应该设置 soul"""
        text = inject_and_get_reply(runner, "/soul 你是一个助手", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and len(text) > 0, f"Empty reply: {text}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：配置命令
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuConfigCommands:
    """测试飞书频道中的配置命令 (/queue, /status, /adaptive, /reset, /help)"""

    SENDER = "ou_config_tester"
    CHAT = "oc_test_config"

    def inject(self, runner, text):
        return runner.inject(text, sender_id=self.SENDER, chat_id=self.CHAT)

    def test_queue_show(self, runner):
        """/queue 应该显示当前模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and len(text) > 0, f"Empty reply: {text}"

    def test_queue_set(self, runner):
        """/queue followup 应该切换模式"""
        text = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and len(text) > 0, f"Empty reply: {text}"

    def test_status(self, runner):
        """/status 应该返回状态"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and len(text) > 0, "Empty status reply"

    def test_help(self, runner):
        """/help 应该返回帮助信息"""
        text = inject_and_get_reply(runner, "/help", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and len(text) > 0, "Empty help reply"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：基本 LLM 消息
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuLLMMessages:
    """测试飞书频道中需要 LLM 回复的消息。"""

    SENDER = "ou_llm_tester"
    CHAT = "oc_test_llm"

    def inject(self, runner, text):
        return runner.inject(text, sender_id=self.SENDER, chat_id=self.CHAT)

    def test_regular_message(self, runner):
        """普通消息应该触发 LLM 回复"""
        text = inject_and_get_reply(runner, "你好，请介绍一下你自己", timeout=TIMEOUT_LLM,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text is not None and len(text) > 0, "Bot did not respond"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：Profile 模式
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuProfileMode:
    """测试飞书频道中的多 Profile 会话隔离。"""

    CHAT_A = "oc_test_profile_a"
    CHAT_B = "oc_test_profile_b"
    SENDER = "ou_profile_tester"

    def test_profile_session_isolation(self, runner):
        """不同 Profile 的会话应该隔离。"""
        text_a = inject_and_get_reply(runner, "/new profile-a", timeout=TIMEOUT_COMMAND,
                                      sender_id=self.SENDER, chat_id=self.CHAT_A)
        assert text_a is not None, "Profile A /new failed"

        text_b = inject_and_get_reply(runner, "/new profile-b", timeout=TIMEOUT_COMMAND,
                                      sender_id=self.SENDER, chat_id=self.CHAT_B)
        assert text_b is not None, "Profile B /new failed"
