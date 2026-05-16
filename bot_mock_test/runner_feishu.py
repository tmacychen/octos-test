#!/usr/bin/env python3
"""
FeishuTestRunner - 飞书 Mock Server 测试辅助工具

连接已运行的飞书 Mock Server，供 pytest 测试用例使用。
"""

from typing import Optional
import httpx
from base_runner import BaseMockRunner

MOCK_BASE_URL = "http://127.0.0.1:5004"


class FeishuTestRunner(BaseMockRunner):
    """飞书 Mock Server 测试辅助工具。"""

    def __init__(self, base_url: str = MOCK_BASE_URL):
        super().__init__(base_url)

    def inject(
        self,
        text: str,
        sender_id: str = "ou_test_user",
        chat_id: str = "oc_test_chat",
        sender_name: str = "Test User",
    ) -> dict:
        """向 Mock Server 注入一条飞书消息事件。

        模拟飞书推送 im.message.receive_v1 webhook 事件。

        Args:
            text: 消息文本内容
            sender_id: 飞书用户 open_id
            chat_id: 飞书群聊/会话 chat_id
            sender_name: 发送者姓名

        Returns:
            Mock Server 响应
        """
        payload = {
            "text": text,
            "sender_id": sender_id,
            "chat_id": chat_id,
            "sender_name": sender_name,
        }
        resp = httpx.post(f"{self.base_url}/_inject", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
