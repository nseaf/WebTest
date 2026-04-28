# 共享状态文件规范

本文档定义了 Agent 间通信使用的所有状态文件格式、读写时机和注意事项。

---

## 数据存储架构

### MongoDB Collections（实时写入）

使用BurpBridge现有MongoDB，扩展以下collections：

| Collection | 用途 | 写入时机 | 写入Agent |
|------------|------|---------|-----------|
| test_sessions | 测试会话 | Coordinator初始化 | Coordinator |
| findings | 漏洞发现 | Security发现立即写入 | Security |
| apis | API发现 | Navigator 确认或补充证据后立即写入 | Navigator |
| pages | 页面发现 | Navigator 分析后写入 | Navigator |
| events | 事件队列 | 任意Agent创建事件 | 所有Agent |
| progress | 测试进度 | 每个Agent完成任务后更新 | Navigator/Security |

**核心原则**：每发现一个数据立即写入MongoDB，不等Agent完成，防止数据丢失。

详细Schema定义见：`skills/data/mongodb-writer/SKILL.md`

### JSON文件（保留）

以下数据仍使用JSON文件存储（便于查看和调试）：

| 文件 | 路径 | 用途 |
|------|------|------|
| 会话状态 | `result/sessions.json` | 登录状态、Cookie信息、CDP连接、当前流程态 |
| Chrome实例 | `result/chrome_instances.json` | Chrome实例注册表、PID、端口 |

---

## 文件路径总览

| 文件 | 路径 | 用途 | 模板位置 |
|------|------|------|----------|
| 事件队列 | `result/events.json` | Agent间异步通信 | `memory/templates/events_template.json` |
| 全貌测绘 | `result/site_survey.json` | 首轮测绘与补测聚合快照 | `memory/templates/site_survey_template.json` |
| 窗口注册 | `result/windows.json` | 多标签页管理 | `memory/templates/windows_template.json` |
| 会话状态 | `result/sessions.json` | 账号登录状态 | `memory/templates/sessions_template.json` |
| API发现 | `result/apis.json` | 发现的API端点 | `memory/templates/apis_template.json` |
| 页面记录 | `result/pages.json` | 访问过的页面 | `memory/discoveries/pages.json` |
| 表单记录 | `result/forms.json` | 发现的表单 | `memory/discoveries/forms.json` |
| 链接记录 | `result/links.json` | 发现的链接 | `memory/discoveries/links.json` |
| 漏洞记录 | `result/vulnerabilities.json` | 发现的漏洞 | `memory/discoveries/vulnerabilities.json` |
| 会话配置 | `memory/sessions/session_template.json` | 测试会话配置模板 | - |

---

## 1. 事件队列 (events.json)

### 文件顶层格式

```json
{
  "$schema": "events_schema",
  "allowed_hosts": ["example.com", "sso.example.com"],
  "events": []
}
```

### 统一事件格式

```json
{
  "event_id": "evt_20260415_103000_001",
  "event_type": "SURVEY_GAP_DETECTED",
  "source_agent": "Navigator Agent",
  "priority": "high",
  "status": "pending",
  "payload": {
    "module": "workflow",
    "reason": "role B 未验证"
  },
  "created_at": "2026-04-15T10:30:00Z",
  "handled_at": null,
  "result": null
}
```

### 事件类型定义

| 事件类型 | 来源 Agent | 优先级 | 需要用户操作 |
|----------|-----------|--------|--------------|
| CAPTCHA_DETECTED | Form/Navigator | critical | ✅ 是 |
| SESSION_EXPIRED | Navigator/Security | high | ❌ 否 |
| LOGIN_FAILED | Form | high | ❌ 否 |
| EXPLORATION_SUGGESTION | Security/Analyzer | normal | ❌ 否 |
| VULNERABILITY_FOUND | Security | high | ❌ 否 |
| API_DISCOVERED | Navigator | normal | ❌ 否 |
| FORM_SUBMISSION_ERROR | Form | normal | ❌ 否 |
| EXTERNAL_DOMAIN_SKIPPED | Navigator | normal | ❌ 否 |
| ACCESS_SCOPE_BLOCKED | Navigator | normal | ❌ 否 |
| SURVEY_GAP_DETECTED | Navigator/Coordinator | high | ❌ 否 |
| RECOVERY_ATTEMPTED | Navigator | normal | ❌ 否 |

