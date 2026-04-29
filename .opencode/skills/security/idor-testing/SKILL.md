---
name: idor-testing
description: "越权测试方法论，Security Agent使用。测试矩阵、重放流程、参数变异。"
---

# IDOR Testing Skill

> 越权测试方法论 — 测试矩阵、重放流程、参数变异、结果判定

---

## IDOR测试流程

```
┌─────────────────────────────────────────────────────────────┐
│  Security Agent IDOR测试流程                                  │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. 获取待测试API列表                                         │
│     mongodbFind(apis, test_status: "discovered/pending")     │
│     → 筛选敏感API                                             │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 获取历史请求                                              │
│     mcp__burpbridge__list_paginated_http_history             │
│     → 获取请求ID                                              │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 获取已配置角色                                            │
│     mcp__burpbridge__list_configured_roles                   │
│     → admin, user, guest                                     │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 执行重放测试                                              │
│     for each sensitive API:                                  │
│       for each role:                                         │
│         replay_http_request_as_role                          │
│         → 获取replay_id                                       │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Analyzer Agent分析结果                                    │
│     get_replay_scan_result(replay_id)                        │
│     → 判定漏洞                                                │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  6. 实时写入findings                                          │
│     mongodbInsert(findings, {...})                           │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  7. 更新API测试状态                                           │
│     mongodbUpdate(apis, test_status: "tested")               │
└─────────────────────────────────────────────────────────────┐
```

---

## 测试矩阵

### 标准：API × Role 笛卡尔积

```javascript
// 对每个敏感API，测试所有角色
const testMatrix = [];

for (const api of sensitiveApis) {
  const requiredRole = getRequiredRole(api);  // 从workflow_config或推断
  
  for (const role of configuredRoles) {
    const expectedPermission = role === requiredRole;
    
    testMatrix.push({
      api_id: api.api_id,
      endpoint: api.url,
      method: api.method,
      role: role,
      expected: expectedPermission ? "success" : "forbidden",
      test_type: "IDOR"
    });
  }
}

// 示例矩阵
[
  { api: "/api/users/{id}", role: "admin", expected: "success" },
  { api: "/api/users/{id}", role: "user", expected: "success" },    // 用户可访问自己的数据
  { api: "/api/users/{id}", role: "guest", expected: "forbidden" },
  
  { api: "/api/admin/settings", role: "admin", expected: "success" },
  { api: "/api/admin/settings", role: "user", expected: "forbidden" },
  { api: "/api/admin/settings", role: "guest", expected: "forbidden" }
]
```

---

## BurpBridge MCP调用

### 获取历史请求

```javascript
// 主扫描：从旧到新顺序拉取分页
for (let page = 1; page <= 3; page++) {
  const history = await mcp__burpbridge__list_paginated_http_history(input: {
    host: "www.example.com",
    path: "/api/users/*",
    method: "GET",
    page,
    page_size: 20
  });
}

// 返回格式
{
  total: 5,
  page: 1,
  items: [
    {
      id: "65f1a2b3c4d5e6f7a8b9c0d1",
      url: "https://www.example.com/api/users/123",
      method: "GET",
      responseStatusCode: 200,
      timestampMs: 1710000000000
    }
  ]
}
```

```javascript
// 高危反向追查：独立于主扫描，不修改 main_scan 游标
const firstPage = await mcp__burpbridge__list_paginated_http_history(input: {
  host: "www.example.com",
  path: "/api/users/*",
  method: "GET",
  page: 1,
  page_size: 20
});

const lastPage = Math.ceil(firstPage.total / firstPage.page_size);

for (let page = lastPage; page >= Math.max(1, lastPage - 2); page--) {
  const recent = await mcp__burpbridge__list_paginated_http_history(input: {
    host: "www.example.com",
    path: "/api/users/*",
    method: "GET",
    page,
    page_size: 20
  });

  const newestFirst = [...recent.items].reverse();
  // 命中目标接口或证据后立即停止
}
```

