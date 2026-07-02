#!/usr/bin/env python3
"""
BaseMockRunner - Mock Server 测试辅助工具的基类。

提供与 Mock Server 交互的通用方法：
  - get_sent_messages: 获取 bot 已发送的所有消息
  - wait_for_reply: 等待 bot 发送新消息
  - health: 检查 Mock Server 是否在线
"""

import time
from typing import Optional

import httpx


class BaseMockRunner:
    """连接已运行的 Mock Server，提供测试辅助方法的基类。"""

    def __init__(self, base_url: str):
        self.base_url = base_url

    def get_sent_messages(self, timeout: int = 10) -> list[dict]:
        """获取 bot 已发送的所有消息
        
        Args:
            timeout: HTTP 请求超时时间（秒），默认 10s
        """
        resp = httpx.get(f"{self.base_url}/_sent_messages", timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def wait_for_reply(self, count_before: int = 0,
                       timeout: int = 10, poll_interval: float = 0.5,
                       chat_id: Optional[str] = None) -> Optional[dict]:
        """
        等待 bot 发送新消息，返回最新一条。
        count_before: 调用前已有的消息数量
        timeout: 最长等待秒数
        poll_interval: 轮询间隔秒数（默认 0.5s）
        chat_id: 可选，chat_id/channel_id/room_id 用于过滤
        """
        # 构建所有可能匹配的 chat_id 变体，适配各平台 ID 格式差异
        # WhatsApp: bot 可能发送纯号码而非完整 JID
        # Discord/Matrix: 完整 ID 也可能被截断
        _chat_id_variants: list[str] = []
        if chat_id is not None:
            _chat_id_variants.append(chat_id)
            # 如果 chat_id 包含 @ 符号（如 JID 格式），也尝试本地部分
            if "@" in chat_id:
                local_part = chat_id.split("@")[0]
                if local_part and local_part != chat_id:
                    _chat_id_variants.append(local_part)

        try:
            msgs = self.get_sent_messages(timeout=5)
        except httpx.HTTPError:
            msgs = []
        if len(msgs) > count_before:
            if _chat_id_variants:
                for msg in reversed(msgs[count_before:]):
                    if self._match_chat_id(msg, _chat_id_variants):
                        return msg
            else:
                return msgs[-1]

        elapsed = 0.0
        while elapsed < timeout:
            time.sleep(poll_interval)
            elapsed += poll_interval
            try:
                msgs = self.get_sent_messages(timeout=5)
            except httpx.HTTPError:
                continue
            if len(msgs) > count_before:
                if _chat_id_variants:
                    for msg in reversed(msgs[count_before:]):
                        if self._match_chat_id(msg, _chat_id_variants):
                            return msg
                else:
                    return msgs[-1]
        return None

    @staticmethod
    def _match_chat_id(msg: dict, variants: list[str]) -> bool:
        """检查消息是否匹配任一 chat_id 变体。

        检查字段: chat_id, channel_id, room_id, channel, to, sender, chatid
        """
        for field in ("chat_id", "channel_id", "room_id", "channel",
                      "to", "sender", "chatid"):
            val = msg.get(field)
            if val is not None:
                val_str = str(val)
                for variant in variants:
                    if val_str == variant:
                        return True
        return False

    def health(self) -> bool:
        """检查 Mock Server 是否在线"""
        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False

    def clear(self) -> None:
        """清除 Mock Server 中存储的所有消息和状态"""
        resp = httpx.post(f"{self.base_url}/_clear", timeout=5)
        resp.raise_for_status()

    def disconnect_ws(self) -> dict:
        """断开所有 WebSocket 连接，模拟网络断线。

        Returns:
            包含断开连接数量的字典。
        """
        resp = httpx.post(f"{self.base_url}/_ws_disconnect", timeout=5)
        resp.raise_for_status()
        return resp.json()
