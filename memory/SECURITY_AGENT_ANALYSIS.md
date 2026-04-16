# Security Agent 优化分析报告

## 一、Original-Agents 分析

### 优点

#### 1. 清晰的职责分离

Original-Agents 将越权测试拆分为 5 个专门 Agent：

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| Orchestrator | 协调调度 | 用户目标 | target_config.json |
| Recon | 侦察筛选 | target_config.json | auth_context.json, candidate_endpoints.json |
| Scan | 执行重放 | candidate_endpoints.json | replay_jobs.json |
| Analyze | 分析判别 | replay_jobs.json | verified_bypasses.json |
| Report | 生成报告 | verified_bypasses.json | report.md |

这种分离使得每个 Agent 职责单一，便于测试和维护。

#### 2. 详细的越权判别规则

Analyze Agent 定义了 4 种越权判别规则：

```
✅ 规则 1：用户身份泄露
   - 低权限响应中包含非当前用户的 PII

✅ 规则 2：权限字段暴露
   - 低权限响应包含 role, is_superuser 等字段

✅ 规则 3：资源归属错位
   - URL 路径为 /api/user/123，但响应中 id != 123

✅ 规则 4：高权限专属数据
   - 低权限响应包含 internal_notes, salary 等字段
```

#### 3. 敏感字段识别词典

预定义了敏感字段类别：

| 类别 | 关键词 |
|------|--------|
| 身份信息 | email, phone, ssn, id_card, username |
| 权限控制 | role, group, permissions, is_admin, superuser |
| 资源归属 | owner_id, user_id, created_by, belong_to |
| 内部数据 | internal, debug, config, secret, apikey, salary |
| 操作日志 | audit, log, history, trace |

### 缺点

#### 1. Agent 粒度过细

5 个 Agent 增加了协调复杂度和上下文传递开销。对于本项目已有多 Agent 架构，会与 Coordinator、Navigator 等产生冲突。

#### 2. MCP 工具名称过时

使用了旧版 BurpBridge API：
- `sync_proxy_history_with_filters` → 应为 `POST /sync`
- `list_paginated_http_history` → 应为 `GET /history`
- `configure_authentication_context` → 应为 `POST /auth/config`
- `replay_http_request_as_role` → 应为 `POST /scan/single`
- `get_replay_scan_result` → 应为 `GET /history/:id` 或查询 MongoDB

#### 3. 缺乏并行架构

串行执行 `Recon → Scan → Analyze → Report` 效率低。

#### 4. 未结合 Web 探索

专注于越权测试，未考虑与页面探索的协作。

---

## 二、BurpBridge 最新 API 分析

### REST API 端点

