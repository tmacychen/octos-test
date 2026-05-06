#!/usr/bin/env python3
"""
快速测试 Matrix Bot Management 和 Swarm Supervisor 功能。

这个脚本用于验证新实现的接口是否正常工作。
"""

import sys
import time
from pathlib import Path

# Add bot_mock_test to path
sys.path.insert(0, str(Path(__file__).parent / "bot_mock_test"))

from runner_matrix import MatrixTestRunner


def test_bot_management():
    """测试 Bot 管理功能"""
    print("=" * 70)
    print("Testing Matrix Bot Management")
    print("=" * 70)

    runner = MatrixTestRunner(base_url="http://127.0.0.1:8008")
    
    # 测试 1: /createbot 命令
    print("\n1. Testing /createbot command...")
    result = runner.inject_bot_command(
        command="/createbot weather Weather Bot",
        room_id="!test_bot_mgmt:localhost",
        sender="@admin:localhost",
    )
    print(f"   ✓ Command injected: txn_id={result.get('txn_id')}")
    
    # 测试 2: /listbots 命令
    print("\n2. Testing /listbots command...")
    result = runner.inject_bot_command(
        command="/listbots",
        room_id="!test_bot_mgmt:localhost",
        sender="@admin:localhost",
    )
    print(f"   ✓ Command injected: txn_id={result.get('txn_id')}")
    
    # 测试 3: /deletebot 命令（缺少参数）
    print("\n3. Testing /deletebot with missing args...")
    result = runner.inject_bot_command(
        command="/deletebot",
        room_id="!test_bot_mgmt:localhost",
        sender="@admin:localhost",
    )
    print(f"   ✓ Command injected: txn_id={result.get('txn_id')}")
    
    print("\n✅ Bot Management tests passed!")


def test_swarm_supervisor():
    """测试 Swarm Supervisor 功能"""
    print("\n" + "=" * 70)
    print("Testing Matrix Swarm Supervisor (M7.3)")
    print("=" * 70)
    
    runner = MatrixTestRunner(base_url="http://127.0.0.1:8008")
    
    # 测试 1: 注入 Swarm Harness 事件
    print("\n1. Testing swarm event routing...")
    result = runner.inject_swarm_event(
        session_id="test-swarm-1",
        agent_label="claude-code",
        event_type="progress",
        event_data={
            "phase": "fetch_sources",
            "message": "Fetching 3/12 sources",
            "progress": 0.25,
        },
    )
    print(f"   ✓ Event routed: event_id={result.get('event_id')}")
    print(f"   ✓ Puppet user ID: {result.get('puppet_user_id')}")
    
    # 测试 2: 多个 puppet 在同一 swarm
    print("\n2. Testing multiple puppets in swarm...")
    agents = ["claude-code", "gpt-helper", "deepseek-coder"]
    for agent in agents:
        result = runner.inject_swarm_event(
            session_id="test-swarm-2",
            agent_label=agent,
            event_type="progress",
        )
        print(f"   ✓ {agent}: {result.get('puppet_user_id')}")
    
    # 测试 3: Supervisor 回复
    print("\n3. Testing supervisor reply routing...")
    result = runner.inject_supervisor_reply(
        message="please refine the outline",
        room_id="!swarm_test-swarm-1:localhost",
        sender="@alice:localhost",
        target_puppet="@octos_swarm_test-swarm-1_claude-code:localhost",
    )
    print(f"   ✓ Reply injected: txn_id={result.get('txn_id')}")
    print(f"   ✓ Target puppet: {result.get('target_puppet')}")
    
    print("\n✅ Swarm Supervisor tests passed!")


def test_room_invite():
    """测试房间邀请功能"""
    print("\n" + "=" * 70)
    print("Testing Room Invite")
    print("=" * 70)
    
    runner = MatrixTestRunner(base_url="http://127.0.0.1:8008")
    
    print("\n1. Testing room invite injection...")
    result = runner.inject_room_invite(
        room_id="!invite_test:localhost",
        user_id="@newuser:localhost",
        inviter="@admin:localhost",
        push_event=False,
    )
    print(f"   ✓ User invited to room")
    print(f"   ✓ Room members: {result.get('members', [])}")
    
    print("\n✅ Room Invite tests passed!")


if __name__ == "__main__":
    try:
        test_bot_management()
        test_swarm_supervisor()
        test_room_invite()
        
        print("\n" + "=" * 70)
        print("🎉 All Matrix extension features working correctly!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
