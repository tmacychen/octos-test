#!/usr/bin/env python3
"""
Email Bot 集成测试 — 真实邮箱模式

本测试使用真实 QQ 邮箱，不需要 Mock 服务器。
运行时仅验证配置有效性并给出引导提示。

使用方法：
  1. 在 .env 中配置邮箱信息：
       EMAIL_USERNAME=your_bot@qq.com
       EMAIL_PASSWORD=your_authorization_code    （QQ邮箱请使用授权码，非QQ密码）
       EMAIL_REAL_TEST=true                        # 启用真实邮箱模式
       # 可选自定义服务器：
       # EMAIL_IMAP_HOST=imap.qq.com               # 默认 imap.qq.com
       # EMAIL_IMAP_PORT=993
       # EMAIL_SMTP_HOST=smtp.qq.com               # 默认 smtp.qq.com
       # EMAIL_SMTP_PORT=465

  2. 运行测试：
       uv run python test_run.py --test bot email

  3. 向 bot 邮箱发送一封邮件，octos 会通过 IMAP 轮询收取并回复。
     回复邮件会发送到你的发件箱，请检查邮箱。

QQ邮箱设置： 设置 → 账户 → 开启 IMAP/SMTP → 生成授权码
"""

import pytest
import logging
import os
import smtplib
import time
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


_EMAIL_INTERVAL = 30  # 每封邮件间隔秒数，对齐 IMAP 轮询周期
_send_count = [0]     # 用列表实现闭包可写计数器


def _smtp_send(body: str, subject_tag: str = "Test"):
    """通过 SMTP 发送一封邮件到 bot 邮箱，返回用于识别的主题。"""
    username = os.environ.get("EMAIL_USERNAME", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    smtp_host = os.environ.get("EMAIL_SMTP_HOST", "smtp.qq.com")
    smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "465"))

    _send_count[0] += 1
    seq = _send_count[0]
    time.sleep(_EMAIL_INTERVAL)

    subject = f"{subject_tag}-{seq:02d}"
    msg = MIMEText(body, _charset="utf-8")
    msg["From"] = username
    msg["To"] = username
    msg["Subject"] = subject

    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as s:
        s.login(username, password)
        s.send_message(msg)

    logger.info(f"  [{seq:02d}] 📤 已发送，主题: {subject}")
    logger.info(f"  [{seq:02d}] 👀 内容: {body[:60]}")
    return subject


@pytest.fixture(scope="session")
def runner():
    """Email 模式无 Mock 服务器，返回一个空对象供 conftest.py 引用。"""
    class _FakeRunner:
        @staticmethod
        def health() -> bool:
            return True  # 真实邮箱模式总是 "健康"
        @staticmethod
        def get_sent_messages(**kwargs):
            return []
        @staticmethod
        def clear():
            pass
    return _FakeRunner()


