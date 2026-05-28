---
name: mongodb-writer
description: "实时数据库写入规范，防止数据丢失，解决并发写入问题。核心原则：每发现一个数据立即写入，不等Agent完成。"
---

# MongoDB Writer Skill

> 实时数据库写入规范 — 使用BurpBridge现有MongoDB，但 WebTest 自有数据按项目写入 `webtest_<project_key>` 数据库

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

使用BurpBridge现有MongoDB（localhost:27017），但 WebTest 自有运行和分析数据必须写入项目级数据库。

## 项目级数据库规则

```text
database_name = "webtest_" + normalize(project_key)
```

- `project_key` 优先使用用户显式提供的项目标识
- 若用户未提供，则使用 `target_host` 归一化生成
- 归一化规则固定为：
  - 转小写
  - 非字母数字字符替换为下划线
  - 连续下划线折叠
  - 长度超限时截断
- 不再通过清空统一 `webtest`/`WebTest` 数据库开始下一个项目
- BurpBridge 自身的 `history` / `replays` 集合不在本次数据库改造范围内

### Collection定义

| Collection | 用途 | 写入时机 | 写入Agent |
|------------|------|---------|-----------|
| test_sessions | 测试会话 | Coordinator初始化 | Coordinator |
| workflow_runs | 单次运行元数据 | Coordinator启动轮次与最终收尾 | Coordinator |
| permission_targets | 权限点中心状态 | 基线建立、证据补全、测试状态变化时立即写入 | Coordinator/Navigator/Security |
| findings | 漏洞发现 | Security发现立即写入 | Security |
| apis | API发现 | Navigator发现立即写入 | Navigator |
| pages | 页面发现 | Navigator分析后写入 | Navigator |
| events | 事件队列 | 任意Agent创建事件 | 所有Agent |
| progress | 测试进度 | 每个Agent完成任务后更新 | Navigator/Security |

---

## Collection Schema

### test_sessions

