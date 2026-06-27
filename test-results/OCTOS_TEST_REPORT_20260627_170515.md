# Octos 统一测试报告

**测试日期**: 2026-06-27 12:32:10

**二进制**: /Volumes/AppleData/octos/target/release/octos

---

## 1. 总体结果


| 模块 | 总计 | 通过 | 失败 | 跳过 | 通过率 | 状态 |
|------|------|------|------|------|--------|------|
| bot | 181 | 3 | 178 | 0 | 1.7% | ❌ |
| cli | 124 | 91 | 13 | 0 | 73.4% | ❌ |
| serve | 96 | 91 | 0 | 5 | 94.8% | ✅ |
| stdio | 6 | 1 | 5 | 0 | 16.7% | ❌ |
| **总计** | **407** | **186** | **196** | **5** | **45.7%** | **❌** |

---

## 2. 各模块详细结果

### 2.4 Bot 测试

**总计**: 181 | **通过**: 3 | **失败**: 178 | **跳过**: 0 | **通过率**: 1.7%

| 通道 | 通过 | 失败 | 总计 | 状态 |
|------|------|------|------|------|
| discord | 0 | 39 | 39 | ❌ |
| feishu | 0 | 1 | 1 | ❌ |
| matrix | 0 | 18 | 18 | ❌ |
| qq-bot | 0 | 20 | 20 | ❌ |
| slack | 0 | 47 | 47 | ❌ |
| telegram | 1 | 0 | 1 | ✅ |
| twilio | 0 | 21 | 21 | ❌ |
| wechat | 1 | 0 | 1 | ✅ |
| wecom | 1 | 0 | 1 | ✅ |
| wecom-bot | 0 | 3 | 3 | ❌ |
| whatsapp | 0 | 29 | 29 | ❌ |

### 2.1 CLI 测试

**总计**: 124 | **通过**: 91 | **失败**: 13 | **跳过**: 0 | **通过率**: 73.4%

