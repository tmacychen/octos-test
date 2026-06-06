#!/usr/bin/env python3
"""
WeComBotTestRunner - WeCom Bot Mock Server 测试辅助工具

连接已运行的 WeCom Bot Mock Server，供 pytest 测试用例使用。
"""

from typing import Optional
import httpx
from base_runner import BaseMockRunner

MOCK_BASE_URL = "http://127.0.0.1:5008"


class WeComBotTestRunner(BaseMockRunner):
    """WeCom Bot Mock Server 测试辅助工具。"""

    def __init__(self, base_url: str = MOCK_BASE_URL):
        super().__init__(base_url)

    def inject(
        self,
        text: str,
        sender: str = "test_user",
        chatid: str = "test_group",
        msgtype: str = "text",
        chattype: str = "group",
        message_id: Optional[str] = None,
    ) -> dict:
        """向 Mock Server 注入一条 WeCom Bot 消息事件。

        模拟 WeCom 服务器通过 WebSocket 推送 aibot_msg_callback 帧。

        Args:
            text: 消息文本内容
            sender: 发送者用户 ID
            chatid: 群聊 ID
            msgtype: 消息类型 (text/mixed/image/etc)
            chattype: 聊天类型 (group/single)
            message_id: 可选消息 ID（用于去重测试）

        Returns:
            Mock Server 响应
        """
        payload = {
            "text": text,
            "sender": sender,
            "chatid": chatid,
            "msgtype": msgtype,
            "chattype": chattype,
        }
        if message_id:
            payload["message_id"] = message_id
        resp = httpx.post(f"{self.base_url}/_inject", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_sent_messages(self, timeout: int = 10) -> list:
        """获取 bot 发送的所有消息。

        Returns send_messages list for BaseMockRunner compatibility.
        Each message has a "text" field.
        """
        resp = httpx.get(f"{self.base_url}/_sent_messages", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("send_messages", [])

    def get_subscribe_state(self) -> dict:
        """获取订阅状态。"""
        resp = httpx.get(f"{self.base_url}/_subscribe_state", timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_send_messages(self) -> list:
        """获取 bot 通过 aibot_send_msg 发送的回复消息。"""
        return self.get_sent_messages()

    def get_stream_chunks(self) -> list:
        """获取 bot 通过 aibot_respond_msg 发送的流式回复片段。"""
        resp = httpx.get(f"{self.base_url}/_sent_messages", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("stream_chunks", [])
