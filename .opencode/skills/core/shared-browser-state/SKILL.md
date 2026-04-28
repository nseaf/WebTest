---
name: shared-browser-state
description: "共享浏览器状态机制：受管 Chrome、项目级 attach 模式、session 复用、tab 元数据与 Cookie 同步。"
---

# Shared Browser State Skill

> 本项目的浏览器状态是“项目协议”，不是 `browser-use` 的默认行为。所有 Agent 必须按本 Skill 约束复用受管 Chrome、session 和 tab 状态。

## 核心规则

### 1. `session_name` 是浏览器操作主键

- `create_instance` 阶段由 Navigator 创建或恢复 `session_name`。
- 一旦 session attach 成功，后续 `open/state/click/input/tab/cookies` 一律只使用 `--session {name}`。
- `cdp_url` 仅允许用于以下场景：
  - 首次 attach：`attach_mode=bootstrap`
  - 会话修复：`attach_mode=repair`
- `explore`、`execute_logins`、`process_form` 不再把 `cdp_url` 当作常规输入。

### 2. Windows 下统一走项目包装脚本

- 所有 Windows 浏览器命令优先使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

- 包装脚本负责：
  - 统一 UTF-8 输出
  - 识别 `--attach-mode`
  - 在可复用 session 上自动忽略重复传入的 `--cdp-url`
  - 输出兼容期提示，但不污染 `browser-use --json` 的 stdout

### 3. attach 模式定义

| 模式 | 含义 | 是否允许 `--cdp-url` |
|------|------|----------------------|
| `bootstrap` | 首次把 session 接入受管 Chrome | 允许，且通常需要 |
| `reuse` | 复用已 attach 的 session | 不需要；若传入应忽略 |
| `repair` | session 或页面状态异常后的修复接入 | 允许 |

默认策略：

- 已知 session 且 `attach_completed=true` 时，默认使用 `reuse`
- 新建 session 且提供了 `cdp_url` 时，默认使用 `bootstrap`
- 明确恢复场景时使用 `repair`

## 推荐命令模式

### 首次 attach

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 `
  --attach-mode bootstrap `
  --session admin_001 `
  --cdp-url http://localhost:9222 `
  open https://example.com
```

### 复用已 attach session

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 click 5
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 tab list
```

### 修复 attach

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 `
  --attach-mode repair `
  --session admin_001 `
  --cdp-url http://localhost:9222 `
  state
```

## 共享状态结构

### `result/sessions.json`

每个 session 至少应维护以下字段：

```json
{
  "session_name": "admin_001",
  "account_id": "admin_001",
  "role": "admin",
  "cdp_url": "http://localhost:9222",
  "status": "active",
  "attach_mode": "bootstrap",
  "attach_completed": true,
  "active_tab_index": 0,
  "last_verified_url": "https://example.com/dashboard",
  "last_verified_title": "Dashboard",
  "current_url": "https://example.com/dashboard",
  "burpbridge_sync_status": "success"
}
```

规则：

- `attach_completed=true` 代表后续默认进入 `reuse`
- `active_tab_index` 记录当前活动标签页
- `last_verified_url` / `last_verified_title` 来自最近一次成功的页面核验

### `result/windows.json`

每个受管窗口至少应维护以下字段：

```json
{
  "window_id": "window_0",
  "session_name": "admin_001",
  "status": "active",
  "active_tab_index": 1,
  "known_tabs": [
    {
      "tab_index": 0,
      "tab_purpose": "login_entry",
      "url": "https://example.com/login",
      "last_seen_at": "2026-04-28T10:00:00Z"
    },
    {
      "tab_index": 1,
      "tab_purpose": "primary_exploration",
      "url": "https://example.com/dashboard",
      "last_seen_at": "2026-04-28T10:01:00Z"
    }
  ]
}
```

规则：

- `known_tabs` 用于跨步骤比对点击前后的 tab 变化
- `tab_purpose` 由 Navigator/Form 结合当前任务更新
- `last_seen_at` 用于判断新 tab、失效 tab 和恢复优先级

## Navigator 责任

- 创建受管 Chrome，并登记 `cdp_url`、`session_name`、`chrome_pid`
- 首次 attach 成功后立刻把 `attach_completed=true` 写入 `sessions.json`
- 每次成功导航后更新：
  - `active_tab_index`
  - `last_verified_url`
  - `last_verified_title`
  - `current_url`
- 维护 `windows.json` 中的 `known_tabs`
- 负责 Cookie 同步到 BurpBridge

## Form 责任

- 仅消费 Navigator 已建立的 `session_name`
- 登录、填写和提交流程默认使用 `attach_mode=reuse`
- 遇到 `SESSION_CONFIG_CONFLICT`、新 tab、登录回跳时先按 browser-recovery 规则自恢复
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
