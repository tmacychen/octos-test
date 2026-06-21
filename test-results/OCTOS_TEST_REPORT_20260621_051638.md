# Octos 统一测试报告

**测试日期**: 2026-06-20 22:31:50

**二进制**: /Volumes/AppleData/octos/target/release/octos

---

## 1. 总体结果


| 模块 | 总计 | 通过 | 失败 | 跳过 | 通过率 | 状态 |
|------|------|------|------|------|--------|------|
| bot | 214 | 0 | 214 | 0 | 0.0% | ❌ |
| cli | 123 | 41 | 82 | 0 | 33.3% | ❌ |
| serve | 24 | 20 | 4 | 0 | 83.3% | ❌ |
| stdio | 6 | 0 | 6 | 0 | 0.0% | ❌ |
| **总计** | **367** | **61** | **306** | **0** | **16.6%** | **❌** |

---

## 2. 各模块详细结果

### 2.4 Bot 测试

**总计**: 214 | **通过**: 0 | **失败**: 214 | **跳过**: 0 | **通过率**: 0.0%

| 通道 | 通过 | 失败 | 总计 | 状态 |
|------|------|------|------|------|
| discord | 0 | 4 | 4 | ❌ |
| feishu | 0 | 40 | 40 | ❌ |
| matrix | 0 | 30 | 30 | ❌ |
| qq-bot | 0 | 20 | 20 | ❌ |
| slack | 0 | 49 | 49 | ❌ |
| telegram | 0 | 1 | 1 | ❌ |
| twilio | 0 | 21 | 21 | ❌ |
| wechat | 0 | 1 | 1 | ❌ |
| wecom | 0 | 1 | 1 | ❌ |
| wecom-bot | 0 | 18 | 18 | ❌ |
| whatsapp | 0 | 29 | 29 | ❌ |

### 2.1 CLI 测试

**总计**: 123 | **通过**: 41 | **失败**: 82 | **跳过**: 0 | **通过率**: 33.3%

