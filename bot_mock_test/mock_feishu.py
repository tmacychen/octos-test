#!/usr/bin/env python3
"""
飞书 Mock Server - FastAPI 实现，模拟飞书 Webhook 模式 API

模拟飞书开放平台 REST API，用于测试 octos 飞书 Bot 集成。

端口: 5004 (默认)
端点:
  - POST /auth/v3/tenant_access_token/internal - 获取 tenant access token
  - POST /im/v1/messages - 发送消息
  - POST /im/v1/messages/{id}/reply - 回复消息
  - PATCH /im/v1/messages/{id} - 编辑消息
  - DELETE /im/v1/messages/{id} - 删除消息
  - GET /health - 健康检查
  - POST /_inject - 注入测试事件（模拟飞书推送消息事件）
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态
"""

import time
import uuid
import sys
import logging
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, HTTPException
from starlette.requests import Request
from fastapi.responses import JSONResponse
import uvicorn

logger = logging.getLogger("mock_feishu")

FEISHU_APP_ID = "cli_test_app_id"
FEISHU_APP_SECRET = "test_app_secret"


class MockFeishuServer:
    """Mock Feishu server with FastAPI REST API."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5004):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []
        self._injected_events: list[dict] = []
        self._access_tokens: list[dict] = []
        self._token_counter = 0

        self.app = FastAPI(title="Feishu Mock Server")
        self._setup_routes()

    def _generate_message_id(self) -> str:
        return f"om_{uuid.uuid4().hex[:24]}"

    def _generate_token(self) -> str:
        self._token_counter += 1
        return f"test_tenant_access_token_{self._token_counter}"

    def _setup_routes(self):
        app = self.app

        @app.get("/health")
        async def health():
            """Health check endpoint."""
            return JSONResponse({
                "status": "ok",
                "service": "feishu-mock-server",
            })

        @app.post("/auth/v3/tenant_access_token/internal")
        async def get_tenant_access_token(request: Request):
            """
            飞书 API: 获取 tenant_access_token。

            octos 用 app_id + app_secret 换取 token。
            """
            try:
                body = await request.json()
                app_id = body.get("app_id", "")
                app_secret = body.get("app_secret", "")

                logger.info(f"🔑 Token request: app_id={app_id}")

                if app_id != FEISHU_APP_ID or app_secret != FEISHU_APP_SECRET:
                    logger.warning(f"⚠ Invalid credentials: app_id={app_id}")
                    return JSONResponse({
                        "code": 99991663,
                        "msg": "app id or secret is invalid",
                    }, status_code=200)

                token = self._generate_token()
                expire = int(time.time()) + 7200
                self._access_tokens.append({
                    "token": token,
                    "expire": expire,
                    "app_id": app_id,
                })

                logger.info(f"✅ Token issued: {token[:20]}...")
                return JSONResponse({
                    "code": 0,
                    "msg": "ok",
                    "tenant_access_token": token,
                    "expire": 7200,
                })

            except Exception as e:
                logger.error(f"❌ Error in token endpoint: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/im/v1/messages")
        async def send_message(request: Request):
            """
            飞书 API: 发送消息。

            octos 通过此接口发送 bot 回复。
            """
            try:
                auth = request.headers.get("authorization", "")
                logger.info(f"🔑 send_message - Authorization: {auth[:30] if auth else 'MISSING'}...")

                body = await request.json()
                receive_id = body.get("receive_id", "")
                msg_type = body.get("msg_type", "text")
                content = body.get("content", "{}")

                # 记录消息
                message_id = self._generate_message_id()
                record = {
                    "message_id": message_id,
                    "chat_id": receive_id,
                    "receive_id": receive_id,
                    "msg_type": msg_type,
                    "content": content,
                    "timestamp": time.time(),
                }
                self._sent_messages.append(record)

                logger.info(f"💬 Bot sent message to receive_id={receive_id}: {content[:80]}")

                return JSONResponse({
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "message_id": message_id,
                        "root_id": "",
                        "parent_id": "",
                        "msg_type": msg_type,
                        "create_time": str(int(time.time() * 1000)),
                        "update_time": "",
                        "content": content,
                        "sender": {
                            "id": "ou_bot_user_id",
                            "id_type": "open_id",
                        },
                        "body": {
                            "content": content,
                        },
                    },
                })

            except Exception as e:
                logger.error(f"❌ Error in send_message: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/im/v1/messages/{message_id}/reply")
        async def reply_message(message_id: str, request: Request):
            """
            飞书 API: 回复消息。
            """
            try:
                body = await request.json()
                content = body.get("content", "{}")
                msg_type = body.get("msg_type", "text")

                # 从被回复的消息中查找 chat_id
                reply_chat_id = "oc_unknown"
                for prev in self._sent_messages:
                    if prev.get("message_id") == message_id:
                        reply_chat_id = prev.get("chat_id", "oc_unknown")
                        break
                record = {
                    "message_id": f"om_{uuid.uuid4().hex[:24]}",
                    "chat_id": reply_chat_id,
                    "reply_to": message_id,
                    "msg_type": msg_type,
                    "content": content,
                    "timestamp": time.time(),
                }
                self._sent_messages.append(record)

                logger.info(f"💬 Bot replied to {message_id}: {content[:80]}")

                return JSONResponse({
                    "code": 0,
                    "msg": "ok",
                    "data": {
                        "message_id": record["message_id"],
                    },
                })

            except Exception as e:
                logger.error(f"❌ Error in reply_message: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.patch("/im/v1/messages/{message_id}")
        async def edit_message(message_id: str, request: Request):
            """飞书 API: 编辑消息。"""
            try:
                body = await request.json()
                content = body.get("content", "{}")

                # 找到并更新消息
                for msg in self._sent_messages:
                    if msg.get("message_id") == message_id:
                        msg["content"] = content
                        msg["edited"] = True
                        break

                logger.info(f"✏️ Bot edited message {message_id}")

                return JSONResponse({
                    "code": 0,
                    "msg": "ok",
                    "data": {},
                })

            except Exception as e:
                logger.error(f"❌ Error in edit_message: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.delete("/im/v1/messages/{message_id}")
        async def delete_message(message_id: str):
            """飞书 API: 撤回消息。"""
            logger.info(f"🗑 Bot deleted message {message_id}")
            return JSONResponse({
                "code": 0,
                "msg": "ok",
                "data": {},
            })

        @app.get("/im/v1/messages/{message_id}")
        async def get_message(message_id: str):
            """飞书 API: 获取消息详情。"""
            for msg in self._sent_messages:
                if msg.get("message_id") == message_id:
                    return JSONResponse({
                        "code": 0,
                        "msg": "ok",
                        "data": {
                            "message_id": message_id,
                            "msg_type": msg["msg_type"],
                            "content": msg["content"],
                        },
                    })
            return JSONResponse({
                "code": 99999999,
                "msg": "message not found",
            }, status_code=200)

        @app.post("/_inject")
        async def inject_event(request: Request):
            """
            注入测试事件——模拟飞书推送 im.message.receive_v1 webhook 事件。
            """
            try:
                body = await request.json()
                text = body.get("text", "")
                sender_id = body.get("sender_id", "ou_test_user")
                chat_id = body.get("chat_id", "oc_test_chat")
                sender_name = body.get("sender_name", "Test User")

                message_id = f"om_{uuid.uuid4().hex[:24]}"
                event = {
                    "schema": "2.0",
                    "header": {
                        "app_id": FEISHU_APP_ID,
                        "event_type": "im.message.receive_v1",
                        "tenant_key": "test_tenant",
                        "token": "test_event_token",
                    },
                    "event": {
                        "sender": {
                            "sender_id": {
                                "open_id": sender_id,
                                "union_id": f"uu_{uuid.uuid4().hex[:16]}",
                                "user_id": sender_id,
                            },
                        },
                        "message": {
                            "chat_id": chat_id,
                            "chat_type": "group",
                            "content": f'{{"text":"{text}"}}',
                            "message_id": message_id,
                            "message_type": "text",
                            "create_time": str(int(time.time() * 1000)),
                        },
                    },
                }

                self._injected_events.append(event)
                logger.info(f"🔔 Injected Feishu event: chat_id={chat_id}, text={text[:50]}")

                # 将事件转发到 octos 的飞书 webhook 端点
                import httpx as _httpx
                try:
                    forward_url = "http://127.0.0.1:9321/webhook/event"
                    async with _httpx.AsyncClient(timeout=5) as client:
                        fwd_resp = await client.post(forward_url, json=event)
                        logger.info(f"📤 Forwarded event to octos webhook: {forward_url} → {fwd_resp.status_code}")
                except Exception as e:
                    logger.warning(f"⚠ Failed to forward event to octos webhook: {e}")

                return JSONResponse({
                    "success": True,
                    "event": event,
                    "note": "Feishu webhook event generated and forwarded to octos"
                })

            except Exception as e:
                logger.error(f"❌ Error injecting event: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/_sent_messages")
        async def get_sent_messages():
            """获取 bot 已发送的所有消息。"""
            return JSONResponse(self._sent_messages)

        @app.post("/_clear")
        async def clear_state():
            """清理所有状态。"""
            self._sent_messages.clear()
            self._injected_events.clear()
            self._access_tokens.clear()
            self._token_counter = 0
            logger.info("🗑 Cleared all mock server state")
            return JSONResponse({"success": True})

    def start_background(self, log_file=None):
        """在后台线程启动服务器。"""
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(formatter)
            stdout_handler.setLevel(logging.INFO)

            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            root_logger.addHandler(stdout_handler)
            root_logger.setLevel(logging.INFO)

        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
        )


if __name__ == "__main__":
    server = MockFeishuServer(port=5004)
    server.start_background()
