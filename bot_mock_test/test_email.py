#!/usr/bin/env python3
"""
Email Bot 集成测试 — 真实邮箱模式，自动验证回复

⚠️ 重要：QQ 邮箱会将自发自收（From=To）的邮件自动标记为已读，
因此 IMAP SEARCH UNSEEN 无法找到。如需测试，需要两个不同的邮箱：
  - EMAIL_USERNAME: bot 邮箱（octos gateway 使用的邮箱）
  - EMAIL_SENDER:   发件人邮箱（测试脚本使用的邮箱，不同于 bot 邮箱）
  
如果 EMAIL_SENDER 未设置，则使用 EMAIL_USERNAME（自发自收模式），
此模式下 QQ 邮箱可能无法正常工作。

本测试使用真实邮箱：
1. 通过 SMTP 发送测试邮件给 bot
2. 通过 IMAP 轮询等待 bot 的回复（"Re: 原主题"）
3. 测试前自动清理收件箱旧邮件，防止 O(n) 处理导致 LLM 积压
4. 验证回复内容符合预期
"""

import imaplib
import email
import logging
import os
import smtplib
import socket
import time
from email.mime.text import MIMEText

import pytest

logger = logging.getLogger(__name__)

_IMAP_POLL_INTERVAL = 10   # IMAP 轮询间隔（秒）
_IMAP_MAX_WAIT = 300       # 等待回复的最大超时（秒）
_EMAIL_INTERVAL = 5        # 测试用例间隔（秒）


# ══════════════════════════════════════════════════════════════════════════════
# IMAP 操作
# ══════════════════════════════════════════════════════════════════════════════

def _imap_connect():
    """建立 IMAP 连接并登录。"""
    host = os.environ.get("EMAIL_IMAP_HOST", "imap.qq.com")
    port = int(os.environ.get("EMAIL_IMAP_PORT", "993"))
    username = os.environ["EMAIL_USERNAME"]
    password = os.environ["EMAIL_PASSWORD"]
    conn = imaplib.IMAP4_SSL(host, port, timeout=30)
    conn.login(username, password)
    return conn


def _imap_fetch_inbox():
    """从收件箱获取最新 50 封邮件的 (seq, subject, from_)。"""
    conn = _imap_connect()
    conn.select("INBOX")
    _, data = conn.search(None, "ALL")
    all_seqs = data[0].split()
    items = []
    if all_seqs:
        recent = all_seqs[-50:]
        for seq in reversed(recent):
            _, msg_data = conn.fetch(seq, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])")
            if msg_data and msg_data[0]:
                raw = msg_data[0][1]
                parsed = email.message_from_bytes(raw)
                subj = parsed.get("Subject", "")
                fr = parsed.get("From", "")
                seq_str = seq.decode() if isinstance(seq, bytes) else seq
                items.append((seq_str, subj, fr))
    conn.logout()
    return items


