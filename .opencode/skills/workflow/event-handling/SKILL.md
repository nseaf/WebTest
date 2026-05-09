---
name: event-handling
description: "事件处理规范，定义事件类型、优先级、处理流程。支持认证失效、测绘缺口、外域跳转和恢复尝试事件。"
---

# Event Handling Skill

> 事件处理规范：让 Coordinator 能稳定消费 Navigator/Form/Security 返回的异常、建议和恢复证据。

## 事件类型定义

| 事件类型 | 来源 Agent | 优先级 | 需要用户操作 | 说明 |
|----------|-----------|--------|--------------|------|
| `CAPTCHA_DETECTED` | Form/Navigator | critical | 是 | 检测到验证码 |
| `SESSION_EXPIRED` | Navigator | high | 否 | 浏览器会话已过期 |
| `SESSION_STALE` | Navigator | normal | 否 | 浏览器会话需要快速确认或预刷新 |
| `AUTH_CONTEXT_STALE` | Security | high | 否 | Burp 重放使用的认证上下文已失效 |
| `LOGIN_FAILED` | Navigator | high | 否 | 登录失败 |
| `COOKIE_CHANGED` | Navigator | normal | 否 | Cookie 已变化 |
| `API_DISCOVERED` | Navigator | normal | 否 | 发现已证实 API |
| `EXPLORATION_SUGGESTION` | Security/Analyzer | normal | 否 | 测试建议 |
| `BURPBRIDGE_ERROR` | Security | high | 否 | BurpBridge 异常 |
| `EXTERNAL_DOMAIN_SKIPPED` | Navigator | normal | 否 | 命中外域，已跳过并回退 |
| `ACCESS_SCOPE_BLOCKED` | Navigator | normal | 否 | 当前角色不可达某模块/入口 |
| `SURVEY_GAP_DETECTED` | Navigator/Coordinator | high | 否 | 发现高价值测绘缺口 |
| `RECOVERY_ATTEMPTED` | Navigator | normal | 否 | 记录一轮恢复动作与结果 |

## 核心处理流程

### `AUTH_CONTEXT_STALE`

1. 读取目标角色、history_entry_id、当前游标、失败响应摘要
2. 标记为 high 优先级事件
3. 通知 Coordinator 立即执行：
   - `@security pause_on_auth_stale`
   - `@navigator refresh_auth_session`
   - `@navigator sync_cookies`
   - `@security resume_from_cursor`
4. 不允许 Security 自行登录或跳过断点直接重跑整批测试

### `EXTERNAL_DOMAIN_SKIPPED`

1. 读取外域 URL、来源页面、回退动作
2. 标记为非致命事件
3. 将该入口从当前导航队列移出
4. 如存在同模块替代入口，生成 `EXPLORATION_SUGGESTION`
5. 记录到 `site_survey.external_domains`

### `ACCESS_SCOPE_BLOCKED`

1. 记录当前角色、模块、入口 URL
2. 标记 `role_access_matrix` 中该角色为 `blocked|hidden|readonly`
3. 如仍有其他角色未验证，创建 `SURVEY_GAP_DETECTED`
4. 不将该模块记为“未发现”

### `SURVEY_GAP_DETECTED`

1. 读取 gap 的模块、子模块、优先级、原因
2. 更新 `progress.modules[].survey_status`
3. 如果优先级为 `high/critical`，插队给下一轮 `continue_survey`

### `RECOVERY_ATTEMPTED`

1. 记录问题类型、尝试次数、恢复动作、结果
2. 如果两轮恢复后仍失败，升级为上报建议
3. 如果已恢复，保持 normal 事件，不打断主流程

## 状态流转

```text
pending -> processing -> handled
                     └-> failed
```

## 加载要求

```yaml
1. 尝试: skill({ name: "event-handling" })
2. 若失败: Read(".opencode/skills/workflow/event-handling/SKILL.md")
3. Coordinator 必须加载本 Skill
```