### 事件状态流转

```
pending → processing → handled
                    ↘ failed
```

### 创建事件示例

```javascript
function createEvent(eventType, sourceAgent, priority, payload) {
  return {
    "event_id": `evt_${Date.now()}_${Math.random().toString(36).substr(2, 3)}`,
    "event_type": eventType,
    "source_agent": sourceAgent,
    "priority": priority,
    "status": "pending",
    "payload": payload,
    "created_at": new Date().toISOString(),
    "handled_at": null,
    "result": null
  };
}
```

---

## 2. 窗口注册表 (windows.json)

### 窗口记录格式

```json
{
  "window_id": "window_0",
  "tab_index": 0,
  "assigned_account": "admin_001",
  "purpose": "primary_exploration",
  "status": "active",
  "login_status": "logged_in",
  "cookies_valid": true,
  "created_at": "2026-04-15T10:00:00Z",
  "last_activity": "2026-04-15T10:30:00Z"
}
```

### 窗口用途定义

| 用途 | 说明 |
|------|------|
| primary_exploration | 主探索窗口，用于发现页面和功能 |
| idor_testing | 越权测试窗口，用于重放请求测试越权漏洞 |
| secondary_exploration | 次级探索窗口，用于并行探索 |
| monitoring | 监控窗口，用于观察状态变化 |

### 窗口状态定义

| 状态 | 说明 |
|------|------|
| active | 窗口活跃，正在使用 |
| idle | 窗口空闲，等待任务 |
| waiting_captcha | 等待用户处理验证码 |
| expired | 窗口会话已过期 |

---

## 3. 会话状态 (sessions.json)

### 会话记录格式

```json
{
  "account_id": "admin_001",
  "role": "admin",
  "window_id": "window_0",
  "status": "active",
  "current_state": "SITE_SURVEY",
  "attach_status": "attached",
  "attach_mode": "reuse",
  "cdp_url": "http://127.0.0.1:9222",
  "chrome_pid": 12345,
  "last_verified_url": "https://example.com/dashboard",
  "last_verified_title": "Dashboard",
  "logged_in_at": "2026-04-15T10:00:00Z",
  "last_activity_time": "2026-04-15T10:30:00Z",
  "cookies": ["session=abc123", "token=xyz789"],
  "relogin_attempts": 0,
  "max_relogin_attempts": 3
}
```

### 会话状态定义

| 状态 | 说明 |
|------|------|
| pending | 等待登录 |
| active | 会话有效，可正常使用 |
| expired | 会话已过期，需要重新登录 |
| failed | 登录失败 |

---

## 4. API发现记录 (apis.json)

### API记录格式

```json
{
  "api_id": "api_001",
  "url": "https://api.example.com/users/123",
  "method": "GET",
  "pattern_detected": "/api/users/{id}",
  "headers": {
    "Authorization": "Bearer xxx",
    "Content-Type": "application/json"
  },
  "parameters": [
    { "name": "id", "value": "123", "location": "path" }
  ],
  "response_status": 200,
  "response_type": "application/json",
  "sensitive_fields_found": ["email", "phone"],
  "discovered_at": "2026-04-15T10:00:00Z",
  "source_page": "https://example.com/dashboard",
  "tested": false,
  "vulnerabilities": []
}
```

---

## 5. 漏洞记录 (vulnerabilities.json)

### 漏洞记录格式

