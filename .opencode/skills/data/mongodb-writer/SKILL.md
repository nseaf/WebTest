---
name: mongodb-writer
description: "实时数据库写入规范，防止数据丢失，解决并发写入问题。核心原则：每发现一个数据立即写入，不等Agent完成。"
---

# MongoDB Writer Skill

> 实时数据库写入规范 — 使用BurpBridge现有MongoDB，扩展webtest collections

---

## 核心原则

```
⚠️ 核心原则：每发现一个数据立即写入，不等Agent完成

✗ 禁止批量写入（Agent完成后再写）
  - Agent输出截断可能导致数据丢失
  - 并发写入JSON文件存在冲突风险
  
✓ 必须实时写入MongoDB
  - 发现API立即写入apis collection
  - 发现漏洞立即写入findings collection
  - 每个操作完成后更新progress
```

---

## 数据库架构

使用BurpBridge现有MongoDB（localhost:27017），扩展以下collections：

### Collection定义

| Collection | 用途 | 写入时机 | 写入Agent |
|------------|------|---------|-----------|
| test_sessions | 测试会话 | Coordinator初始化 | Coordinator |
| findings | 漏洞发现 | Security发现立即写入 | Security |
| apis | API发现 | Scout发现立即写入 | Scout |
| pages | 页面发现 | Scout分析后写入 | Scout |
| events | 事件队列 | 任意Agent创建事件 | 所有Agent |
| progress | 测试进度 | 每个Agent完成任务后更新 | Scout/Security |

---

## Collection Schema

### test_sessions

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",       // 会话标识
  target_url: "https://example.com",
  target_host: "www.example.com",
  mode: "standard",                     // quick/standard/deep
  status: "running",                    // running/completed/failed/paused
  current_state: "ROUND_1_TEST",        // 状态机当前状态
  created_at: Date,
  updated_at: Date,
  config: {
    max_depth: 3,
    max_pages: 50,
    timeout_ms: 30000
  },
  statistics: {
    pages_visited: 0,
    apis_discovered: 0,
    apis_tested: 0,
    vulnerabilities_found: 0
  }
}
```

### findings

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",
  vuln_id: "IDOR_001",                  // 漏洞标识
  type: "IDOR",                         // IDOR/XSS/SQLI/CSRF等
  severity: "High",                     // Critical/High/Medium/Low
  confidence: 0.95,                     // 置信度
  endpoint: "/api/users/{id}",
  method: "GET",
  tested_role: "guest",
  result: {
    original_status: 200,
    replayed_status: 200,
    sensitive_data_exposed: ["email", "phone"]
  },
  history_entry_id: "65f1a2b3c4d5e6f7",  // BurpBridge历史记录ID
  replay_id: "uuid-xxx",                 // 重放ID
  discovered_at: Date,
  analyzed_at: Date,                     // Analyzer分析时间
  description: "Guest用户可访问Admin用户的个人数据"
}
```

### apis

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",
  api_id: "api_001",
  url: "/api/users/{id}",
  method: "GET",
  pattern_detected: "/api/users/{id}",
  module: "user",                        // 模块分类
  sensitive_fields: ["email", "phone"],
  test_status: "pending",                // discovered/pending/testing/tested/skipped
  tested_by: null,                       // Security Agent ID
  tested_at: null,
  vulnerabilities: [],                   // 关联的漏洞ID列表
  discovered_at: Date,
  source_page: "https://example.com/dashboard",
  headers: {
    Authorization: "Bearer xxx"
  },
  parameters: [
    { name: "id", value: "123", location: "path" }
  ]
}
```

### pages

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",
  page_id: "page_001",
  url: "https://example.com/dashboard",
  title: "Dashboard",
  type: "dashboard",                     // home/login/dashboard/list/detail
  analyzed_at: Date,
  links_found: 5,
  forms_found: 2,
  apis_found: 3
}
```

### events

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",
  event_id: "evt_20260422_001",
  event_type: "CAPTCHA_DETECTED",        // 事件类型
  source_agent: "Form Agent",
  priority: "critical",                  // critical/high/normal
  status: "pending",                     // pending/processing/handled/failed
  payload: {
    window_id: "window_0",
    login_url: "https://example.com/login"
  },
  created_at: Date,
  handled_at: null,
  result: null
}
```

### progress

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",
  modules: [
    {
      module_name: "user",
      apis: [
        { api_id: "api_001", endpoint: "/api/users/{id}", test_status: "tested" },
        { api_id: "api_002", endpoint: "/api/users/profile", test_status: "pending" }
      ],
      stats: {
        total: 2,
        tested: 1,
        pending: 1,
        vulnerabilities: 1
      }
    }
  ],
  overall_stats: {
    total_apis: 10,
    tested_apis: 3,
    pending_apis: 7,
    vulnerabilities_found: 2
  },
  last_updated: Date
}
```