| 端点 | 方法 | 用途 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/sync` | POST | 同步代理历史（支持增量同步） |
| `/sync/auto` | POST | 配置自动同步 |
| `/sync/auto/status` | GET | 获取自动同步状态 |
| `/history` | GET | 分页查询历史记录 |
| `/history/:id` | GET | 获取单条历史记录详情 |
| `/auth/config` | POST | 配置认证上下文 |
| `/auth/roles` | GET | 列出已配置角色 |
| `/auth/roles/:role` | DELETE | 删除角色配置 |
| `/scan/single` | POST | 单次重放（支持请求修改） |
| `/scan/batch` | POST | 批量重放 |

### 新增功能（相比旧版）

#### 1. 请求修改支持

```json
POST /scan/single
{
  "history_entry_id": "65f1a2b3...",
  "target_role": "guest",
  "modifications": {
    "query_param_overrides": {"page": "2"},
    "json_field_overrides": {"user.id": 123},
    "header_removals": ["X-Debug-Mode"]
  }
}
```

**用途**：参数变异测试，无需手动修改请求。

#### 2. 自动同步配置

```json
POST /sync/auto
{
  "enabled": true,
  "host": "api.example.com",
  "methods": ["GET", "POST"],
  "path_pattern": "/api/*",
  "status_code": 200
}
```

**用途**：Security Agent 可配置自动同步，无需定期轮询。

#### 3. 增量同步

`POST /sync` 使用上次同步时间戳，只拉取新请求。

#### 4. MIME 类型过滤

```
POST /sync?exclude_mime=image,video&include_html=true
```

**用途**：精确控制同步内容。

### 数据模型

#### AuthContext

```java
public class AuthContext {
    private String role;
    private String level;
    private Map<String, String> headers;  // Authorization, X-Auth-Token 等
    private Map<String, String> cookies;  // 自动合并为 Cookie header
}
```

#### ScanResult

```java
public class ScanResult {
    private String originalRequest;
    private String originalResponseSummary;  // 摘要化
    private String replayRequest;
    private String replayResponseSummary;    // 摘要化
    private int originalStatusCode;
    private int replayedStatusCode;
    private String bodyHash;                 // SHA-256
    private List<String> piiFlags;
    private long scanTimeMs;
}
```

#### ReplayRecord

```java
public class ReplayRecord {
    private String replayId;           // UUID
    private String originalHistoryId;
    private String targetRole;
    private long timestampMs;
    private ScanResult result;
}
```

---

## 三、优化建议

### 1. 保持当前 Agent 架构

当前 Security Agent + Analyzer Agent 的架构已经合理：
- **Security Agent**：执行重放测试
- **Analyzer Agent**：分析结果、判别漏洞

不建议拆分为 5 个 Agent，保持简洁。

### 2. 适配新版 BurpBridge API

更新 MCP 工具调用：

| 旧版工具 | 新版 REST API | 说明 |
|---------|--------------|------|
| `check_burp_health` | `GET /health` | 不变 |
| `sync_proxy_history_with_filters` | `POST /sync` | 增量同步 |
| `list_paginated_http_history` | `GET /history` | 分页查询 |
| `get_http_request_detail` | `GET /history/:id` | 获取详情 |
| `configure_authentication_context` | `POST /auth/config` | 支持 level 字段 |
| `list_configured_roles` | `GET /auth/roles` | 不变 |
| `delete_authentication_context` | `DELETE /auth/roles/:role` | 不变 |
| `replay_http_request_as_role` | `POST /scan/single` | 支持修改 |
| `get_replay_scan_result` | MongoDB 查询 | replays 集合 |

### 3. 新增自动同步能力

Security Agent 可配置自动同步，减少轮询开销：

```
1. 探索开始时：POST /sync/auto 启用自动同步
2. 探索过程中：自动捕获所有请求
3. 发现敏感 API 时：立即执行重放测试
4. 探索结束时：POST /sync/auto 禁用
```

### 4. 增强请求修改测试

利用 `modifications` 参数进行参数变异测试：

```json
{
  "history_entry_id": "entry_xxx",
  "target_role": "guest",
  "modifications": {
    "query_param_overrides": {"id": "999"},
    "json_field_overrides": {"user.id": 1, "role": "admin"}
  }
}
```

### 5. 引入越权判别规则

将 Analyze Agent 的判别规则细化：

```json
{
  "idor_rules": {
    "user_identity_leak": {
      "description": "用户身份泄露",
      "patterns": ["email", "phone", "ssn", "id_card"],
      "check": "response contains PII of other user"
    },
    "permission_field_exposure": {
      "description": "权限字段暴露",
      "patterns": ["role", "is_admin", "superuser", "permissions"],
      "check": "low_role response contains admin fields"
    },
    "resource_ownership_mismatch": {
      "description": "资源归属错位",
      "check": "url_id != response.owner_id"
    },
    "privileged_data_exposure": {
      "description": "高权限专属数据暴露",
      "patterns": ["internal_notes", "salary", "audit_log", "config"],
      "check": "low_role response contains privileged fields"
    }
  },
  "exclusion_rules": {
    "ignore_fields": ["timestamp", "nonce", "request_id", "trace_id", "updated_at"],
    "ignore_patterns": ["X-Cache: HIT/MISS", "Date: ..."]
  }
}
```

### 6. 敏感 API 自动识别

增强 Scout Agent 的 API 发现能力：

```json
{
  "sensitive_path_patterns": [
    "/api/users/{id}",
    "/api/orders/{id}",
    "/api/admin/*",
    "/api/settings/*",
    "/api/profile/*"
  ],
  "sensitive_response_patterns": [
    "email", "phone", "address", "ssn",
    "role", "permission", "admin",
    "password", "token", "secret", "api_key"
  ]
}
```

---

## 四、实施优先级

| 优先级 | 任务 | 预估工作量 |
|--------|------|-----------|
| P0 | 更新 Security Agent 使用新版 BurpBridge API | 2小时 |
| P1 | 增强 Analyzer Agent 的越权判别规则 | 1小时 |
| P1 | 添加自动同步配置能力 | 1小时 |
| P2 | 添加请求修改测试功能 | 2小时 |
| P2 | 优化敏感 API 自动识别 | 1小时 |