```json
{
  "id": "vuln_001",
  "type": "IDOR",
  "url": "https://api.example.com/users/123",
  "method": "GET",
  "parameter": "id",
  "description": "越权访问：Guest用户可访问Admin用户的个人数据",
  "evidence": {
    "original_role": "admin",
    "original_status": 200,
    "replay_role": "guest",
    "replay_status": 200,
    "body_similarity": 0.95,
    "sensitive_data_exposed": ["email", "phone"],
    "payload": null,
    "response_indicator": null
  },
  "severity": "high",
  "cvss_score": 7.5,
  "cwe_id": "CWE-639",
  "owasp_category": "A01:2021 - Broken Access Control",
  "discovered_at": "2026-04-15T10:00:00Z",
  "history_entry_id": "entry_xxx",
  "replay_id": "replay_xxx"
}
```

### 漏洞类型与严重性

| 类型 | 说明 | 默认严重性 |
|------|------|-----------|
| IDOR | 越权访问 | high/critical |
| XSS | 跨站脚本 | medium/high |
| SQLI | SQL注入 | critical/high |
| COMMAND_INJECTION | 命令注入 | critical |
| CSRF | 跨站请求伪造 | medium |
| OTHER | 其他漏洞 | 视情况 |

---

## 文件读写规范

### 初始化时机

1. **测试会话开始时** (Coordinator Agent 负责)
   - 复制 `memory/templates/*_template.json` 到 `result/` 目录
   - 或直接创建空的状态文件（数组为空）
   - 初始化 `result/site_survey.json`
   - 初始化 `test_sessions.current_state = INIT`

2. **各 Agent 首次写入时**
   - 读取现有文件
   - 追加新记录
   - 写回文件

### 写入规范

```javascript
// 推荐：完整读取-修改-写入
function appendRecord(filePath, newRecord) {
  // 1. 读取现有数据
  const data = readJsonFile(filePath);
  
  // 2. 追加新记录
  data.push(newRecord);
  
  // 3. 写回文件
  writeJsonFile(filePath, data);
}
```

### 注意事项

1. **避免并发写入冲突**
   - 同一文件尽量由一个 Agent 负责写入
   - 事件队列：所有 Agent 可创建事件，Coordinator 负责处理和清理

2. **文件格式一致性**
   - 使用 JSON 格式，UTF-8 编码
   - 数组字段名使用复数形式（events, windows, apis 等）
   - 时间戳使用 ISO 8601 格式

3. **错误处理**
   - 文件不存在时创建空文件
   - 解析失败时记录错误并跳过

---

## 快速初始化脚本

测试会话开始前，Coordinator Agent 应执行以下初始化：

```bash
# 创建 result 目录（如不存在）
mkdir -p result

# 初始化所有状态文件（清空或重置）
echo '{"$schema":"events_schema","allowed_hosts":[],"events":[]}' > result/events.json
echo '{"$schema":"windows_schema","windows":[]}' > result/windows.json
echo '{"$schema":"sessions_schema","sessions":[]}' > result/sessions.json
echo '{"$schema":"apis_schema","apis":[]}' > result/apis.json
echo '{"$schema":"discovered_pages_schema","pages":[]}' > result/pages.json
echo '{"$schema":"site_survey_schema","allowed_hosts":[],"modules":[],"submodules":[],"entry_points":[],"role_access_matrix":[],"confirmed_apis":[],"api_hints":[],"coverage_gaps":[],"external_domains":[],"recommended_next_actions":[]}' > result/site_survey.json
echo '{"$schema":"discovered_forms_schema","forms":[]}' > result/forms.json
echo '{"$schema":"discovered_links_schema","links":[]}' > result/links.json
echo '{"$schema":"vulnerabilities_schema","vulnerabilities":[],"statistics":{"total":0,"by_severity":{"critical":0,"high":0,"medium":0,"low":0},"by_type":{"IDOR":0,"XSS":0,"SQLI":0,"COMMAND_INJECTION":0,"CSRF":0,"OTHER":0}}}' > result/vulnerabilities.json
```
