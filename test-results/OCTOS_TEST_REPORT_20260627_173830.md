# Octos 统一测试报告

**测试日期**: 2026-06-27 17:33:51

**二进制**: /Volumes/AppleData/octos/target/release/octos

**日志目录**: /tmp/octos_test/logs

**报告生成**: 2026-06-27 17:38:30

---

## 1. 总体结果


| 模块 | 总计 | 通过 | 失败 | 跳过 | 通过率 | 状态 |
|------|------|------|------|------|--------|------|
| cli | 124 | 92 | 13 | 19 | 74.2% | ❌ |
| serve | 96 | 91 | 0 | 5 | 94.8% | ✅ |
| stdio | 6 | 1 | 5 | 0 | 16.7% | ❌ |
| **总计** | **226** | **184** | **18** | **24** | **81.4%** | **❌** |

---

## 2. 各模块详细结果

### 2.1 CLI 测试

**总计**: 124 | **通过**: 92 | **失败**: 13 | **跳过**: 19 | **通过率**: 74.2%

| 编号 | 分类 | 名称 | 状态 |
|------|------|------|------|
| 1.1 | CLI | help command | PASS |
| 2.1 | Chat | chat help | PASS |
| 2.2 | Chat | quit message | PASS |
| 2.24 | Chat | provider minimax | SKIP |
| 2.3 | Chat | colon q message | PASS |
| 2.4 | Chat | slash quit message | PASS |
| 2.5 | Chat | single message | PASS |
| 2.6 | Chat | max iterations | PASS |
| 2.7 | Chat | verbose mode | PASS |
| 2.8 | Chat | no retry | PASS |
| 2.9 | Chat | cwd option | PASS |
| 2.10 | Chat | data dir option | SKIP |
| 2.11 | Chat | streaming output | PASS |
| 2.12 | Chat | model claude | SKIP |
| 2.13 | Chat | model gpt4o | SKIP |
| 2.14 | Chat | provider anthropic | SKIP |
| 2.15 | Chat | provider openai | SKIP |
| 2.16 | Chat | provider gemini | SKIP |
| 2.17 | Chat | provider deepseek | SKIP |
| 2.18 | Chat | provider ollama | SKIP |
| 2.19 | Chat | provider moonshot | SKIP |
| 2.20 | Chat | provider dashscope | SKIP |
| 2.21 | Chat | provider minimax | SKIP |
| 2.22 | Chat | provider groq | SKIP |
| 2.23 | Chat | custom base url | SKIP |
| 2.25 | Chat | deepseek full config | SKIP |
| 2.26 | Chat | save memory | PASS |
| 2.27 | Chat | recall memory | PASS |
| 2.28 | Chat | 7 day window | PASS |
| 2.29 | Chat | hybrid search fallback | PASS |
| 3.1 | Tools | read file | PASS |
| 3.2 | Tools | write file | PASS |
| 3.3 | Tools | shell echo | PASS |
| 3.4 | Tools | glob rust files | PASS |
| 3.5 | Tools | grep fn main | PASS |
| 3.6 | Tools | list directory | PASS |
| 3.7 | Tools | web search | PASS |
| 3.8 | Tools | web fetch | PASS |
| 3.9 | Tools | git status | PASS |
| 3.10 | Tools | parallel read | PASS |
| 3.11 | Tools | edit file | PASS |
| 3.12 | Tools | context filter | PASS |
| 3.13 | Tools | spawn only | PASS |
| 4.1 | Security | no api key error | SKIP |
| 4.2 | Security | dangerous command rm rf | FAIL |
| 4.3 | Security | dangerous command sudo | FAIL |
| 4.4 | Security | fork bomb block | FAIL |
| 4.5 | Security | dd block | FAIL |
| 4.6 | Security | mkfs block | FAIL |
| 4.7 | Security | ssrf localhost | FAIL |
| 4.8 | Security | ssrf private ip | FAIL |
| 4.9 | Security | ssrf aws metadata | FAIL |
| 4.10 | Security | ssrf ipv6 loopback | FAIL |
| 4.11 | Security | ssrf ipv4 mapped | FAIL |
| 4.12 | Security | ssrf dns fail | PASS |
| 4.13 | Security | prompt injection | FAIL |
| 4.14 | Security | env block | PASS |
| 4.15 | Security | credential sanitize openai | PASS |
| 4.16 | Security | credential sanitize aws | PASS |
| 4.17 | Security | credential sanitize github | PASS |
| 5.1 | Init | init defaults | PASS |
| 6.1 | Status | status | SKIP |
| 7.1 | Clean | clean dry run | PASS |
| 8.1 | Completions | completions bash | PASS |
| 8.2 | Completions | completions zsh | PASS |
| 8.3 | Completions | completions fish | PASS |
| 8.4 | Completions | completions powershell | PASS |
| 8.5 | Completions | completions elvish | PASS |
| 8.6 | Completions | dynamic completions models | PASS |
| 8.7 | Completions | dynamic completions providers | PASS |
| 8.8 | Completions | dynamic completions sessions | PASS |
| 8.9 | Completions | dynamic completions skills | PASS |
| 9.1 | Skills | skills help | PASS |
| 9.2 | Skills | skills list | PASS |
| 9.3 | Skills | skills search | PASS |
| 9.4 | Skills | skills info | PASS |
| 9.5 | Skills | skills remove | PASS |
| 10.1 | Auth | auth status | PASS |
| 10.2 | Auth | auth keys | PASS |
| 11.1 | Channels | channels status | PASS |
| 12.1 | Cron | cron list | PASS |
| 13.1 | Gateway | gateway help | PASS |
| 14.1 | Serve | serve help | PASS |
| 15.1 | Docs | docs output | PASS |
| 16.1 | Office | office validate | PASS |
| 16.2 | Office | office extract | PASS |
| 16.3 | Office | office pack | PASS |
| 16.4 | Office | office clean | PASS |
| 16.5 | Office | office thumbnail | PASS |
| 17.1 | Account | account list | PASS |
| 18.1 | Admin | admin tenant list | PASS |
| 19.1 | Tools | tool policy deny | PASS |
| 19.2 | Tools | tool policy allow | PASS |
| 19.3 | Tools | provider policy gemini | PASS |
| 20.1 | Memory | episode storage | PASS |
| 20.2 | Memory | long term memory edit | PASS |
| 20.3 | Memory | entity bank | PASS |
| 20.4 | Memory | hybrid search fallback | PASS |
| 21.2 | Provider | sub providers | PASS |
| 22.1 | Extension | skill override | PASS |
| 22.2 | Extension | skill availability | PASS |
| 22.3 | Extension | plugin sha256 | PASS |
| 22.4 | Extension | mcp stdio | PASS |
| 22.5 | Extension | mcp http | PASS |
| 22.6 | Extension | gating check | PASS |
| 24.1 | Config | config priority | SKIP |
| 24.2 | Config | config parse fail | PASS |
| 24.3 | Hooks | before tool call hook | PASS |
| 24.4 | Hooks | after tool call hook | PASS |
| 24.5 | Hooks | hook timeout | PASS |
| 24.6 | Hooks | circuit breaker | PASS |
| 24.7 | Config | feature flags | PASS |
| 25.1 | Loop | loop detection length 1 | PASS |
| 25.2 | Loop | loop detection length 2 | PASS |
| 25.5 | Loop | context compaction | PASS |
| 26.1 | Security | base64 uri sanitize | PASS |
| 26.2 | Security | sandbox macos | FAIL |
| 26.3 | Security | sandbox linux | FAIL |
| 26.4 | Security | sbpl injection | PASS |
| 27.1 | Gateway | jsonl persistence | PASS |
| 28.1 | ToolPolicy | tool deny policy | PASS |
| 28.2 | ToolPolicy | tool allow policy | PASS |
| 28.3 | ToolPolicy | provider policy | SKIP |
| 28.4 | ToolPolicy | context filter | PASS |

