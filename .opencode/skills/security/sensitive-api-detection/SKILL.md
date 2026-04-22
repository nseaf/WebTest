---
name: sensitive-api-detection
description: "敏感API识别规则。路径模式、敏感字段词典、优先级判定。"
---

# Sensitive API Detection Skill

> 敏感API识别规则 — 路径模式、敏感字段词典、优先级判定

---

## 路径模式识别

```json
{
  "sensitive_path_patterns": [
    { "pattern": "/api/users/{id}", "priority": "critical", "test_id_range": true },
    { "pattern": "/api/orders/{id}", "priority": "high", "test_id_range": true },
    { "pattern": "/api/admin/*", "priority": "high", "test_role_escalation": true },
    { "pattern": "/api/settings/*", "priority": "medium" },
    { "pattern": "/api/profile/*", "priority": "medium" },
    { "pattern": "/api/workflow/*", "priority": "high", "test_authorization": true },
    { "pattern": "/api/approve/*", "priority": "high", "test_authorization": true }
  ]
}
```

**优先级说明**：

| 优先级 | 含义 | 测试建议 |
|--------|------|----------|
| critical | 高危API，包含PII | 必测，遍历ID范围 |
| high | 重要API，权限控制关键 | 必测，角色遍历 |
| medium | 中等风险 | 建议测试 |
| low | 低风险 | 可选测试 |

---

## 敏感字段词典

### 身份信息（PII）

| 字段名 | 风险级别 | 说明 |
|--------|---------|------|
| email | 高 | 电子邮箱 |
| phone | 高 | 电话号码 |
| ssn | 严重 | 社会安全号 |
| id_card | 严重 | 身份证号 |
| username | 中 | 用户名 |
| address | 高 | 地址 |
| birthday | 高 | 生日 |

### 权限控制

| 字段名 | 风险级别 | 说明 |
|--------|---------|------|
| role | 高 | 角色 |
| is_admin | 高 | 是否管理员 |
| superuser | 高 | 超级用户 |
| permissions | 高 | 权限列表 |
| group | 中 | 用户组 |
| level | 中 | 级别 |

### 资源归属

| 字段名 | 风险级别 | 说明 |
|--------|---------|------|
| owner_id | 高 | 所有者ID |
| user_id | 高 | 用户ID |
| created_by | 中 | 创建者 |
| belong_to | 中 | 归属 |

### 内部数据

| 字段名 | 风险级别 | 说明 |
|--------|---------|------|
| internal_notes | 高 | 内部备注 |
| salary | 严重 | 薪资 |
| api_key | 严重 | API密钥 |
| secret | 严重 | 密钥 |
| config | 高 | 配置 |
| debug | 中 | 调试信息 |

---

## 完整字段配置

```json
{
  "sensitive_response_fields": {
    "identity": ["email", "phone", "ssn", "id_card", "username", "address"],
    "permission": ["role", "is_admin", "superuser", "permissions", "group"],
    "ownership": ["owner_id", "user_id", "created_by", "belong_to"],
    "internal": ["internal", "debug", "config", "secret", "api_key", "salary"],
    "audit": ["audit", "log", "history", "trace"]
  }
}
```

---

## 检测逻辑

```javascript
function checkSensitiveFields(responseBody) {
  const found = [];
  const body = JSON.parse(responseBody);
  
  for (const category of Object.keys(sensitiveFields)) {
    for (const field of sensitiveFields[category]) {
      if (body[field] !== undefined) {
        found.push({
          field: field,
          category: category,
          value: body[field]
        });
      }
    }
  }
  
  return found;
}
```

---

## 加载要求

```yaml
## Skill加载规则（双通道）

# Security、Analyzer必须加载

1. 尝试: skill({ name: "sensitive-api-detection" })
2. 若失败: Read("skills/security/sensitive-api-detection/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```