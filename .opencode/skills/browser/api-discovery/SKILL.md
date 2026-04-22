---
name: api-discovery
description: "API发现方法论，网络请求分析、敏感数据检测、模式识别。"
---

# API Discovery Skill

> API发现方法论 — 网络请求分析、敏感数据检测、模式识别、模块分类

---

## 发现流程

```
页面加载 → browser_network_requests → 过滤API → 分析参数 → 检测敏感数据 → 写入MongoDB
```

---

## API路径模式

### 常见API模式

| 模式 | 示例 | 测试优先级 |
|------|------|-----------|
| `/api/users/{id}` | /api/users/123 | **Critical** |
| `/api/orders/{id}` | /api/orders/456 | **High** |
| `/api/admin/*` | /api/admin/config | **High** |
| `/api/settings/*` | /api/settings/profile | **Medium** |
| `/api/profile/*` | /api/profile/me | **Medium** |
| `/api/data/*` | /api/data/export | **Medium** |
| `/v1/*`, `/v2/*` | /v1/products | 按内容判定 |

### 模式提取函数

```javascript
function extractApiPattern(url) {
  const pathSegments = url.pathname.split('/');
  
  const pattern = pathSegments.map(segment => {
    // 数字ID → {id}
    if (/^\d+$/.test(segment)) return '{id}';
    
    // UUID → {uuid}
    if (/^[a-f0-9-]{36}$/i.test(segment)) return '{uuid}';
    
    // 其他保持不变
    return segment;
  }).join('/');
  
  return pattern;
}

// 示例
extractApiPattern("/api/users/123")       // → /api/users/{id}
extractApiPattern("/api/posts/abc/comments") // → /api/posts/{id}/comments
```

---

## 敏感字段检测

### 敏感字段类别

| 类别 | 关键词 | 风险级别 |
|------|--------|---------|
| **身份信息** | email, phone, ssn, id_card, username, address | High |
| **权限控制** | role, is_admin, superuser, permissions, group | High |
| **所有权** | owner_id, user_id, created_by, belong_to | High |
| **内部数据** | internal, debug, config, secret, api_key, salary | High |
| **财务数据** | balance, credit_card, bank_account, transaction | Critical |
| **凭证** | password, token, session, auth, credential | Critical |

### 检测函数

```javascript
const sensitiveFieldPatterns = {
  identity: /email|phone|ssn|id_card|username|address/i,
  permission: /role|is_admin|superuser|permissions|group/i,
  ownership: /owner_id|user_id|created_by|belong_to/i,
  internal: /internal|debug|config|secret|api_key|salary/i,
  finance: /balance|credit_card|bank_account|transaction/i,
  credential: /password|token|session|auth|credential/i
};

function detectSensitiveFields(responseBody) {
  const found = [];
  
  // 尝试解析JSON
  try {
    const json = JSON.parse(responseBody);
    for (const [category, pattern] of sensitiveFieldPatterns) {
      if (containsField(json, pattern)) {
        found.push({
          category: category,
          fields: extractMatchingFields(json, pattern)
        });
      }
    }
  } catch {
    // 非JSON响应，使用文本检测
    for (const [category, pattern] of sensitiveFieldPatterns) {
      if (pattern.test(responseBody)) {
        found.push({ category: category });
      }
    }
  }
  
  return found;
}
```

---

## 网络请求分析

### 使用browser_network_requests

```javascript
// 获取网络请求
const requests = await browser_network_requests({
  static: false,           // 排除静态资源
  requestBody: true,       // 包含请求体
  requestHeaders: true,    // 包含请求头
  filter: "/api/.*user"    // 正则过滤（可选）
});

// 请求格式
[
  {
    url: "https://example.com/api/users/123",
    method: "GET",
    requestHeaders: {
      Authorization: "Bearer xxx",
      Content-Type: "application/json"
    },
    requestBody: null,
    responseStatus: 200,
    responseHeaders: {
      Content-Type: "application/json"
    },
    responseBody: '{"id":123,"email":"user@example.com"}'
  }
]
```

### 过滤静态资源

默认排除的MIME类型：

```
image/*, video/*, audio/*, font/*
application/javascript, text/javascript
application/x-javascript, text/css
application/pdf, application/zip
```

---

## API模块分类

### 自动分类规则

```javascript
function classifyApiModule(endpoint) {
  const modulePatterns = {
    "user": [/\/api\/users/, /\/api\/profile/, /\/api\/account/, /\/api\/member/],
    "admin": [/\/api\/admin/, /\/api\/settings/, /\/api\/config/, /\/api\/system/],
    "order": [/\/api\/orders/, /\/api\/cart/, /\/api\/payment/, /\/api\/transaction/],
    "content": [/\/api\/posts/, /\/api\/articles/, /\/api\/comments/, /\/api\/media/],
    "workflow": [/\/api\/workflow/, /\/api\/approval/, /\/api\/process/, /\/api\/task/],
    "auth": [/\/api\/auth/, /\/api\/login/, /\/api\/token/, /\/api\/session/],
    "data": [/\/api\/data/, /\/api\/export/, /\/api\/import/, /\/api\/report/],
    "other": [/\/api\//]  // 兜底
  };
  
  for (const [module, patterns] of modulePatterns) {
    for (const pattern of patterns) {
      if (pattern.test(endpoint)) {
        return module;
      }
    }
  }
  
  return "other";
}
```

---

## 实时写入MongoDB

### 发现API后立即写入

```javascript
async function saveApiToMongo(apiData) {
  await mongodb-mcp-server_insert-many({
    database: "webtest",
    collection: "apis",
    documents: [{
      session_id: currentSessionId,
      api_id: generateApiId(),
      url: apiData.url,
      method: apiData.method,
      pattern_detected: extractApiPattern(apiData.url),
      module: classifyApiModule(apiData.url),
      sensitive_fields: detectSensitiveFields(apiData.responseBody),
      test_status: "discovered",
      discovered_at: Date.now(),
      source_page: currentPageUrl,
      headers: apiData.requestHeaders,
      parameters: extractParameters(apiData.url)
    }]
  });
}
```

### 更新progress collection

```javascript
async function updateProgress(module, apiId) {
  await mongodb-mcp-server_update-many({
    database: "webtest",
    collection: "progress",
    filter: { session_id: currentSessionId },
    update: {
      $push: {
        `modules.${module}.apis`: {
          api_id: apiId,
          test_status: "discovered"
        }
      },
      $inc: {
        "overall_stats.total_apis": 1,
        "overall_stats.discovered": 1
      }
    }
  });
}
```

---

## 创建事件

发现敏感API时创建事件：

```javascript
async function createApiDiscoveredEvent(apiData) {
  await mongodb-mcp-server_insert-many({
    database: "webtest",
    collection: "events",
    documents: [{
      session_id: currentSessionId,
      event_id: generateEventId(),
      event_type: "API_DISCOVERED",
      source_agent: "Scout Agent",
      priority: apiData.sensitive_fields.length > 0 ? "high" : "normal",
      status: "pending",
      payload: {
        api_id: apiData.api_id,
        endpoint: apiData.url,
        method: apiData.method,
        sensitive: apiData.sensitive_fields.length > 0,
        module: apiData.module
      },
      created_at: Date.now()
    }]
  });
}
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Scout 必须加载

1. 尝试: skill({ name: "api-discovery" })
2. 若失败: Read("skills/browser/api-discovery/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```