---
name: burpbridge-api-reference
description: "BurpBridge REST API完整参考文档，Security Agent专用。API端点、参数、响应格式、调用规范。"
---

# BurpBridge API Reference Skill

> BurpBridge REST API完整参考 — 端点、参数、响应格式、调用规范

---

## 基础配置

```json
{
  "base_url": "http://localhost:8090",
  "default_timeout_ms": 30000
}
```

---

## 重要：MCP工具调用格式

**所有 BurpBridge MCP 工具调用必须使用 `input` 参数包装**

### 正确调用方式

```javascript
// 无参数工具
mcp__burpbridge__check_burp_health(input: {})
mcp__burpbridge__list_configured_roles(input: {})
mcp__burpbridge__get_auto_sync_status(input: {})

// 带参数工具
mcp__burpbridge__list_paginated_http_history(input: {"host": "example.com", "page": 1})
mcp__burpbridge__configure_auto_sync(input: {"enabled": true, "host": "www.example.com"})
mcp__burpbridge__replay_http_request_as_role(input: {"history_entry_id": "xxx", "target_role": "admin"})
mcp__burpbridge__sync_proxy_history_with_filters(input: {"host": "www.example.com", "require_response": true})
```

### 错误调用方式

```javascript
mcp__burpbridge__check_burp_health()  // ❌ 缺少 input 参数
mcp__burpbridge__list_paginated_http_history({"host": "example.com"})  // ❌ 缺少 input 包装
mcp__burpbridge__get_auto_sync_status(input)  // ❌ input 必须是对象格式
```

---

## API端点列表

| 端点 | 方法 | 用途 | 优先级 |
|------|------|------|--------|
| `/health` | GET | 健康检查 | 初始化 |
| `/sync/auto` | POST | **配置自动同步（推荐）** | ⭐ 首选 |
| `/sync/auto/status` | GET | 获取自动同步状态 | 监控 |
| `/sync` | POST | 手动同步代理历史 | 备用 |
| `/history` | GET | 分页查询历史记录 | 查询 |
| `/history/:id` | GET | 获取单条历史记录详情 | 详情 |
| `/auth/config` | POST | 配置认证上下文 | 初始化 |
| `/auth/roles` | GET | 列出已配置角色 | 查询 |
| `/auth/roles/:role` | DELETE | 删除角色配置 | 管理 |
| `/scan/single` | POST | 单次重放 | 测试 |
| `/scan/batch` | POST | 批量重放 | 测试 |

---

## 详细API说明

### 1. 健康检查

```
GET /health
```

**响应**：
```json
{
  "status": "ok",
  "plugin": "BurpBridge",
  "burpVersion": "2026.3"
}
```

---

### 2. 配置自动同步（⭐ 首选）

