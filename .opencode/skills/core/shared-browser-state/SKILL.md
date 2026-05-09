---
name: shared-browser-state
description: "共享浏览器状态机制：受管 Chrome、项目级 attach 模式、session 复用、tab 元数据与 Cookie 同步。"
---

# Shared Browser State Skill

> 本项目的浏览器状态是“项目协议”，不是 `browser-use` 的默认行为。所有 Agent 必须按本 Skill 约束复用受管 Chrome、session 和 tab 状态。

## 核心规则

### 1. `session_name` 是浏览器操作主键

- `create_instance` 阶段由 Navigator 创建或恢复 `session_name`
- 一旦 session attach 成功，后续 `open/state/click/input/tab/cookies` 一律只使用 `--session {name}`
- `cdp_url` 仅允许用于：
  - 首次 attach：`attach_mode=bootstrap`
  - 会话修复：`attach_mode=repair`
- `explore`、`login_or_resume`、`process_complex_form` 不再把 `cdp_url` 当作常规输入

### 2. Windows 下统一走项目包装脚本

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

### 3. attach 模式定义

| 模式 | 含义 | 是否允许 `--cdp-url` |
|------|------|----------------------|
| `bootstrap` | 首次把 session 接入受管 Chrome | 允许 |
| `reuse` | 复用已 attach 的 session | 不需要 |
| `repair` | session 或页面状态异常后的修复接入 | 允许 |

## 共享状态结构

### `result/sessions.json`

```json
{
  "session_name": "admin_001",
  "account_id": "admin_001",
  "role": "admin",
  "cdp_url": "http://localhost:9222",
  "status": "active",
  "attach_mode": "reuse",
  "attach_completed": true,
  "active_tab_index": 0,
  "last_verified_url": "https://example.com/dashboard",
  "last_verified_title": "Dashboard",
  "last_auth_check_at": "2026-05-09T10:00:00Z",
  "auth_state": {
    "needs_reauth": false,
    "relogin_attempts": 0,
    "last_refresh_at": "2026-05-09T10:00:00Z"
  },
  "resume_context": {
    "task_type": "survey_site",
    "resume_target_url": "https://example.com/dashboard",
    "pending_urls": []
  },
  "burpbridge_sync_status": "success"
}
```

## Navigator 责任

- 创建受管 Chrome，并登记 `cdp_url`、`session_name`、`chrome_pid`
- 首次 attach 成功后立刻把 `attach_completed=true` 写入 `sessions.json`
- 负责首次登录、会话判活、快速复登和 Cookie 同步到 BurpBridge
- 维护 `windows.json` 中的 `known_tabs`

## Form 责任

- 仅消费 Navigator 已建立的 `session_name`
- 复杂业务表单填写和提交流程默认使用 `attach_mode=reuse`
- 遇到 `SESSION_CONFIG_CONFLICT`、新 tab、登录回跳时先按 browser-recovery 规则自恢复
- 发现登录态失效时必须把恢复上下文交回 Navigator
- 不负责创建新浏览器实例，不负责直接同步 Cookie

## 边界与禁用项

- 不要把 `--cdp-url` 当作所有 browser-use 命令的固定前缀
- 不要在 Form 中新建第二个浏览器实例
- 不要通过“关闭所有 Chrome”来做修复
- 不要仅凭记忆假设当前 tab 仍然是活动页面，必须通过 `tab list` / `state` 验证

## 加载要求

```yaml
1. 尝试: skill({ name: "shared-browser-state" })
2. 若失败: Read(".opencode/skills/core/shared-browser-state/SKILL.md")
3. 本 Skill 必须加载完成才能继续执行
```