| 编号 | 分类 | 名称 | 状态 | 耗时 |
|------|------|------|------|------|
| 1.1 | CLI | help command | PASS | 0.01s |
| 2.1 | Chat | chat help | PASS | 0.01s |
| 2.2 | Chat | quit message | PASS | 1.39s |
| 2.24 | Chat | provider minimax | SKIP | 0.57s |
| 2.3 | Chat | colon q message | PASS | 1.68s |
| 2.4 | Chat | slash quit message | PASS | 1.18s |
| 2.5 | Chat | single message | PASS | 2.49s |
| 2.6 | Chat | max iterations | PASS | 1.54s |
| 2.7 | Chat | verbose mode | PASS | 1.59s |
| 2.8 | Chat | no retry | PASS | 1.44s |
| 2.9 | Chat | cwd option | PASS | 4.20s |
| 2.10 | Chat | data dir option | SKIP | 0.02s |
| 2.11 | Chat | streaming output | PASS | 2.00s |
| 2.12 | Chat | model claude | SKIP | 0.56s |
| 2.13 | Chat | model gpt4o | SKIP | 0.69s |
| 2.14 | Chat | provider anthropic | SKIP | 0.59s |
| 2.15 | Chat | provider openai | SKIP | 0.59s |
| 2.16 | Chat | provider gemini | SKIP | 0.60s |
| 2.17 | Chat | provider deepseek | SKIP | 0.56s |
| 2.18 | Chat | provider ollama | SKIP | 0.58s |
| 2.19 | Chat | provider moonshot | SKIP | 0.60s |
| 2.20 | Chat | provider dashscope | SKIP | 0.56s |
| 2.21 | Chat | provider minimax | SKIP | 0.57s |
| 2.22 | Chat | provider groq | SKIP | 0.65s |
| 2.23 | Chat | custom base url | SKIP | 7.06s |
| 2.25 | Chat | deepseek full config | SKIP | 0.21s |
| 2.26 | Chat | save memory | PASS | 2.65s |
| 2.27 | Chat | recall memory | PASS | 1.20s |
| 2.28 | Chat | 7 day window | PASS | 1.20s |
| 2.29 | Chat | hybrid search fallback | PASS | 1.15s |
| 3.1 | Tools | read file | PASS | 1.33s |
| 3.2 | Tools | write file | PASS | 2.07s |
| 3.3 | Tools | shell echo | PASS | 1.20s |
| 3.4 | Tools | glob rust files | PASS | 1.21s |
| 3.5 | Tools | grep fn main | PASS | 1.19s |
| 3.6 | Tools | list directory | PASS | 1.94s |
| 3.7 | Tools | web search | PASS | 1.75s |
| 3.8 | Tools | web fetch | PASS | 1.29s |
| 3.9 | Tools | git status | PASS | 1.93s |
| 3.10 | Tools | parallel read | PASS | 5.06s |
| 3.11 | Tools | edit file | PASS | 2.81s |
| 3.12 | Tools | context filter | PASS | 1.76s |
| 3.13 | Tools | spawn only | PASS | 1.96s |
| 4.1 | Security | no api key error | SKIP | 0.02s |
| 4.2 | Security | dangerous command rm rf | FAIL | 2.29s |
| 4.3 | Security | dangerous command sudo | FAIL | 1.41s |
| 4.4 | Security | fork bomb block | FAIL | 1.46s |
| 4.5 | Security | dd block | FAIL | 1.54s |
| 4.6 | Security | mkfs block | FAIL | 1.97s |
| 4.7 | Security | ssrf localhost | FAIL | 1.35s |
| 4.8 | Security | ssrf private ip | FAIL | 1.33s |
| 4.9 | Security | ssrf aws metadata | FAIL | 1.32s |
| 4.10 | Security | ssrf ipv6 loopback | FAIL | 1.41s |
| 4.11 | Security | ssrf ipv4 mapped | FAIL | 1.42s |
| 4.12 | Security | ssrf dns fail | PASS | 1.44s |
| 4.13 | Security | prompt injection | FAIL | 1.69s |
| 4.14 | Security | env block | PASS | 1.36s |
| 4.15 | Security | credential sanitize openai | PASS | 2.23s |
| 4.16 | Security | credential sanitize aws | PASS | 1.31s |
| 4.17 | Security | credential sanitize github | PASS | 1.23s |
| 5.1 | Init | init defaults | PASS | 0.02s |
| 6.1 | Status | status | SKIP | 0.01s |
| 7.1 | Clean | clean dry run | PASS | 0.01s |
| 8.1 | Completions | completions bash | PASS | 0.01s |
| 8.2 | Completions | completions zsh | PASS | 0.01s |
| 8.3 | Completions | completions fish | PASS | 0.01s |
| 8.4 | Completions | completions powershell | PASS | 0.01s |
| 8.5 | Completions | completions elvish | PASS | 0.01s |
| 8.6 | Completions | dynamic completions models | PASS | 0.01s |
| 8.7 | Completions | dynamic completions providers | PASS | 0.01s |
| 8.8 | Completions | dynamic completions sessions | PASS | 0.01s |
| 8.9 | Completions | dynamic completions skills | PASS | 0.01s |
| 9.1 | Skills | skills help | PASS | 0.01s |
| 9.2 | Skills | skills list | PASS | 0.01s |
| 9.3 | Skills | skills search | SKIP | 15.02s |
| 9.4 | Skills | skills info | PASS | 0.02s |
| 9.5 | Skills | skills remove | PASS | 0.01s |
| 10.1 | Auth | auth status | PASS | 0.01s |
| 10.2 | Auth | auth keys | PASS | 0.01s |
| 11.1 | Channels | channels status | PASS | 0.01s |
| 12.1 | Cron | cron list | PASS | 0.01s |
| 13.1 | Gateway | gateway help | PASS | 0.01s |
| 14.1 | Serve | serve help | PASS | 0.01s |
| 15.1 | Docs | docs output | PASS | 0.01s |
| 16.1 | Office | office validate | PASS | 0.01s |
| 16.2 | Office | office extract | PASS | 0.01s |
| 16.3 | Office | office pack | PASS | 0.01s |
| 16.4 | Office | office clean | PASS | 0.01s |
| 16.5 | Office | office thumbnail | PASS | 0.01s |
| 17.1 | Account | account list | PASS | 0.01s |
| 18.1 | Admin | admin tenant list | PASS | 0.01s |
| 19.1 | Tools | tool policy deny | PASS | 1.24s |
| 19.2 | Tools | tool policy allow | PASS | 1.36s |
| 19.3 | Tools | provider policy gemini | PASS | 2.15s |
| 20.1 | Memory | episode storage | PASS | 1.30s |
| 20.2 | Memory | long term memory edit | PASS | 3.02s |
| 20.3 | Memory | entity bank | PASS | 1.50s |
| 20.4 | Memory | hybrid search fallback | PASS | 1.19s |
| 21.2 | Provider | sub providers | PASS | 1.89s |
| 22.1 | Extension | skill override | PASS | 0.02s |
| 22.2 | Extension | skill availability | PASS | 0.01s |
| 22.3 | Extension | plugin sha256 | PASS | 1.68s |
| 22.4 | Extension | mcp stdio | PASS | 1.21s |
| 22.5 | Extension | mcp http | PASS | 1.28s |
| 22.6 | Extension | gating check | PASS | 1.37s |
| 24.1 | Config | config priority | SKIP | 0.61s |
| 24.2 | Config | config parse fail | PASS | 2.72s |
| 24.3 | Hooks | before tool call hook | PASS | 2.00s |
| 24.4 | Hooks | after tool call hook | PASS | 2.19s |
| 24.5 | Hooks | hook timeout | PASS | 1.45s |
| 24.6 | Hooks | circuit breaker | PASS | 1.81s |
| 24.7 | Config | feature flags | PASS | 0.02s |
| 25.1 | Loop | loop detection length 1 | PASS | 1.77s |
| 25.2 | Loop | loop detection length 2 | PASS | 1.30s |
| 25.5 | Loop | context compaction | PASS | 1.54s |
| 26.1 | Security | base64 uri sanitize | PASS | 1.27s |
| 26.2 | Security | sandbox macos | FAIL | 1.28s |
| 26.3 | Security | sandbox linux | FAIL | 1.28s |
| 26.4 | Security | sbpl injection | PASS | 1.54s |
| 27.1 | Gateway | jsonl persistence | PASS | 0.02s |
| 28.1 | ToolPolicy | tool deny policy | PASS | 1.24s |
| 28.2 | ToolPolicy | tool allow policy | PASS | 1.42s |
| 28.3 | ToolPolicy | provider policy | SKIP | 0.59s |
| 28.4 | ToolPolicy | context filter | PASS | 1.21s |

