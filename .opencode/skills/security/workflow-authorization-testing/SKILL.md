---
name: workflow-authorization-testing
description: "流程审批越权测试方法论。请求重放测试、API发现关联、测试矩阵生成、结果判断规则。"
---

# Workflow Authorization Testing Skill

> 流程审批越权测试方法论 — 请求重放测试、API发现关联、测试矩阵生成

---

## 核心原理

流程审批场景具有特殊性：审批操作是不可逆的，用正常账号审批后流程状态改变，无法在原流程上测试其他账户的越权。

**解决方案**：请求重放测试 - 不实际执行审批操作，而是拦截请求并用其他角色的认证信息重放，分析响应判断是否存在越权漏洞。

```
正常审批流程：
┌─────────────────────────────────────────────────────────────────┐
│ 1. 账号A登录，执行审批操作                                        │
│ 2. 请求通过Burp代理，被BurpBridge捕获                              │
│ 3. 请求记录到MongoDB（包含完整请求头和请求体）                      │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 越权测试（不影响原流程）：                                          │
│ 4. Security Agent获取审批请求详情                                  │
│ 5. 使用其他角色的Cookie重放该请求                                   │
│ 6. Analyzer Agent分析响应：                                        │
│    - 如果返回"无权限"：安全                                        │
│    - 如果返回"审批成功"：越权漏洞！                                  │
│ 7. 原流程状态不变，可继续正常审批                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 配置文件依赖

流程审批测试依赖 `result/workflow_config.json`：

```json
{
  "$schema": "workflow_config_schema",
  "workflows": [
    {
      "workflow_id": "software_nre_approval",
      "workflow_name": "软件NRE审批流程",
      "nodes": [
        {
          "node_id": "submit_terminate",
          "node_name": "提交终止",
          "menu_path": ["软件NRE"],
          "actions": ["提交"],
          "required_roles": ["生态经理"],
          "api_endpoint": null,
          "http_method": null,
          "request_template": null,
          "discovered": false
        }
      ]
    }
  ],
  "api_discovery": {
    "auto_record_enabled": true,
    "pending_nodes": [],
    "discovered_nodes": []
  },
  "test_results": {
    "last_test_at": null,
    "total_tests": 0,
    "passed": 0,
    "failed": 0,
    "vulnerabilities_found": []
  }
}
```

---

## 测试流程

### 阶段1：API发现（自动记录）

在正常审批流程执行时，Navigator Agent记录页面侧 API 线索，并由 Security 结合 BurpBridge 历史确认端点：

```
1. Navigator Agent按流程顺序操作
2. Form Agent执行审批操作
3. Navigator Agent记录页面中的接口线索
4. 识别审批相关请求（POST/PUT）
5. 关联到流程节点（通过菜单路径或请求内容）
6. 更新workflow_config.json
```

**API_DISCOVERED事件**：

```json
{
  "event_type": "API_DISCOVERED",
  "source_agent": "Navigator Agent",
  "payload": {
    "api_url": "/api/workflow/terminate",
    "method": "POST",
    "workflow_node": "submit_terminate",
    "discovered_at": "2026-04-20T10:00:00Z"
  }
}
```

---

### 阶段2：越权测试

**步骤1：查询审批请求**

```javascript
const approvalRequests = await mcp__burpbridge__list_paginated_http_history(input: {
  "host": "target.example.com",
  "method": "POST",
  "path": "/api/workflow/*",
  "page": 1,
  "page_size": 50
});
```

**步骤2：获取请求详情**

```javascript
const requestDetail = await mcp__burpbridge__get_http_request_detail(input: {
  "history_id": "65f1a2b3c4d5e6f7a8b9c0d1"
});
```

**步骤3：配置测试角色**

```javascript
await mcp__burpbridge__configure_authentication_context(input: {
  "role": "生态经理",
  "headers": { "Authorization": "Bearer token_ecosystem_manager" },
  "cookies": { "session": "session_abc123" }
});
```

**步骤4：批量越权测试**

```javascript
const workflowConfig = readJson('result/workflow_config.json');

