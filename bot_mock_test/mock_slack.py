#!/usr/bin/env python3
"""
Slack Mock Server - FastAPI 实现的 Slack API Mock 服务

模拟 Slack Events API 和 Web API，用于测试 octos Slack bot 集成。

端口: 5003 (默认)
端点:
  - POST /slack/events - Slack Events API webhook
  - GET /health - 健康检查
  - POST /_inject - 注入测试事件
  - GET /_sent_messages - 获取 bot 发送的消息
  - POST /_clear - 清理状态
"""

import time
import uuid
import sys
import logging
from typing import Optional
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logger = logging.getLogger("mock_slack")


class MockSlackServer:
    """Mock Slack server with FastAPI."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 5003):
        self.host = host
        self.port = port
        self._sent_messages: list[dict] = []
        self._injected_events: list[dict] = []
        self._transactions: list[dict] = []
        self._txn_counter = 0
        
        # Create FastAPI app
        self.app = FastAPI(title="Slack Mock Server")
        self._setup_routes()
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        return f"E{uuid.uuid4().hex[:16]}"
    
    def _next_txn_id(self) -> str:
        """Generate next transaction ID."""
        self._txn_counter += 1
        return f"T{self._txn_counter:06d}"
    
    def _setup_routes(self):
        """Set up FastAPI routes."""
        app = self.app
        
        @app.get("/health")
        async def health():
            """Health check endpoint."""
            return JSONResponse({"status": "ok", "service": "slack-mock-server"})
        
        @app.post("/slack/events")
        async def slack_events(request: Request):
            """Slack Events API webhook endpoint."""
            try:
                body = await request.json()
                
                # Handle URL verification challenge
                if body.get("type") == "url_verification":
                    challenge = body.get("challenge", "")
                    logger.info(f"🔐 URL verification challenge received")
                    return JSONResponse({"challenge": challenge})
                
                # Handle regular events
                event = body.get("event", {})
                event_type = event.get("type", "unknown")
                
                logger.info(f"📥 Received Slack event: type={event_type}")
                
                # Record the event
                self._transactions.append({
                    "txn_id": self._next_txn_id(),
                    "event": event,
                    "timestamp": time.time(),
                })
                
                return JSONResponse({"ok": True})
            
            except Exception as e:
                logger.error(f"❌ Error processing event: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.post("/_inject")
        async def inject_event(request: Request):
            """Inject a test event into the mock server."""
            try:
                body = await request.json()
                text = body.get("text", "")
                channel = body.get("channel", "C012AB3CD")
                user = body.get("user", "U012AB3CD")
                
                # Create a Slack message event
                event = {
                    "token": "test_token",
                    "team_id": "T012AB3CD",
                    "api_app_id": "A012AB3CD",
                    "event": {
                        "type": "message",
                        "text": text,
                        "user": user,
                        "channel": channel,
                        "ts": str(time.time()),
                        "event_ts": str(time.time()),
                    },
                    "type": "event_callback",
                    "event_id": self._generate_event_id(),
                    "event_time": int(time.time()),
                }
                
                # Store the injected event
                self._injected_events.append(event)
                
                logger.info(f"🔔 Injected event: channel={channel}, text={text[:50]}")
                
                return JSONResponse({
                    "success": True,
                    "event_id": event["event_id"],
                    "note": "Event injected successfully"
                })
            
            except Exception as e:
                logger.error(f"❌ Error injecting event: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/_sent_messages")
        async def get_sent_messages():
            """Get all messages sent by the bot."""
            return JSONResponse(self._sent_messages)
        
        @app.post("/_clear")
        async def clear_state():
            """Clear all stored state."""
            self._sent_messages.clear()
            self._injected_events.clear()
            self._transactions.clear()
            self._txn_counter = 0
            logger.info("🗑 Cleared all mock server state")
            return JSONResponse({"success": True})
        
        @app.get("/_transactions")
        async def get_transactions():
            """Get all received transactions (for debugging)."""
            return JSONResponse(self._transactions)
        
        @app.get("/_stats")
        async def get_stats():
            """Get mock server statistics."""
            return JSONResponse({
                "sent_messages": len(self._sent_messages),
                "injected_events": len(self._injected_events),
                "transactions": len(self._transactions),
            })
    
    def start_background(self, log_file=None):
        """Start the server in a background thread."""
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Configure logging to both file and stdout
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            
            # File handler
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.INFO)
            
            # Stdout handler
            stdout_handler = logging.StreamHandler(sys.stdout)
            stdout_handler.setFormatter(formatter)
            stdout_handler.setLevel(logging.INFO)
            
            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            root_logger.addHandler(stdout_handler)
            root_logger.setLevel(logging.INFO)
            
            # Configure uvicorn loggers
            uvicorn_logger = logging.getLogger("uvicorn")
            uvicorn_logger.addHandler(file_handler)
            uvicorn_logger.addHandler(stdout_handler)
            uvicorn_logger.setLevel(logging.INFO)
            
            uvicorn_access_logger = logging.getLogger("uvicorn.access")
            uvicorn_access_logger.addHandler(file_handler)
            uvicorn_access_logger.addHandler(stdout_handler)
            uvicorn_access_logger.setLevel(logging.INFO)
            
            uvicorn_error_logger = logging.getLogger("uvicorn.error")
            uvicorn_error_logger.addHandler(file_handler)
            uvicorn_error_logger.addHandler(stdout_handler)
            uvicorn_error_logger.setLevel(logging.INFO)
        
        # Start uvicorn server
        uvicorn.run(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
            access_log=False,
        )


if __name__ == "__main__":
    server = MockSlackServer(port=5003)
    server.start_background()