### 2.2 Serve 测试

**总计**: 96 | **通过**: 91 | **失败**: 0 | **跳过**: 5 | **通过率**: 94.8%

| 编号 | 名称 | 状态 | 耗时 |
|------|------|------|------|
| 8.1 | Server Startup | PASS | 0.01s |
| 8.2 | Version Endpoint | PASS | 0.01s |
| 8.3 | Metrics Endpoint | PASS | 0.01s |
| 8.4 | Auth Token Required | PASS | 0.01s |
| 8.5 | Auth Invalid Token | PASS | 0.00s |
| 8.6 | Dashboard Web UI | PASS | 0.00s |
| 8.7 | WS Connection + Hello | PASS | 0.37s |
| 8.8 | WS system/status.get | PASS | 0.00s |
| 8.9 | WS session/list | PASS | 0.00s |
| 8.10 | WS session/open + turn/start | PASS | 0.00s |
| 8.11 | WS session/delete | PASS | 0.00s |
| 8.14 | WS session/snapshot | PASS | 0.01s |
| 8.15 | WS session/messages_page | SKIP | 0.01s |
| 8.16 | WS session/status.get | PASS | 0.01s |
| 8.17 | WS session/title.set | SKIP | 0.01s |
| 8.18 | WS content/list | PASS | 0.00s |
| 8.19 | WS turn/interrupt | PASS | 1.51s |
| 10.1 | WS Hello Capabilities | PASS | 0.00s |
| 10.2 | Config Capabilities List | PASS | 0.00s |
| 10.3 | WS System Status | PASS | 0.00s |
| 10.4 | WS Auth Me | PASS | 0.00s |
| 11.1 | Session List Empty | PASS | 0.00s |
| 11.2 | Profile Local Create | PASS | 0.00s |
| 11.3 | Session Open After Profile | PASS | 0.01s |
| 11.4 | Session List After Open | PASS | 0.01s |
| 11.5 | Session Title Set | PASS | 0.01s |
| 11.6 | Session Messages Page | PASS | 0.01s |
| 11.7 | Session Status Get | PASS | 0.01s |
| 11.8 | Session Files List | PASS | 0.01s |
| 11.9 | Session Tasks List | PASS | 0.01s |
| 11.10 | Session Workspace Get | PASS | 0.01s |
| 11.11 | Session Delete | PASS | 0.01s |
| 11.12 | Session Hydrate | PASS | 0.01s |
| 11.13 | Session Goal Get | PASS | 0.01s |
| 11.14 | Session Goal Set | PASS | 0.01s |
| 12.1 | Turn State Get No Active | PASS | 0.01s |
| 12.2 | Turn Start Error Without LLM | SKIP | 0.00s |
| 13.1 | Profile LLM List | PASS | 0.01s |
| 13.2 | Profile Skills List | PASS | 0.00s |
| 13.3 | Profile LLM Catalog | PASS | 0.00s |
| 13.4 | Onboarding Workspace Probe | PASS | 0.00s |
| 14.1 | Auth Status | PASS | 0.00s |
| 14.2 | MCP Status List | PASS | 0.01s |
| 15.1 | Tool Status List | PASS | 0.00s |
| 15.2 | Content List | PASS | 0.00s |
| 16.1 | Notification Session Opened | PASS | 1.01s |
| 16.2 | Notification Turn Started | SKIP | 5.02s |
| 16.3 | Notification Turn Completed | SKIP | 5.02s |
| 16.4 | Notification Turn Error | PASS | 0.01s |
| 16.5 | Notification Agent Updated | PASS | 0.00s |
| 17.1 | Unknown Method Error | PASS | 0.00s |
| 17.2 | Missing Session ID | PASS | 0.00s |
| 17.3 | Session Open Invalid | PASS | 0.00s |
| 17.4 | Turn State Unknown | PASS | 0.01s |
| 17.5 | JSON-RPC Missing Version | PASS | 0.00s |
| 18.1 | Approval Scopes List | PASS | 0.00s |
| 18.2 | Permission Profile List | PASS | 0.01s |
| 18.3 | Permission Profile Set | PASS | 0.01s |
| 18.4 | Diff Preview Get | PASS | 0.01s |
| 18.5 | User Question Respond | PASS | 0.00s |
| 19.1 | Task List | PASS | 0.00s |
| 19.2 | Task Cancel | PASS | 0.00s |
| 19.3 | Task Restart From Node | PASS | 0.00s |
| 19.4 | Task Output Read | PASS | 0.00s |
| 19.5 | Task Artifact List | PASS | 0.00s |
| 19.6 | Task Artifact Read | PASS | 0.00s |
| 20.1 | Agent List | PASS | 0.00s |
| 20.2 | Agent Status Read | PASS | 0.00s |
| 20.3 | Agent Output Read | PASS | 0.00s |
| 20.4 | Agent Artifact List | PASS | 0.00s |
| 20.5 | Agent Artifact Read | PASS | 0.00s |
| 20.6 | Agent Interrupt | PASS | 0.00s |
| 20.7 | Agent Close | PASS | 0.00s |
| 21.1 | Session Goal Clear | PASS | 0.01s |
| 21.2 | Thread Graph Get | PASS | 0.01s |
| 21.3 | Session Status Read | PASS | 0.01s |
| 21.4 | Loop List | PASS | 0.01s |
| 21.5 | Loop Create | PASS | 0.01s |
| 21.6 | Review Start | PASS | 0.01s |
| 22.1 | Router Get Metrics | PASS | 0.01s |
| 22.2 | Router Set Mode | PASS | 0.01s |
| 22.3 | Content Delete | PASS | 0.00s |
| 22.4 | Content Bulk Delete | PASS | 0.00s |
| 23.1 | Profile LLM Select | PASS | 0.00s |
| 23.2 | Profile LLM Upsert | PASS | 0.03s |
| 23.3 | Profile LLM Delete | PASS | 0.01s |
| 23.4 | Profile LLM Test | PASS | 0.00s |
| 23.5 | Profile LLM Fetch Models | PASS | 0.00s |
| 23.6 | Profile Skills Registry Search | PASS | 0.61s |
| 23.7 | Profile Skills Install | PASS | 0.01s |
| 23.8 | Profile Skills Remove | PASS | 0.01s |
| 24.1 | Auth Send Code | PASS | 0.00s |
| 24.2 | Auth Logout | PASS | 0.00s |
| 24.3 | Profile LLM Select No Profile | PASS | 0.00s |
| 8.12 | Bind Address (0.0.0.0) | PASS | 1.10s |
| 8.13 | Default Bind (127.0.0.1) | PASS | 0.01s |