| 编号 | 分类 | 名称 | 状态 | 耗时 |
|------|------|------|------|------|
| 1.1 | CLI | help command | PASS | 0.01s |
| 2.1 | Chat | chat help | PASS | 0.01s |
| 2.2 | Chat | quit message | PASS | 2.37s |
| 2.3 | Chat | colon q message | PASS | 2.72s |
| 2.4 | Chat | slash quit message | PASS | 2.16s |
| 2.5 | Chat | single message | FAIL | 15.01s |
| 2.6 | Chat | max iterations | FAIL | 15.01s |
| 2.7 | Chat | verbose mode | FAIL | 15.01s |
| 2.8 | Chat | no retry | FAIL | 15.01s |
| 2.9 | Chat | cwd option | FAIL | 15.02s |
| 2.10 | Chat | data dir option | FAIL | 0.02s |
| 2.11 | Chat | streaming output | FAIL | 15.01s |
| 2.12 | Chat | model claude | FAIL | 0.62s |
| 2.13 | Chat | model gpt4o | PASS | 0.56s |
| 2.14 | Chat | provider anthropic | FAIL | 0.59s |
| 2.15 | Chat | provider openai | FAIL | 0.60s |
| 2.16 | Chat | provider gemini | FAIL | 0.60s |
| 2.17 | Chat | provider deepseek | FAIL | 0.63s |
| 2.18 | Chat | provider ollama | FAIL | 0.57s |
| 2.19 | Chat | provider moonshot | FAIL | 0.58s |
| 2.20 | Chat | provider dashscope | FAIL | 0.58s |
| 2.21 | Chat | provider minimax | FAIL | 0.57s |
| 2.22 | Chat | provider groq | FAIL | 0.57s |
| 2.23 | Chat | custom base url | FAIL | 7.07s |
| 2.25 | Chat | deepseek full config | FAIL | 0.36s |
| 2.26 | Chat | save memory | FAIL | 15.01s |
| 2.27 | Chat | recall memory | FAIL | 15.01s |
| 2.28 | Chat | 7 day window | FAIL | 15.01s |
| 2.29 | Chat | hybrid search fallback | FAIL | 15.01s |
| 3.1 | Tools | read file | FAIL | 15.02s |
| 3.2 | Tools | write file | FAIL | 15.02s |
| 3.3 | Tools | shell echo | FAIL | 15.01s |
| 3.4 | Tools | glob rust files | FAIL | 15.01s |
| 3.5 | Tools | grep fn main | FAIL | 15.01s |
| 3.6 | Tools | list directory | FAIL | 15.01s |
| 3.7 | Tools | web search | FAIL | 15.01s |
| 3.8 | Tools | web fetch | FAIL | 15.02s |
| 3.9 | Tools | git status | FAIL | 15.02s |
| 3.10 | Tools | parallel read | FAIL | 15.02s |
| 3.11 | Tools | edit file | FAIL | 15.02s |
| 3.12 | Tools | context filter | FAIL | 15.02s |
| 3.13 | Tools | spawn only | FAIL | 15.01s |
| 4.1 | Security | no api key error | PASS | 0.03s |
| 4.2 | Security | dangerous command rm rf | FAIL | 15.01s |
| 4.3 | Security | dangerous command sudo | FAIL | 15.01s |
| 4.4 | Security | fork bomb block | FAIL | 15.01s |
| 4.5 | Security | dd block | FAIL | 15.01s |
| 4.6 | Security | mkfs block | FAIL | 15.02s |
| 4.7 | Security | ssrf localhost | FAIL | 15.02s |
| 4.8 | Security | ssrf private ip | FAIL | 15.01s |
| 4.9 | Security | ssrf aws metadata | FAIL | 15.01s |
| 4.10 | Security | ssrf ipv6 loopback | FAIL | 15.02s |
| 4.11 | Security | ssrf ipv4 mapped | FAIL | 15.01s |
| 4.12 | Security | ssrf dns fail | FAIL | 15.02s |
| 4.13 | Security | prompt injection | FAIL | 15.02s |
| 4.14 | Security | env block | FAIL | 15.01s |
| 4.15 | Security | credential sanitize openai | PASS | 15.01s |
| 4.16 | Security | credential sanitize aws | PASS | 15.02s |
| 4.17 | Security | credential sanitize github | PASS | 15.02s |
| 5.1 | Init | init defaults | PASS | 0.02s |
| 6.1 | Status | status | PASS | 0.01s |
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
| 9.3 | Skills | skills search | PASS | 0.62s |
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
| 16.2 | Office | office extract | FAIL | 0.01s |
| 16.3 | Office | office pack | FAIL | 0.01s |
| 16.4 | Office | office clean | FAIL | 0.01s |
| 16.5 | Office | office thumbnail | FAIL | 0.01s |
| 17.1 | Account | account list | PASS | 0.01s |
| 18.1 | Admin | admin tenant list | PASS | 0.01s |
| 19.1 | Tools | tool policy deny | FAIL | 15.01s |
| 19.2 | Tools | tool policy allow | FAIL | 15.01s |
| 19.3 | Tools | provider policy gemini | FAIL | 15.02s |
| 20.1 | Memory | episode storage | FAIL | 15.02s |
| 20.2 | Memory | long term memory edit | FAIL | 15.01s |
| 20.3 | Memory | entity bank | FAIL | 15.01s |
| 20.4 | Memory | hybrid search fallback | FAIL | 15.01s |
| 21.2 | Provider | sub providers | FAIL | 15.01s |
| 22.1 | Extension | skill override | PASS | 0.02s |
| 22.2 | Extension | skill availability | PASS | 0.01s |
| 22.3 | Extension | plugin sha256 | FAIL | 15.01s |
| 22.4 | Extension | mcp stdio | FAIL | 15.01s |
| 22.5 | Extension | mcp http | FAIL | 15.01s |
| 22.6 | Extension | gating check | FAIL | 15.01s |
| 24.1 | Config | config priority | FAIL | 0.58s |
| 24.2 | Config | config parse fail | FAIL | 15.01s |
| 24.3 | Hooks | before tool call hook | FAIL | 15.01s |
| 24.4 | Hooks | after tool call hook | FAIL | 15.01s |
| 24.5 | Hooks | hook timeout | FAIL | 15.01s |
| 24.6 | Hooks | circuit breaker | FAIL | 15.01s |
| 24.7 | Config | feature flags | PASS | 0.02s |
| 25.1 | Loop | loop detection length 1 | FAIL | 15.01s |
| 25.2 | Loop | loop detection length 2 | FAIL | 15.01s |
| 25.5 | Loop | context compaction | FAIL | 15.01s |
| 26.1 | Security | base64 uri sanitize | FAIL | 15.02s |
| 26.2 | Security | sandbox macos | FAIL | 15.02s |
| 26.3 | Security | sandbox linux | FAIL | 15.01s |
| 26.4 | Security | sbpl injection | FAIL | 15.02s |
| 27.1 | Gateway | jsonl persistence | PASS | 0.02s |
| 28.1 | ToolPolicy | tool deny policy | FAIL | 15.01s |
| 28.2 | ToolPolicy | tool allow policy | FAIL | 15.02s |
| 28.3 | ToolPolicy | provider policy | FAIL | 0.59s |
| 28.4 | ToolPolicy | context filter | FAIL | 15.01s |

