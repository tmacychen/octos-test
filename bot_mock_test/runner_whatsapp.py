#!/usr/bin/env python3
"""
WhatsAppTestRunner - WhatsApp Mock Server 测试辅助工具

连接已运行的 WhatsApp Mock Server，供 pytest 测试用例使用。
"""

from typing import Optional
import httpx
from base_runner import BaseMockRunner

MOCK_BASE_URL = "http://127.0.0.1:5006"


class WhatsAppTestRunner(BaseMockRunner):
    """WhatsApp Mock Server 测试辅助工具。"""

    def __init__(self, base_url: str = MOCK_BASE_URL):
        super().__init__(base_url)

    def inject(
        self,
        text: str,
        sender: str = "test_user@s.whatsapp.net",
        chat_id: Optional[str] = None,
        message_type: str = "message",
        message_id: Optional[str] = None,
    ) -> dict:
        """向 Mock Server 注入一条 WhatsApp 消息事件。

        模拟 whatsapp-bridge 推送 WhatsApp 消息到 WebSocket。

        Args:
            text: 消息文本内容
            sender: 发送者 JID (e.g., "1234567890@s.whatsapp.net")
            chat_id: 聊天 ID，默认使用 sender 的 phone 部分
            message_type: 消息类型 ("message", "image", "audio")
            message_id: 可选消息 ID（用于去重测试）

        Returns:
            Mock Server 响应
        """
        payload = {
            "text": text,
            "sender": sender,
            "message_type": message_type,
        }
        if chat_id:
            payload["chat_id"] = chat_id
        if message_id:
            payload["message_id"] = message_id

        resp = httpx.post(f"{self.base_url}/_inject", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
