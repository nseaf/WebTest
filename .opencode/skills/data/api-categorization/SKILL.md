---
name: api-categorization
description: "API分类规则，与progress-tracking配合使用。定义模块划分、优先级判定。"
---

# API Categorization Skill

> API分类规则 — 模块划分、优先级判定、敏感度检测

---

## 模块划分规则

### 预定义模块

| 模块 | 路径模式 | 说明 | 默认优先级 |
|------|---------|------|-----------|
| **user** | /api/users/*, /api/profile/*, /api/account/* | 用户管理 | high |
| **admin** | /api/admin/*, /api/settings/*, /api/config/* | 系统管理 | high |
| **auth** | /api/auth/*, /api/login/*, /api/token/* | 认证授权 | high |
| **order** | /api/orders/*, /api/cart/*, /api/payment/* | 订单交易 | medium |
| **workflow** | /api/workflow/*, /api/approval/*, /api/process/* | 流程审批 | medium |
| **content** | /api/posts/*, /api/articles/*, /api/comments/* | 内容管理 | low |
| **data** | /api/data/*, /api/export/*, /api/import/* | 数据操作 | medium |
| **other** | /api/* | 其他API | normal |

---

## 分类实现

### 正则匹配

```javascript
const modulePatterns = [
  { module: "user", patterns: [/^\/api\/users/, /^\/api\/profile/, /^\/api\/account/, /^\/api\/member/] },
  { module: "admin", patterns: [/^\/api\/admin/, /^\/api\/settings/, /^\/api\/config/, /^\/api\/system/] },
  { module: "auth", patterns: [/^\/api\/auth/, /^\/api\/login/, /^\/api\/token/, /^\/api\/session/] },
  { module: "order", patterns: [/^\/api\/orders/, /^\/api\/cart/, /^\/api\/payment/, /^\/api\/transaction/] },
  { module: "workflow", patterns: [/^\/api\/workflow/, /^\/api\/approval/, /^\/api\/process/, /^\/api\/task/] },
  { module: "content", patterns: [/^\/api\/posts/, /^\/api\/articles/, /^\/api\/comments/, /^\/api\/media/] },
  { module: "data", patterns: [/^\/api\/data/, /^\/api\/export/, /^\/api\/import/, /^\/api\/report/] },
  { module: "other", patterns: [/^\/api\//] }  // 兜底
];

function classifyModule(endpoint) {
  // 提取路径
  const path = endpoint.split('?')[0];
  
  // 按优先级匹配（精确优先）
  for (const { module, patterns } of modulePatterns) {
    if (module === "other") continue;  // 兜底最后
    
    for (const pattern of patterns) {
      if (pattern.test(path)) {
        return module;
      }
    }
  }
  
  return "other";
}
```

---

## 优先级判定

### API优先级因素

```javascript
function calculateApiPriority(api) {
  let score = 0;
  
  // 1. 模块优先级
  const modulePriority = {
    user: 30,
    admin: 30,
    auth: 30,
    workflow: 20,
    order: 20,
    data: 20,
    content: 10,
    other: 10
  };
  score += modulePriority[api.module] || 10;
  
  // 2. 敏感字段数量
  if (api.sensitive_fields?.length > 0) {
    score += api.sensitive_fields.length * 5;
  }
  
  // 3. HTTP方法
  if (["POST", "PUT", "DELETE"].includes(api.method)) {
    score += 10;  // 写操作优先级更高
  }
  
  // 4. 路径包含关键词
  const highKeywords = ["admin", "config", "password", "token", "secret", "delete"];
  for (const keyword of highKeywords) {
    if (api.url.toLowerCase().includes(keyword)) {
      score += 10;
    }
  }
  
  // 5. 响应包含PII
  if (api.responseContainsPII) {
    score += 15;
  }
  
  // 计算最终优先级
  if (score >= 50) return "critical";
  if (score >= 40) return "high";
  if (score >= 25) return "medium";
  return "low";
}
```

---

## 敏感度检测

### 敏感字段关键词

```javascript
const sensitiveKeywords = {
  // 身份信息（PII）
  identity: [
    "email", "phone", "mobile", "ssn", "id_card",
    "username", "realname", "name", "address",
    "birthday", "age", "gender"
  ],
  
  // 权限相关
  permission: [
    "role", "is_admin", "superuser", "permissions",
    "group", "level", "access", "privilege"
  ],
  
  // 所有权
  ownership: [
    "owner_id", "user_id", "created_by", "belong_to",
    "author", "creator", "uploader"
  ],
  
  // 内部数据
  internal: [
    "internal", "debug", "config", "secret",
    "api_key", "apikey", "salary", "bonus"
  ],
  
  // 财务数据
  finance: [
    "balance", "credit_card", "bank_account",
    "transaction", "payment", "amount"
  ],
  
  // 凭证
  credential: [
    "password", "passwd", "pwd", "token",
    "session", "auth", "secret_key"
  ]
};
```

### 检测函数

```javascript
function detectSensitiveData(responseBody) {
  const found = [];
  
  try {
    const json = JSON.parse(responseBody);
    const flatFields = flattenObject(json);
    
    for (const [field, value] of Object.entries(flatFields)) {
      const fieldLower = field.toLowerCase();
      
      for (const [category, keywords] of Object.entries(sensitiveKeywords)) {
        for (const keyword of keywords) {
          if (fieldLower.includes(keyword)) {
            found.push({
              category: category,
              field: field,
              keyword: keyword,
              value_type: typeof value
            });
            break;
          }
        }
      }
    }
  } catch {
    // 非JSON，文本检测
    for (const [category, keywords] of Object.entries(sensitiveKeywords)) {
      for (const keyword of keywords) {
        if (responseBody.toLowerCase().includes(keyword)) {
          found.push({ category: category, keyword: keyword });
        }
      }
    }
  }
  
  return found;
}
```

---

## 与progress-tracking配合

### 更新progress collection

```javascript
async function updateProgressWithApi(api) {
  const module = classifyModule(api.url);
  const priority = calculateApiPriority(api);
  
  await mongodb-mcp-server_update-many({
    database: "webtest",
    collection: "progress",
    filter: { session_id: currentSessionId },
    update: {
      $push: {
        `modules.${module}.apis`: {
          api_id: api.api_id,
          endpoint: api.url,
          method: api.method,
          test_status: "discovered",
          priority: priority
        }
      },
      $inc: {
        `modules.${module}.stats.total`: 1,
        `modules.${module}.stats.discovered`: 1,
        "overall_stats.total_apis": 1,
        "overall_stats.discovered": 1
      },
      $set: { last_updated: Date.now() }
    }
  });
  
  // 如果高优先级，加入敏感API列表
  if (priority === "critical" || priority === "high") {
    await mongodb-mcp-server_update-many({
      database: "webtest",
      collection: "progress",
      filter: { session_id: currentSessionId },
      update: {
        $push: {
          "sensitive_apis.untested": api.api_id
        },
        $inc: {
          "sensitive_apis.total": 1
        }
      }
    });
  }
}
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Navigator、Security 必须加载

1. 尝试: skill({ name: "api-categorization" })
2. 若失败: Read("skills/data/api-categorization/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```