### 2.2 Serve 测试

**总计**: 24 | **通过**: 20 | **失败**: 4 | **跳过**: 0 | **通过率**: 83.3%

| 编号 | 名称 | 状态 | 耗时 |
|------|------|------|------|
| 8.1 | Server Startup | PASS | 0.01s |
| 8.2 | Version Endpoint | PASS | 0.01s |
| 8.3 | Metrics Endpoint | PASS | 0.01s |
| 8.4 | Auth Token Required | PASS | 0.01s |
| 8.5 | Auth Invalid Token | PASS | 0.01s |
| 8.6 | Dashboard Web UI | PASS | 0.01s |
| 8.7 | WS Connection + Hello | PASS | 0.03s |
| 8.8 | WS system/status.get | PASS | 0.00s |
| 8.9 | WS session/list | PASS | 0.00s |
| 8.10 | WS session/open + turn/start | PASS | 0.00s |
| 8.11 | WS session/delete | PASS | 0.00s |
| 8.14 | WS session/snapshot | PASS | 0.01s |
| 8.15 | WS session/messages_page | FAIL | 0.00s |
| 8.16 | WS session/status.get | PASS | 0.01s |
| 8.17 | WS session/title.set | FAIL | 0.01s |
| 8.18 | WS content/list | PASS | 0.00s |
| 8.19 | WS turn/interrupt | PASS | 1.51s |
| 8.12 | Bind Address (0.0.0.0) | PASS | 1.10s |
| 8.13 | Default Bind (127.0.0.1) | PASS | 0.01s |
| 16.1 | Notification Session Opened | PASS | 1.02s |
| 16.2 | Notification Turn Started | FAIL | 5.03s |
| 16.3 | Notification Turn Completed | FAIL | 10.02s |
| 16.4 | Notification Turn Error | PASS | 0.02s |
| 16.5 | Notification Agent Updated | PASS | 0.00s |

### 2.3 Stdio 测试

**总计**: 6 | **通过**: 0 | **失败**: 6 | **跳过**: 0 | **通过率**: 0.0%

| 编号 | 名称 | 状态 | 耗时 |
|------|------|------|------|
| 30.1 | Stdio Connectivity | FAIL | 315.02s |
| 30.2 | Stdio Capabilities List | FAIL | 314.98s |
| 30.3 | Stdio System Status | FAIL | 315.01s |
| 30.4 | Stdio Session List | FAIL | 315.01s |
| 30.5 | Stdio Session Open | FAIL | 315.04s |
| 30.6 | Stdio Auth Me | FAIL | 315.01s |

---

## 3. 失败测试详情

### bot 测试失败


