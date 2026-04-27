---
name: shared-browser-state
description: "共享浏览器状态机制：受管 Chrome、项目级 CDP 接入、session 管理与 Cookie 同步。"
---

# Shared Browser State Skill

> `browser-use` 官方可以直接 `open/state/click/input/...`。本项目额外要求由 Navigator 管理 Chrome、代理和多实例状态。

## 两层规则

### 1. browser-use 官方语义

- `browser-use open <url>`
- `browser-use state`
- `browser-use click <index>`
- `browser-use input <index> "text"`
- `browser-use cookies get --json`

### 2. 本项目约束

- 为了让流量进入 Burp 代理，本项目通常先启动带 `--proxy-server` 的 Chrome。
- 为了复用浏览器状态，本项目通常让 session 连接到 Navigator 管理的 Chrome 实例。
- 因此，`--cdp-url` 是**项目接入方式**，不是 `browser-use` 的通用前提。

## 受管 Chrome 创建

Windows 示例：

```powershell
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
Start-Process $chromePath -ArgumentList @(
  "--proxy-server=http://127.0.0.1:8080",
  "--remote-debugging-port=9222",
  "--user-data-dir=C:\temp\chrome-admin-001"
)
```

关键参数：

- `--proxy-server`: Burp 代理地址
- `--remote-debugging-port`: 每个实例唯一
- `--user-data-dir`: 每个实例唯一

## 项目中的 session 接入

首次接入受管实例时可使用：

```bash
browser-use --session admin_001 --cdp-url http://localhost:9222 open https://example.com
```

接入完成后，优先只使用：

```bash
browser-use --session admin_001 state
browser-use --session admin_001 click 5
browser-use --session admin_001 input 3 "admin@example.com"
```

## 文本输出建议

Windows 下读取文本结果时优先使用包装脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

如果需要机器可解析输出，优先：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 --json state
```

## 关闭原则

- 只关闭**受管实例**。
- 先关闭对应 `browser-use` session，再关闭登记的 Chrome PID。
- 不要表达为“关闭所有 Chrome 实例”。

错误示例：

```bash
taskkill /F /IM chrome.exe
```

正确含义应为：

- 关闭指定 `session_name`
- 关闭该 session 对应的受管 Chrome 进程
- 清理 `sessions.json` / `chrome_instances.json` 中对应记录

## Cookie 同步

Cookie 同步职责属于 Navigator：

1. 登录成功后或收到 `sync_cookies` 任务
2. 执行 `browser-use --session {name} cookies get --json`
3. 更新 `result/sessions.json`
4. 调用 `mcp__burpbridge__configure_authentication_context(input: {...})`

Security 消费该认证上下文进行重放测试；Form 不直接同步 Cookie。

## 加载要求

```yaml
1. 尝试: skill({ name: "shared-browser-state" })
2. 若失败: Read(".opencode/skills/core/shared-browser-state/SKILL.md")
3. 此 Skill 必须加载完成才能继续执行
```
