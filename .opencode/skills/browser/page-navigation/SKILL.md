---
name: page-navigation
description: "页面导航方法论，Navigator Agent使用。导航策略、深度控制、链接跟踪。"
---

# Page Navigation Skill

> 页面导航方法论 — 导航策略、深度控制、链接跟踪、会话状态监控

---

## 导航流程

```
┌─────────────────────────────────────────────────────────────┐
│  Navigator Agent 导航流程                                     │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. 获取导航目标                                              │
│     - 从Coordinator接收URL                                    │
│     - 或从Scout发现的链接中选择                                │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 检查URL有效性                                             │
│     - 是否已访问过                                            │
│     - 是否在same_domain限制内                                  │
│     - 是否在ignore_patterns中                                  │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 执行导航                                                  │
│     browser-use open {url}                                   │
│     或 browser_click(link_element)                           │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 等待页面稳定                                              │
│     - 等待DOM加载完成                                         │
│     - 等待网络请求完成                                        │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. 记录访问                                                  │
│     - 更新pages.json                                         │
│     - 更新sessions.json的last_activity                       │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  6. 检测Cookie变化                                            │
│     - 如有变化，创建COOKIE_CHANGED事件                        │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  7. 通知Scout Agent分析页面                                   │
└─────────────────────────────────────────────────────────────┐
```

---

## 深度控制

### 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_depth | 3 | 最大探索深度 |
| max_pages | 50 | 最大访问页面数 |
| same_domain_only | true | 仅同域名 |
| ignore_patterns | [] | 忽略的URL模式 |

### 深度计算

```javascript
function calculateDepth(url, baseUrl) {
  // 基于URL路径深度计算
  const pathSegments = url.pathname.split('/').filter(s => s);
  const basePathSegments = baseUrl.pathname.split('/').filter(s => s);
  
  // 计算相对深度
  let depth = 0;
  let matchIndex = 0;
  
  for (let i = 0; i < basePathSegments.length; i++) {
    if (pathSegments[i] === basePathSegments[i]) {
      matchIndex = i + 1;
    }
  }
  
  depth = pathSegments.length - matchIndex;
  
  return depth;
}

// 示例
calculateDepth("/dashboard/profile/settings", "/dashboard")
// → depth = 2
```

---

## URL过滤

### 去重检查

```javascript
function shouldVisit(url, visitedUrls) {
  // 1. 检查是否已访问
  const normalizedUrl = normalizeUrl(url);
  if (visitedUrls.includes(normalizedUrl)) {
    return { visit: false, reason: "already_visited" };
  }
  
  // 2. 检查域名限制
  if (config.same_domain_only) {
    if (!isSameDomain(url, config.target_host)) {
      return { visit: false, reason: "different_domain" };
    }
  }
  
  // 3. 检查忽略模式
  for (const pattern of config.ignore_patterns) {
    if (matchPattern(url, pattern)) {
      return { visit: false, reason: "ignore_pattern" };
    }
  }
  
  // 4. 检查深度限制
  if (calculateDepth(url) > config.max_depth) {
    return { visit: false, reason: "depth_exceeded" };
  }
  
  return { visit: true };
}

function normalizeUrl(url) {
  // 去除fragment、查询参数排序等
  const parsed = new URL(url);
  parsed.hash = "";
  parsed.searchParams.sort();
  return parsed.toString();
}
```

### 默认忽略模式

```javascript
const defaultIgnorePatterns = [
  // 静态资源
  "*.js",
  "*.css",
  "*.png",
  "*.jpg",
  "*.gif",
  "*.svg",
  "*.woff",
  "*.woff2",
  
  // 常见无意义路径
  "#",                          // fragment链接
  "javascript:*",               // JS伪协议
  "mailto:*",                   // 邮件链接
  "tel:*",                      // 电话链接
  
  // 登出操作（避免中断会话）
  "*logout*",
  "*signout*",
  
  // 文件下载
  "*.pdf",
  "*.zip",
  "*.doc",
  "*.xls"
];
```

---

## 链接优先级

### Scout发现链接后排序

