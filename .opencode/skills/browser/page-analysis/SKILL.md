---
name: page-analysis
description: "页面分析方法论，Scout Agent使用。性能优化、元素分类、发现记录。"
---

# Page Analysis Skill

> 页面分析方法论 — 快照获取、元素分类、API发现、性能优化

---

## 分析流程

```
┌─────────────────────────────────────────────────────────────┐
│  Scout Agent 页面分析流程                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. 获取CDP连接信息                                           │
│     Read("result/sessions.json")                             │
│     → cdp_url, browser_use_session                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 获取页面快照                                              │
│     browser_snapshot(depth=2-3)                              │
│     或 browser_snapshot(filename=".tmp/...")                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 解析Accessibility Tree                                    │
│     - 提取链接列表                                            │
│     - 提取表单列表                                            │
│     - 提取按钮、输入框                                        │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 分析网络请求                                              │
│     browser_network_requests(static=false)                   │
│     → 发现API端点                                            │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. 实时写入MongoDB                                           │
│     apis collection                                           │
│     pages collection                                          │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  6. 返回发现报告                                              │
│     HEADER + TRANSFER BLOCK + AGENT_OUTPUT_END               │
└─────────────────────────────────────────────────────────────┘
```

---

## 性能优化策略

### 关键问题：MCP响应可能过大

```
browser_snapshot返回完整Accessibility Tree
- 复杂页面可能产生50k+ tokens
- 导致上下文溢出
- Agent无法正常工作
```

### 优化方法

#### 1. 使用depth参数限制深度

```javascript
// 仅获取前2-3层（足够发现主要元素）
browser_snapshot({ depth: 2 })

// depth建议值：
// - depth=1: 仅页面根元素
// - depth=2: 主要区块和表单（推荐）
// - depth=3: 更详细的元素结构
// - 无depth: 完整树（仅特殊需要时使用）
```

#### 2. 使用filename参数保存到文件

```javascript
// 不返回到上下文，保存到临时文件
browser_snapshot({ 
  filename: ".tmp/snapshots/scout_20260422_page1.yaml" 
})

// 需要详细分析时再读取文件
Read(".tmp/snapshots/scout_20260422_page1.yaml")
```

#### 3. 网络请求过滤

```javascript
// 排除静态资源
browser_network_requests({
  static: false,           // 不包含图片、CSS、JS等
  requestBody: true,       // 包含请求体
  requestHeaders: true     // 包含请求头
})

// 仅匹配API请求
browser_network_requests({
  static: false,
  filter: "/api/.*"        // 正则过滤
})
```

---

## 元素分类规则

### 按交互类型分类

| 类型 | Accessibility角色 | 说明 | 优先级 |
|------|------------------|------|--------|
| 按钮 | button | 可点击操作 | P2 |
| 链接 | link | 导航链接 | P1 |
| 输入框 | textbox | 文本输入 | P2 |
| 表单 | form | 表单容器 | P1 |
| 下拉框 | combobox | 选择框 | P2 |
| 复选框 | checkbox | 多选框 | P3 |

### 按功能类型分类

| 功能类型 | 识别规则 | 优先级 |
|---------|---------|--------|
| 登录入口 | link[name~="登录"], link[href~="login"] | P1 |
| 注册入口 | link[name~="注册"], link[href~="register"] | P1 |
| 用户中心 | link[name~="个人"], link[href~="profile"] | P1 |
| 管理入口 | link[name~="管理"], link[href~="admin"] | P1 |
| 搜索功能 | textbox[placeholder~="搜索"], form[action~="search"] | P2 |
| 数据列表 | grid, table, list | P2 |

---

## 发现记录格式

### 页面分析报告

```json
{
  "page_url": "https://example.com/dashboard",
  "page_title": "Dashboard",
  "page_type": "dashboard",
  "links": [
    {
      "url": "https://example.com/profile",
      "text": "个人中心",
      "priority": 1,
      "visited": false
    }
  ],
  "forms": [
    {
      "selector": "#search-form",
      "type": "search",
      "fields_count": 1
    }
  ],
  "apis_discovered": [
    {
      "url": "/api/users/list",
      "method": "GET",
      "sensitive": false
    }
  ],
  "recommendations": [
    "发现个人中心链接，建议Navigator跟踪",
    "发现用户列表API，建议Security测试IDOR"
  ]
}
```

### API发现记录

```json
{
  "api_id": "api_001",
  "url": "/api/users/123",
  "method": "GET",
  "pattern_detected": "/api/users/{id}",
  "module": "user",
  "sensitive_fields": ["email", "phone"],
  "test_status": "discovered",
  "source_page": "https://example.com/dashboard",
  "discovered_at": Date.now()
}
```

---

## 网络请求分析

### API路径模式识别

```javascript
const apiPatterns = [
  /^\/api\/[\w/-]+$/,           // /api/users, /api/users/123
  /^\/v\d+\/[\w/-]+$/,          // /v1/users, /v2/posts
  /^\/graphql$/,                // GraphQL端点
  /^\/rest\/[\w/-]+$/,          // REST API
  /^\/[\w/-]+\.(json|xml)$/     // JSON/XML响应
];

function isApiRequest(url) {
  return apiPatterns.some(p => p.test(url.pathname));
}
```

### 动态参数提取

```javascript
// /api/users/123 → {id: 123}
// /api/posts/abc/comments → {id: abc}
function extractParameters(url) {
  const pathSegments = url.pathname.split('/');
  const params = [];
  
  for (let i = 0; i < pathSegments.length; i++) {
    const segment = pathSegments[i];
    
    // 数字ID
    if (/^\d+$/.test(segment)) {
      params.push({ name: "id", value: segment, location: "path" });
    }
    
    // UUID
    if (/^[a-f0-9-]{36}$/i.test(segment)) {
      params.push({ name: "uuid", value: segment, location: "path" });
    }
  }
  
  return params;
}
```

### 敏感数据检测

```javascript
const sensitiveKeywords = [
  "password", "token", "secret", "api_key", "apikey",
  "session", "auth", "credential", "private",
  "email", "phone", "address", "ssn", "credit",
  "user", "profile", "account", "setting"
];

function checkSensitiveData(responseBody) {
  const found = [];
  const bodyLower = responseBody.toLowerCase();
  
  for (const keyword of sensitiveKeywords) {
    if (bodyLower.includes(keyword)) {
      found.push(keyword);
    }
  }
  
  return found;
}
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Scout 必须加载

1. 尝试: skill({ name: "page-analysis" })
2. 若失败: Read("skills/browser/page-analysis/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```