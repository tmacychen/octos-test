#!/usr/bin/env python3
"""
EmailTestRunner - 真实邮箱测试辅助工具。

提示：Email 测试使用真实 QQ/163 邮箱，无需 Mock 服务器。
请先在 .env 中配置：
  EMAIL_USERNAME=your_bot@qq.com
  EMAIL_PASSWORD=your_authorization_code
  EMAIL_REAL_TEST=true
"""

import httpx
from base_runner import BaseMockRunner


class EmailTestRunner(BaseMockRunner):
    """Email 测试辅助工具（真实邮箱模式，不使用 Mock 服务器）。"""

    def __init__(self, base_url: str = "http://127.0.0.1:5080"):
        super().__init__(base_url)

    def health(self) -> bool:
        """检查 Mock 服务器是否在线（真实模式总是不可用）。"""
        return False