```javascript
function prioritizeLinks(links) {
  const priorities = {
    // 最高优先级
    critical: [
      "登录", "login", "signin",
      "注册", "register", "signup",
      "管理", "admin", "manage",
      "用户", "user", "profile", "account"
    ],
    
    // 高优先级
    high: [
      "设置", "settings", "config",
      "订单", "order", "cart",
      "数据", "data", "export", "import",
      "审批", "workflow", "approval"
    ],
    
    // 中优先级
    medium: [
      "搜索", "search", "query",
      "列表", "list", "index",
      "详情", "detail", "view"
    ],
    
    // 低优先级
    low: [
      "帮助", "help", "faq",
      "关于", "about",
      "联系", "contact"
    ]
  };
  
  return links.map(link => {
    let priority = "normal";
    const text = link.text.toLowerCase();
    
    for (const [level, keywords] of priorities) {
      for (const keyword of keywords) {
        if (text.includes(keyword)) {
          priority = level;
          break;
        }
      }
    }
    
    return { ...link, priority };
  }).sort((a, b) => {
    const order = ["critical", "high", "medium", "normal", "low"];
    return order.indexOf(a.priority) - order.indexOf(b.priority);
  });
}
```

---

## 导航方法

### 前提条件

**导航前必须确保**：
1. Chrome 实例已创建（带 `--proxy-server` 参数）
2. browser-use session 已通过 `--cdp-url` 首次连接

**首次连接命令**（仅需执行一次）：
```bash
# 首次连接：带 --cdp-url
browser-use --session {session_name} --cdp-url http://localhost:9222 open {初始URL}

# 示例
browser-use --session admin_001 --cdp-url http://localhost:9222 open https://example.com
```

### 直接URL导航

**后续导航不需要 --cdp-url**：
```bash
browser-use --session {session_name} open {url}

# 示例
browser-use --session admin_001 open https://example.com/profile
browser-use --session admin_001 open https://example.com/dashboard
```

### 点击链接导航

```bash
browser-use --session admin_001 click "a[href='/profile']"
browser-use --session admin_001 click "text=用户设置"
```

### 获取页面状态

```bash
# 查看当前页面状态（用于导航后验证）
browser-use --session admin_001 state
```

### 使用/browser-use Skill

```yaml
/browser-use描述任务:
"请导航到用户个人中心页面：
- 点击页面右上角的'个人中心'链接
- 等待页面加载完成
- 返回当前URL"
```

### ⚠️ 注意事项

```bash
# ❌ 错误：session 未建立连接时直接操作
browser-use --session new_session state  # 报错：Session not found

# ✅ 正确：先建立连接，再执行导航
browser-use --session new_session --cdp-url http://localhost:9222 open https://example.com
browser-use --session new_session state  # 现在可以正常操作
```

---

## 会话状态监控

### Cookie变化检测

```javascript
async function checkCookieChange(session_name) {
  const currentCookies = await browser-use_cookies_get(session_name);
  const previousCookies = readJson("result/sessions.json")
    .sessions.find(s => s.browser_use_session === session_name)
    ?.auth_context?.cookies || {};
  
  const changes = compareCookies(previousCookies, currentCookies);
  
  if (changes.length > 0) {
    // 创建COOKIE_CHANGED事件
    createEvent("COOKIE_CHANGED", {
      priority: "normal",
      payload: {
        session_name,
        changes: changes
      }
    });
    
    // 更新sessions.json
    updateSessionCookies(session_name, currentCookies);
  }
}

function compareCookies(previous, current) {
  const changes = [];
  
  for (const [name, value] of Object.entries(current)) {
    if (previous[name] !== value) {
      changes.push({
        name,
        oldValue: previous[name],
        newValue: value,
        type: previous[name] ? "modified" : "added"
      });
    }
  }
  
  for (const name of Object.keys(previous)) {
    if (!current[name]) {
      changes.push({
        name,
        oldValue: previous[name],
        newValue: null,
        type: "removed"
      });
    }
  }
  
  return changes;
}
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Navigator 必须加载

1. 尝试: skill({ name: "page-navigation" })
2. 若失败: Read("skills/browser/page-navigation/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```