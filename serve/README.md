# Octos Serve / API Channel 测试说明

## 概述

本目录包含 `octos serve` 命令的功能测试，验证 REST API、WebSocket UI Protocol、认证机制等核心功能。

**重要架构变更 (M12 Phase D-5)**：以下 REST 端点已废弃，改为 WebSocket RPC 方法：
- `GET /api/sessions` → WS `session/list`
- `GET /api/sessions/{id}/messages` → WS `session/messages_page`
- `POST /api/chat` → WS `session/open` + `turn/start`
- `GET /api/status` → WS `system/status.get`

唯一 chat 传输路径：`/api/ui-protocol/ws` (JSON-RPC over WebSocket)

## 测试用例列表（63 个）

| 编号 | 功能 | 测试内容 |
|------|------|----------|
| 8.1 | Server Startup | `/health` 返回 healthy |
| 8.2 | Version Endpoint | `/api/version` 返回版本信息 |
| 8.3 | Metrics Endpoint | `/metrics` 返回 Prometheus 格式文本 |
| 8.4 | Auth Token Required | 无 token 请求受保护端点返回 401 |
| 8.5 | Auth Invalid Token | 错误 token 请求返回 401/403 |
| 8.6 | Dashboard Web UI | `/admin/` 返回 HTML 页面 |
| 8.7 | WS Connection | WebSocket 连接建立 + client/hello 握手 |
| 8.8 | WS system/status.get | 通过 WS 获取系统状态 |
| 8.9 | WS session/list | 通过 WS 列出会话 |
| 8.10 | WS session/open + turn/start | 通过 WS 创建会话并发送消息 (需 API Key) |
| 8.11 | WS session/delete | 通过 WS 删除会话 |
| 8.14 | WS session/snapshot | 合并引导获取 (status+files+tasks) |
| 8.15 | WS session/messages_page | 分页消息历史 |
| 8.16 | WS session/status.get | 单会话状态轮询 |
| 8.17 | WS session/title.set | 会话重命名 |
| 8.18 | WS content/list | 内容目录列表 |
| 8.19 | WS turn/interrupt | 中断正在进行的 turn (需 API Key) |
| 8.12 | Bind Address External | `--host 0.0.0.0` 可从本地访问 ⚠️ |
| 8.13 | Bind Address Local | 默认绑定 127.0.0.1 ⚠️ |
| 10.1 | WS Hello Capabilities | client/hello 返回 capabilities（methods + features） |
| 10.2 | Config Capabilities List | config/capabilities/list 完整能力列表 |
| 10.3 | WS System Status | system/status.get（无需 profile） |
| 10.4 | WS Auth Me | auth/me 返回当前身份 |
| 11.1 | Session List Empty | session/list 无 profile 时的行为 |
| 11.2 | Profile Local Create | 创建本地 solo profile（onboarding 核心）|
| 11.3 | Session Open After Profile | profile 创建后 session/open |
| 11.4 | Session List After Open | 列出已打开的 session |
| 11.5 | Session Title Set | session/title.set 重命名 + snapshot 验证 |
| 11.6 | Session Messages Page | 分页消息历史 |
| 11.7 | Session Status Get | 单会话状态轮询 |
| 11.8 | Session Files List | 文件列表 |
| 11.9 | Session Tasks List | 任务列表 |
| 11.10 | Session Workspace Get | 工作区信息 |
| 11.11 | Session Delete | 删除 session |
| 11.12 | Session Hydrate | 会话回填 |
| 11.13 | Session Goal Get | 目标查询 |
| 11.14 | Session Goal Set | 目标设置 |
| 12.1 | Turn State Get (no turn) | 无活跃 turn 时 turn/state.get |
| 12.2 | Turn Start Error (no LLM) | 无 LLM 时 turn/start 错误形状验证 |
| 13.1 | Profile LLM List | LLM 配置列表 |
| 13.2 | Profile Skills List | 已安装技能列表 |
| 13.3 | Profile LLM Catalog | LLM 目录查询 |
| 13.4 | Onboarding Workspace Probe | 工作区探测 |
| 14.1 | Auth Status | 认证状态 |
| 14.2 | MCP Status List | MCP 工具状态 |
| 15.1 | Tool Status List | 工具状态列表 |
| 15.2 | Content List | 内容目录 |
| 16.1 | Notification Session Opened | session/open 后收到 session/opened 通知 |
| 16.2 | Notification Turn Started | turn/start 后收到 turn/started 通知 (需 API Key) |
| 16.3 | Notification Turn Completed | turn 完成后收到 turn/completed 通知 (需 API Key) |
| 16.4 | Notification Turn Error | 错误场景下验证 turn/error 通知 |
| 16.5 | Notification Agent Updated | agent 状态变更接收 agent/updated 通知 |
| 17.1 | Unknown Method | 非法 method 返回 -32601 |
| 17.2 | Missing Session ID | 缺 session_id 返回 INVALID_PARAMS |
| 17.3 | Session Open Invalid | 空 session_id 返回错误 |
| 17.4 | Turn State Unknown | 陌生的 turn_id 返回 UNKNOWN_TURN |
| 17.5 | JSON-RPC Missing Version | 缺 jsonrpc 字段被拒绝 |
| 30.1 | Stdio Connectivity | start + client/hello 连通性验证 |
| 30.2 | Stdio Capabilities | 获取 capabilities 方法/特性列表 |
| 30.3 | Stdio System Status | system/status.get 查询 |
| 30.4 | Stdio Session List | session/list 空会话列表 |
| 30.5 | Stdio Session Open | profile/create + session/open 创建会话 |
| 30.6 | Stdio Auth Me | auth/me 在 stdio 模式下被拒绝验证 |

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

