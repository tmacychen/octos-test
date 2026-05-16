#!/usr/bin/env python3
"""
WeChatTestRunner - 微信 Mock Server 测试辅助工具

连接已运行的微信 Mock Server，供 pytest 测试用例使用。
"""

from typing import Optional
import httpx
from base_runner import BaseMockRunner

MOCK_BASE_URL = "http://127.0.0.1:5005"


class WeChatTestRunner(BaseMockRunner):
    """微信 Mock Server 测试辅助工具。"""

    def __init__(self, base_url: str = MOCK_BASE_URL):
        super().__init__(base_url)

    def inject(
        self,
        text: str,
        sender: str = "test_user@im.wechat",
    ) -> dict:
        """向 Mock Server 注入一条微信消息事件。

        模拟 wechat-bridge 推送微信消息到 WebSocket。

        Args:
            text: 消息文本内容
            sender: 发送者 ID (e.g., "test_user@im.wechat")

        Returns:
            Mock Server 响应
        """
        payload = {
            "text": text,
            "sender": sender,
        }
        resp = httpx.post(f"{self.base_url}/_inject", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
