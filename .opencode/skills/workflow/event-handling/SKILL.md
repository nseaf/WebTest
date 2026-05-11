---
name: event-handling
description: "Coordinator 的事件处理规范，统一认证恢复、CSRF 续链事件、survey 缺口与跨 Agent 异常路由。"
---

# Event Handling Skill

本 skill 约束 Coordinator 如何消费 subagent 返回的异常与异步事件。

## 事件类型

| event_type | source | priority | 需要用户 | 含义 |
|---|---|---|---|---|
| `CAPTCHA_DETECTED` | Form/Navigator | critical | yes | 需要人工协助 |
| `SESSION_EXPIRED` | Navigator | high | no | 浏览器 session 已失效 |
| `SESSION_STALE` | Navigator | normal | no | 浏览器 session 需要快速确认或预刷新 |
| `AUTH_CONTEXT_STALE` | Security | high | no | BurpBridge auth context 已失效 |
| `CSRF_TOKEN_STALE` | Security | normal | no | replay 需要刷新 CSRF token 后再试 |
| `CSRF_TOKEN_REFRESHED` | Security | normal | no | Security 已刷新 token 并发起后续 replay |
| `CSRF_REFRESH_FAILED` | Security | high | no | 有界 CSRF 续链失败 |
| `AUTH_CONTEXT_SNAPSHOT_MISSING` | Security | high | no | Security 需要 Navigator 先重新同步 auth context |
| `LOGIN_FAILED` | Navigator | high | no | 登录失败 |
| `COOKIE_CHANGED` | Navigator | normal | no | Cookie 已变化并重新同步 |
| `API_DISCOVERED` | Navigator | normal | no | 发现新的确认 API |
| `EXPLORATION_SUGGESTION` | Security/Analyzer | normal | no | 后续探索或测试建议 |
| `BURPBRIDGE_ERROR` | Security | high | maybe | BurpBridge 或依赖异常 |
| `EXTERNAL_DOMAIN_SKIPPED` | Navigator | normal | no | 跳过了范围外域名 |
| `ACCESS_SCOPE_BLOCKED` | Navigator | normal | no | 当前角色无法访问某模块/路由 |
| `SURVEY_GAP_DETECTED` | Navigator/Coordinator | high | no | 仍存在高价值 survey 缺口 |
| `RECOVERY_ATTEMPTED` | Navigator | normal | no | 记录了一次恢复动作 |

## 核心处理规则

### AUTH_CONTEXT_STALE

Coordinator 应立即按以下顺序执行：
1. `@security pause_on_auth_stale`
2. `@navigator refresh_auth_session`
3. `@navigator sync_cookies`
4. `@security resume_from_cursor`

Security 不得自行登录，也不得跳过断点直接重跑整批测试。

### CSRF_TOKEN_STALE

这是 Security 内部恢复事件，默认不是跨 Agent 切换。

Coordinator 应：
1. 让 Security 执行 `handle_csrf_retry`
2. 等待其返回 `CSRF_TOKEN_REFRESHED`、`CSRF_REFRESH_FAILED` 或 `AUTH_CONTEXT_SNAPSHOT_MISSING`

不允许为了首轮 token 提取而切到 Analyzer。

### AUTH_CONTEXT_SNAPSHOT_MISSING

Coordinator 应：
1. 调度 `@navigator sync_cookies`
2. 再把控制权交回 Security 继续 replay chain

这是可恢复状态，不应当直接当作登录失败处理。

### CSRF_REFRESH_FAILED

Coordinator 应：
1. 把失败记录到 findings 或 exceptions；
2. 终止该 replay chain；
3. 在安全前提下继续其他独立测试分支。

### SURVEY_GAP_DETECTED

当 gap 属于高价值缺口时，应提高优先级，尽快插入 `continue_survey`。

## 状态流转

```text
pending -> processing -> handled
                     -> failed
```

## 加载要求

```yaml
1. Try: skill({ name: "event-handling" })
2. Fallback: Read(".opencode/skills/workflow/event-handling/SKILL.md")
3. Coordinator 必须加载本 skill
```
