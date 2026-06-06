#!/usr/bin/env python3
"""
WeComTestRunner - WeCom Channel Mock Server 测试辅助工具
"""

from typing import Optional
import httpx
from base_runner import BaseMockRunner

MOCK_BASE_URL = "http://127.0.0.1:5009"


class WeComTestRunner(BaseMockRunner):
    """WeCom Channel Mock Server 测试辅助工具。"""

    def __init__(self, base_url: str = MOCK_BASE_URL):
        super().__init__(base_url)

    def inject(
        self,
        text: str,
        sender: str = "test_user",
        webhook_url: str = "http://127.0.0.1:9323/wecom/webhook",
    ) -> dict:
        """向 Mock Server 注入一条 WeCom 消息事件。

        Mock Server 会将消息 AES 加密后 POST 到 octos 的 webhook 端点。

        Args:
            text: 消息文本内容
            sender: 发送者用户 ID (FromUserName)
            webhook_url: octos wecom webhook URL

        Returns:
            Mock Server 响应
        """
        payload = {
            "text": text,
            "sender": sender,
            "webhook_url": webhook_url,
        }
        resp = httpx.post(f"{self.base_url}/_inject", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_sent_messages(self, timeout: int = 10) -> list:
        """获取 bot 通过 WeCom REST API 发送的消息。

        Returns list of dicts with "text" field for BaseMockRunner compatibility.
        """
        resp = httpx.get(f"{self.base_url}/_sent_messages", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("messages", [])

    def get_messages_list(self) -> list:
        """获取 bot 消息列表。"""
        return self.get_sent_messages()

    def get_server_config(self) -> dict:
        """获取 Mock Server 的配置信息（crypto keys etc）。"""
        resp = httpx.get(f"{self.base_url}/_config", timeout=10)
        resp.raise_for_status()
        return resp.json()
