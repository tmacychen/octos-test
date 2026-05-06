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
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mock_slack")

app = FastAPI(title="Slack Mock Server")


class InjectedMessage(BaseModel):
    """Injected message for testing."""
    text: str
    channel: str = "C012AB3CD"
    user: str = "U012AB3CD"
    ts: Optional[str] = None


class MockSlackServer:
    """Mock Slack server state manager."""
    
    def __init__(self):
        self._sent_messages: list[dict] = []
        self._injected_events: list[dict] = []
        self._transactions: list[dict] = []
        self._txn_counter = 0
    
    def _generate_event_id(self) -> str:
        """Generate a unique event ID."""
        return f"E{uuid.uuid4().hex[:16]}"
    
    def _next_txn_id(self) -> str:
        """Generate next transaction ID."""
        self._txn_counter += 1
        return f"T{self._txn_counter:06d}"
    
    def add_sent_message(self, message: dict):
        """Record a message sent by the bot."""
        self._sent_messages.append(message)
        logger.info(f"📨 Bot send_message: channel={message.get('channel')}, text={message.get('text', '')[:50]}")
    
    def get_sent_messages(self) -> list[dict]:
        """Get all messages sent by the bot."""
        return self._sent_messages
    
    def clear_state(self):
        """Clear all stored state."""
        self._sent_messages.clear()
        self._injected_events.clear()
        self._transactions.clear()
        self._txn_counter = 0
        logger.info("🗑 Cleared all mock server state")


# Global state
mock_server = MockSlackServer()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return JSONResponse({"status": "ok", "service": "slack-mock-server"})


@app.post("/slack/events")
async def slack_events(request: Request):
    """
    Slack Events API webhook endpoint.
    
    Receives events from octos gateway and records them.
    """
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
        mock_server._transactions.append({
            "txn_id": mock_server._next_txn_id(),
            "event": event,
            "timestamp": time.time(),
        })
        
        # If it's a message event, simulate bot response
        if event_type == "message":
            text = event.get("text", "")
            channel = event.get("channel", "")
            user = event.get("user", "")
            
            logger.info(f"💬 Message event: channel={channel}, user={user}, text={text[:50]}")
            
            # Simulate bot response (octos will handle this)
            # The actual response will be added via _sent_messages when octos sends it
        
        return JSONResponse({"ok": True})
    
    except Exception as e:
        logger.error(f"❌ Error processing event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/_inject")
async def inject_event(request: Request):
    """
    Inject a test event into the mock server.
    
    Simulates Slack sending an event to octos gateway.
    """
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
            "event_id": mock_server._generate_event_id(),
            "event_time": int(time.time()),
        }
        
        # Store the injected event
        mock_server._injected_events.append(event)
        
        # Forward to octos gateway (if configured)
        # This would normally be done by Slack's infrastructure
        
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
    return JSONResponse(mock_server.get_sent_messages())


@app.post("/_clear")
async def clear_state():
    """Clear all stored state."""
    mock_server.clear_state()
    return JSONResponse({"success": True})


@app.get("/_transactions")
async def get_transactions():
    """Get all received transactions (for debugging)."""
    return JSONResponse(mock_server._transactions)


@app.get("/_stats")
async def get_stats():
    """Get mock server statistics."""
    return JSONResponse({
        "sent_messages": len(mock_server._sent_messages),
        "injected_events": len(mock_server._injected_events),
        "transactions": len(mock_server._transactions),
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)
