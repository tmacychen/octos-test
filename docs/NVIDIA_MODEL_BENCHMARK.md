# NVIDIA Free Endpoint 模型响应速度基准测试

**测试时间**: 2026-06-21 16:47  
**API 端点**: `https://integrate.api.nvidia.com/v1/chat/completions`  
**测试方法**: 单轮 `chat/completions`，`max_tokens=10`，每次测量端到端延迟

---

## Top 10 最快模型

| # | 模型 | 耗时 | 响应示例 | model_id |
|---|------|:---:|------|------|
| 1 | llama-3.1-8b | 0.6s | "Hello." | `meta/llama-3.1-8b-instruct` |
| 2 | llama-4-maverick-17b | 0.6s | "hello" | `meta/llama-4-maverick-17b-128e-instruct` |
| 3 | nemotron-3-nano-30b | 0.7s | ✅ | `nvidia/nemotron-3-nano-30b-a3b` |
| 4 | mistral-small-4-119b | 0.7s | "Hello! 😊" | `mistralai/mistral-small-4-119b-2603` |
| 5 | qwen3-next-80b | 0.7s | "Hello! 😊" | `qwen/qwen3-next-80b-a3b-instruct` |
| 6 | llama-3.3-nemotron-49b | 0.8s | "Hello!" | `nvidia/llama-3.3-nemotron-super-49b-v1` |
| 7 | nemotron-3-super-120b | 0.8s | ✅ | `nvidia/nemotron-3-super-120b-a12b` |
| 8 | ministral-14b | 0.8s | "Hello! 😊" | `mistralai/ministral-14b-instruct-2512` |
| 9 | deepseek-v4-flash | 0.9s | "hello" | `deepseek-ai/deepseek-v4-flash` |
| 10 | kimi-k2.6 | 1.0s | "Hello!" | `moonshotai/kimi-k2.6` |

---

## 其他测试结果

| 模型 | 耗时 | 状态 | 说明 |
|------|:---:|------|------|
| qwen3.5-397b | 1.1s | ✅ | 较快的超大模型 |
| llama-3.3-70b | 11.9s | ⚠️ | 响应偏慢 |
| minimax-m2.7 | 15.9s | ⚠️ | 空响应 |
| deepseek-v4-pro | 0.5s | 🔴 | HTTP 429 Rate Limit |
| gemma-4-31b | 30s+ | 🔴 | 无响应超时 |

---

## 建议

- **当前使用**: `meta/llama-4-maverick-17b-128e-instruct`（0.6s，流稳定，tool calling OK）
- **备选**: `nvidia/llama-3.3-nemotron-super-49b-v1`（0.8s，agent/tool calling 支持好）
- **最快**: `meta/llama-3.1-8b-instruct`（0.6s，轻量级）

## 注意

`deepseek-ai/deepseek-v4-flash` curl 测 0.9s，但 octos chat 流式调用时
NVIDIA 端频繁断连（`retryable stream error`），导致重试耗 10-30s/次，
不适合批量测试。推荐 llama/nemotron 系列。

---

*报告由 `test_nvidia_models.py` 自动生成*