- **[ALL_TESTS_SKIPPED] ALL_TESTS_SKIPPED**: 
- **[[31m[1m________ ERROR at setup of TestDiscordLLMMessages.test_regular_message _________[0m] [31m[1m________ ERROR at setup of TestDiscordLLMMessages.test_regular_message _________[0m**: 
- **[[31m[1m________ ERROR at setup of TestDiscordLLMMessages.test_chinese_message _________[0m] [31m[1m________ ERROR at setup of TestDiscordLLMMessages.test_chinese_message _________[0m**: 
- **[[31mERROR[0m bot_mock_test/test_discord.py::[1mTestDiscordLLMMessages::test_regular_message[0m - AssertionError: Bot 未在 30s 内回复 '/new'] [31mERROR[0m bot_mock_test/test_discord.py::[1mTestDiscordLLMMessages::test_regular_message[0m - AssertionError: Bot 未在 30s 内回复 '/new'**: 
- **[[31mERROR[0m bot_mock_test/test_discord.py::[1mTestDiscordLLMMessages::test_chinese_message[0m - AssertionError: Bot 未在 30s 内回复 '/new'] [31mERROR[0m bot_mock_test/test_discord.py::[1mTestDiscordLLMMessages::test_chinese_message[0m - AssertionError: Bot 未在 30s 内回复 '/new'**: 
- **[test_new_creates_session] test_new_creates_session**: 
- **[test_new_with_invalid_name] test_new_with_invalid_name**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_switch_session] test_switch_session**: 
- **[test_back_to_previous] test_back_to_previous**: 
- **[test_delete_session] test_delete_session**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_very_long_message] test_very_long_message**: 
- **[test_special_characters] test_special_characters**: 
- **[test_unicode_emoji] test_unicode_emoji**: 
- **[test_html_formatted_message] test_html_formatted_message**: 
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
- **[test_profile_session_isolation] test_profile_session_isolation**: 
- **[test_queue_mode_per_profile] test_queue_mode_per_profile**: 
- **[test_rapid_messages] test_rapid_messages**: 
- **[test_concurrent_rooms] test_concurrent_rooms**: 
- **[test_message_with_mention] test_message_with_mention**: 
- **[test_message_with_code_block] test_message_with_code_block**: 
- **[test_message_with_link] test_message_with_link**: 
- **[test_duplicate_event_id_ignored] test_duplicate_event_id_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
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
- **[test_rapid_messages] test_rapid_messages**: 
- **[test_who_are_you] test_who_are_you**: 
- **[test_hello_greeting] test_hello_greeting**: 
- **[test_chinese_greeting] test_chinese_greeting**: 
- **[test_abort_with_whitespace] test_abort_with_whitespace**: 
- **[test_abort_multilanguage[english_stop]] test_abort_multilanguage[english_stop]**: 
- **[test_abort_multilanguage[chinese_stop]] test_abort_multilanguage[chinese_stop]**: 
- **[test_abort_multilanguage[japanese_stop]] test_abort_multilanguage[japanese_stop]**: 
- **[test_abort_multilanguage[russian_stop]] test_abort_multilanguage[russian_stop]**: 
- **[test_duplicate_event_id_ignored] test_duplicate_event_id_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
- **[test_new_default] test_new_default**: 
- **[test_new_named] test_new_named**: 
- **[test_new_invalid_name] test_new_invalid_name**: 
- **[test_switch_to_existing] test_switch_to_existing**: 
- **[test_switch_to_default] test_switch_to_default**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_back_returns_session] test_back_returns_session**: 
- **[test_back_with_history] test_back_with_history**: 
- **[test_delete_session] test_delete_session**: 
- **[test_delete_no_name] test_delete_no_name**: 
- **[test_soul_show_default] test_soul_show_default**: 
- **[test_soul_set] test_soul_set**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_soul_reset] test_soul_reset**: 
- **[test_adaptive_no_router] test_adaptive_no_router**: 
- **[test_queue_show] test_queue_show**: 
- **[test_queue_set_followup] test_queue_set_followup**: 
- **[test_queue_set_invalid] test_queue_set_invalid**: 
- **[test_status_show] test_status_show**: 
- **[test_reset_command] test_reset_command**: 
- **[test_unknown_command_help] test_unknown_command_help**: 
- **[test_two_users_independent] test_two_users_independent**: 
- **[test_abort_with_whitespace] test_abort_with_whitespace**: 
- **[test_abort_multilanguage[english_stop]] test_abort_multilanguage[english_stop]**: 
- **[test_abort_multilanguage[chinese_stop]] test_abort_multilanguage[chinese_stop]**: 
- **[test_abort_multilanguage[japanese_stop]] test_abort_multilanguage[japanese_stop]**: 
- **[test_abort_multilanguage[russian_stop]] test_abort_multilanguage[russian_stop]**: 
- **[test_regular_message] test_regular_message**: 
- **[test_profile_session_isolation] test_profile_session_isolation**: 
- **[test_concurrent_session_creation] test_concurrent_session_creation**: 
- **[test_stream_edit_creates_edit_operations] test_stream_edit_creates_edit_operations**: 
- **[test_edit_preserves_message_identity] test_edit_preserves_message_identity**: 
- **[test_large_message_handling] test_large_message_handling**: 
- **[test_session_file_size_limit_enforcement] test_session_file_size_limit_enforcement**: 
- **[test_session_created_on_first_message] test_session_created_on_first_message**: 
- **[test_short_idle_session_cleanup] test_short_idle_session_cleanup**: 
- **[test_jsonl_file_created_after_message] test_jsonl_file_created_after_message**: 
- **[test_jsonl_entries_have_required_fields] test_jsonl_entries_have_required_fields**: 
- **[test_duplicate_message_id_ignored] test_duplicate_message_id_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
- **[test_new_default] test_new_default**: 
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
- **[test_subscription_state] test_subscription_state**: 
- **[test_multiple_connections_tracked] test_multiple_connections_tracked**: 
- **[test_new_default] test_new_default**: 
- **[test_sessions_list] test_sessions_list**: 
- **[test_help] test_help**: 
- **[test_clear_resets_session] test_clear_resets_session**: 
- **[test_soul_show] test_soul_show**: 
- **[test_queue_show] test_queue_show**: 
- **[test_status] test_status**: 
- **[test_simple_greeting] test_simple_greeting**: 
- **[test_chinese_message] test_chinese_message**: 
- **[test_llm_meaningful_reply] test_llm_meaningful_reply**: 
- **[test_stream_chunks_received] test_stream_chunks_received**: 
- **[test_stream_final_content_nonempty] test_stream_final_content_nonempty**: 
- **[test_multiple_users_isolated] test_multiple_users_isolated**: 
- **[test_duplicate_message_id_ignored] test_duplicate_message_id_ignored**: 
- **[test_allowed_sender_gets_reply] test_allowed_sender_gets_reply**: 
- **[test_ws_reconnect] test_ws_reconnect**: 
- **[unknown] unknown failure**: 
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


- **[2.5] single message**: 
- **[2.6] max iterations**: 
- **[2.7] verbose mode**: 
- **[2.8] no retry**: 
- **[2.9] cwd option**: 
- **[2.10] data dir option**: 
- **[2.11] streaming output**: 
- **[2.12] model claude**: 
- **[2.14] provider anthropic**: 
- **[2.15] provider openai**: 
- **[2.16] provider gemini**: 
- **[2.17] provider deepseek**: 
- **[2.18] provider ollama**: 
- **[2.19] provider moonshot**: 
- **[2.20] provider dashscope**: 
- **[2.21] provider minimax**: 
- **[2.22] provider groq**: 
- **[2.23] custom base url**: 
- **[2.25] deepseek full config**: 
- **[2.26] save memory**: 
- **[2.27] recall memory**: 
- **[2.28] 7 day window**: 
- **[2.29] hybrid search fallback**: 
- **[3.1] read file**: 
- **[3.2] write file**: 
- **[3.3] shell echo**: 
- **[3.4] glob rust files**: 
- **[3.5] grep fn main**: 
- **[3.6] list directory**: 
- **[3.7] web search**: 
- **[3.8] web fetch**: 
- **[3.9] git status**: 
- **[3.10] parallel read**: 
- **[3.11] edit file**: 
- **[3.12] context filter**: 
- **[3.13] spawn only**: 
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
- **[4.12] ssrf dns fail**: 
- **[4.13] prompt injection**: 
- **[4.14] env block**: 
- **[16.2] office extract**: 
- **[16.3] office pack**: 
- **[16.4] office clean**: 
- **[16.5] office thumbnail**: 
- **[19.1] tool policy deny**: 
- **[19.2] tool policy allow**: 
- **[19.3] provider policy gemini**: 
- **[20.1] episode storage**: 
- **[20.2] long term memory edit**: 
- **[20.3] entity bank**: 
- **[20.4] hybrid search fallback**: 
- **[21.2] sub providers**: 
- **[22.3] plugin sha256**: 
- **[22.4] mcp stdio**: 
- **[22.5] mcp http**: 
- **[22.6] gating check**: 
- **[24.1] config priority**: 
- **[24.2] config parse fail**: 
- **[24.3] before tool call hook**: 
- **[24.4] after tool call hook**: 
- **[24.5] hook timeout**: 
- **[24.6] circuit breaker**: 
- **[25.1] loop detection length 1**: 
- **[25.2] loop detection length 2**: 
- **[25.5] context compaction**: 
- **[26.1] base64 uri sanitize**: 
- **[26.2] sandbox macos**: 
- **[26.3] sandbox linux**: 
- **[26.4] sbpl injection**: 
- **[28.1] tool deny policy**: 
- **[28.2] tool allow policy**: 
- **[28.3] provider policy**: 
- **[28.4] context filter**: 

### serve 测试失败


- **[8.15] WS session/messages_page**: session/messages_page error: session/messages_page: REST handler not configured on this server
- **[8.17] WS session/title.set**: session/title.set error: unknown session: test-title-5354633f
- **[16.2] Notification Turn Started**: Exception: TimeoutError: 
- **[16.3] Notification Turn Completed**: Exception: TimeoutError: 

### stdio 测试失败


- **[30.1] Stdio Connectivity**: Exception: TimeoutError: 
- **[30.2] Stdio Capabilities List**: Exception: TimeoutError: 
- **[30.3] Stdio System Status**: Exception: TimeoutError: 
- **[30.4] Stdio Session List**: Exception: TimeoutError: 
- **[30.5] Stdio Session Open**: Exception: TimeoutError: 
- **[30.6] Stdio Auth Me**: Exception: TimeoutError: 

---

## 4. 功能覆盖矩阵


| 模块 | 测试数 | 通过率 | 评估 |
|------|--------|--------|------|
| bot | 214 | 0.0% | 🔴 不足 |
| cli | 123 | 33.3% | 🔴 不足 |
| serve | 24 | 83.3% | 🟡 一般 |
| stdio | 6 | 0.0% | 🔴 不足 |

---

*报告生成时间: 2026-06-21 05:16:38*
