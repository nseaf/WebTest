---
name: auth-context-sync
description: "Navigator 将真实浏览器认证上下文同步到 sessions.json 和 BurpBridge；Security 读取该快照，并在必要时合并新的 CSRF header 后整份回写。"
---

# Auth Context Sync Skill

当 Navigator 或 Security 需要处理 BurpBridge 认证上下文时，使用本 skill。

## 职责边界

- `Navigator`
  - 负责浏览器登录与 Cookie 提取；
  - 更新 `result/sessions.json`；
  - 在登录成功或认证恢复后，把当前 auth context 同步到 BurpBridge。
- `Security`
  - 使用同步后的 auth context 进行 replay 测试；
  - 在识别到新的 CSRF token 时，可以在本地快照中合并后整份回写。
- `Form`
  - 不负责登录与 auth-context 同步。

## 本地事实源

BurpBridge replay 所依赖的本地镜像是 `result/sessions.json`。

每个活跃 session 至少应包含：

```json
{
  "role": "admin",
  "auth_context": {
    "headers": {
      "Authorization": "Bearer token",
      "X-CSRF-Token": "csrf-value"
    },
    "cookies": {
      "session": "abc123"
    },
    "last_synced_at": "2026-05-11T09:00:00Z"
  }
}
```

如果某个 role 的 `headers` 或 `cookies` 不完整，Security 不得猜测缺失字段，而应要求重新执行 `@navigator sync_cookies`。

## Navigator 同步流程

1. Navigator 完成登录或认证恢复。
2. Navigator 从受管 `session_name` 中读取真实浏览器 Cookie。
3. Navigator 更新 `result/sessions.json` 对应 role 的记录。
4. Navigator 调用 BurpBridge：

```javascript
mcp__burpbridge__configure_authentication_context({
  role: "admin",
  headers: {
    "X-CSRF-Token": "csrf-value"
  },
  cookies: {
    session: "admin_session_abc",
    token: "admin_token_def"
  }
})
```

## 整份回写规则

`configure_authentication_context(...)` 必须被当作“整份 auth context 回写”，而不是单字段 patch。

因此：
- Security 在更新单个 auth header 前，必须先读取本地 snapshot；
- 必须先在内存中合并新的 header；
- 必须携带完整的 `headers` 与 `cookies` 整份回写；
- 不允许发送部分字段，导致其他认证字段被覆盖丢失。

## 与 CSRF 续链的关系

当 Security 在 replay 响应中发现新的 CSRF token 时：
1. 读取 `result/sessions.json` 中该 role 的 snapshot；
2. 识别原始请求中承载 CSRF token 的 header 名；
3. 只在内存中替换该 header 的值；
4. 调用 `configure_authentication_context(...)` 用合并后的完整上下文回写；
5. 立即再次 replay。

如果原始请求中并没有明确的 CSRF header，不允许自动发明一个新的目标 header。

## 加载要求

```yaml
1. Try: skill({ name: "auth-context-sync" })
2. Fallback: Read(".opencode/skills/security/auth-context-sync/SKILL.md")
3. Navigator 与 Security 必须加载本 skill
```
