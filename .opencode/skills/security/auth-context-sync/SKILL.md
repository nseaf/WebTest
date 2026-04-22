---
name: auth-context-sync
description: "认证上下文同步，Cookie同步到BurpBridge的方法论。Form Agent登录后同步，Security Agent测试时使用。"
---

# Auth Context Sync Skill

> 认证上下文同步 — Cookie获取、同步到BurpBridge、角色管理

---

## 核心流程

```
┌─────────────────────────────────────────────────────────────┐
│  认证上下文同步流程                                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. Form Agent 执行登录                                       │
│     - 填写表单                                               │
│     - 提交登录                                               │
│     - 等待登录成功                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 获取浏览器 Cookie                                         │
│     browser-use cookies get --json                           │
│     或 Playwright browser_context.cookies()                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 更新 result/sessions.json                                │
│     auth_context.cookies = {session: xxx, token: yyy}        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 同步到 BurpBridge                                         │
│     mcp__burpbridge__configure_authentication_context        │
│     或 mcp__burpbridge__import_playwright_cookies            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Security Agent 可使用该角色认证进行重放测试                 │
│     replay_http_request_as_role(role: "admin")               │
└─────────────────────────────────────────────────────────────┘
```

---

## BurpBridge MCP调用规范

### 重要：必须使用input参数包装

```javascript
// ✓ 正确调用方式
mcp__burpbridge__configure_authentication_context(input: {
  role: "admin",
  headers: {
    "Authorization": "Bearer admin_token_xxx"
  },
  cookies: {
    "session": "admin_session_abc",
    "token": "admin_token_def"
  }
})

// ✗ 错误调用方式
mcp__burpbridge__configure_authentication_context({ role: "admin" })
// 缺少input包装，会导致调用失败
```

### 其他正确调用示例

```javascript
// 无参数工具
mcp__burpbridge__list_configured_roles(input: {})

// 带参数工具
mcp__burpbridge__sync_proxy_history_with_filters(input: {
  host: "www.example.com",
  require_response: true
})

mcp__burpbridge__replay_http_request_as_role(input: {
  history_entry_id: "65f1a2b3c4d5e6f7",
  target_role: "guest"
})
```

---

## Cookie获取方法

### 方法1：browser-use CLI

```bash
# 获取Cookie（JSON格式）
browser-use --session {session_name} cookies get --json

# 输出格式
{
  "cookies": [
    {
      "name": "session",
      "value": "abc123",
      "domain": ".example.com",
      "path": "/",
      "expires": 1234567890
    },
    {
      "name": "token",
      "value": "xyz789",
      "domain": ".example.com",
      "path": "/"
    }
  ]
}
```

### 方法2：Playwright MCP

```javascript
// 获取所有Cookie（Playwright格式）
const cookies = await browser_context.cookies();

// Playwright Cookie格式
[
  {
    "name": "session",
    "value": "abc123",
    "domain": ".example.com",
    "path": "/",
    "expires": 1234567890,
    "httpOnly": true,
    "secure": true
  }
]
```

---

## 同步到BurpBridge

### 使用configure_authentication_context

```javascript
// 将Cookie同步到BurpBridge角色配置
async function syncCookiesToBurp(role, cookies, headers = {}) {
  // 转换Cookie格式为对象
  const cookieObj = {};
  for (const cookie of cookies) {
    cookieObj[cookie.name] = cookie.value;
  }
  
  await mcp__burpbridge__configure_authentication_context(input: {
    role: role,
    headers: headers,
    cookies: cookieObj
  });
}
```

### 使用import_playwright_cookies（Playwright专用）

```javascript
// 从Playwright浏览器导入Cookie
async function importPlaywrightCookies(role, cookies) {
  await mcp__burpbridge__import_playwright_cookies(input: {
    role: role,
    cookies: cookies,  // Playwright格式
    merge_with_existing: true
  });
}
```

---

## 角色管理

### 列出已配置角色

```javascript
const roles = await mcp__burpbridge__list_configured_roles(input: {});
// 返回: { status: "ok", roles: ["admin", "user", "guest"] }
```

### 删除角色配置

```javascript
await mcp__burpbridge__delete_authentication_context(input: {
  role: "guest"
});
```

---

## 完整同步示例

### Form Agent登录后同步

```javascript
// Form Agent执行登录后的完整流程
async function loginAndSync(account_id, role) {
  // 1. 执行登录
  await browser-use_form_submit(session_name, account_id);
  
  // 2. 验证登录成功
  const loginStatus = await checkLoginSuccess(session_name);
  if (!loginStatus) {
    throw new Error("登录失败");
  }
  
  // 3. 获取Cookie
  const cookies = await browser-use_cookies_get(session_name);
  
  // 4. 更新sessions.json
  const sessions = readJson("result/sessions.json");
  const session = sessions.sessions.find(s => s.account_id === account_id);
  session.auth_context = {
    headers: {},
    cookies: cookies
  };
  session.status = "active";
  session.logged_in_at = Date.now();
  writeJson("result/sessions.json", sessions);
  
  // 5. 同步到BurpBridge
  await mcp__burpbridge__configure_authentication_context(input: {
    role: role,
    cookies: cookies
  });
  
  // 6. 创建事件通知
  createEvent("COOKIE_SYNCED", {
    priority: "normal",
    payload: { account_id, role }
  });
}
```

---

## Headers同步（可选）

除了Cookie，还可以同步Headers：

```javascript
// 同步Authorization Header
await mcp__burpbridge__configure_authentication_context(input: {
  role: "admin",
  headers: {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIs...",
    "X-Auth-Token": "admin_token_xxx"
  },
  cookies: {
    "session": "admin_session_abc"
  }
});
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Form、Security 必须加载

1. 尝试: skill({ name: "auth-context-sync" })
2. 若失败: Read("skills/security/auth-context-sync/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```