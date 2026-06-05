# Octos Serve 测试说明

## 概述

本目录包含 `octos serve` 命令的功能测试，验证 REST API、SSE 流式响应、Dashboard Web UI、认证机制等核心功能。

## 测试用例列表（14 个）

| 编号 | 功能 | 测试内容 |
|------|------|----------|
| 8.1 | Server Startup | 启动 octos serve 并监听端口，/api/status 返回 200 |
| 8.2 | REST API Sessions | GET /api/sessions 返回 JSON 数组 |
| 8.3 | SSE Streaming | POST /api/chat 收到多个 SSE 事件流 |
| 8.4 | Dashboard WebUI | 访问 /admin/ 返回 HTML Web UI |
| 8.5 | Auth Token Required | 无 token 请求受保护端点返回 401 |
| 8.6 | Bind Address External | `--host 0.0.0.0` 可从本地访问 |
| 8.7 | Bind Address Local Default | 默认绑定 127.0.0.1 |

## 运行测试

### 前置条件

1. **编译 octos 二进制**（需 `api` feature）：
   ```bash
   cargo build --release -p octos-cli --features api
   ```

2. **安装依赖**：
   ```bash
   uv sync  # 项目根目录
   ```

### 通过 test_run.py（推荐）

```bash
# 全部
uv run python test_run.py --test serve

# 详细输出
uv run python test_run.py --test serve -v

# 特定测试
uv run python test_run.py --test serve 8.1

# 列出可用测试
uv run python test_run.py --test serve list
```

### 通过 pytest 直接运行

```bash
cd serve
uv run pytest test_serve.py -v

# 单个测试
uv run pytest test_serve.py::test_8_1_startup -v
```

## 超时配置

- 服务启动超时：15 秒
- HTTP 请求超时：5-10 秒
- SSE 流式测试：10 秒

## 注意事项

1. **端口占用**：测试使用端口 8080 和 8081，确保未被占用
2. **认证令牌**：测试使用固定 token `test-token-12345`
3. **绑定地址**：8.6/8.7 在单机环境无法完全验证外部可访问性，仅验证绑定地址

## 故障排查

### 测试启动失败

```
Failed to start octos serve for testing
```

可能原因：
1. 二进制文件不存在或缺少 `api` feature
2. 端口 8080 已被占用

```bash
lsof -i :8080
```

### SSE 测试超时

确保 config.json 中配置了有效的 LLM 提供商（如 `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`）。

## 技术实现

- 使用 `subprocess.Popen` 管理 serve 进程
- 使用 `httpx` 库发起 HTTP/SSE 请求
- 每个测试会话使用独立的临时数据目录
- 支持 Bearer Token 认证验证