@pytest.fixture(scope="session")
def check_config():
    """验证 .env 配置是否就绪。"""
    import os

    errors = []
    username = os.environ.get("EMAIL_USERNAME", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    real_test = os.environ.get("EMAIL_REAL_TEST", "").lower() in ("1", "true")

    if not real_test:
        errors.append("请设置 EMAIL_REAL_TEST=true 启用真实邮箱模式")
    if not username:
        errors.append("请设置 EMAIL_USERNAME（bot 邮箱地址）")
    if not password:
        errors.append("请设置 EMAIL_PASSWORD（QQ邮箱请使用授权码，非QQ密码）")
    if "@" not in username:
        errors.append(f"EMAIL_USERNAME 格式错误，需要完整的邮箱地址，当前: {username}")

    if errors:
        pytest.fail(f"Email 配置不完整, {'; '.join(errors)}")


# ══════════════════════════════════════════════════════════════════════════════
# 配置验证测试
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailConfig:
    """验证 Email 配置是否正确"""

    def test_env_vars(self, check_config):
        """验证环境变量已正确配置"""
        smtp_host = os.environ.get("EMAIL_SMTP_HOST", "smtp.qq.com")
        senders = 19  # 自动发送的测试邮件数（不含本次引导）
        total_wait = senders * _EMAIL_INTERVAL
        logger.info(f"  邮箱地址: {os.environ.get('EMAIL_USERNAME', '未设置')}")
        logger.info(f"  IMAP: {os.environ.get('EMAIL_IMAP_HOST', 'imap.qq.com')}:{os.environ.get('EMAIL_IMAP_PORT', '993')}")
        logger.info(f"  SMTP: {smtp_host}:{os.environ.get('EMAIL_SMTP_PORT', '465')}")
        logger.info(f"  EMAIL_REAL_TEST: {os.environ.get('EMAIL_REAL_TEST', '未设置')}")
        logger.info(f"")
        logger.info(f"  ╔══════════════════════════════════════════════════════════╗")
        logger.info(f"  ║  📋 测试计划                                         ║")
        logger.info(f"  ║                                                      ║")
        logger.info(f"  ║  将自动发送 {senders} 封测试邮件                        ║")
        logger.info(f"  ║  每封间隔 {_EMAIL_INTERVAL}s，总耗时 ≈ {total_wait}s（{total_wait//60}min）        ║")
        logger.info(f"  ║  预计从 {time.strftime('%H:%M')} 开始发送              ║")
        logger.info(f"  ║  至 {time.strftime('%H:%M', time.localtime(time.time()+total_wait))} 前后全部发送完毕        ║")
        logger.info(f"  ║                                                      ║")
        logger.info(f"  ║  请关注收件箱，回复主题会带有 Re: 前缀                 ║")
        logger.info(f"  ║  例如 Hello-01 → 回复标题 Re: Hello-01               ║")
        logger.info(f"  ╚══════════════════════════════════════════════════════════╝")
        logger.info(f"")

    def test_imap_connectivity(self):
        """测试能否连接到 QQ 邮箱 IMAP 服务器（DNS 解析和端口可达性）"""
        import os, socket
        imap_host = os.environ.get("EMAIL_IMAP_HOST", "imap.qq.com")
        imap_port = int(os.environ.get("EMAIL_IMAP_PORT", "993"))

        try:
            addr = socket.getaddrinfo(imap_host, imap_port)
            logger.info(f"  ✓ DNS 解析成功: {imap_host} → {addr[0][4][0]}")
        except socket.gaierror as e:
            pytest.fail(f"DNS 解析失败: {imap_host} - {e}")

        try:
            sock = socket.create_connection((imap_host, imap_port), timeout=5)
            sock.close()
            logger.info(f"  ✓ TCP 连接成功: {imap_host}:{imap_port}")
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            pytest.fail(f"端口不可达: {imap_host}:{imap_port} - {e}")




# ══════════════════════════════════════════════════════════════════════════════
# 端到端基本收发测试
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailSendReceive:
    """基本收发：发送后人工去收件箱确认回复"""

    @pytest.mark.slow
    def test_simple_message(self):
        """发送简单问候，验证 LLM 回复"""
        subj = _smtp_send("Hello, this is a test. Please reply briefly.", "Hello")
        logger.info(f"  🔍 请去收件箱检查主题为 [{subj}] 的回复")
        logger.info(f"  ✅ 预期: LLM 回复内容")

    @pytest.mark.slow
    def test_chinese_message(self):
        """发送中文消息，验证中文 LLM 回复"""
        subj = _smtp_send("你好，请用中文简单回复一下", "ZH")
        logger.info(f"  🔍 请去收件箱检查主题为 [{subj}] 的回复")
        logger.info(f"  ✅ 预期: 中文回复内容")

    @pytest.mark.slow
    def test_long_email(self):
        """发送长消息，验证长文本处理"""
        long_text = "This is a long message. " * 50
        subj = _smtp_send(long_text, "Long")
        logger.info(f"  🔍 请去收件箱检查主题为 [{subj}] 的回复")
        logger.info(f"  ✅ 预期: 回复长度应与消息长度相关")


# ══════════════════════════════════════════════════════════════════════════════
# 会话管理命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailSessionCommands:
    """会话管理命令（通过邮件发送，人工验证回复）"""

    @pytest.mark.slow
    def test_new_session(self):
        """/new → 'Session cleared.'"""
        subj = _smtp_send("/new", "Session-New")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Session cleared.'")

    @pytest.mark.slow
    def test_new_named_session(self):
        """/new <name> → 'Switched to session: <name>'"""
        subj = _smtp_send("/new test-topic", "Session-Named")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Switched to session: test-topic'")

    @pytest.mark.slow
    def test_switch_session(self):
        """/s <name> → 'Switched to session: <name>'"""
        _smtp_send("/new research", "Switch-Prepare")
        time.sleep(2)
        subj = _smtp_send("/s research", "Switch-Exec")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 切换到 research 会话")

    @pytest.mark.slow
    def test_sessions_list(self):
        """/sessions → 显示会话列表"""
        _smtp_send("/new topic-a", "List-PrepA")
        _smtp_send("/new topic-b", "List-PrepB")
        time.sleep(2)
        subj = _smtp_send("/sessions", "List-Show")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 包含 topic-a 和 topic-b")

    @pytest.mark.slow
    def test_back_session(self):
        """/back → 'Switched back to session: ...'"""
        _smtp_send("/new first", "Back-Prep1")
        _smtp_send("/new second", "Back-Prep2")
        time.sleep(1)
        subj = _smtp_send("/back", "Back-Exec")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 回到 first 会话")

    @pytest.mark.slow
    def test_delete_session(self):
        """/delete <name> → 'Deleted session: <name>'"""
        _smtp_send("/new to-delete", "Del-Prep")
        time.sleep(1)
        subj = _smtp_send("/delete to-delete", "Del-Exec")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Deleted session: to-delete'")


# ══════════════════════════════════════════════════════════════════════════════
# Soul / Queue / Status 命令测试
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailConfigCommands:
    """配置命令测试（通过邮件发送，人工验证回复）"""

    @pytest.mark.slow
    def test_soul_show(self):
        """/soul → 显示当前 soul"""
        subj = _smtp_send("/soul", "Soul-Show")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 显示 soul 内容")

    @pytest.mark.slow
    def test_soul_set(self):
        """/soul <text> → 'Soul updated. Takes effect in new sessions.'"""
        subj = _smtp_send("/soul You are a helpful assistant.", "Soul-Set")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Soul updated'")

    @pytest.mark.slow
    def test_soul_reset(self):
        """/soul reset → 'Soul reset to default.'"""
        subj = _smtp_send("/soul reset", "Soul-Reset")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Soul reset'")

    @pytest.mark.slow
    def test_queue_show(self):
        """/queue → 显示当前队列模式"""
        subj = _smtp_send("/queue", "Queue-Show")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Queue mode: ...'")

    @pytest.mark.slow
    def test_queue_set_followup(self):
        """/queue followup → 'Queue mode set to: Followup'"""
        subj = _smtp_send("/queue followup", "Queue-FU")
        logger.info(f"  🔍 主题 [{subj}] → 预期: Followup 模式")

    @pytest.mark.slow
    def test_status(self):
        """/status → 显示状态配置"""
        subj = _smtp_send("/status", "Status")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Status Config'")

    @pytest.mark.slow
    def test_adaptive(self):
        """/adaptive → 'Adaptive routing is not enabled.'"""
        subj = _smtp_send("/adaptive", "Adaptive")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Adaptive routing is not enabled'")

    @pytest.mark.slow
    def test_reset(self):
        """/reset → 'Reset: queue=collect, adaptive=off, history cleared.'"""
        subj = _smtp_send("/reset", "Reset")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 重置确认")

    @pytest.mark.slow
    def test_unknown_command(self):
        """未知命令 → 帮助文本"""
        subj = _smtp_send("/unknowncmd", "Unknown")
        logger.info(f"  🔍 主题 [{subj}] → 预期: 'Unknown command.' 帮助信息")


# ══════════════════════════════════════════════════════════════════════════════
# 人工验证引导
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailManualVerify:
    """打印引导信息，提示用户如何验证测试结果"""

    @pytest.mark.slow
    def test_manual_verify_all(self):
        """所有测试邮件已发送完毕，请去收件箱验证"""
        username = os.environ.get("EMAIL_USERNAME", "your bot email")
        total = _send_count[0]
        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════════╗")
        logger.info(f"║  ✅ 所有测试邮件已发送完毕 ({time.strftime('%H:%M')})               ║")
        logger.info(f"║  请登录 {username} 检查收件箱              ║")
        logger.info("║                                                          ║")
        logger.info(f"║  共发送 {total} 封邮件，按序号排列：                          ║")
        logger.info("║    01-03  Hello / ZH / Long         基本消息              ║")
        logger.info("║    04-10  Session-New / Named / ...  会话命令              ║")
        logger.info("║    11-12  Soul-Show / Soul-Set       Soul 命令             ║")
        logger.info("║    13-18  Queue / Status / Reset     配置命令              ║")
        logger.info("║    19     Unknown                    未知命令帮助          ║")
        logger.info("║                                                          ║")
        logger.info("║  回复主题格式: Re: 前缀-序号                              ║")
        logger.info("║  例如 Re: Hello-01 → 第1封的回复                        ║")
        logger.info("╚══════════════════════════════════════════════════════════════╝")
        logger.info("")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
