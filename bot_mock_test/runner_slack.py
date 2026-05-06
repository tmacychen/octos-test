#!/usr/bin/env python3
"""
SlackTestRunner - Slack Mock Server 测试辅助工具

连接已运行的 Slack Mock Server，供 pytest 测试用例使用。
"""

from typing import Optional
import httpx
from base_runner import BaseMockRunner

MOCK_BASE_URL = "http://127.0.0.1:5003"


class SlackTestRunner(BaseMockRunner):
    """Slack Mock Server 测试辅助工具。
    
    提供与 Telegram、Discord、Matrix 一致的接口，
    支持核心消息注入和回复获取。
    """
    
    def __init__(self, base_url: str = MOCK_BASE_URL):
        super().__init__(base_url)
    
    def inject(
        self,
        text: str,
        channel: str = "C012AB3CD",
        user: str = "U012AB3CD",
    ) -> dict:
        """向 Mock Server 注入一条 Slack 消息事件。
        
        模拟 Slack Events API 推送 message 事件到 octos gateway。
        
        Args:
            text: 消息文本内容
            channel: Slack channel ID (e.g., "C012AB3CD")
            user: Slack user ID (e.g., "U012AB3CD")
        
        Returns:
            Mock Server 响应，包含生成的 event
        """
        payload = {
            "text": text,
            "channel": channel,
            "user": user,
        }
        
        resp = httpx.post(f"{self.base_url}/_inject", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json()
    
    def get_stats(self) -> dict:
        """获取 Mock Server 统计信息。"""
        resp = httpx.get(f"{self.base_url}/_stats", timeout=5)
        resp.raise_for_status()
        return resp.json()