3. **API Channel 深度测试** (8.10) 需要配置 LLM API Key：
   ```bash
   # 二选一，NVIDIA 的 OpenAI 兼容 API 也可以用
   export OPENAI_API_KEY=nvapi-your-nvidia-key
   export ANTHROPIC_API_KEY=sk-ant-...
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
uv run pytest test_serve.py::test_8_1_server_startup -v
```

### Stdio 模式测试

Stdio 传输测试（30.x）验证 `octos serve --stdio` 的 JSON-RPC over stdin/stdout 通信：

```bash
# 通过 test_run.py
uv run python test_run.py --test serve stdio

# 直接运行
cd serve
uv run python test_serve.py --stdio  # 只运行 stdio 测试
```

## WebSocket UI Protocol 测试说明

### 协议格式

所有 WS 测试使用 JSON-RPC 2.0 格式：

```json
// 请求
{"jsonrpc":"2.0","id":"uuid","method":"session/list","params":{}}

// 响应
{"jsonrpc":"2.0","id":"uuid","result":{"sessions":[...]}}

// 错误
{"jsonrpc":"2.0","id":"uuid","error":{"code":-32600,"message":"..."}}
```

### client/hello 握手

WS 连接建立后，客户端必须先发送 `client/hello` 消息协商功能特性，之后才能调用其他 RPC 方法。

### 认证

WS 连接通过 query parameter `?token=<auth_token>` 传递 Bearer token。

## 超时配置

- 服务启动超时：15 秒
- HTTP 请求超时：5-10 秒
- WS RPC 超时：10-30 秒（LLM 交互较长）

## 注意事项

1. **端口占用**：测试使用端口 8080 和 8081，确保未被占用
2. **认证令牌**：测试使用固定 token `test-token-12345`
3. **SKIP 行为**：缺少 API Key 或 LLM 配置时，相关测试会返回 SKIP 而非 FAIL
4. **绑定地址**：8.12/8.13 在单机环境无法完全验证外部可访问性

## 故障排查

### 测试启动失败

可能原因：
1. 二进制文件不存在或缺少 `api` feature
2. 端口 8080 已被占用

```bash
lsof -i :8080
```

### WS 测试失败

1. 确认 `websockets` 库已安装：`pip install websockets`
2. 确认 octos 二进制包含 `api` feature
3. 检查 auth token 是否匹配

### LLM 相关测试 SKIP

8.10/8.19 测试需要有效的 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY` 才能获得实际回复。8.14–8.18 需要 LLM profile 配置才能创建会话。如果缺少，相关测试会安全 SKIP。
