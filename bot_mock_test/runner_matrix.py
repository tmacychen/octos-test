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
        """注入 Bot 管理命令。

        用于测试 Matrix 特有的 /createbot, /deletebot, /listbots 命令。
        命令会作为普通消息事件注入，由 octos 的 handle_slash_command 处理。

        Args:
            command: Bot 命令文本，如 "/createbot mybot My Bot"
            room_id: Matrix 房间 ID
            sender: 发送者用户 ID（需要是 admin）

        Returns:
            Mock Server 响应，包含 txn_id 和注入状态
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
        inviter: str = "@bot:localhost",
        push_event: bool = False,
    ) -> dict:
        """注入房间邀请事件。

        用于测试房间路由和成员管理。更新房间成员列表，
        可选地推送 m.room.member invite 事件到 octos。

        Args:
            room_id: Matrix 房间 ID
            user_id: 被邀请的用户 ID
            inviter: 邀请者用户 ID（默认 bot）
            push_event: 是否推送事件到 octos（默认 False）

        Returns:
            Mock Server 响应，包含房间成员列表
        """
        resp = httpx.post(
            f"{self.base_url}/_inject_room_invite",
            json={
                "room_id": room_id,
                "user_id": user_id,
                "inviter": inviter,
                "push_event": push_event,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def inject_swarm_event(
        self,
        session_id: str = "test-session",
        agent_label: str = "claude-code",
        event_type: str = "progress",
        event_data: Optional[dict] = None,
        room_id: Optional[str] = None,
    ) -> dict:
        """注入 Swarm Harness 事件（M7.3 Supervisor 功能）。

        模拟子代理向 swarm 房间发送类型化事件，测试 route_subagent_event 功能。

        Args:
            session_id: Swarm 会话 ID
            agent_label: 子代理标签（如 "claude-code", "gpt-helper"）
            event_type: 事件类型（progress, error, complete, etc.）
            event_data: 事件数据字典，默认为 progress 示例
            room_id: Swarm 房间 ID，默认为 "!swarm_{session_id}:localhost"

        Returns:
            Mock Server 响应，包含 event_id 和 puppet_user_id
        """
        if event_data is None:
            event_data = {
                "phase": "fetch_sources",
                "message": "Fetching data...",
                "progress": 0.5,
            }

        if room_id is None:
            room_id = f"!swarm_{session_id}:localhost"

        resp = httpx.post(
            f"{self.base_url}/_inject_swarm_event",
            json={
                "session_id": session_id,
                "agent_label": agent_label,
                "event_type": event_type,
                "event_data": event_data,
                "room_id": room_id,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def inject_supervisor_reply(
        self,
        message: str,
        room_id: str = "!swarm_test:localhost",
        sender: str = "@alice:localhost",
        target_puppet: str = "",
    ) -> dict:
        """注入 Supervisor 回复（M7.3 Supervisor 功能）。

        模拟人类 supervisor 在 swarm 房间中回复特定 puppet，
        测试 handle_supervisor_reply 功能。

        Args:
            message: 回复消息内容
            room_id: Swarm 房间 ID
            sender: Supervisor 用户 ID
            target_puppet: 目标 puppet（可选），会自动添加 @mention

        Returns:
            Mock Server 响应，包含 txn_id 和目标 puppet
        """
        resp = httpx.post(
            f"{self.base_url}/_inject_supervisor_reply",
            json={
                "message": message,
                "room_id": room_id,
                "sender": sender,
                "target_puppet": target_puppet,
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
