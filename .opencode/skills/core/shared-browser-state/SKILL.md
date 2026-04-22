---
name: shared-browser-state
description: "共享浏览器状态机制，所有Agent通过CDP连接访问同一Chrome实例，避免页面重复加载。"
---

# Shared Browser State Skill

> 共享浏览器状态机制 — CDP连接、Session管理、状态同步

---

## 核心原理

```
所有子Agent共享同一个Chrome实例和页面状态：

┌─────────────────────────────────────────────────────────────┐
│                   Chrome 浏览器实例                           │
│                  (Navigator 创建并管理)                       │
│                                                             │
│        当前页面状态: URL, DOM, Cookie                         │
│        CDP端口: localhost:9222                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ CDP连接 (sessions.json记录)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Navigator   │    │    Scout      │    │     Form      │
│   (导航)      │    │   (分析)      │    │   (表单)      │
└───────────────┘    └───────────────┘    └───────────────┘

关键点：
- Navigator导航后，页面已加载在Chrome中
- Scout和Form通过相同CDP连接访问当前页面
- 无需重新导航，直接操作当前页面
```

---

## 连接信息获取

### sessions.json结构

```json
{
  "sessions": [
    {
      "session_id": "session_20260422",
      "account_id": "admin_001",
      "role": "admin",
      "browser_use_session": "admin_001",
      "cdp_url": "http://localhost:9222",
      "cdp_port": 9222,
      "status": "active",
      "logged_in_at": "2026-04-22T10:00:00Z",
      "auth_context": {
        "headers": {
          "Authorization": "Bearer xxx"
        },
        "cookies": {
          "session": "abc123",
          "token": "xyz789"
        }
      }
    }
  ]
}
```

### 获取CDP连接

```javascript
// 所有Agent在执行前必须获取CDP连接信息
function getCdpConnection(account_id) {
  const sessions = readJson("result/sessions.json");
  const session = sessions.sessions.find(s => s.account_id === account_id);
  
  if (!session || session.status !== "active") {
    throw new Error(`No active session for account ${account_id}`);
  }
  
  return {
    cdp_url: session.cdp_url,
    cdp_port: session.cdp_port,
    browser_use_session: session.browser_use_session,
    cookies: session.auth_context.cookies
  };
}
```

---

## browser-use连接方式

### 连接到已有Chrome实例

```bash
# 使用已有CDP连接
browser-use --session {session_name} --cdp-url {cdp_url} describe

# 示例
browser-use --session admin_001 --cdp-url http://localhost:9222 describe "当前页面内容"
```

### 执行操作

```bash
# 导航（Navigator）
browser-use --session admin_001 --cdp-url http://localhost:9222 open https://example.com

# 截图（Scout）
browser-use --session admin_001 --cdp-url http://localhost:9222 screenshot

# 填写表单（Form）
browser-use --session admin_001 --cdp-url http://localhost:9222 type "#username" "admin"

# 获取Cookie（Form）
browser-use --session admin_001 cookies get --json
```

---

## Playwright MCP连接方式

### 注意：Playwright MCP需要单独配置

```json
// .mcp.json中Playwright配置
"playwright": {
  "command": "npx",
  "args": [
    "@playwright/mcp@latest",
    "--proxy-server", "http://127.0.0.1:8080"
  ]
}
```

Playwright MCP启动的浏览器与browser-use的Chrome实例是**独立的**，不能共享CDP连接。

**推荐**：主要使用browser-use进行浏览器操作，Playwright MCP仅在需要更精细控制时使用。

---

## 状态同步机制

### Cookie同步流程

```
Form Agent登录成功
    ↓
browser-use cookies get --json
    ↓
更新 result/sessions.json (auth_context.cookies)
    ↓
mcp__burpbridge__configure_authentication_context
    ↓
Security Agent可用该角色认证进行测试
```

### Cookie获取示例

```javascript
// Form Agent执行登录后
async function syncCookies(session_name, role) {
  // 1. 获取浏览器Cookie
  const cookies = await browser-use_cookies_get(session_name);
  
  // 2. 更新sessions.json
  const sessions = readJson("result/sessions.json");
  const session = sessions.sessions.find(s => s.browser_use_session === session_name);
  session.auth_context.cookies = cookies;
  writeJson("result/sessions.json", sessions);
  
  // 3. 同步到BurpBridge
  await mcp__burpbridge__configure_authentication_context(input: {
    role: role,
    cookies: cookies
  });
}
```

---

## 多实例管理

### 实例池结构

```json
{
  "instances": [
    {
      "instance_id": "chrome_admin_001",
      "account_id": "admin_001",
      "pid": 12345,
      "cdp_port": 9222,
      "user_data_dir": "C:\\temp\\chrome-admin-001",
      "status": "running",
      "created_at": "2026-04-22T10:00:00Z"
    },
    {
      "instance_id": "chrome_user_001",
      "account_id": "user_001",
      "pid": 12346,
      "cdp_port": 9223,
      "user_data_dir": "C:\\temp\\chrome-user-001",
      "status": "running",
      "created_at": "2026-04-22T10:05:00Z"
    }
  ],
  "next_port": 9224
}
```

### 实例命名规范

| 账号 | Session名 | CDP端口 | User Data Dir |
|------|----------|---------|---------------|
| admin_001 | admin_001 | 9222 | C:\temp\chrome-admin-001 |
| user_001 | user_001 | 9223 | C:\temp\chrome-user-001 |

---

## 成对关闭原则

**重要**：browser-use session和Chrome实例必须成对关闭

```
关闭流程：
1. 关闭browser-use session
   browser-use --session {session_name} close
   
2. 获取Chrome PID（从chrome_instances.json）
   
3. 关闭指定PID的Chrome
   Windows: taskkill /PID {pid} /F
   macOS/Linux: kill {pid}
   
4. 清理记录
   - 从chrome_instances.json移除记录
   - 更新sessions.json状态为"closed"

⚠️ 禁止：taskkill /F /IM chrome.exe
   这会关闭所有Chrome实例，可能导致其他Agent的浏览器被误关
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Navigator、Scout、Form 必须加载

1. 尝试: skill({ name: "shared-browser-state" })
2. 若失败: Read("skills/core/shared-browser-state/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```