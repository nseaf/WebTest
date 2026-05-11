---
name: security-error-handling
description: "Security Agent 的异常处理规范，覆盖 BurpBridge 故障、AUTH_CONTEXT_STALE、CSRF 续链失败以及安全降级策略。"
---

# Security Error Handling Skill

本 skill 用于约束 Security 在 replay 测试中的异常处理与降级逻辑。

## 错误矩阵

| error_type | 处理方式 |
|---|---|
| `burpbridge_unavailable` | 通知 Coordinator，并暂停 replay 驱动测试 |
| `mongodb_unavailable` | 记录依赖故障，并做可控降级 |
| `role_not_configured` | 跳过该 role，并记录 warning |
| `replay_failed` | 记录失败并继续 |
| `AUTH_CONTEXT_STALE` | 保存断点，等待 Navigator 恢复 |
| `AUTO_SYNC_DRIFT` | 进入 repair 流程并再次校验 |
| `CSRF_TOKEN_STALE` | 在 Security 内部调用 `csrf-replay-recovery` |
| `CSRF_REFRESH_FAILED` | 终止该 replay chain，并记录终态 |
| `AUTH_CONTEXT_SNAPSHOT_MISSING` | 要求 Coordinator 调用 `@navigator sync_cookies` |

## BurpBridge 健康异常

当 BurpBridge 不可用时：
1. 创建 `BURPBRIDGE_ERROR` 异常或事件；
2. 暂停依赖 replay 的安全测试；
3. 由 Coordinator 决定是继续页面探索还是整体暂停。

## AUTH_CONTEXT_STALE 流程

1. 保存失败请求来源、目标 role、响应摘要与 cursor 状态；
2. 返回 `AUTH_CONTEXT_STALE` 和 `resume_token`；
3. 等待：
   - `@navigator refresh_auth_session`
   - `@navigator sync_cookies`
4. 从断点继续，而不是重跑整批历史记录。

## CSRF 续链失败

一旦进入 CSRF 续链：
1. 优先在 Security 内部完成重试，不切换到 Analyzer；
2. 使用 `sessions.json` 中的本地 auth snapshot 做合并；
3. 不允许部分 auth 回写。

以下情况返回 `CSRF_REFRESH_FAILED`：
- 达到重试上限；
- 没有可用新 token；
- 无法映射目标 header；
- 合并所需的 auth snapshot 不完整。

## AUTH_CONTEXT_SNAPSHOT_MISSING

当 `result/sessions.json` 中找不到完整的 `auth_context.headers` 与 `auth_context.cookies`：
1. 返回 `AUTH_CONTEXT_SNAPSHOT_MISSING`
2. 要求 Coordinator 调用 `@navigator sync_cookies`
3. 不允许尝试部分覆盖 BurpBridge auth context

## 降级策略

如果 replay 型测试无法安全继续：
1. 优先只暂停受影响的 replay chain 或 role；
2. 其余独立测试分支在安全前提下继续；
3. 在最终报告中记录失败原因与影响范围。

## 加载要求

```yaml
1. Try: skill({ name: "security-error-handling" })
2. Fallback: Read(".opencode/skills/workflow/security-error-handling/SKILL.md")
3. Security 在 replay 测试前必须加载本 skill
```