### 2.3 Stdio 测试

**总计**: 6 | **通过**: 1 | **失败**: 5 | **跳过**: 0 | **通过率**: 16.7%

| 编号 | 名称 | 状态 | 耗时 |
|------|------|------|------|
| 30.1 | Stdio Connectivity | FAIL | 15.62s |
| 30.2 | Stdio Capabilities List | FAIL | 15.61s |
| 30.3 | Stdio System Status | FAIL | 15.61s |
| 30.4 | Stdio Session List | FAIL | 15.61s |
| 30.5 | Stdio Session Open | PASS | 1.22s |
| 30.6 | Stdio Auth Me | FAIL | 15.62s |

---

## 3. 失败测试详情

### bot 测试失败


- **[test_new_creates_session] test_new_creates_session**: 
- **[test_new_with_invalid_name] test_new_with_invalid_name**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_switch_session] test_switch_session**: 
- **[test_back_to_default] test_back_to_default**: 
- **[test_delete_session] test_delete_session**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_very_long_message] test_very_long_message**: 
- **[test_special_characters] test_special_characters**: 
- **[test_unicode_emoji] test_unicode_emoji**: 
- **[test_queue_mode_show] test_queue_mode_show**: 
- **[test_queue_mode_set] test_queue_mode_set**: 
- **[test_soul_show_empty] test_soul_show_empty**: 
- **[test_soul_set] test_soul_set**: 
- **[test_status_command] test_status_command**: 
- **[test_adaptive_command] test_adaptive_command**: 
- **[test_reset_command] test_reset_command**: 
- **[test_help_command] test_help_command**: 
- **[test_steer_mode_non_abort_messages_not_triggered] test_steer_mode_non_abort_messages_not_triggered**: 
- **[test_interrupt_mode_non_abort_messages_not_triggered] test_interrupt_mode_non_abort_messages_not_triggered**: 
- **[test_abort_multilanguage[english_stop]] test_abort_multilanguage[english_stop]**: 
- **[test_abort_multilanguage[chinese_stop]] test_abort_multilanguage[chinese_stop]**: 
- **[test_abort_multilanguage[japanese_stop]] test_abort_multilanguage[japanese_stop]**: 
- **[test_abort_multilanguage[russian_stop]] test_abort_multilanguage[russian_stop]**: 
- **[test_abort_with_whitespace] test_abort_with_whitespace**: 
- **[test_profile_session_isolation] test_profile_session_isolation**: 
- **[test_queue_mode_per_profile] test_queue_mode_per_profile**: 
- **[test_rapid_messages] test_rapid_messages**: 
- **[test_concurrent_channels] test_concurrent_channels**: 
- **[test_message_with_mention] test_message_with_mention**: 
- **[test_message_with_code_block] test_message_with_code_block**: 
- **[test_message_with_link] test_message_with_link**: 
- **[test_long_response_split] test_long_response_split**: 
- **[test_streaming_edit_simulation] test_streaming_edit_simulation**: 
- **[test_duplicate_message_id_ignored] test_duplicate_message_id_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
- **[test_inject_reaction_event] test_inject_reaction_event**: 
- **[test_reaction_tracking_on_bot_api_call] test_reaction_tracking_on_bot_api_call**: 
- **[test_ws_reconnect] test_ws_reconnect**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_switch_session] test_switch_session**: 
- **[test_delete_session] test_delete_session**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_special_characters] test_special_characters**: 
- **[test_html_formatted_message] test_html_formatted_message**: 
- **[test_queue_mode_set] test_queue_mode_set**: 
- **[test_soul_show_empty] test_soul_show_empty**: 
- **[test_status_command] test_status_command**: 
- **[test_adaptive_command] test_adaptive_command**: 
- **[test_help_command] test_help_command**: 
- **[test_regular_message] test_regular_message**: 
- **[test_profile_session_isolation] test_profile_session_isolation**: 
- **[test_rapid_messages] test_rapid_messages**: 
- **[test_concurrent_rooms] test_concurrent_rooms**: 
- **[test_message_with_mention] test_message_with_mention**: 
- **[test_message_with_link] test_message_with_link**: 
- **[test_duplicate_event_id_ignored] test_duplicate_event_id_ignored**: 
- **[test_simple_message] test_simple_message**: 
- **[test_empty_message] test_empty_message**: 
- **[test_very_long_message] test_very_long_message**: 
- **[test_special_characters] test_special_characters**: 
- **[test_unicode_emoji] test_unicode_emoji**: 
- **[test_new_default] test_new_default**: 
- **[test_new_named] test_new_named**: 
- **[test_new_invalid_name] test_new_invalid_name**: 
- **[test_switch_to_existing] test_switch_to_existing**: 
- **[test_switch_to_default] test_switch_to_default**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_back_returns_session] test_back_returns_session**: 
- **[test_back_with_history] test_back_with_history**: 
- **[test_delete_session] test_delete_session**: 
- **[test_soul_show_default] test_soul_show_default**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_soul_set] test_soul_set**: 
- **[test_soul_reset] test_soul_reset**: 
- **[test_adaptive_no_router] test_adaptive_no_router**: 
- **[test_queue_show] test_queue_show**: 
- **[test_queue_set_followup] test_queue_set_followup**: 
- **[test_queue_set_invalid] test_queue_set_invalid**: 
- **[test_status_show] test_status_show**: 
- **[test_reset_command] test_reset_command**: 
- **[test_unknown_command_help] test_unknown_command_help**: 
- **[test_back_alias_b] test_back_alias_b**: 
- **[test_delete_alias_d] test_delete_alias_d**: 
- **[test_delete_no_name] test_delete_no_name**: 
- **[test_steer_mode_non_abort_messages_not_triggered] test_steer_mode_non_abort_messages_not_triggered**: 
- **[test_interrupt_mode_non_abort_messages_not_triggered] test_interrupt_mode_non_abort_messages_not_triggered**: 
- **[test_two_users_independent] test_two_users_independent**: 
- **[test_profile_session_isolation] test_profile_session_isolation**: 
- **[test_soul_per_profile] test_soul_per_profile**: 
- **[test_queue_mode_per_profile] test_queue_mode_per_profile**: 
- **[test_message_with_mention] test_message_with_mention**: 
- **[test_message_with_code_block] test_message_with_code_block**: 
- **[test_message_with_link] test_message_with_link**: 
- **[test_concurrent_session_creation] test_concurrent_session_creation**: 
- **[test_who_are_you] test_who_are_you**: 
- **[test_hello_greeting] test_hello_greeting**: 
- **[test_chinese_greeting] test_chinese_greeting**: 
- **[test_abort_multilanguage[english_stop]] test_abort_multilanguage[english_stop]**: 
- **[test_abort_multilanguage[chinese_stop]] test_abort_multilanguage[chinese_stop]**: 
- **[test_abort_multilanguage[japanese_stop]] test_abort_multilanguage[japanese_stop]**: 
- **[test_abort_multilanguage[russian_stop]] test_abort_multilanguage[russian_stop]**: 
- **[test_duplicate_event_id_ignored] test_duplicate_event_id_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
- **[test_blocked_sender_no_reply] test_blocked_sender_no_reply**: 
- **[test_new_creates_session] test_new_creates_session**: 
- **[test_new_with_invalid_name] test_new_with_invalid_name**: 
- **[test_switch_session] test_switch_session**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_back_to_previous] test_back_to_previous**: 
- **[test_delete_session] test_delete_session**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_empty_message] test_empty_message**: 
- **[test_special_characters] test_special_characters**: 
- **[test_unicode_emoji] test_unicode_emoji**: 
- **[test_queue_mode_show] test_queue_mode_show**: 
- **[test_queue_mode_set] test_queue_mode_set**: 
- **[test_soul_show_empty] test_soul_show_empty**: 
- **[test_soul_set] test_soul_set**: 
- **[test_status_command] test_status_command**: 
- **[test_adaptive_command] test_adaptive_command**: 
- **[test_reset_command] test_reset_command**: 
- **[test_help_command] test_help_command**: 
- **[test_regular_message] test_regular_message**: 
- **[test_chinese_message] test_chinese_message**: 
- **[test_two_users_independent_sessions] test_two_users_independent_sessions**: 
- **[test_abort_multilanguage] test_abort_multilanguage**: 
- **[test_image_with_caption] test_image_with_caption**: 
- **[test_audio_message] test_audio_message**: 
- **[test_duplicate_message_id_ignored] test_duplicate_message_id_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
- **[test_ws_reconnect] test_ws_reconnect**: 
- **[test_typing_tracking_on_bot_api_call] test_typing_tracking_on_bot_api_call**: 
- **[test_location_message] test_location_message**: 
- **[test_stream_chunks_received] test_stream_chunks_received**: 
- **[test_stream_final_content_nonempty] test_stream_final_content_nonempty**: 
- **[test_blocked_sender_no_reply] test_blocked_sender_no_reply**: 
- **[test_new_default] test_new_default**: 
- **[test_new_with_name] test_new_with_name**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_back_command] test_back_command**: 
- **[test_delete_session] test_delete_session**: 
- **[test_help] test_help**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_soul_show] test_soul_show**: 
- **[test_queue_show] test_queue_show**: 
- **[test_status] test_status**: 
- **[test_reset] test_reset**: 
- **[test_adaptive] test_adaptive**: 
- **[test_simple_greeting] test_simple_greeting**: 
- **[test_chinese_message] test_chinese_message**: 
- **[test_llm_has_content] test_llm_has_content**: 
- **[test_multiple_users_isolated] test_multiple_users_isolated**: 
- **[test_c2c_message_gets_reply] test_c2c_message_gets_reply**: 
- **[test_duplicate_message_id_ignored] test_duplicate_message_id_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
- **[test_ws_reconnect] test_ws_reconnect**: 
- **[test_new_default] test_new_default**: 
- **[test_new_with_name] test_new_with_name**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_back_command] test_back_command**: 
- **[test_delete_session] test_delete_session**: 
- **[test_help] test_help**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_soul_show] test_soul_show**: 
- **[test_queue_show] test_queue_show**: 
- **[test_status] test_status**: 
- **[test_reset] test_reset**: 
- **[test_adaptive] test_adaptive**: 
- **[test_simple_greeting] test_simple_greeting**: 
- **[test_chinese_message] test_chinese_message**: 
- **[test_llm_has_content] test_llm_has_content**: 
- **[test_multiple_users_isolated] test_multiple_users_isolated**: 
- **[test_duplicate_message_sid_ignored] test_duplicate_message_sid_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
- **[test_long_message_gets_reply] test_long_message_gets_reply**: 
- **[test_very_long_message_handled] test_very_long_message_handled**: 
- **[test_help_text_complete] test_help_text_complete**: 