```javascript
{
  _id: ObjectId,
  project_key: "example_com",
  database_name: "webtest_example_com",
  session_id: "session_20260422",       // 会话标识
  target_url: "https://example.com",
  target_host: "www.example.com",
  workflow_mode: "permission_first",
  mode: "standard",                     // quick/standard/deep
  status: "running",                    // running/completed/failed/paused
  current_state: "SITE_SURVEY",         // 状态机当前状态
  current_account_id: "test1020",
  current_role: "manager",
  current_permission_key: "workflow.approval.submit",
  current_round_stage: "navigator_phase",
  current_round_backlog_count: 0,
  pending_role_permission_pairs: [],
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

### workflow_runs

```javascript
{
  _id: ObjectId,
  project_key: "example_com",
  session_id: "session_20260422",
  run_id: "run_20260519_001",
  target_host: "www.example.com",
  round_type: "account_round|deferred_round|final_stage",
  role: "manager",
  account_id: "test1020",
  permission_key: "workflow.approval.submit",
  navigator_phase_status: "pending|completed",
  security_phase_status: "pending|completed|no_targets|deferred",
  security_skip_reason: null,
  negative_backlog_count: 0,
  status: "running|completed|deferred",
  started_at: Date,
  finished_at: Date
}
```

### permission_targets

```javascript
{
  _id: ObjectId,
  project_key: "example_com",
  database_name: "webtest_example_com",
  session_id: "session_20260422",
  permission_key: "workflow.approval.submit",
  module_path: ["workflow", "approval"],
  menu_path: ["流程中心", "审批管理"],
  permission_name: "提交审批",
  baseline_source: "permission_matrix",
  allowed_roles: ["manager"],
  allowed_accounts: ["test1020"],
  denied_roles: ["employee", "guest"],
  entry_points: [
    {
      entry_type: "menu",
      entry_url: "https://example.com/workflow/approval",
      entry_label: "审批管理",
      source: "navigator_survey"
    }
  ],
  access_steps: [
    "从首页进入 流程中心",
    "点击左侧菜单 审批管理",
    "进入审批列表后打开 提交审批"
  ],
  ui_locations: [
    {
      menu_path: ["流程中心", "审批管理"],
      page_title: "审批列表",
      region: "主内容区",
      element_text: "提交审批",
      locator: null
    }
  ],
  related_pages: ["https://example.com/workflow/approval"],
  related_apis: [
    { api_id: "api_001", url: "/api/workflow/submit", method: "POST", confirmed: true }
  ],
  evidence_history_ids: ["65f1a2b3c4d5e6f7a8b9c0d1"],
  matched_history_ids: [],
  confirmed_request_samples: [
    {
      history_entry_id: "65f1a2b3c4d5e6f7a8b9c0d1",
      source_role: "manager",
      source_account_id: "test1020",
      action_kind: "approve",
      request_fingerprint: "POST:/api/workflow/submit"
    }
  ],
  tested_roles: [
    { role: "manager", status: "allowed_confirmed", last_tested_at: Date }
  ],
  denied_test_results: [
    {
      role: "employee",
      account_id: "test2040",
      source_role: "manager",
      action_kind: "approve",
      used_history_entry_id: "65f1a2b3c4d5e6f7a8b9c0d1",
      matched_history_id: null,
      result: "blocked|allowed|deferred",
      tested_at: Date
    }
  ],
  untested_roles: ["employee", "guest"],
  deferred_roles: [
    {
      role: "employee",
      reason_code: "AUTH_SNAPSHOT_MISSING",
      reason: "Employee role has not produced a usable auth snapshot yet."
    }
  ],
  deferred_reasons: ["AUTH_SNAPSHOT_MISSING"],
  irreversible: false,
  final_stage_required: false,
  status: "ready_for_replay",
  updated_at: Date
}
```

规则补充：
- `permission_key` 是唯一记录中心；即使同一权限点由多个账号探索或测试，也不能拆成多条账号主记录。
- 一个 `permission_key` 下允许挂多个操作样本，必须通过 `action_kind` 或等价字段区分 `view/create/update/delete/approve/revoke`。
- Navigator 负责写入正向证据：`allowed_roles`、`allowed_accounts`、`denied_roles`、`related_apis` 与 `confirmed_request_samples.history_entry_id`。
- Security 负责把 denied replay 结果写回同一 `permission_key`，包括当前被测 denied role/account、命中的历史样本与 deferred 结果。
- 当某权限点存在稳定可复测的真实请求样本时，必须至少保留一个真实 `history_entry_id` 或等价请求指纹，不能只保留接口 URL。
- 对不可逆动作，额外记录 `matched_history_id` 并与来源 `permission_key` 绑定。
- denied replay 必须优先消费 `permission_key` 中已绑定的 `history_entry_id`；只有绑定缺失时才允许回退到 history 搜索。

### findings

```javascript
{
  _id: ObjectId,
  project_key: "example_com",
  session_id: "session_20260422",
  permission_key: "workflow.approval.submit",
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
  project_key: "example_com",
  session_id: "session_20260422",
  api_id: "api_001",
  url: "/api/users/{id}",
  method: "GET",
  pattern_detected: "/api/users/{id}",
  module: "user",                        // 模块分类
  permission_keys: ["workflow.approval.submit"],
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
  project_key: "example_com",
  session_id: "session_20260422",
  page_id: "page_001",
  url: "https://example.com/dashboard",
  title: "Dashboard",
  type: "dashboard",                     // home/login/dashboard/list/detail
  permission_keys: ["workflow.approval.submit"],
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
  project_key: "example_com",
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
  project_key: "example_com",
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
  database: "webtest_example_com",
  collection: "test_sessions",
  documents: [{
    project_key: "example_com",
    database_name: "webtest_example_com",
    session_id: "session_20260422",
    target_url: "https://example.com",
    target_host: "www.example.com",
    workflow_mode: "permission_first",
    mode: "standard",
    status: "running",
    current_state: "INIT",
    created_at: Date.now(),
    config: { max_depth: 3, max_pages: 50, timeout_ms: 30000 }
  }]
})
```

### 写入权限中心

```javascript
mongodb-mcp-server_insert-many({
  database: "webtest_example_com",
  collection: "permission_targets",
  documents: [{
    project_key: "example_com",
    session_id: "session_20260422",
    permission_key: "workflow.approval.submit",
    baseline_source: "permission_matrix",
    allowed_roles: ["manager"],
    allowed_accounts: ["test1020"],
    denied_roles: ["employee", "guest"],
    status: "pending",
    updated_at: Date.now()
  }]
})
```

### 写入API发现

```javascript
mongodb-mcp-server_insert-many({
  database: "webtest_example_com",
  collection: "apis",
  documents: [{
    project_key: "example_com",
    session_id: "session_20260422",
    api_id: "api_001",
    url: "/api/users/123",
    method: "GET",
    module: "user",
    permission_keys: ["workflow.approval.submit"],
    sensitive_fields: ["email"],
    test_status: "discovered",
    discovered_at: Date.now()
  }]
})
```

### 写入漏洞发现

```javascript
mongodb-mcp-server_insert-many({
  database: "webtest_example_com",
  collection: "findings",
  documents: [{
    project_key: "example_com",
    session_id: "session_20260422",
    permission_key: "workflow.approval.submit",
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
  database: "webtest_example_com",
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
  database: "webtest_example_com",
  collection: "events",
  documents: [{
    project_key: "example_com",
    session_id: "session_20260422",
    event_id: "evt_001",
    event_type: "API_DISCOVERED",
    source_agent: "Navigator Agent",
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
  database: "webtest_example_com",
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
| permission_targets.json | 权限点中心真相源，便于Coordinator调度和 deferred 管理 |

以下数据迁移到MongoDB：

| 原文件 | MongoDB Collection |
|--------|-------------------|
| vulnerabilities.json | findings |
| apis.json | apis |
| pages.json | pages |
| forms.json | forms（可选，也可保留JSON） |
| links.json | links（可选，也可保留JSON） |
| events.json | events |
| permission_targets.json | permission_targets |

---

## 数据清理策略

### 会话开始时

Coordinator 初始化时不得清空整个历史数据库。只创建新的 `test_sessions` / `workflow_runs` 记录，并让新项目写入独立数据库。

```javascript
mongodb-mcp-server_insert-many({
  database: "webtest_example_com",
  collection: "workflow_runs",
  documents: [{
    project_key: "example_com",
    session_id: "session_20260422",
    run_id: "run_20260519_001",
    round_type: "permission_round",
    role: "manager",
    permission_key: "workflow.approval.submit",
    status: "running",
    started_at: Date.now()
  }]
})
```

### 会话结束时

可选：保留历史数据供分析，或清理：

```javascript
// 标记会话完成
mongodb-mcp-server_update-many({
  database: "webtest_example_com",
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

# Coordinator、Navigator、Security 必须加载

1. 尝试: skill({ name: "mongodb-writer" })
2. 若失败: Read("skills/data/mongodb-writer/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```
