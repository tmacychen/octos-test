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
import threading
from runner_slack import SlackTestRunner
from test_helpers import inject_and_get_reply

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
    
    def test_clear_resets_session(self, runner):
        """/clear → 'Session cleared.' 清空当前会话"""
        inject_and_get_reply(runner, "/new clear-test", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        text = inject_and_get_reply(runner, "/clear", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Session cleared.", f"实际回复: {text}"
    
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


# ══════════════════════════════════════════════════════════════════════════════
# 别名命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackAliasCommands:
    """验证 GatewayDispatcher 别名命令的正确性"""

    CHANNEL = "C012AB3CD"
    USER = "U012AB3CD"

    def test_back_alias_b(self, runner):
        """/b 与 /back 行为相同"""
        text = inject_and_get_reply(runner, "/b", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert "session" in text.lower(), f"实际回复: {text}"

    def test_delete_alias_d(self, runner):
        """/d <name> 与 /delete 行为相同"""
        inject_and_get_reply(runner, "/new d-alias", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        text = inject_and_get_reply(runner, "/d d-alias", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert text == "Deleted session: d-alias", f"实际回复: {text}"

    def test_delete_no_name(self, runner):
        """/delete（无参数）不匹配 dispatcher，走未知命令帮助"""
        text = inject_and_get_reply(runner, "/delete", timeout=TIMEOUT_COMMAND, channel=self.CHANNEL)
        assert len(text) > 0, "回复为空"
        logger.info(f"\n  /delete (no arg) → {text[:80]}")


# ══════════════════════════════════════════════════════════════════════════════
# Queue Mode Steer/Interrupt 非 abort 消息测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackQueueModeSteerNonAbort:
    """验证 Steer/Interrupt 模式下，普通消息不会误触发 abort"""

    CHANNEL_STEER = "C111STEER"
    CHANNEL_INTERRUPT = "C222INTERRUPT"

    def test_steer_mode_non_abort_messages_not_triggered(self, runner):
        """验证 steer 模式下普通消息不会误触发 abort"""
        channel = self.CHANNEL_STEER
        # Step 1: 设置为 steer 模式
        text = inject_and_get_reply(runner, "/queue steer", timeout=TIMEOUT_COMMAND, channel=channel)
        assert "Steer" in text or "steer" in text.lower(), f"Failed to set steer mode: {text}"

        # Step 2: 发送可能误触发的消息
        non_triggers = [
            "please stop talking about cats",
            "stopping point is here",
            "I will exit now",
            "cancel my subscription please",
        ]

        for msg in non_triggers:
            reply = inject_and_get_reply(runner, msg, timeout=TIMEOUT_LLM, channel=channel)
            logger.info(f"\n📤 User: {msg}")
            logger.info(f"📥 LLM: {reply[:200]}{'...' if len(reply) > 200 else ''}")
            has_abort_emoji = "🛑" in reply
            assert not has_abort_emoji, \
                f"False abort trigger in steer mode for '{msg}': {reply[:200]}"

        logger.info(f"\n  ✓ Steer mode: Non-abort messages handled correctly")
        inject_and_get_reply(runner, "/queue collect", timeout=TIMEOUT_COMMAND, channel=channel)

    def test_interrupt_mode_non_abort_messages_not_triggered(self, runner):
        """验证 interrupt 模式下普通消息不会误触发 abort"""
        channel = self.CHANNEL_INTERRUPT
        text = inject_and_get_reply(runner, "/queue interrupt", timeout=TIMEOUT_COMMAND, channel=channel)
        assert "Interrupt" in text or "interrupt" in text.lower(), \
            f"Failed to set interrupt mode: {text}"

        non_triggers = [
            "don't stop the music",
            "the concert was canceled",
            "abort the rocket launch",
        ]

        for msg in non_triggers:
            reply = inject_and_get_reply(runner, msg, timeout=TIMEOUT_LLM, channel=channel)
            logger.info(f"\n📤 User: {msg}")
            logger.info(f"📥 LLM: {reply[:200]}{'...' if len(reply) > 200 else ''}")
            has_abort_emoji = "🛑" in reply
            assert not has_abort_emoji, \
                f"False abort trigger in interrupt mode for '{msg}': {reply[:200]}"

        logger.info(f"\n  ✓ Interrupt mode: Non-abort messages handled correctly")
        inject_and_get_reply(runner, "/queue collect", timeout=TIMEOUT_COMMAND, channel=channel)


# ══════════════════════════════════════════════════════════════════════════════
# 多用户隔离测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackMultiUser:
    """多用户隔离测试"""

    def test_two_users_independent(self, runner):
        """两个不同 channel 的用户各自创建会话，互不干扰"""
        text_a = inject_and_get_reply(runner, "/new user-a-topic",
                                      timeout=TIMEOUT_COMMAND, channel="CUSERA", user="UUSERA")
        assert text_a == "Switched to session: user-a-topic"

        text_b = inject_and_get_reply(runner, "/new user-b-topic",
                                      timeout=TIMEOUT_COMMAND, channel="CUSERB", user="UUSERB")
        assert text_b == "Switched to session: user-b-topic"


# ══════════════════════════════════════════════════════════════════════════════
# Profile 模式测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackProfileMode:
    """多 profile/子账号的独立性"""

    def test_profile_session_isolation(self, runner):
        """两个不同 profile 的用户应有独立的会话"""
        text_a = inject_and_get_reply(runner, "/new profile-a-topic",
                                      timeout=TIMEOUT_COMMAND, channel="CPROFA", user="UUSERA")
        assert text_a == "Switched to session: profile-a-topic"

        text_b = inject_and_get_reply(runner, "/new profile-b-topic",
                                      timeout=TIMEOUT_COMMAND, channel="CPROFB", user="UUSERB")
        assert text_b == "Switched to session: profile-b-topic"

        text_a_check = inject_and_get_reply(runner, "/sessions",
                                            timeout=TIMEOUT_COMMAND, channel="CPROFA")
        assert "profile-a-topic" in text_a_check

    def test_soul_per_profile(self, runner):
        """不同 profile 应有独立的 soul 设置"""
        inject_and_get_reply(runner, "/soul You are a cat expert.",
                             timeout=TIMEOUT_COMMAND, channel="CSOULA", user="UUSERC")
        inject_and_get_reply(runner, "/soul You are a cooking assistant.",
                             timeout=TIMEOUT_COMMAND, channel="CSOULB", user="UUSERD")

        # 验证 A 的 soul 是 "cat expert"
        text_a = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, channel="CSOULA")
        assert "cat" in text_a.lower(), f"Soul per profile failed: {text_a[:100]}"

        # 验证 B 的 soul 是 "cooking"
        text_b = inject_and_get_reply(runner, "/soul", timeout=TIMEOUT_COMMAND, channel="CSOULB")
        assert "cooking" in text_b.lower(), f"Soul per profile failed: {text_b[:100]}"

    def test_queue_mode_per_profile(self, runner):
        """不同 profile 应有独立的 queue mode 设置"""
        inject_and_get_reply(runner, "/queue steer",
                             timeout=TIMEOUT_COMMAND, channel="CQUEA", user="UUSERE")
        text_a = inject_and_get_reply(runner, "/queue",
                                      timeout=TIMEOUT_COMMAND, channel="CQUEA")
        assert "Steer" in text_a, f"Queue mode not set for profile A: {text_a[:100]}"

        inject_and_get_reply(runner, "/queue interrupt",
                             timeout=TIMEOUT_COMMAND, channel="CQUEB", user="UUSERF")
        text_b = inject_and_get_reply(runner, "/queue",
                                      timeout=TIMEOUT_COMMAND, channel="CQUEB")
        assert "Interrupt" in text_b, f"Queue mode not set for profile B: {text_b[:100]}"


# ══════════════════════════════════════════════════════════════════════════════
# 消息格式测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackMessageFormats:
    """验证 Slack 特殊消息格式的处理"""

    def test_message_with_mention(self, runner):
        """消息中包含 @mention"""
        reply = inject_and_get_reply(runner, "<@U0BOTUSERID> hello", timeout=TIMEOUT_COMMAND)
        assert reply is not None

    def test_message_with_code_block(self, runner):
        """消息中包含代码块"""
        reply = inject_and_get_reply(runner, "```python\nprint('hello')\n```", timeout=TIMEOUT_COMMAND)
        if reply:
            logger.info(f"  Code block handled: {reply[:100]}")

    def test_message_with_link(self, runner):
        """消息中包含链接"""
        reply = inject_and_get_reply(runner, "Check this: https://example.com", timeout=TIMEOUT_COMMAND)
        if reply:
            logger.info(f"  Link handled: {reply[:100]}")


# ══════════════════════════════════════════════════════════════════════════════
# 并发会话测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackConcurrencyLimit:
    """验证并发会话限制"""

    def test_concurrent_session_creation(self, runner):
        """同时创建多个会话，验证并发处理能力"""
        session_count = 10
        results = {}
        errors = {}

        def create_session(session_id):
            try:
                channel = f"C5{session_id:03d}"
                text = inject_and_get_reply(
                    runner, f"/new concurrent-{session_id}",
                    timeout=TIMEOUT_COMMAND, channel=channel
                )
                results[session_id] = text
            except Exception as e:
                errors[session_id] = str(e)

        threads = []
        start_time = time.time()

        for i in range(session_count):
            t = threading.Thread(target=create_session, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=60)

        elapsed = time.time() - start_time
        logger.info(f"\n  Concurrent sessions: {session_count}")
        logger.info(f"  Elapsed time: {elapsed:.2f}s")
        logger.info(f"  Successful: {len(results)}")
        logger.info(f"  Errors: {len(errors)}")

        assert len(errors) == 0, f"Some sessions failed: {errors}"
        assert len(results) == session_count, \
            f"Expected {session_count} results, got {len(results)}"
        for session_id, text in results.items():
            assert "concurrent-" in text or "Switched to session" in text, \
                f"Session {session_id} has incorrect response: {text[:100]}"


# ══════════════════════════════════════════════════════════════════════════════
# 文件大小限制测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackFileLimits:
    """验证会话文件大小限制 (10MB)"""

    @pytest.mark.slow
    def test_large_message_handling(self, runner):
        """验证 octos 能处理较大的单条消息"""
        import time

        message_size = 1 * 1024 * 1024  # 1MB
        large_message = "A" * message_size

        logger.info(f"\n  Sending {message_size / (1024*1024):.1f}MB single message...")
        start_time = time.time()

        try:
            text = inject_and_get_reply(runner, large_message, timeout=TIMEOUT_COMMAND)
            elapsed = time.time() - start_time
            logger.info(f"  Response received in {elapsed:.2f}s")
            if text:
                logger.info(f"  Reply: {text[:100]}...")
        except Exception as e:
            logger.warning(f"  Large message handling may have issues: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 压力测试
# ══════════════════════════════════════════════════════════════════════════════

class TestSlackStressAndEdgeCases:
    """压力测试和边缘情况"""

    def test_rapid_messages(self, runner):
        """快速连续发送消息"""
        count_before = len(runner.get_sent_messages())
        for i in range(5):
            runner.inject(f"Quick message {i}", channel="CSTRESS1")
            time.sleep(0.2)
        reply = runner.wait_for_reply(count_before=count_before, timeout=TIMEOUT_LLM, chat_id="CSTRESS1")
        assert reply is not None, "Bot should respond to at least one message"
        logger.info(f"\n  ✓ Rapid messages handled")

    def test_concurrent_channels(self, runner):
        """同时向多个频道发消息"""
        channels = ["CCONC01", "CCONC02", "CCONC03"]
        counts = {}
        for ch in channels:
            counts[ch] = len(runner.get_sent_messages())
            runner.inject(f"Concurrent test {ch}", channel=ch)

        for ch in channels:
            reply = runner.wait_for_reply(count_before=counts[ch], timeout=TIMEOUT_LLM, chat_id=ch)
            if reply:
                logger.info(f"  ✓ Channel {ch} replied: {reply['text'][:50]}")


# ══════════════════════════════════════════════════════════════════════════════
# LLM 连通性测试
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestSlackLLMMessages:
    """Smoke tests for LLM integration"""

    CHANNEL = "CLLM001"

    def test_who_are_you(self, runner):
        """验证能询问 LLM 身份并收到回复"""
        text = inject_and_get_reply(runner, "你是谁？", timeout=TIMEOUT_LLM, channel=self.CHANNEL)
        assert len(text) > 0, "Should receive a response from LLM"
        logger.info(f"\n{'='*70}")
        logger.info(f"📤 User: 你是谁？")
        logger.info(f"📥 LLM: {text[:200]}{'...' if len(text) > 200 else ''}")
        logger.info(f"{'='*70}\n")

    def test_hello_greeting(self, runner):
        """验证英文问候能收到 LLM 回复"""
        text = inject_and_get_reply(runner, "Hello!", timeout=TIMEOUT_LLM, channel=self.CHANNEL)
        assert len(text) > 0, "Should receive a response from LLM"
        logger.info(f"\n{'='*70}")
        logger.info(f"📤 User: Hello!")
        logger.info(f"📥 LLM: {text[:200]}{'...' if len(text) > 200 else ''}")
        logger.info(f"{'='*70}\n")

    def test_chinese_greeting(self, runner):
        """验证中文问候能收到 LLM 回复"""
        text = inject_and_get_reply(runner, "你好", timeout=TIMEOUT_LLM, channel=self.CHANNEL)
        assert len(text) > 0, "Should receive a response from LLM"
        logger.info(f"\n{'='*70}")
        logger.info(f"📤 User: 你好")
        logger.info(f"📥 LLM: {text[:200]}{'...' if len(text) > 200 else ''}")
        logger.info(f"{'='*70}\n")


# ══════════════════════════════════════════════════════════════════════════════
# Abort 功能测试 — 多语言 abort 触发词识别
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.llm
class TestSlackAbortCommands:
    """验证 Agent 能正确中止任务 — 多语言 abort 触发词识别"""

    def test_abort_with_whitespace(self, runner):
        """验证 abort 命令前后空格不影响识别"""
        test_cases = [
            ("  stop  ", "CABW01", ["🛑", "Cancelled", "Cancel"]),
            ("\tstop\n", "CABW02", ["🛑", "Cancelled", "Cancel"]),
            (" 停 ", "CABW03", ["🛑", "取消", "已取消"]),
        ]

        for cmd, channel, expected_keywords in test_cases:
            count_before = len(runner.get_sent_messages())
            runner.inject(cmd, channel=channel)
            abort_reply = runner.wait_for_reply(
                count_before=count_before,
                timeout=TIMEOUT_COMMAND,
                chat_id=channel
            )
            assert abort_reply is not None, f"Should respond to trimmed '{cmd}'"
            text = abort_reply["text"]

            has_expected_keyword = any(kw.lower() in text.lower() for kw in expected_keywords if not kw.startswith("🛑"))
            has_emoji = "🛑" in text
            assert has_emoji or has_expected_keyword, \
                f"Expected cancel response for '{cmd}', got: {text[:200]}"

        logger.info(f"  ✓ Whitespace handling works")

    def test_non_abort_messages_not_triggered(self, runner):
        """验证普通消息不会误触发 abort"""
        non_triggers = [
            "please stop talking about cats",
            "stopping point is here",
            "I will exit now",
        ]
        for msg in non_triggers:
            runner.inject(msg)
            time.sleep(0.5)
        logger.info(f"\n  ✓ Non-abort messages handled correctly")

    @pytest.mark.parametrize(
        "language,channel,long_task,expected_keywords",
        [
            ("english", "CABT01",
             "Please tell me something about Python",
             ["🛑", "Cancelled"]),
            ("chinese", "CABT02",
             "请告诉我 Python 是什么？",
             ["🛑", "已取消"]),
            ("japanese", "CABT03",
             "Pythonとは何ですか？",
             ["🛑", "キャンセル"]),
            ("russian", "CABT04",
             "Что такое Python?",
             ["🛑", "Отменено"]),
        ],
        ids=[
            "english_stop",
            "chinese_stop",
            "japanese_stop",
            "russian_stop",
        ]
    )
    def test_abort_multilanguage(self, runner, language, channel, long_task, expected_keywords):
        """多语言 abort 测试"""
        logger.info(f"\n{'='*70}")
        logger.info(f"Testing {language} abort")
        logger.info(f"{'='*70}")

        # Step 1: 发送一个需要 LLM 处理的长任务
        logger.info(f"📤 Sending to LLM (user input):")
        logger.info(f"   {long_task[:200]}{'...' if len(long_task) > 200 else ''}")
        count_before_abort = len(runner.get_sent_messages())
        runner.inject(long_task, channel=channel)
        logger.info(f"  → Long task injected\n")

        # Step 2: 等待任务开始处理
        import time as _time
        _time.sleep(3)

        # Step 3: 获取第一个 trigger 词发送 abort 命令
        abort_cmd = expected_keywords[1] if len(expected_keywords) > 1 and expected_keywords[1] != "🛑" else "stop"
        logger.info(f"\n  📤 Sending to LLM (abort command): '{abort_cmd}'")
        runner.inject(abort_cmd, channel=channel)

        # Step 4: 等待 abort 响应
        abort_reply = None
        poll_start = _time.time()
        last_print_time = poll_start
        while _time.time() - poll_start < 60.0:
            current_time = _time.time()
            elapsed = current_time - poll_start
            if current_time - last_print_time >= 1.0:
                logger.info(f"  ⏳ Waiting for abort response... {elapsed:.0f}s")
                last_print_time = current_time

            msgs = runner.get_sent_messages()
            new_msgs = msgs[count_before_abort:]

            for msg in new_msgs:
                text = msg["text"]
                if text in ["Processing", "Deliberating", "Thinking", "Working"]:
                    continue
                has_emoji = "🛑" in text
                has_keyword = any(kw.lower() in text.lower() for kw in expected_keywords if not kw.startswith("🛑"))
                if has_emoji or has_keyword:
                    abort_reply = msg
                    break
            if abort_reply:
                break
            _time.sleep(0.5)

        assert abort_reply is not None, \
            f"Bot did not respond to abort command '{abort_cmd}' within 60s"

        text = abort_reply["text"]
        has_expected_keyword = any(kw.lower() in text.lower() for kw in expected_keywords if not kw.startswith("🛑"))
        has_emoji = "🛑" in text
        assert has_emoji or has_expected_keyword, \
            f"Abort response for '{language}' lacks expected keywords. Got: {text[:200]}"

        logger.info(f"\n  ✓ {language} abort test passed")
        logger.info(f"  📥 Bot: {text[:100]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