### cli 测试失败


- **[4.2] dangerous command rm rf**: 
- **[4.3] dangerous command sudo**: 
- **[4.4] fork bomb block**: 
- **[4.5] dd block**: 
- **[4.6] mkfs block**: 
- **[4.7] ssrf localhost**: 
- **[4.8] ssrf private ip**: 
- **[4.9] ssrf aws metadata**: 
- **[4.10] ssrf ipv6 loopback**: 
- **[4.11] ssrf ipv4 mapped**: 
- **[4.13] prompt injection**: 
- **[26.2] sandbox macos**: 
- **[26.3] sandbox linux**: 

### stdio 测试失败


- **[30.1] Stdio Connectivity**: Exception: TimeoutError: RPC system/status.get timed out
- **[30.2] Stdio Capabilities List**: Exception: TimeoutError: RPC config/capabilities/list timed out
- **[30.3] Stdio System Status**: Exception: TimeoutError: RPC system/status.get timed out
- **[30.4] Stdio Session List**: Exception: TimeoutError: RPC session/list timed out
- **[30.6] Stdio Auth Me**: Exception: TimeoutError: RPC auth/me timed out

---

## 4. 功能覆盖矩阵


| 模块 | 测试数 | 通过率 | 评估 |
|------|--------|--------|------|
| bot | 181 | 1.7% | 🔴 不足 |
| cli | 124 | 73.4% | 🔴 不足 |
| serve | 96 | 94.8% | 🟡 一般 |
| stdio | 6 | 16.7% | 🔴 不足 |

---

*报告生成时间: 2026-06-27 17:05:16*
