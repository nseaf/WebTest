---
name: auth-context-sync
description: "认证上下文同步。Navigator 将真实 Cookie 同步到 BurpBridge，Security 使用该上下文进行测试。"
---

# Auth Context Sync Skill

> 认证上下文必须来自真实登录会话，不得猜测或伪造。

## 职责边界

- Form：执行登录并返回结果
- Navigator：读取 Cookie、更新 `sessions.json`、同步到 BurpBridge
- Security：消费该认证上下文进行重放与越权测试

## 同步流程

1. Form 完成登录并报告成功账号。
2. Navigator 对对应 session 执行：

```bash
browser-use --session admin_001 --json cookies get
```

Windows 建议：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 --json cookies get
```

3. Navigator 更新 `result/sessions.json` 中该账号的 `auth_context`。
4. Navigator 调用 BurpBridge：

```javascript
mcp__burpbridge__configure_authentication_context(input: {
  role: "admin",
  headers: {},
  cookies: {
    session: "admin_session_abc",
    token: "admin_token_def"
  }
})
```

## 规则

- 所有 BurpBridge MCP 调用必须使用 `input` 包装。
- Cookie 值必须来自 `browser-use --json cookies get` 的真实输出。
- 若页面登录成功但 Cookie 未变化，也应记录该状态，不要伪造字段。

## 角色管理

```javascript
mcp__burpbridge__list_configured_roles(input: {})
```

## 加载要求

```yaml
1. 尝试: skill({ name: "auth-context-sync" })
2. 若失败: Read(".opencode/skills/security/auth-context-sync/SKILL.md")
3. Navigator、Security 必须加载此 Skill
```