for (const workflow of workflowConfig.workflows) {
  for (const node of workflow.nodes) {
    if (!node.discovered || !node.api_endpoint) continue;
    
    const requests = await findRequestsByEndpoint(node.api_endpoint);
    const roles = await mcp__burpbridge__list_configured_roles(input: {});
    
    for (const request of requests) {
      for (const role of roles.roles) {
        const hasPermission = node.required_roles.includes(role);
        
        const result = await mcp__burpbridge__replay_http_request_as_role(input: {
          "history_entry_id": request.id,
          "target_role": role
        });
      }
    }
  }
}
```

---

## 测试矩阵生成

```json
{
  "test_matrix": {
    "workflow_id": "software_nre_approval",
    "test_time": "2026-04-20T10:30:00Z",
    "nodes": [
      {
        "node_id": "submit_terminate",
        "node_name": "提交终止",
        "api_endpoint": "/api/workflow/terminate",
        "tests": [
          {
            "role": "生态经理",
            "expected": "success",
            "actual": "success",
            "status": "pass",
            "replay_id": "uuid-001"
          },
          {
            "role": "技术评估专家组组长",
            "expected": "forbidden",
            "actual": "forbidden",
            "status": "pass",
            "replay_id": "uuid-002"
          },
          {
            "role": "技术评估专家组",
            "expected": "forbidden",
            "actual": "success",
            "status": "fail",
            "replay_id": "uuid-003",
            "vulnerability": {
              "type": "IDOR",
              "severity": "high",
              "description": "无权限角色成功执行审批操作"
            }
          }
        ]
      }
    ]
  }
}
```

---

## 结果判断规则

| 场景 | 预期响应 | 判定 |
|------|----------|------|
| 有权限角色 | 200/201 + 成功响应 | 正常 |
| 无权限角色 | 401/403 或 错误响应 | 安全 |
| 无权限角色 | 200 + 成功响应 | **越权漏洞** |

**响应判断逻辑**：

```javascript
function analyzeResponse(result, expectedPermission) {
  const statusCode = result.replayedStatusCode;
  const body = result.replayResponseSummary;
  
  if (expectedPermission) {
    if (statusCode >= 200 && statusCode < 300) {
      return { status: "pass", message: "权限正常" };
    }
    return { status: "warning", message: "有权限但请求失败" };
  }
  
  if (statusCode === 401 || statusCode === 403) {
    return { status: "pass", message: "权限控制有效" };
  }
  if (body.includes("无权限") || body.includes("forbidden")) {
    return { status: "pass", message: "权限控制有效" };
  }
  if (statusCode >= 200 && statusCode < 300) {
    return { 
      status: "fail", 
      vulnerability: "IDOR",
      message: "发现越权漏洞" 
    };
  }
  return { status: "unknown", message: "需人工确认" };
}
```

---

## 参数变异测试

```javascript
await mcp__burpbridge__replay_http_request_as_role(input: {
  "history_entry_id": "审批请求ID",
  "target_role": "生态经理",
  "modifications": {
    "query_param_overrides": {
      "workflow_id": "其他流程ID",
      "approver_id": "其他审批人ID"
    },
    "json_field_overrides": {
      "approval_result": "rejected",
      "approver_comment": "越权测试"
    }
  }
});
```

---

## 注意事项

1. **不影响原流程**：越权测试只是请求重放，不会改变流程状态
2. **测试时机**：在正常审批操作后立即测试，确保请求有效
3. **角色覆盖**：测试所有已配置的角色，包括有权限和无权限的
4. **结果验证**：对可疑结果二次确认，避免误报
5. **日志记录**：记录所有测试请求和响应，便于追溯

---

## 加载要求

```yaml
## Skill加载规则（双通道）

# Security必须加载

1. 尝试: skill({ name: "workflow-authorization-testing" })
2. 若失败: Read("skills/security/workflow-authorization-testing/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```