---

## MongoDB MCP调用示例

### 初始化测试会话

```javascript
mongodb-mcp-server_insert-many({
  database: "webtest",
  collection: "test_sessions",
  documents: [{
    session_id: "session_20260422",
    target_url: "https://example.com",
    target_host: "www.example.com",
    mode: "standard",
    status: "running",
    current_state: "INIT",
    created_at: Date.now(),
    config: { max_depth: 3, max_pages: 50, timeout_ms: 30000 }
  }]
})
```

### 写入API发现

```javascript
mongodb-mcp-server_insert-many({
  database: "webtest",
  collection: "apis",
  documents: [{
    session_id: "session_20260422",
    api_id: "api_001",
    url: "/api/users/123",
    method: "GET",
    module: "user",
    sensitive_fields: ["email"],
    test_status: "discovered",
    discovered_at: Date.now()
  }]
})
```

### 写入漏洞发现

```javascript
mongodb-mcp-server_insert-many({
  database: "webtest",
  collection: "findings",
  documents: [{
    session_id: "session_20260422",
    vuln_id: "IDOR_001",
    type: "IDOR",
    severity: "High",
    endpoint: "/api/users/{id}",
    tested_role: "guest",
    result: {
      original_status: 200,
      replayed_status: 200,
      sensitive_data_exposed: ["email", "phone"]
    },
    history_entry_id: "65f1a2b3c4d5e6f7",
    replay_id: "uuid-xxx",
    discovered_at: Date.now()
  }]
})
```

### 更新API测试状态

```javascript
mongodb-mcp-server_update-many({
  database: "webtest",
  collection: "apis",
  filter: { session_id: "session_20260422", api_id: "api_001" },
  update: { 
    $set: { 
      test_status: "tested",
      tested_by: "Security",
      tested_at: Date.now()
    }
  }
})
```

### 创建事件

```javascript
mongodb-mcp-server_insert-many({
  database: "webtest",
  collection: "events",
  documents: [{
    session_id: "session_20260422",
    event_id: "evt_001",
    event_type: "API_DISCOVERED",
    source_agent: "Scout Agent",
    priority: "normal",
    status: "pending",
    payload: { api_id: "api_001" },
    created_at: Date.now()
  }]
})
```

### 查询进度

```javascript
mongodb-mcp-server_find({
  database: "webtest",
  collection: "progress",
  filter: { session_id: "session_20260422" }
})
```

---

## JSON文件保留策略

以下数据仍使用JSON文件（便于查看和调试）：

| 文件 | 保留原因 |
|------|---------|
| sessions.json | 会话状态、Cookie信息，便于Coordinator查看 |
| chrome_instances.json | Chrome实例注册表，便于Navigator管理 |

以下数据迁移到MongoDB：

| 原文件 | MongoDB Collection |
|--------|-------------------|
| vulnerabilities.json | findings |
| apis.json | apis |
| pages.json | pages |
| forms.json | forms（可选，也可保留JSON） |
| links.json | links（可选，也可保留JSON） |
| events.json | events |

---

## 数据清理策略

### 会话开始时

Coordinator初始化时清理上一会话数据：

```javascript
mongodb-mcp-server_delete-many({
  database: "webtest",
  collection: "test_sessions",
  filter: {}  // 清空所有历史会话（可选）
})

mongodb-mcp-server_delete-many({
  database: "webtest",
  collection: "findings",
  filter: {}
})

mongodb-mcp-server_delete-many({
  database: "webtest",
  collection: "apis",
  filter: {}
})
```

### 会话结束时

可选：保留历史数据供分析，或清理：

```javascript
// 标记会话完成
mongodb-mcp-server_update-many({
  database: "webtest",
  collection: "test_sessions",
  filter: { session_id: "session_20260422" },
  update: { $set: { status: "completed", updated_at: Date.now() } }
})
```

---

## 加载要求

此Skill由以下Agent加载：

```yaml
## Skill 加载规则（双通道）

# Coordinator、Scout、Security 必须加载

1. 尝试: skill({ name: "mongodb-writer" })
2. 若失败: Read("skills/data/mongodb-writer/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```