### 2.2 Serve 测试

**总计**: 96 | **通过**: 91 | **失败**: 0 | **跳过**: 5 | **通过率**: 94.8%

| 编号 | 名称 | 状态 |
|------|------|------|
| 8.1 | Server Startup | PASS |
| 8.2 | Version Endpoint | PASS |
| 8.3 | Metrics Endpoint | PASS |
| 8.4 | Auth Token Required | PASS |
| 8.5 | Auth Invalid Token | PASS |
| 8.6 | Dashboard Web UI | PASS |
| 8.7 | WS Connection + Hello | PASS |
| 8.8 | WS system/status.get | PASS |
| 8.9 | WS session/list | PASS |
| 8.10 | WS session/open + turn/start | PASS |
| 8.11 | WS session/delete | PASS |
| 8.14 | WS session/snapshot | PASS |
| 8.15 | WS session/messages_page | SKIP |
| 8.16 | WS session/status.get | PASS |
| 8.17 | WS session/title.set | SKIP |
| 8.18 | WS content/list | PASS |
| 8.19 | WS turn/interrupt | PASS |
| 10.1 | WS Hello Capabilities | PASS |
| 10.2 | Config Capabilities List | PASS |
| 10.3 | WS System Status | PASS |
| 10.4 | WS Auth Me | PASS |
| 11.1 | Session List Empty | PASS |
| 11.2 | Profile Local Create | PASS |
| 11.3 | Session Open After Profile | PASS |
| 11.4 | Session List After Open | PASS |
| 11.5 | Session Title Set | PASS |
| 11.6 | Session Messages Page | PASS |
| 11.7 | Session Status Get | PASS |
| 11.8 | Session Files List | PASS |
| 11.9 | Session Tasks List | PASS |
| 11.10 | Session Workspace Get | PASS |
| 11.11 | Session Delete | PASS |
| 11.12 | Session Hydrate | PASS |
| 11.13 | Session Goal Get | PASS |
| 11.14 | Session Goal Set | PASS |
| 12.1 | Turn State Get No Active | PASS |
| 12.2 | Turn Start Error Without LLM | SKIP |
| 13.1 | Profile LLM List | PASS |
| 13.2 | Profile Skills List | PASS |
| 13.3 | Profile LLM Catalog | PASS |
| 13.4 | Onboarding Workspace Probe | PASS |
| 14.1 | Auth Status | PASS |
| 14.2 | MCP Status List | PASS |
| 15.1 | Tool Status List | PASS |
| 15.2 | Content List | PASS |
| 16.1 | Notification Session Opened | PASS |
| 16.2 | Notification Turn Started | SKIP |
| 16.3 | Notification Turn Completed | SKIP |
| 16.4 | Notification Turn Error | PASS |
| 16.5 | Notification Agent Updated | PASS |
| 17.1 | Unknown Method Error | PASS |
| 17.2 | Missing Session ID | PASS |
| 17.3 | Session Open Invalid | PASS |
| 17.4 | Turn State Unknown | PASS |
| 17.5 | JSON-RPC Missing Version | PASS |
| 18.1 | Approval Scopes List | PASS |
| 18.2 | Permission Profile List | PASS |
| 18.3 | Permission Profile Set | PASS |
| 18.4 | Diff Preview Get | PASS |
| 18.5 | User Question Respond | PASS |
| 19.1 | Task List | PASS |
| 19.2 | Task Cancel | PASS |
| 19.3 | Task Restart From Node | PASS |
| 19.4 | Task Output Read | PASS |
| 19.5 | Task Artifact List | PASS |
| 19.6 | Task Artifact Read | PASS |
| 20.1 | Agent List | PASS |
| 20.2 | Agent Status Read | PASS |
| 20.3 | Agent Output Read | PASS |
| 20.4 | Agent Artifact List | PASS |
| 20.5 | Agent Artifact Read | PASS |
| 20.6 | Agent Interrupt | PASS |
| 20.7 | Agent Close | PASS |
| 21.1 | Session Goal Clear | PASS |
| 21.2 | Thread Graph Get | PASS |
| 21.3 | Session Status Read | PASS |
| 21.4 | Loop List | PASS |
| 21.5 | Loop Create | PASS |
| 21.6 | Review Start | PASS |
| 22.1 | Router Get Metrics | PASS |
| 22.2 | Router Set Mode | PASS |
| 22.3 | Content Delete | PASS |
| 22.4 | Content Bulk Delete | PASS |
| 23.1 | Profile LLM Select | PASS |
| 23.2 | Profile LLM Upsert | PASS |
| 23.3 | Profile LLM Delete | PASS |
| 23.4 | Profile LLM Test | PASS |
| 23.5 | Profile LLM Fetch Models | PASS |
| 23.6 | Profile Skills Registry Search | PASS |
| 23.7 | Profile Skills Install | PASS |
| 23.8 | Profile Skills Remove | PASS |
| 24.1 | Auth Send Code | PASS |
| 24.2 | Auth Logout | PASS |
| 24.3 | Profile LLM Select No Profile | PASS |
| 8.12 | Bind Address (0.0.0.0) | PASS |
| 8.13 | Default Bind (127.0.0.1) | PASS |