### 获取请求详情

```javascript
const detail = await mcp__burpbridge__get_http_request_detail(input: {
  history_id: "65f1a2b3c4d5e6f7a8b9c0d1"
});

// 返回格式
{
  id: "65f1a2b3c4d5e6f7a8b9c0d1",
  url: "https://www.example.com/api/users/123",
  method: "GET",
  requestRaw: "GET /api/users/123 HTTP/1.1\r\nHost: www.example.com\r\nAuthorization: Bearer xxx\r\n...",
  responseSummary: "HTTP/1.1 200 OK\r\n\r\n{\"id\":123,\"email\":\"user@example.com\",\"phone\":\"13800138000\"}"
}
```

### 重放请求

```javascript
const replay = await mcp__burpbridge__replay_http_request_as_role(input: {
  history_entry_id: "65f1a2b3c4d5e6f7a8b9c0d1",
  target_role: "guest"
});

// 返回格式
{
  replay_id: "uuid-xxx",
  status: "queued"
}

// 等待重放完成，然后查询结果
const result = await mongodbFind({
  collection: "replays",
  filter: { replayId: "uuid-xxx" }
});
```

---

## 参数变异测试

### 使用modifications参数

```javascript
// 测试ID参数变异
await mcp__burpbridge__replay_http_request_as_role(input: {
  history_entry_id: "entry_xxx",
  target_role: "guest",
  modifications: {
    query_param_overrides: {
      id: "1",           // 尝试访问其他用户
      userId: "admin"    // 尝试越权
    },
    json_field_overrides: {
      "user.id": 1,
      "role": "admin"
    },
    header_removals: ["X-Debug-Mode"]
  }
});
```

### ID范围测试

```javascript
// 测试IDOR：遍历不同ID
const testIds = [1, 2, 100, 999, "admin", "superadmin"];

for (const testId of testIds) {
  await mcp__burpbridge__replay_http_request_as_role(input: {
    history_entry_id: "entry_xxx",
    target_role: "guest",
    modifications: {
      path_param_overrides: { id: testId }
    }
  });
}
```

---

## 结果判定

### 状态码判定

| 场景 | 原始响应 | 重放响应 | 判定 |
|------|---------|---------|------|
| 有权限 | 200 + 数据 | 200 + 数据 | 正常 |
| 有权限 | 200 + 数据 | 200 + 错误数据 | 需进一步分析 |
| 无权限 | 200 + 数据 | 401/403 | **安全** |
| 无权限 | 200 + 数据 | 200 + 数据 | **越权漏洞** |
| 无权限 | 200 + 数据 | 200 + 部分数据 | **部分越权** |

### 响应体相似度

```javascript
function calculateSimilarity(originalBody, replayBody) {
  // 简化：计算字段覆盖率
  const originalFields = Object.keys(JSON.parse(originalBody));
  const replayFields = Object.keys(JSON.parse(replayBody));
  
  const intersection = originalFields.filter(f => replayFields.includes(f));
  
  return intersection.length / originalFields.length;
}

// 判定规则
// similarity >= 90% → 高概率越权
// similarity >= 50% → 部分越权（部分字段泄露）
// similarity < 50% → 安全或需人工确认
```

---

## 批量测试

### 使用replay_requests工具

```javascript
// 批量重放：多API × 多角色
await mcp__burpbridge__replay_requests(input: {
  history_entry_ids: ["id1", "id2", "id3"],
  target_roles: ["admin", "user", "guest"],
  stop_on_error: false
});

// 返回每个组合的replay_id
{
  results: [
    { history_id: "id1", role: "admin", replay_id: "uuid-1", status: "queued" },
    { history_id: "id1", role: "user", replay_id: "uuid-2", status: "queued" },
    { history_id: "id1", role: "guest", replay_id: "uuid-3", status: "queued" },
    ...
  ]
}
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Security 必须加载

1. 尝试: skill({ name: "idor-testing" })
2. 若失败: Read("skills/security/idor-testing/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```
