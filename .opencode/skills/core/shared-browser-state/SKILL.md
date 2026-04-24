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

| Session名 | CDP端口 | User Data Dir | 用途 |
|-----------|---------|---------------|------|
| admin_001 | 9222 | /tmp/chrome-admin-001 | 管理员账号 |
| user_001 | 9223 | /tmp/chrome-user-001 | 普通用户账号 |

---

## browser-use CDP连接（Step 2）

### 连接到已有Chrome实例

**必须使用 `--cdp-url` 参数连接**：

```bash
# 连接到Chrome实例
browser-use --session {session_name} --cdp-url http://localhost:9222 open https://example.com

# 查看当前页面状态
browser-use --session {session_name} --cdp-url http://localhost:9222 state --json

# 执行操作
browser-use --session {session_name} --cdp-url http://localhost:9222 click 0
browser-use --session {session_name} --cdp-url http://localhost:9222 type "#username" "admin"
```

### ⚠️ 常见错误

```bash
# ❌ 错误：不通过CDP连接，代理不生效
browser-use open https://example.com

# ✅ 正确：先创建Chrome实例，再通过CDP连接
# Step 1: 创建带代理的Chrome
chrome --proxy-server=http://127.0.0.1:8080 --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-test

# Step 2: browser-use通过CDP连接
browser-use --cdp-url http://localhost:9222 open https://example.com
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

## 成对关闭原则

**重要**：browser-use session和Chrome实例必须成对关闭

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
