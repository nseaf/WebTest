---
name: page-navigation
description: "页面导航方法论，Navigator Agent使用。基于 browser-use CLI 的 URL 导航、状态读取、索引点击和深度控制。"
---

# Page Navigation Skill

> 页面导航以 `browser-use` 官方 CLI 语义为准；本项目只在其之上补充受管 Chrome、代理和多实例约束。

## 核心原则

- 先 `state`，再交互。
- 优先使用 `open` 直接导航到明确 URL。
- 需要点击时，先从 `state` 读取元素索引，再执行 `click <index>`。
- 不使用伪原语，也不把选择器式点击当作主工作流。
- Windows 下读取文本时优先使用 `scripts/browser-use-utf8.ps1`。

## 本项目中的导航流程

1. Navigator 接收目标 URL 或待访问链接。
2. 校验是否同域、是否已访问、是否命中忽略模式。
3. 使用 `browser-use` 打开页面或点击索引元素。
4. 使用 `state`、`get title`、必要时 `get html` 验证结果。
5. 记录页面访问、更新进度、必要时通知后续分析或安全测试。

## browser-use 命令工作流

### Windows 推荐写法

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

### 直接 URL 导航

```bash
browser-use --session admin_001 open https://example.com/dashboard
browser-use --session admin_001 get title
browser-use --session admin_001 state
```

### 索引式点击导航

```bash
browser-use --session admin_001 state
browser-use --session admin_001 click 5
browser-use --session admin_001 wait text "个人中心"
browser-use --session admin_001 get title
```

### 读取页面文本或结构

```bash
browser-use --session admin_001 state
browser-use --session admin_001 get html
browser-use --session admin_001 eval "location.href"
```

## 项目约束：受管 Chrome 与 CDP

- `browser-use` 官方默认支持直接 `open/state/click/input/...`。
- 本项目为了让流量进入 Burp 代理，并让多个 Agent 共享同一浏览器状态，通常由 Navigator 先启动带代理的 Chrome，再把 session 接到该实例。
- 因此，`--cdp-url` 是**本项目的接入方式**，不是 `browser-use` 的通用前提。
- 一旦 session 已建立，后续操作优先只传 `--session {name}`。

## URL 过滤与深度控制

默认策略：

- 仅访问目标域名。
- 跳过登出链接、下载链接、静态资源链接。
- 对重复 URL 去重。
- 受 `max_pages` 和 `max_depth` 约束。

推荐优先级：

- 高优先级：登录、管理、个人中心、设置、审批、数据导出
- 中优先级：列表页、详情页、查询页
- 低优先级：帮助、关于、联系页

## 受支持的证据来源

- 页面元素：`state`
- 当前 URL：`eval "location.href"`
- 标题：`get title`
- 页面结构：`get html`
- 视觉确认：`screenshot`

不要使用不存在的 `browser_click(...)` 之类伪接口。

## Cookie 变化检查

- Navigator 可以在关键导航后执行 `browser-use --session {name} cookies get --json`。
- 如果 Cookie 与 `result/sessions.json` 中登记的认证上下文不同，应记录 `COOKIE_CHANGED` 并在需要时触发同步。
- Cookie 同步职责属于 Navigator，不属于 Form。

## 加载要求

```yaml
1. 尝试: skill({ name: "page-navigation" })
2. 若失败: Read(".opencode/skills/browser/page-navigation/SKILL.md")
3. 此 Skill 必须加载完成才能继续执行
```
