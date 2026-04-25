---
name: anti-hallucination
description: "防幻觉规则，所有Agent必加载。防止误报漏洞，确保数据真实性。核心原则：宁可漏报，不可误报。"
---

# Anti-Hallucination Rules (防幻觉规则)

> 所有Agent必须遵守的防幻觉规则，防止误报漏洞，确保数据真实性。

## 核心原则

```
⚠️ 核心原则：宁可漏报，不可误报。质量优于数量。

Every finding MUST be based on actual data read via tools

✗ Do NOT guess API endpoints based on "typical patterns"
✗ Do NOT fabricate request IDs or replay IDs
✗ Do NOT assume elements exist without verification
✗ Do NOT report vulnerabilities without actual test results

✓ MUST verify data exists before reporting
✓ MUST quote actual output from tools
✓ MUST match project's actual situation
```

---

## 详细规则

### 1. API端点验证

```
✗ 禁止猜测API路径
  - 不要假设存在 /api/users
  - 不要假设存在 /api/admin
  - 不要基于"常见模式"推断API
  
✓ 必须来自实际网络请求
  - 使用 browser_network_requests 获取实际请求
  - 使用 BurpBridge list_paginated_http_history 查询历史
  - 记录实际的URL和参数
```

### 2. 请求ID验证

```
✗ 禁止编造history_entry_id
  - 不要使用 "xxx" 或 "entry_001" 等假ID
  - 不要基于推测生成ID
  
✓ 必须来自BurpBridge实际查询结果
  - 先查询历史记录获取真实ID
  - 使用 get_http_request_detail 验证ID有效
  - ID格式：MongoDB ObjectId（24位十六进制）
```

### 3. Cookie值验证

```
✗ 禁止猜测Cookie内容
  - 不要假设 session=abc123
  - 不要编造 Authorization: Bearer xxx
  
✓ 必须来自browser-use实际输出
  - 使用 browser-use cookies get --json 获取实际Cookie
  - 从 sessions.json 读取已登录账号的Cookie
```

### 4. 页面元素验证

```
✗ 禁止假设元素存在
  - 不要假设有登录表单
  - 不要假设有特定按钮
  
✓ 必须来自browser_snapshot实际输出
  - 使用 browser_snapshot 获取Accessibility Tree
  - 元素必须存在于实际快照中
  - selector必须匹配实际元素
```

### 5. 漏洞判定验证

```
✗ 禁止凭"感觉"判定漏洞
  - 不要因为"看起来像"就判定漏洞
  - 不要基于理论知识假设漏洞存在
  
✓ 必须基于实际重放结果
  - 使用 get_replay_scan_result 获取重放详情
  - 状态码、响应体必须来自实际响应
  - 敏感数据必须在实际响应中发现
```

---

## 错误示例（幻觉来源）

```
❌ 错误示例：
1. 查询 IDOR 知识 → 看到 /api/users/{id} 示例
2. 没有在项目中找到该API
3. 仍然报告 "IDOR漏洞: /api/users/{id}"  ← 这是幻觉！

❌ 错误示例：
1. 假设网站有登录功能
2. 没有实际检测登录表单
3. 报告 "登录绕过漏洞"  ← 这是幻觉！

❌ 错误示例：
1. 理论上"Cookie应该包含session"
2. 没有实际获取Cookie
3. 使用编造的Cookie进行测试  ← 这是幻觉！
```

---

## 正确示例

```
✓ 正确示例（API发现）：
1. 使用 browser_network_requests 获取实际请求
2. 过滤出 /api/* 路径的请求
3. 记录实际的API端点（如 /api/products/list）
4. 只有实际发现的API才进行测试

✓ 正确示例（越权测试）：
1. 使用 BurpBridge list_paginated_http_history 查询历史
2. 获取真实的 history_entry_id
3. 使用 configure_authentication_context 配置实际Cookie
4. 使用 replay_http_request_as_role 执行重放
5. 使用 get_replay_scan_result 获取实际结果
6. 基于实际响应判定漏洞

✓ 正确示例（Cookie同步）：
1. 使用 browser-use cookies get --json 获取实际Cookie
2. 记录到 sessions.json
3. 使用 configure_authentication_context 同步到BurpBridge
4. 使用实际Cookie进行后续测试
```

---

## Agent级别验证清单

每个Agent在报告发现前必须验证：

| Agent | 验证项 |
|-------|--------|
| Scout | API端点来自browser_network_requests |
| Form | 表单元素来自browser_snapshot |
| Security | history_entry_id来自BurpBridge查询 |
| Security | replay_id来自实际重放结果 |
| Analyzer | 漏洞判定基于get_replay_scan_result |

---

## 加载要求

此Skill必须由所有Agent加载：

```yaml
## Skill 加载规则（双通道）

1. 尝试: skill({ name: "anti-hallucination" })
2. 若失败: Read("skills/core/anti-hallucination/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```