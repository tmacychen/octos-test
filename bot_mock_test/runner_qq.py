#!/usr/bin/env python3
"""
QQ Bot Test Runner - QQ Bot Mock Server 测试辅助工具

连接已运行的 QQ Bot Mock Server，供 pytest 测试用例使用。
"""

from typing import Optional
import httpx
from base_runner import BaseMockRunner

MOCK_BASE_URL = "http://127.0.0.1:5010"


class QqTestRunner(BaseMockRunner):
    """QQ Bot Mock Server 测试辅助工具。"""

    def __init__(self, base_url: str = MOCK_BASE_URL):
        super().__init__(base_url)

    def inject(
        self,
        text: str,
        group_openid: str = "group_test_001",
        member_openid: str = "member_test_001",
        user_openid: Optional[str] = None,
        event_type: str = "GROUP_AT_MESSAGE_CREATE",
        message_id: Optional[str] = None,
    ) -> dict:
        """向 Mock Server 注入一条 QQ Bot 消息事件。

        Args:
            text: 消息文本内容
            group_openid: 群的 openid（群消息场景）
            member_openid: 群成员的 openid（群消息场景）
            user_openid: 用户 openid（C2C 私聊场景）
            event_type: 事件类型，默认 GROUP_AT_MESSAGE_CREATE
            message_id: 可选消息 ID（用于去重测试）
        """
        payload = {
            "text": text,
            "group_openid": group_openid,
            "member_openid": member_openid,
            "event_type": event_type,
        }
        if user_openid:
            payload["user_openid"] = user_openid
        if message_id:
            payload["message_id"] = message_id

        resp = httpx.post(f"{self.base_url}/_inject", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def get_stats(self) -> dict:
        """获取 Mock Server 统计信息。"""
        resp = httpx.get(f"{self.base_url}/_stats", timeout=5)
        resp.raise_for_status()
        return resp.json()
