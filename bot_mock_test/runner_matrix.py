#!/usr/bin/env python3
"""
MatrixTestRunner - Matrix Mock Server 测试辅助工具

连接已运行的 Matrix Mock Server，供 pytest 测试用例使用。
预留 Bot 管理和 Swarm Supervisor 接口供未来扩展。
"""

from typing import Optional

import httpx

from base_runner import BaseMockRunner

MOCK_BASE_URL = "http://127.0.0.1:5002"


class MatrixTestRunner(BaseMockRunner):
    """Matrix Mock Server 测试辅助工具。

    提供与 Telegram (BotTestRunner) 和 Discord (DiscordTestRunner)
    一致的接口，支持核心消息注入和回复获取。

    预留接口（未来扩展）：
    - inject_bot_command: Bot 管理命令 (/createbot, /deletebot, /listbots)
    - inject_room_invite: 房间邀请事件
    - set_appservice_endpoint: 设置 Appservice 推送端点
    """

    def __init__(self, base_url: str = MOCK_BASE_URL):
        super().__init__(base_url)

    def inject(
        self,
        text: str,
        room_id: str = "!test:localhost",
        sender: str = "@user:localhost",
        msgtype: str = "m.text",
        formatted_body: Optional[str] = None,
    ) -> dict:
        """向 Mock Server 注入一条 Matrix 消息事件。

        模拟 Homeserver 推送 m.room.message 事件到 Appservice。

        Args:
            text: 消息文本内容
            room_id: Matrix 房间 ID
            sender: 发送者 Matrix 用户 ID
            msgtype: 消息类型 (m.text, m.notice, etc.)
            formatted_body: HTML 格式内容 (可选)

        Returns:
            Mock Server 响应，包含生成的 event
        """
        payload: dict = {
            "text": text,
            "room_id": room_id,
            "sender": sender,
            "msgtype": msgtype,
        }
        if formatted_body:
            payload["formatted_body"] = formatted_body

        resp = httpx.post(f"{self.base_url}/_inject", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def inject_bot_command(
        self,
        command: str,
        room_id: str = "!test:localhost",
        sender: str = "@admin:localhost",
    ) -> dict:
        """注入 Bot 管理命令（预留接口）。

        用于测试 Matrix 特有的 /createbot, /deletebot, /listbots 命令。
        当前为预留实现，未来扩展 Bot 管理测试时使用。

        Args:
            command: Bot 命令文本，如 "/createbot mybot My Bot"
            room_id: Matrix 房间 ID
            sender: 发送者用户 ID（需要是 admin）

        Returns:
            Mock Server 响应
        """
        resp = httpx.post(
            f"{self.base_url}/_inject_bot_command",
            json={
                "command": command,
                "room_id": room_id,
                "sender": sender,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def inject_room_invite(
        self,
        room_id: str = "!test:localhost",
        user_id: str = "@user:localhost",
    ) -> dict:
        """注入房间邀请事件（预留接口）。

        用于测试房间路由和成员管理。
        当前为预留实现，未来扩展房间功能测试时使用。

        Args:
            room_id: Matrix 房间 ID
            user_id: 被邀请的用户 ID

        Returns:
            Mock Server 响应
        """
        resp = httpx.post(
            f"{self.base_url}/_inject_room_invite",
            json={
                "room_id": room_id,
                "user_id": user_id,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def set_appservice_endpoint(self, endpoint: str) -> dict:
        """设置 octos appservice 端点地址。

        配置后，Mock Server 会主动推送事件到该端点
        （模拟 Homeserver → Appservice 的推送）。

        Args:
            endpoint: octos appservice HTTP 端点，
                     如 "http://127.0.0.1:8009"

        Returns:
            Mock Server 响应
        """
        resp = httpx.post(
            f"{self.base_url}/_set_appservice_endpoint",
            json={"endpoint": endpoint},
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json()
