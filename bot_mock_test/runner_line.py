#!/usr/bin/env python3
"""
LINE Test Runner - 封装 LINE Mock API 调用
"""

import httpx
from base_runner import BaseMockRunner


class LineTestRunner(BaseMockRunner):
    """LINE 测试辅助工具。"""

    def __init__(self, base_url: str = "http://127.0.0.1:5007",
                 webhook_port: int = 8647,
                 channel_secret: str = "test_secret"):
        super().__init__(base_url)
        self.webhook_port = webhook_port
        self.channel_secret = channel_secret

    def inject(self, text: str, chat_id: str = "U_test_user",
               username: str = "testuser", **kwargs):
        """注入一条 LINE 文本消息到 bot webhook。"""
        event = {
            "type": "message",
            "replyToken": f"reply_{int(__import__('time').time())}",
            "source": {
                "type": "user",
                "userId": chat_id,
            },
            "message": {
                "type": "text",
                "id": f"msg_{int(__import__('time').time() * 1000)}",
                "text": text,
            },
        }
        payload = {
            "event": event,
            "channel_secret": self.channel_secret,
        }
        resp = httpx.post(
            f"{self.base_url}/_inject?webhook_port={self.webhook_port}",
            json=payload, timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