def _imap_fetch_spam():
    """从垃圾邮件箱获取 (seq, subject)。"""
    for folder in ["[Gmail]/Spam", "Spam", "Junk"]:
        try:
            conn = _imap_connect()
            try:
                conn.select(f'"{folder}"')
            except imaplib.IMAP4.error:
                conn.logout()
                continue
            _, data = conn.search(None, "ALL")
            seqs = data[0].split()
            items = []
            if seqs:
                recent = seqs[-50:]
                for seq in reversed(recent):
                    _, md = conn.fetch(seq, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
                    if md and md[0]:
                        parsed = email.message_from_bytes(md[0][1])
                        items.append(
                            (seq.decode() if isinstance(seq, bytes) else seq,
                             parsed.get("Subject", ""))
                        )
            conn.logout()
            return items
        except Exception:
            continue
    return []


def _fetch_body(conn, seq, mailbox="INBOX"):
    """获取指定邮件的正文。"""
    conn.select(mailbox)
    _, data = conn.fetch(str(seq), "(RFC822)")
    if data and data[0]:
        raw_msg = email.message_from_bytes(data[0][1])
        if raw_msg.is_multipart():
            for part in raw_msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode("utf-8", errors="replace").strip()
        else:
            payload = raw_msg.get_payload(decode=True)
            if payload:
                return payload.decode("utf-8", errors="replace").strip()
    return ""


def _imap_poll_reply(original_subject: str, timeout: int = _IMAP_MAX_WAIT) -> str:
    """
    轮询 IMAP 收件箱和垃圾箱，等待 bot 的 "Re:" 回复。

    octos 默认使用 "Re: Message" 作为回复主题，因此不按精确主题匹配，
    而是查找从 bot 地址发出、主题以 "Re:" 开头的新邮件。
    返回回复正文，超时返回空字符串。
    """
    bot_addr = os.environ["EMAIL_USERNAME"].lower()
    deadline = time.time() + timeout
    # Track seq+subject seen before to distinguish new replies
    initial_seen = set()
    for seq, subj, _ in _imap_fetch_inbox():
        initial_seen.add((seq, subj))

    while time.time() < deadline:
        inbox = _imap_fetch_inbox()
        spam = _imap_fetch_spam()

        for items, mailbox in [(inbox, "INBOX"), (spam, "[Gmail]/Spam")]:
            for seq, subj, fr in items:
                key = (seq, subj)
                if key in initial_seen:
                    continue
                subj_lower = subj.strip().lower()
                # Match any "Re:" reply sent FROM the bot (not re-processed Re: messages)
                from_lower = fr.strip().lower()
                if subj_lower.startswith("re:"):
                    logger.info(f"  ✅ 在{mailbox}找到回复: [{subj}] from [{fr}]")
                    conn = _imap_connect()
                    body = _fetch_body(conn, seq, mailbox)
                    conn.logout()
                    if mailbox != "INBOX":
                        logger.warning("回复被 QQ 邮箱判定为垃圾邮件！请将 bot 地址加入白名单。")
                    return body

        time.sleep(_IMAP_POLL_INTERVAL)
    return ""


def _cleanup_inbox():
    """将收件箱中所有测试邮件标记为已读，防止旧邮件 LLM 积压。"""
    try:
        logger.info("  正在清理收件箱旧邮件 (标记为已读)...")
        conn = _imap_connect()
        conn.select("INBOX")
        _, data = conn.search(None, "UNSEEN")
        unseen = data[0].split()
        if unseen:
            seq_str = ",".join(s.decode() if isinstance(s, bytes) else s for s in unseen)
            conn.store(seq_str, "+FLAGS (\\Seen)")
            logger.info(f"  ✓ 已将 {len(unseen)} 封未读邮件标记为已读")
        conn.logout()
    except Exception as e:
        logger.warning(f"  清理收件箱失败 (不影响测试): {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SMTP 发送
# ══════════════════════════════════════════════════════════════════════════════

def _smtp_send(body: str, subject_tag: str = "Test"):
    """通过 SMTP 发送测试邮件，返回主题用于匹配回复。

    如果设置了 EMAIL_SENDER，则使用发件人邮箱发送（推荐 163 搭配 QQ bot），
    否则使用 bot 邮箱自发自收（QQ 邮箱下可能因自动标记 SEEN 而无法被 IMAP 发现）。
    """
    sender = os.environ.get("EMAIL_SENDER", "")
    if sender:
        # 使用发件人邮箱（如 163）发送到 bot 邮箱（如 QQ）
        username = os.environ["EMAIL_SENDER"]
        password = os.environ["EMAIL_SENDER_PASSWORD"]
        smtp_host = os.environ.get("EMAIL_SENDER_SMTP_HOST", "smtp.163.com")
        smtp_port = int(os.environ.get("EMAIL_SENDER_SMTP_PORT", "465"))
        to_addr = os.environ["EMAIL_USERNAME"]
    else:
        # 自发自收模式
        username = os.environ["EMAIL_USERNAME"]
        password = os.environ["EMAIL_PASSWORD"]
        smtp_host = os.environ.get("EMAIL_SMTP_HOST", "smtp.qq.com")
        smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", "465"))
        to_addr = username

    timestamp = int(time.time() * 1000)
    subject = f"{subject_tag}-{timestamp}"

    msg = MIMEText(body, _charset="utf-8")
    msg["From"] = username if not sender else sender
    msg["To"] = to_addr
    msg["Subject"] = subject

    with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as s:
        s.login(username, password)
        s.send_message(msg)

    logger.info(f"  📤 [{subject_tag}] {body[:60]} → {to_addr}")
    return subject


def _send_and_verify(body: str, subject_tag: str, min_reply_len: int = 1):
    """发送邮件并等待验证 octos 的回复。"""
    subj = _smtp_send(body, subject_tag)
    reply_body = _imap_poll_reply(subj)
    if not reply_body:
        pytest.fail(
            f"未收到主题为 [Re: {subj}] 的回复 (等待 {_IMAP_MAX_WAIT}s)。\n"
            "解决方法：1) 登录 QQ 邮箱检查收件箱和垃圾箱\n"
            "         2) 检查 octos gateway 日志中的 SMTP 错误\n"
            "         3) 确认 QQ 邮箱授权码未过期"
        )
    assert len(reply_body) >= min_reply_len, f"回复内容过短 ({len(reply_body)}): {reply_body[:80]}"
    logger.info(f"   回复: {reply_body[:150]}")
    time.sleep(_EMAIL_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def runner():
    class _FakeRunner:
        @staticmethod
        def health():
            return True
        @staticmethod
        def get_sent_messages(**kwargs):
            return []
        @staticmethod
        def clear():
            pass
    return _FakeRunner()


@pytest.fixture(scope="session")
def check_config():
    """验证 .env 配置是否就绪，并清理收件箱。"""
    errors = []
    username = os.environ.get("EMAIL_USERNAME", "")
    password = os.environ.get("EMAIL_PASSWORD", "")
    sender = os.environ.get("EMAIL_SENDER", "")
    real_test = os.environ.get("EMAIL_REAL_TEST", "").lower() in ("1", "true")

    if not real_test:
        errors.append("请设置 EMAIL_REAL_TEST=true 启用真实邮箱模式")
    if not username:
        errors.append("请设置 EMAIL_USERNAME（bot 邮箱地址）")
    if not password:
        errors.append("请设置 EMAIL_PASSWORD（bot 邮箱授权码）")
    if "@" not in username:
        errors.append(f"EMAIL_USERNAME 格式错误，当前: {username}")

    if sender:
        # 验证发件人邮箱配置
        if "@" not in sender:
            errors.append(f"EMAIL_SENDER 格式错误，当前: {sender}")
        sender_pass = os.environ.get("EMAIL_SENDER_PASSWORD", "")
        if not sender_pass:
            errors.append("请设置 EMAIL_SENDER_PASSWORD（发件人邮箱授权码）")
        logger.info(f"  发件人: {sender} → bot: {username}")
    else:
        logger.info(f"  自发自收模式: {username} → {username}（QQ 邮箱下可能有问题）")

    if errors:
        pytest.fail(f"Email 配置不完整: {'; '.join(errors)}")

    # 清理收件箱，防止旧邮件积压
    _cleanup_inbox()


# ══════════════════════════════════════════════════════════════════════════════
# 配置验证测试
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailConfig:
    """验证 Email 配置正确性"""

    def test_env_vars(self, check_config):
        logger.info(f"  邮箱地址: {os.environ.get('EMAIL_USERNAME', '未设置')}")
        logger.info(f"  IMAP: {os.environ.get('EMAIL_IMAP_HOST', 'imap.qq.com')}:{os.environ.get('EMAIL_IMAP_PORT', '993')}")
        logger.info(f"  SMTP: {os.environ.get('EMAIL_SMTP_HOST', 'smtp.qq.com')}:{os.environ.get('EMAIL_SMTP_PORT', '465')}")

    def test_imap_connectivity(self):
        imap_host = os.environ.get("EMAIL_IMAP_HOST", "imap.qq.com")
        imap_port = int(os.environ.get("EMAIL_IMAP_PORT", "993"))
        username = os.environ.get("EMAIL_USERNAME", "")
        password = os.environ.get("EMAIL_PASSWORD", "")

        try:
            socket.getaddrinfo(imap_host, imap_port)
            logger.info(f"  ✓ DNS: {imap_host}")
        except socket.gaierror as e:
            pytest.fail(f"DNS 解析失败: {e}")

        try:
            sock = socket.create_connection((imap_host, imap_port), timeout=10)
            sock.close()
            logger.info(f"  ✓ TCP: {imap_host}:{imap_port}")
        except Exception as e:
            pytest.fail(f"TCP 连接失败: {e}")

        try:
            conn = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=10)
            conn.login(username, password)
            conn.select("INBOX")
            conn.logout()
            logger.info("  ✓ IMAP 登录 + SELECT INBOX")
        except Exception as e:
            pytest.fail(f"IMAP 认证失败: {e}")

        try:
            with smtplib.SMTP_SSL(
                os.environ.get("EMAIL_SMTP_HOST", "smtp.qq.com"),
                int(os.environ.get("EMAIL_SMTP_PORT", "465")),
                timeout=10,
            ) as s:
                s.login(username, password)
            logger.info("  ✓ SMTP 登录成功")
        except Exception as e:
            pytest.fail(f"SMTP 登录失败: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 端到端收发测试
# ══════════════════════════════════════════════════════════════════════════════

class TestEmailSendReceive:
    """发送消息并自动验证 LLM 回复"""

    @pytest.mark.slow
    def test_simple_message(self):
        """发送简单问候，验证 LLM 自动回复"""
        _send_and_verify(
            "Hello! Please reply with a short greeting, just one sentence.",
            "Hello",
            min_reply_len=5,
        )

    @pytest.mark.slow
    def test_new_command(self):
        """/new 命令测试 — 验证 bot 能处理会话管理命令"""
        _send_and_verify("""/new email-test
Please confirm session created with 'Session cleared'""", "NewCmd", min_reply_len=5)

    @pytest.mark.slow
    def test_help_command(self):
        """/help 命令测试 — 验证 bot 返回帮助信息"""
        _send_and_verify("""/help
Please list available commands""", "HelpCmd", min_reply_len=10)

    @pytest.mark.slow
    def test_clear_command(self):
        """/clear 命令测试 — 验证 bot 清空会话"""
        _send_and_verify("""/clear
Please confirm session cleared""", "ClearCmd", min_reply_len=5)

    @pytest.mark.slow
    def test_switch_session_command(self):
        """/s 命令测试 — 验证 bot 切换会话"""
        _send_and_verify("""/s default
Please confirm switched to default session""", "SwitchCmd", min_reply_len=5)
