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
               username: str = "testuser", message_id: str = None, **kwargs):
        """注入一条 LINE 文本消息到 bot webhook。"""
        msg_id = message_id or f"msg_{int(__import__('time').time() * 1000)}"
        event = {
            "type": "message",
            "replyToken": f"reply_{int(__import__('time').time())}",
            "source": {
                "type": "user",
                "userId": chat_id,
            },
            "message": {
                "type": "text",
                "id": msg_id,
                "text": text,
            },
        }
        return self._post_event(event)

    def inject_event(self, event_data: dict = None, chat_id: str = "U_test_user",
                     source_type: str = "user", group_id: str = None,
                     message_type: str = "text", message_body: dict = None,
                     reply_token: str = None):
        """注入任意类型的 LINE 事件（媒体消息、群组 @提及 等）。

        Args:
            event_data: 完整事件字典（若提供则忽略其他参数）
            chat_id: 用户ID
            source_type: 来源类型 (user/group/room)
            group_id: 群组ID (source_type=group 时)
            message_type: 消息类型 (image/audio/video/file/location/sticker/text)
            message_body: 消息体字段
            reply_token: 可选，不传则自动生成
        """
        if event_data:
            return self._post_event(event_data)

        msg_id = f"msg_{int(__import__('time').time() * 1000)}"
        source = {"type": source_type, "userId": chat_id}
        if source_type == "group":
            source["groupId"] = group_id or f"G_test_group_{chat_id}"
        elif source_type == "room":
            source["roomId"] = group_id or f"R_test_room_{chat_id}"

        event = {
            "type": "message",
            "replyToken": reply_token or f"reply_{int(__import__('time').time())}",
            "source": source,
            "message": {"id": msg_id, "type": message_type, **(message_body or {})},
        }
        return self._post_event(event)

    def _post_event(self, event: dict) -> dict:
        """向 mock server 发送事件，由 mock 转发到 bot webhook。"""
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
