#!/usr/bin/env python3
"""
测试 NVIDIA OpenAI API 是否可用
"""

import httpx
import json

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODELS = [
    "moonshotai/kimi-k2.6",
    "deepseek-ai/deepseek-v4-flash",
    "deepseek-ai/deepseek-v4-pro"
]

def test_model(model_name):
    """测试单个模型"""
    print(f"\n{'='*70}")
    print(f"Testing Model: {model_name}")
    print(f"{'='*70}")
    
    url = f"{BASE_URL}/chat/completions"
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Hello, this is a test message."}
        ],
        "max_tokens": 50,
        "temperature": 0.7
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    print(f"📤 Endpoint: {url}")
    print(f"💬 Message: Hello, this is a test message.")
    
    try:
        print("⏳ Waiting for response (timeout: 60s)...")
        response = httpx.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"\n✅ Status: {response.status_code}")
        print(f"📊 Usage:")
        print(f"   - Prompt tokens: {data['usage']['prompt_tokens']}")
        print(f"   - Completion tokens: {data['usage']['completion_tokens']}")
        print(f"   - Total tokens: {data['usage']['total_tokens']}")
        
        print(f"\n🤖 Response:")
        content = data['choices'][0]['message']['content']
        # 只显示前200个字符
        preview = content[:200] + "..." if len(content) > 200 else content
        print(f"   {preview}")
        
        return True
        
    except httpx.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        if hasattr(e, 'response'):
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api():
    print("=" * 70)
    print("Testing NVIDIA OpenAI API - Multiple Models")
    print("Rate Limit: Up to 40 rpm")
    print("=" * 70)
    
    results = {}
    
    for model in MODELS:
        success = test_model(model)
        results[model] = success
        
        # 避免速率限制，等待 2 秒
        if model != MODELS[-1]:
            print("\n⏸️  Waiting 2s to avoid rate limit...")
            import time
            time.sleep(2)
    
    # 总结
    print(f"\n{'='*70}")
    print("Test Summary")
    print(f"{'='*70}")
    
    for model, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {model}")
    
    all_passed = all(results.values())
    print(f"\n{'='*70}")
    if all_passed:
        print("✨ All models working correctly!")
    else:
        print("⚠️  Some models failed")
    print(f"{'='*70}")
    
    return all_passed

if __name__ == "__main__":
    success = test_api()
    exit(0 if success else 1)
