#!/usr/bin/env python3
"""
WeCom Bot Mock Server - FastAPI + WebSocket 实现

模拟 WeCom 企业微信群机器人的 WebSocket 协议，用于测试 octos wecom-bot 集成。

协议:
  连接 → aibot_subscribe → ACK → ping(30s) ↔ pong
  注入 → aibot_msg_callback → 发送回复

端口: 5008 (默认)
端点:
  - GET /health - 健康检查
  - POST /_inject - 注入测试事件（通过 WebSocket 推送 aibot_msg_callback 帧）
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态
"""

import time
import uuid
import sys
import json
import logging
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from starlette.websockets import WebSocketState
from starlette.requests import Request

logger = logging.getLogger("mock_wecom_bot")


class MockWeComBotServer:
    """Mock WeCom Bot server with FastAPI and WebSocket."""

    def __init__(self, host: str = "127.0.0.1", port: int = 5008):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []       # aibot_send_msg frames
        self._stream_chunks: list[dict] = []         # aibot_respond_msg frames
        self._injected_events: list[dict] = []
        self._ws_connections: list[WebSocket] = []
        self._subscribed = False                     # Track subscription state

        self.app = FastAPI(title="WeCom Bot Mock Server")
        self._setup_routes()

    def _generate_message_id(self) -> str:
        return f"mock_msg_{uuid.uuid4().hex[:16]}"

    def _generate_req_id(self) -> str:
        return f"req_{uuid.uuid4().hex[:24]}"

    async def _broadcast_to_websockets(self, message: dict):
        """Broadcast message to all connected WebSocket clients."""
        disconnected = []
        for ws in self._ws_connections:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps(message))
                    logger.info(f"📤 Sent via WebSocket: {message.get('cmd', message.get('type', 'unknown'))}")
            except Exception as e:
                logger.error(f"Failed to send to WebSocket: {e}")
                disconnected.append(ws)

        for ws in disconnected:
            if ws in self._ws_connections:
                self._ws_connections.remove(ws)

    def _setup_routes(self):
        app = self.app

        @app.get("/health")
        async def health():
            """Health check endpoint."""
            return JSONResponse({
                "status": "ok",
                "service": "wecom-bot-mock-server",
                "ws_connections": len(self._ws_connections),
                "subscribed": self._subscribed,
                "sent_messages": len(self._sent_messages),
            })

        @app.post("/_inject")
        async def inject_event(request: Request):
            """
            Inject a test event — simulate WeCom pushing a message to the bot.

            Body:
            {
                "text": "hello world",          # required
                "sender": "user123",             # optional, default "test_user"
                "chatid": "group_abc",           # optional, default "test_group"
                "msgtype": "text",               # optional, default "text"
                "chattype": "group"              # optional, default "group"
            }
            """
            import json as _json
            try:
                raw = await request.body()
                body = _json.loads(raw)
                text = body.get("text", "")
                sender = body.get("sender", "test_user")
                chatid = body.get("chatid", "test_group")
                msgtype = body.get("msgtype", "text")
                chattype = body.get("chattype", "group")

                req_id = self._generate_req_id()

                event = {
                    "cmd": "aibot_msg_callback",
                    "headers": {
                        "req_id": req_id,
                    },
                    "body": {
                        "msgid": self._generate_message_id(),
                        "msgtype": msgtype,
                        "chatid": chatid,
                        "chattype": chattype,
                        "from": {"userid": sender},
                        "text": {"content": text},
                    }
                }

                self._injected_events.append(event)
                logger.info(f"🔔 Injected WeCom Bot event: sender={sender}, text={text[:50]}")

                # Push via WebSocket
                await self._broadcast_to_websockets(event)

                return JSONResponse({
                    "success": True,
                    "event": event,
                    "note": "Event injected and broadcast via WebSocket"
                })

            except Exception as e:
                logger.error(f"Error injecting event: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/_sent_messages")
        async def get_sent_messages():
            """Get all messages sent by the bot via aibot_send_msg."""
            return JSONResponse({
                "send_messages": self._sent_messages,
                "stream_chunks": self._stream_chunks,
                "total": len(self._sent_messages) + len(self._stream_chunks),
            })

        @app.post("/_clear")
        async def clear_state():
            """Clear message state (preserve WebSocket connections and subscription)."""
            self._sent_messages.clear()
            self._stream_chunks.clear()
            self._injected_events.clear()
            # Do NOT reset _subscribed — WebSocket connections are preserved
            # and octos won't re-subscribe after a cleared state.
            logger.info("Cleared mock server message state (preserved WS + subscription)")
            return JSONResponse({"success": True})

        @app.get("/_subscribe_state")
        async def get_subscribe_state():
            """Get current subscription state."""
            return JSONResponse({
                "subscribed": self._subscribed,
                "ws_connections": len(self._ws_connections),
            })

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """
            WeCom Bot WebSocket endpoint.

            octos 连接到这里进行订阅和消息收发。
            """
            await websocket.accept()
            self._ws_connections.append(websocket)
            self._subscribed = False
            logger.info(f"WebSocket client connected. Total: {len(self._ws_connections)}")

            try:
                while True:
                    data = await websocket.receive_text()
                    try:
                        msg = json.loads(data)
                        cmd = msg.get("cmd", "")

                        if cmd == "aibot_subscribe":
                            # Verify credentials
                            body = msg.get("body", {})
                            bot_id = body.get("bot_id", "")
                            secret = body.get("secret", "")
                            logger.info(f"🔑 Subscribe request: bot_id={bot_id}, secret={'*' * len(secret)}")

                            # Accept any non-empty credentials for mock
                            if bot_id and secret:
                                self._subscribed = True
                                ack = {"errcode": 0, "errmsg": "ok"}
                                await websocket.send_text(json.dumps(ack))
                                logger.info("✅ Subscribe ACK sent")
                            else:
                                ack = {"errcode": 400, "errmsg": "invalid bot_id or secret"}
                                await websocket.send_text(json.dumps(ack))
                                logger.warning("❌ Subscribe rejected: missing credentials")

                        elif cmd == "ping":
                            # Respond to ping with pong
                            pong = {
                                "cmd": "pong",
                                "headers": msg.get("headers", {}),
                            }
                            await websocket.send_text(json.dumps(pong))
                            logger.debug("🏓 Pong sent")

                        elif cmd == "aibot_send_msg":
                            # Bot is sending a reply message (non-streaming)
                            body = msg.get("body", {})
                            record = {
                                "type": "send_msg",
                                "chatid": body.get("chatid", ""),
                                "msgtype": body.get("msgtype", ""),
                                "content": body.get("markdown", {}).get("content", ""),
                                "timestamp": time.time(),
                            }
                            self._sent_messages.append(record)
                            logger.info(f"💬 Bot sent msg to {record['chatid']}: {record['content'][:80]}")

                            # Send ACK for the send
                            ack = {"errcode": 0, "errmsg": "ok"}
                            await websocket.send_text(json.dumps(ack))

                        elif cmd == "aibot_respond_msg":
                            # Bot is sending a streaming reply chunk
                            body = msg.get("body", {})
                            stream = body.get("stream", {})
                            record = {
                                "type": "respond_msg",
                                "req_id": msg.get("headers", {}).get("req_id", ""),
                                "stream_id": stream.get("id", ""),
                                "content": stream.get("content", ""),
                                "finish": stream.get("finish", False),
                                "timestamp": time.time(),
                            }
                            self._stream_chunks.append(record)
                            status = "✅" if record["finish"] else "📝"
                            logger.info(f"{status} Bot stream chunk: id={record['stream_id'][:20]}, finish={record['finish']}, len={len(record['content'])}")

                            # Send ACK
                            ack = {"errcode": 0, "errmsg": "ok"}
                            await websocket.send_text(json.dumps(ack))

                        else:
                            logger.debug(f"📨 Unknown command: {cmd}")

                    except json.JSONDecodeError:
                        logger.warning(f"⚠ Invalid JSON received: {data[:100]}")

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                if websocket in self._ws_connections:
                    self._ws_connections.remove(websocket)
                self._subscribed = False
                logger.info(f"WebSocket closed. Remaining: {len(self._ws_connections)}")

    def start_background(self, log_file=None):
        """Start the server in background thread."""
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
    server = MockWeComBotServer(port=5008)
    server.start_background()
