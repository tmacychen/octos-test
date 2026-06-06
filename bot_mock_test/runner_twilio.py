#!/usr/bin/env python3
"""
Twilio Test Runner - 封装 Twilio Mock API 调用
"""

import httpx
from base_runner import BaseMockRunner


class TwilioTestRunner(BaseMockRunner):
    """Twilio 测试辅助工具。"""

    def __init__(self, base_url: str = "http://127.0.0.1:5011",
                 webhook_port: int = 8649,
                 auth_token: str = "test_auth_token"):
        super().__init__(base_url)
        self.webhook_port = webhook_port
        self.auth_token = auth_token

    def inject(self, text: str, from_number: str = "+15550000001",
               to_number: str = "+15559999999", message_sid: str = None, **kwargs):
        """注入一条 Twilio SMS 消息到 bot webhook。"""
        payload = {
            "body": text,
            "from_number": from_number,
            "to_number": to_number,
            "webhook_port": self.webhook_port,
            "auth_token": self.auth_token,
        }
        if message_sid:
            payload["message_sid"] = message_sid

        resp = httpx.post(
            f"{self.base_url}/_inject",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
