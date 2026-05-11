---
name: csrf-replay-recovery
description: "由 Security 自主管理的 CSRF token 失效识别、auth-context 合并回写与有界 replay 续链规则。"
---

# CSRF Replay Recovery Skill

本 skill 约束“请求头中的 CSRF token 过期后，如何在 Security 内部完成快速恢复重放”。

## 适用范围

支持：
- 请求头中的 CSRF token
- 响应头返回的新 token
- 响应体 JSON 中的常见 token 字段
- 基于 `replay_id` 优先、`history_entry_id` 兜底的二次 replay

不支持：
- 隐藏表单字段
- multipart body 中的 token
- URL query 中的 token
- 无依据地猜测目标 header 名

## 判定优先级

必须按以下顺序判断：
1. `AUTH_CONTEXT_STALE`
2. `CSRF_TOKEN_STALE`
3. 语义漏洞或普通失败分析

如果已经满足 auth stale，则立即停止 CSRF 处理，转入 Navigator 认证恢复链。

## 何时标记为 `CSRF_TOKEN_STALE`

只有在以下条件全部满足时，才标记 `CSRF_TOKEN_STALE`：
- 原始请求中存在 CSRF 类请求头；
- replay 返回的拒绝结果符合 token 过期语义，常见为 `403`、`419`、`422`；
- 响应中出现明确 CSRF 语义或替换 token。

强信号包括：
- 响应头出现 `Next-CSRF-Token`、`X-CSRF-Token`、`CSRF-Token`
- 响应体包含 `csrf`、`token expired`、`token mismatch`、`forgery`
- 响应 JSON 含 `csrfToken`、`csrf_token`、`nextToken`、`next_token`

以下情况不自动重试：
- 普通 `403`，但没有 CSRF 证据；
- 原始请求中没有 CSRF 请求头；
- 虽然提取到 token，但无法稳定映射回原请求头。

## Token 提取顺序

优先读取响应头：
1. `Next-CSRF-Token`
2. `X-CSRF-Token`
3. `CSRF-Token`
4. `X-Next-Token`

其次解析 JSON 响应体字段：
1. `csrf_token`
2. `csrfToken`
3. `next_token`
4. `nextToken`

提取结果至少要形成：
- `selected_token`
- `token_source`
- `target_header`
- `should_retry_with_token`

## 目标 Header 映射规则

必须用原始请求决定目标 header：
- 如果原请求中有 `X-CSRF-Token`，就覆盖 `X-CSRF-Token`
- 如果原请求中有 `CSRF-Token`，就覆盖 `CSRF-Token`
- 如果存在多个 CSRF 类 header，则选择与新 token 语义最匹配的那个

不允许在原始请求没有明确目标时，凭空构造不相关 header 名。

## Auth Context 回写流程

由于 BurpBridge auth 写入是整份覆盖：
1. 读取 `result/sessions.json`
2. 找到对应 role
3. 读取 `auth_context.headers` 与 `auth_context.cookies`
4. 确认二者足够完整，可以安全回写
5. 在内存中替换目标 CSRF header
6. 调用 `configure_authentication_context(role, headers=merged_headers, cookies=existing_cookies)`
7. 立即再次 replay

如果 snapshot 缺失或不完整：
- 返回 `AUTH_CONTEXT_SNAPSHOT_MISSING`
- 不允许做部分 auth 回写

## Replay Chain 状态

使用有界 replay chain：

```json
{
  "source_history_entry_id": "entry_001",
  "source_replay_id": "replay_001",
  "attempt_index": 1,
  "target_role": "user",
  "csrf_target_header": "X-CSRF-Token",
  "csrf_token_source": "response_header:Next-CSRF-Token",
  "csrf_refresh_applied": true,
  "last_retry_reason": "CSRF_TOKEN_STALE",
  "max_csrf_refresh_attempts": 2
}
```

以下情况终止该链：
- 已获得稳定响应
- 识别为 `AUTH_CONTEXT_STALE`
- 无法提取新 token
- snapshot 不完整
- `attempt_index >= max_csrf_refresh_attempts`

## 事件约定

本 skill 使用以下事件：
- `CSRF_TOKEN_STALE`
- `CSRF_TOKEN_REFRESHED`
- `CSRF_REFRESH_FAILED`
- `AUTH_CONTEXT_SNAPSHOT_MISSING`

语义建议：
- `CSRF_TOKEN_STALE`：识别到了可续链的 token 失效
- `CSRF_TOKEN_REFRESHED`：已合并新 token 并发起后续 replay
- `CSRF_REFRESH_FAILED`：有界重试失败，或没有安全应用路径
- `AUTH_CONTEXT_SNAPSHOT_MISSING`：需要 Navigator 先重新同步本地 auth mirror

## 与 Analyzer 的边界

Analyzer 不是 CSRF 快速恢复路径的一部分。

只有在以下条件满足后，才交给 Analyzer：
- replay 续链已完成；
- replay 响应已稳定；
- 可以进入语义漏洞分析阶段。
