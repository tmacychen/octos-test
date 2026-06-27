# Octos 统一测试报告

**测试日期**: 2026-06-27 17:33:51

**二进制**: /Volumes/AppleData/octos/target/release/octos

**日志目录**: /tmp/octos_test/logs

**报告生成**: 2026-06-27 17:37:49

---

## 1. 总体结果


| 模块 | 总计 | 通过 | 失败 | 跳过 | 通过率 | 状态 |
|------|------|------|------|------|--------|------|
| cli | 19 | 0 | 0 | 19 | 0.0% | ✅ |
| serve | 96 | 91 | 0 | 5 | 94.8% | ✅ |
| **总计** | **115** | **91** | **0** | **24** | **79.1%** | **✅** |

---

## 2. 各模块详细结果

### 2.1 CLI 测试

**总计**: 19 | **通过**: 0 | **失败**: 0 | **跳过**: 19 | **通过率**: 0.0%

| 编号 | 分类 | 名称 | 状态 |
|------|------|------|------|
| 2.24 | Chat | provider minimax | SKIP |
| 2.10 | Chat | data dir option | SKIP |
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
| 4.1 | Security | no api key error | SKIP |
| 6.1 | Status | status | SKIP |
| 24.1 | Config | config priority | SKIP |
| 28.3 | ToolPolicy | provider policy | SKIP |

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

---

## 3. 失败测试详情

*无失败测试 🎉*

---

## 4. 功能覆盖矩阵


| 模块 | 测试数 | 通过率 | 评估 |
|------|--------|--------|------|
| cli | 19 | 0.0% | 🔴 严重不足 |
| serve | 96 | 94.8% | 🟡 一般 |

---

*日志收集路径: `/Volumes/AppleData/octos-test/test-results/logs/`*

*报告生成时间: 2026-06-27 17:37:49*
