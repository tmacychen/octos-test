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
import time
import httpx
from test_helpers import inject_and_get_reply
from runner_feishu import FeishuTestRunner

logger = logging.getLogger(__name__)

# ── 超时配置 ──────────────────────────────────────────────────────────────────
TIMEOUT_COMMAND = 50
TIMEOUT_LLM     = 90

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def runner():
    """创建飞书测试运行器（session 级）。"""
    r = FeishuTestRunner()
    assert r.health(), "Mock Server 未运行"
    return r


@pytest.fixture(autouse=True)
def clear_before(runner):
    """每个测试前清理 Mock Server 状态，包含健康检查和稳定性检测。"""
    # Health check
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if runner.health():
                break
        except Exception:
            pass
        if attempt < max_retries - 1:
            logger.info(f"  ⚠ Mock Server not responding, retry {attempt + 1}/{max_retries}...")
            time.sleep(1.0)
    else:
        pytest.skip("Mock Server 崩溃，无法恢复")

    # 等待消息稳定
    try:
        prev_count = len(runner.get_sent_messages(timeout=2))
    except httpx.HTTPError:
        pytest.skip("Mock Server 响应异常，跳过测试")
        return

    for _ in range(10):
        time.sleep(0.5)
        try:
            curr_count = len(runner.get_sent_messages(timeout=2))
            if curr_count == prev_count:
                break
            prev_count = curr_count
        except httpx.HTTPError:
            break

    # 清理状态
    try:
        runner.clear()
    except httpx.HTTPError:
        pytest.skip("Mock Server 无法清理，跳过测试")
        return

    # 重置所有非默认状态
    try:
        inject_and_get_reply(runner, "/reset", timeout=3,
                             sender_id="reset_cleanup", chat_id="oc_test_reset")
    except (httpx.HTTPError, AssertionError, Exception):
        pass

    time.sleep(0.5)
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：会话管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuSessionCommands:
    """测试飞书频道中的会话管理命令 (/new, /s, /back, /sessions, /delete, /soul)"""

    SENDER = "ou_session_tester"
    CHAT = "oc_test_session"

    def inject(self, runner, text):
        inject_and_get_reply(runner, text, timeout=TIMEOUT_COMMAND,
                             sender_id=self.SENDER, chat_id=self.CHAT)

    def test_new_default(self, runner):
        """/new 应该创建默认会话"""
        text = inject_and_get_reply(runner, "/new", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Session cleared.", f"实际回复: {text}"

    def test_new_named(self, runner):
        """/new <name> 应该创建命名会话"""
        text = inject_and_get_reply(runner, "/new work", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Switched to session: work", f"实际回复: {text}"

    def test_new_invalid_name(self, runner):
        """/new bad:name 应该报错"""
        text = inject_and_get_reply(runner, "/new bad:name", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Invalid session name:"), f"实际回复: {text}"

    def test_switch_to_existing(self, runner):
        """/s <name> 应该切换会话"""
        self.inject(runner, "/new research")
        text = inject_and_get_reply(runner, "/s research", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Switched to session: research"), f"实际回复: {text}"

    def test_switch_to_default(self, runner):
        """/s（无参数）应该切换到默认会话"""
        self.inject(runner, "/new custom")
        text = inject_and_get_reply(runner, "/s", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Switched to default session.", f"实际回复: {text}"

    def test_sessions_list(self, runner):
        """/sessions 应该列出所有会话"""
        self.inject(runner, "/new list-a")
        self.inject(runner, "/new list-b")
        text = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "list-a" in text and "list-b" in text, f"会话列表缺少预期会话: {text}"

    def test_back_returns_session(self, runner):
        """/back 应该返回会话相关回复"""
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "session" in text.lower(), f"实际回复: {text}"

    def test_back_with_history(self, runner):
        """/back（有历史）应该返回上一个会话"""
        self.inject(runner, "/new alpha")
        self.inject(runner, "/new beta")
        text = inject_and_get_reply(runner, "/back", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Switched back to session:"), f"实际回复: {text}"

    def test_delete_session(self, runner):
        """/delete <name> 应该删除会话"""
        self.inject(runner, "/new to-delete")
        text = inject_and_get_reply(runner, "/delete to-delete", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Deleted session: to-delete", f"实际回复: {text}"

    def test_delete_no_name(self, runner):
        """/delete（无参数）走未知命令帮助"""
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert len(text) > 0, "回复为空"
        logger.info(f"\n  /delete (no arg) → {text[:80]}")

    def test_soul_show_default(self, runner):
        """/soul 应该显示当前 soul"""
        text = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert len(text) > 0, "回复为空"

    def test_soul_set(self, runner):
        """/soul <text> 应该设置 soul"""
        text = inject_and_get_reply(runner, "/soul 你是一个助手", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Soul updated. Takes effect in new sessions.", f"实际回复: {text}"

    def test_soul_reset(self, runner):
        """/soul reset 应该重置 soul"""
        text = inject_and_get_reply(runner, "/soul reset", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Soul reset to default. Takes effect in new sessions.", f"实际回复: {text}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：配置命令
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuConfigCommands:
    """测试飞书频道中的配置命令 (/queue, /status, /adaptive, /reset, /help)"""

    SENDER = "ou_config_tester"
    CHAT = "oc_test_config"

    def test_adaptive_no_router(self, runner):
        """/adaptive 未启用自适应路由"""
        text = inject_and_get_reply(runner, "/adaptive", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Adaptive routing is not enabled.", f"实际回复: {text}"

    def test_queue_show(self, runner):
        """/queue 应该显示当前模式"""
        text = inject_and_get_reply(runner, "/queue", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Queue mode:"), f"实际回复: {text}"

    def test_queue_set_followup(self, runner):
        """/queue followup 应该切换模式"""
        text = inject_and_get_reply(runner, "/queue followup", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "Followup" in text, f"实际回复: {text}"

    def test_queue_set_invalid(self, runner):
        """/queue badmode 应该提示未知模式"""
        text = inject_and_get_reply(runner, "/queue badmode", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "Unknown mode" in text, f"实际回复: {text}"

    def test_status_show(self, runner):
        """/status 应该返回状态配置"""
        text = inject_and_get_reply(runner, "/status", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert "Status Config" in text, f"实际回复: {text}"

    def test_reset_command(self, runner):
        """/reset 应该重置所有配置"""
        text = inject_and_get_reply(runner, "/reset", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text == "Reset: queue=collect, adaptive=off, history cleared.", \
            f"实际回复: {text}"

    def test_unknown_command_help(self, runner):
        """未知命令应该返回帮助文本"""
        text = inject_and_get_reply(runner, "/unknowncmd", timeout=TIMEOUT_COMMAND,
                                    sender_id=self.SENDER, chat_id=self.CHAT)
        assert text.startswith("Unknown command."), f"实际回复: {text}"
        for cmd in ["/new", "/s", "/sessions", "/back", "/delete", "/soul",
                    "/status", "/adaptive", "/reset"]:
            assert cmd in text, f"帮助文本缺少 {cmd}: {text}"


# ═══════════════════════════════════════════════════════════════════════════════
# 测试类：基本 LLM 消息
# ═══════════════════════════════════════════════════════════════════════════════

class TestFeishuLLMMessages:
    """测试飞书频道中需要 LLM 回复的消息。"""

    SENDER = "ou_llm_tester"
    CHAT = "oc_test_llm"

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
        assert text_a.startswith("Switched to session:"), f"Profile A 失败: {text_a}"

        text_b = inject_and_get_reply(runner, "/new profile-b", timeout=TIMEOUT_COMMAND,
                                      sender_id=self.SENDER, chat_id=self.CHAT_B)
        assert text_b.startswith("Switched to session:"), f"Profile B 失败: {text_b}"

        # 验证 A 的会话不受 B 影响
        sessions_a = inject_and_get_reply(runner, "/sessions", timeout=TIMEOUT_COMMAND,
                                          sender_id=self.SENDER, chat_id=self.CHAT_A)
        assert "profile-a" in sessions_a, f"Profile A 会话列表缺失: {sessions_a}"