### 2.3 Stdio 传输测试

**总计**: 6 | **通过**: 1 | **失败**: 5 | **跳过**: 0 | **通过率**: 16.7%

| 编号 | 名称 | 状态 |
|------|------|------|
| 30.1 | Stdio Connectivity | FAIL |
| 30.2 | Stdio Capabilities List | FAIL |
| 30.3 | Stdio System Status | FAIL |
| 30.4 | Stdio Session List | FAIL |
| 30.5 | Stdio Session Open | PASS |
| 30.6 | Stdio Auth Me | FAIL |

---

## 3. 失败测试详情

### cli 测试失败

- **[4.2] dangerous command rm rf**
- **[4.3] dangerous command sudo**
- **[4.4] fork bomb block**
- **[4.5] dd block**
- **[4.6] mkfs block**
- **[4.7] ssrf localhost**
- **[4.8] ssrf private ip**
- **[4.9] ssrf aws metadata**
- **[4.10] ssrf ipv6 loopback**
- **[4.11] ssrf ipv4 mapped**
- **[4.13] prompt injection**
- **[26.2] sandbox macos**
- **[26.3] sandbox linux**

### stdio 测试失败

- **[30.1] Stdio Connectivity**: RPC system/status.get timed out
- **[30.2] Stdio Capabilities List**: RPC config/capabilities/list timed out
- **[30.3] Stdio System Status**: RPC system/status.get timed out
- **[30.4] Stdio Session List**: RPC session/list timed out
- **[30.6] Stdio Auth Me**: RPC auth/me timed out

---

## 4. 功能覆盖矩阵


| 模块 | 测试数 | 通过率 | 评估 |
|------|--------|--------|------|
| cli | 124 | 74.2% | 🟠 不足 |
| serve | 96 | 94.8% | 🟡 一般 |
| stdio | 6 | 16.7% | 🔴 严重不足 |

---

*日志收集路径: `/Volumes/AppleData/octos-test/test-results/logs/`*

*报告生成时间: 2026-06-27 17:38:30*
