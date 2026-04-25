---
name: shared-browser-state
description: "共享浏览器状态机制：Chrome实例创建 → browser-use CDP连接 → 多Agent共享"
---

# Shared Browser State Skill

> 共享浏览器状态机制 — Chrome实例创建、CDP连接、Session管理、状态同步

---

## 核心原理

```
工作流程：Chrome创建 → CDP连接 → browser-use操作

┌─────────────────────────────────────────────────────────────┐
│  Step 1: 创建Chrome实例（必须配置代理）                       │
│                                                             │
│  Chrome --proxy-server=http://127.0.0.1:8080                │
│         --remote-debugging-port=9222                        │
│         --user-data-dir=/tmp/chrome-{session}               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2: browser-use通过CDP连接                             │
│                                                             │
│  browser-use --session {name} --cdp-url http://localhost:9222│
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3: 多Agent共享同一Chrome实例                            │
│                                                             │
│        Navigator ──┐                                        │
│        Form      ──┼──→ 同一CDP连接                          │
│        (其他)    ──┘                                        │
└─────────────────────────────────────────────────────────────┘

关键点：
- 代理必须在Chrome启动时配置（browser-use无法配置代理）
- browser-use必须通过CDP连接到已有Chrome实例
- 所有Agent通过相同CDP连接共享页面状态
```

---

## Chrome实例创建（Step 1）

### ⚠️ 关键：代理配置必须在Chrome启动时设置

**browser-use无法配置代理**，必须通过Chrome启动参数设置。

### 创建命令

**Windows**:
```powershell
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
Start-Process $chromePath -ArgumentList @(
  "--proxy-server=http://127.0.0.1:8080",
  "--remote-debugging-port=9222",
  "--user-data-dir=C:\temp\chrome-{session_name}"
)
```

**macOS**:
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --proxy-server=http://127.0.0.1:8080 \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-{session_name} &
```

### 参数说明

| 参数 | 说明 | 示例 |
|------|------|------|
| `--proxy-server` | Burp代理地址 | `http://127.0.0.1:8080` |
| `--remote-debugging-port` | CDP端口（每实例唯一） | `9222`, `9223` |
| `--user-data-dir` | 用户数据目录（每实例唯一） | `/tmp/chrome-admin` |

### 多实例配置

针对具体测试场景，决定创建实例个数（例如多账户越权场景测试，应针对每一个账户或角色创建对应实例）并创建对应的session与其连接

| Session名 | CDP端口 | User Data Dir | 用途 |
|-----------|---------|---------------|------|
| admin_001 | 9222 | /tmp/chrome-admin-001 | 管理员账号 |
| user_001 | 9223 | /tmp/chrome-user-001 | 普通用户账号 |

---

## browser-use CDP连接（Step 2）

### 连接机制说明

**关键原则**：
- **首次连接**：session 首次创建时，必须使用 `--cdp-url` 连接到 Chrome 实例
- **后续操作**：session 创建后，所有操作**不需要**重复传递 `--cdp-url` 参数
- browser-use CLI 会自动维护 session 与 CDP 连接的映射关系

### 首次连接到 Chrome 实例

**必须使用 `--cdp-url` 参数建立连接**：

```bash
# 首次连接：需要 --cdp-url（会创建/关联 session）
browser-use --session {session_name} --cdp-url http://localhost:9222 open https://example.com
```

### 后续操作（无需 --cdp-url）

```bash
# session 已建立连接后，所有操作都不需要 --cdp-url
browser-use --session {session_name} state
browser-use --session {session_name} click 0
browser-use --session {session_name} type "#username" "admin"
browser-use --session {session_name} scroll down
```

### ⚠️ 常见错误

```bash
# ❌ 错误：不创建 Chrome 实例直接使用 browser-use
browser-use open https://example.com

# ❌ 错误：每次操作都带 --cdp-url（不必要，但不会报错）
browser-use --session admin_001 --cdp-url http://localhost:9222 state
browser-use --session admin_001 --cdp-url http://localhost:9222 click 0

# ✅ 正确工作流：
# Step 1: 创建带代理的 Chrome 实例
chrome --proxy-server=http://127.0.0.1:8080 --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-test

# Step 2: 首次连接（带 --cdp-url）
browser-use --session admin_001 --cdp-url http://localhost:9222 open https://example.com

# Step 3: 后续操作（不需要 --cdp-url）
browser-use --session admin_001 state
browser-use --session admin_001 click 0
```

### 连接验证

```bash
# 验证 session 是否已连接
browser-use --session {session_name} state

# 如果 session 未连接，会报错：
# Error: Session '{session_name}' not found or not connected
```

---

## Session管理

### sessions.json结构

```json
{
  "sessions": [
    {
      "session_id": "session_20260424",
      "account_id": "admin_001",
      "role": "admin",
      "browser_use_session": "admin_001",
      "cdp_url": "http://localhost:9222",
      "cdp_port": 9222,
      "chrome_pid": 12345,
      "user_data_dir": "/tmp/chrome-admin-001",
      "status": "active",
      "auth_context": {
        "cookies": { "session": "abc123" }
      }
    }
  ]
}
```

### 获取连接信息

```javascript
function getCdpConnection(account_id) {
  const sessions = readJson("result/sessions.json");
  const session = sessions.sessions.find(s => s.account_id === account_id);
  
  if (!session || session.status !== "active") {
    throw new Error(`No active session for account ${account_id}`);
  }
  
  return {
    cdp_url: session.cdp_url,
    browser_use_session: session.browser_use_session
  };
}
```

---

## 成对原则

**重要**：browser-use session和Chrome实例必须成对打开或关闭

```bash
# 1. 先关闭browser-use session
browser-use --session {session_name} close

# 2. 再关闭对应的Chrome（通过PID）
# Windows
taskkill /PID {pid} /F

# macOS/Linux
kill {pid}

# 3. 清理记录
# 从sessions.json和chrome_instances.json移除记录
```

### ⚠️ 禁止操作

```bash
# ❌ 禁止：关闭所有Chrome实例
taskkill /F /IM chrome.exe  # Windows
pkill -f "Google Chrome"    # macOS/Linux
```

这会关闭所有Chrome实例，包括用户自己的浏览器和其他Agent的实例。

---

## 状态同步

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

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Navigator、Form 必须加载

1. 尝试: skill({ name: "shared-browser-state" })
2. 若失败: Read(".opencode/skills/core/shared-browser-state/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```

---

## 检查清单

执行任务前确认：

- [ ] Chrome实例已创建（带 --proxy-server 参数）
- [ ] CDP端口已分配且唯一
- [ ] browser-use通过 --cdp-url 连接
- [ ] sessions.json已记录连接信息