```
POST /sync/auto
Content-Type: application/json

{
  "enabled": true,
  "host": "www.baidu.com",
  "methods": null,
  "path_pattern": null,
  "status_code": null,
  "require_response": true
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | boolean | 启用/禁用自动同步 |
| `host` | string | 目标主机名（支持部分匹配） |
| `methods` | string[] | HTTP方法列表，`null` = 全部 |
| `path_pattern` | string | 路径通配符，`null` = 无过滤 |
| `status_code` | int | 状态码过滤，`null` = 无过滤 |
| `require_response` | boolean | 是否必须有响应 |

**响应**：
```json
{
  "status": "ok",
  "auto_sync_enabled": true,
  "config": {
    "host": "www.baidu.com",
    "methods": [],
    "path_pattern": "",
    "status_code": 0
  }
}
```

**推荐默认值**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `methods` | `null` | **推荐**：接受所有HTTP方法 |
| `path_pattern` | `null` | **推荐**：无路径过滤 |
| `status_code` | `null` | **推荐**：无状态码过滤 |
| `require_response` | `true` | **推荐**：仅同步有响应的请求 |

---

### 3. 获取自动同步状态

```
GET /sync/auto/status
```

**响应**：
```json
{
  "status": "ok",
  "auto_sync_enabled": true,
  "synced_count": 1523,
  "config": { ... }
}
```

---

### 4. 手动同步代理历史（备用）

仅在自动同步不可用时使用：

```
POST /sync?host=api.example.com&methods=GET,POST&path=/api/*&status=200&requireResponse=true
```

**查询参数**：

| 参数 | 必填 | 说明 |
|------|------|------|
| host | ✅ | 目标主机名 |
| methods | ❌ | HTTP方法，逗号分隔 |
| path | ❌ | URL路径模式（支持 * 通配符） |
| status | ❌ | 响应状态码 |
| requireResponse | ❌ | 是否要求有响应（默认 true） |
| exclude_mime | ❌ | 排除的MIME类型 |
| include_html | ❌ | 是否包含HTML（默认排除） |

---

### 5. 分页查询历史记录

```
GET /history?host=api.example.com&path=/api/*&method=GET&page=1&page_size=20
```

**响应**：
```json
{
  "total": 1250,
  "page": 1,
  "page_size": 20,
  "items": [
    {
      "id": "65f1a2b3c4d5e6f7a8b9c0d1",
      "url": "https://api.example.com/api/users/123",
      "method": "GET",
      "responseStatusCode": 200,
      "timestampMs": 1710000000000
    }
  ]
}
```

---

### 6. 获取历史记录详情

```
GET /history/:id
```

**响应**：
```json
{
  "id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "url": "https://api.example.com/api/users/123",
  "method": "GET",
  "responseStatusCode": 200,
  "timestampMs": 1710000000000,
  "requestRaw": "GET /api/users/123 HTTP/1.1\r\nHost: ...",
  "responseSummary": "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"id\":123,\"email\":\"...\"}"
}
```

---

### 7. 配置认证上下文

```
POST /auth/config
Content-Type: application/json

{
  "role": "admin",
  "level": "high",
  "headers": {
    "Authorization": "Bearer admin_token_xxx"
  },
  "cookies": {
    "session": "admin_session_abc",
    "token": "admin_token_def"
  }
}
```

**字段说明**：

| 字段 | 说明 |
|------|------|
| role | 角色名称（如 admin, user, guest） |
| level | 权限级别（high, medium, low） |
| headers | 认证相关headers（Authorization, X-Auth-Token等） |
| cookies | Cookie键值对（自动合并为Cookie header） |

---

### 8. 列出已配置角色

```
GET /auth/roles
```

**响应**：
```json
{
  "status": "ok",
  "roles": ["admin", "user", "guest"]
}
```

---

### 9. 删除角色配置

```
DELETE /auth/roles/:role
```

---

### 10. 单次重放

```
POST /scan/single
Content-Type: application/json

{
  "history_entry_id": "65f1a2b3c4d5e6f7a8b9c0d1",
  "target_role": "guest",
  "modifications": {
    "query_param_overrides": {"id": "999"},
    "json_field_overrides": {"user.id": 1},
    "header_removals": ["X-Debug-Mode"]
  }
}
```

**modifications参数**（可选）：

| 字段 | 说明 |
|------|------|
| query_param_overrides | 覆盖查询参数 |
| json_field_overrides | 覆盖JSON body字段（支持嵌套路径） |
| header_removals | 移除指定headers |

**响应**：
```json
{
  "replay_id": "uuid-xxx",
  "status": "queued"
}
```

---

### 11. 批量重放

```
POST /scan/batch
Content-Type: application/json

{
  "history_entry_ids": ["id1", "id2", "id3"],
  "target_role": "guest",
  "stop_on_error": false
}
```

**响应**：
```json
{
  "status": "completed",
  "total": 3,
  "successful": 2,
  "failed": 1,
  "results": [...]
}
```

---

## 重放结果存储

重放结果存储在MongoDB的`replays`集合中：

```javascript
// 查询重放结果
db.replays.findOne({ replayId: "uuid-xxx" })

// 结果结构
{
  "replayId": "uuid-xxx",
  "originalHistoryId": "65f1a2b3...",
  "targetRole": "guest",
  "timestampMs": 1710000000000,
  "result": {
    "originalStatusCode": 200,
    "replayedStatusCode": 200,
    "bodyHash": "sha256:...",
    "originalRequest": "GET /api/users/123 ...",
    "originalResponseSummary": "HTTP/1.1 200 ...",
    "replayRequest": "GET /api/users/123 ...",
    "replayResponseSummary": "HTTP/1.1 200 ...",
    "piiFlags": [],
    "scanTimeMs": 150
  }
}
```

---

## MIME类型自动排除

自动同步默认排除以下静态资源：

```
image/*, video/*, audio/*, font/*
application/javascript, text/javascript
application/x-javascript, text/css
application/pdf, application/zip
```

---

## 加载要求

```yaml
## Skill加载规则（双通道）

# Security必须加载

1. 尝试: skill({ name: "burpbridge-api-reference" })
2. 若失败: Read("skills/security/burpbridge-api-reference/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```