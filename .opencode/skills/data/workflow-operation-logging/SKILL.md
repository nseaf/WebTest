---
name: workflow-operation-logging
description: "流程审批操作记录方法论。审批执行流程、API_DISCOVERED事件、workflow_config更新、多账号审批。"
---

# Workflow Operation Logging Skill

> 流程审批操作记录方法论 — 审批执行流程、API发现事件、配置更新、多账号审批

---

## 核心流程

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 接收审批操作任务                                             │
│     参数: node_name, action, account_id                         │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. 执行审批操作                                                 │
│     - 点击审批按钮                                               │
│     - 填写审批意见                                               │
│     - 提交审批                                                   │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. 请求自动记录到 BurpBridge                                    │
│     （通过 Burp 代理自动捕获）                                    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Scout Agent 分析网络请求                                     │
│     - 识别审批相关请求                                            │
│     - 关联到流程节点                                              │
│     - 更新 workflow_config.json                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. 创建 API_DISCOVERED 事件                                     │
│     通知 Security Agent 发现了新的审批 API                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 审批操作任务格式

```json
{
  "task": "execute_approval",
  "node_name": "提交终止",
  "action": "submit",
  "account_id": "test1020",
  "role": "生态经理",
  "window_id": "window_0"
}
```

---

## 执行审批操作

使用 browser-use Skill 或 Playwright MCP 执行审批操作：

```javascript
// 示例：执行审批提交
await browserUseTask({
  description: `执行审批操作：
    1. 找到并点击"${node_name}"按钮
    2. 如果有审批意见输入框，填写"同意"
    3. 点击确认提交按钮
    4. 等待操作完成
  `
});
```

---

## 审批请求识别规则

| 规则 | 说明 |
|------|------|
| URL 模式 | `/api/workflow/*`, `/api/approve/*`, `/api/review/*` |
| HTTP 方法 | POST, PUT, DELETE |
| 请求内容 | 包含 `approve`, `reject`, `workflow_id` 等字段 |
| 菜单关联 | 根据当前菜单路径关联到流程节点 |

---

## 关联请求到流程节点

```javascript
// 从 workflow_config.json 获取流程节点
const workflowConfig = readJson('result/workflow_config.json');

// 查找匹配的节点
function findMatchingNode(request) {
  for (const workflow of workflowConfig.workflows) {
    for (const node of workflow.nodes) {
      // 检查菜单路径是否匹配
      if (node.menu_path && isCurrentMenuPath(node.menu_path)) {
        return node;
      }
      // 检查 API 端点是否匹配
      if (node.api_endpoint && request.url.includes(node.api_endpoint)) {
        return node;
      }
    }
  }
  return null;
}
```

---

## 更新 workflow_config.json

发现审批 API 后，更新流程配置：

```javascript
// 更新节点信息
node.api_endpoint = request.url;
node.http_method = request.method;
node.request_template = {
  url: request.url,
  method: request.method,
  headers: request.headers,
  body_keys: Object.keys(request.body)
};
node.discovered = true;
node.discovered_at = new Date().toISOString();
```

---

## 创建 API_DISCOVERED 事件

```json
{
  "event_type": "API_DISCOVERED",
  "source_agent": "Form Agent",
  "priority": "normal",
  "payload": {
    "api_url": "/api/workflow/terminate",
    "method": "POST",
    "workflow_id": "software_nre_approval",
    "node_id": "submit_terminate",
    "node_name": "提交终止",
    "discovered_at": "2026-04-20T10:00:00Z",
    "request_preview": {
      "has_body": true,
      "body_keys": ["workflow_id", "action", "comment"]
    }
  }
}
```

---

## 多账号审批流程

对于需要多账号按顺序审批的场景：

```javascript
// 按流程顺序执行
const approvalSequence = [
  { role: "生态经理", node: "提交终止", account: "test1020" },
  { role: "技术评估专家组组长", node: "NRE申请预审", account: "test1021" },
  { role: "技术评估专家组", node: "技术评估", account: "test1022" }
];

for (const step of approvalSequence) {
  // 1. 切换到对应账号的 Chrome 实例
  await switchToAccount(step.account);
  
  // 2. 执行审批操作
  await executeApproval(step.node, step.account);
  
  // 3. 等待请求被记录
  await sleep(2000);
  
  // 4. 验证操作成功
  await verifyApprovalResult(step.node);
}
```

---

## 审批操作报告

```json
{
  "approval_result": {
    "node_name": "提交终止",
    "action": "submit",
    "status": "success",
    "account_id": "test1020",
    "role": "生态经理",
    "executed_at": "2026-04-20T10:00:00Z"
  },
  "api_recorded": {
    "discovered": true,
    "api_url": "/api/workflow/terminate",
    "method": "POST",
    "history_id": "65f1a2b3c4d5e6f7a8b9c0d1"
  },
  "workflow_state": {
    "current_node": "提交终止",
    "next_node": "NRE申请预审",
    "status": "pending_next_approval"
  }
}
```

---

## 注意事项

1. **确保代理配置正确**：审批请求必须通过 Burp 代理才能被记录
2. **等待请求完成**：操作后等待足够时间，确保请求被 BurpBridge 同步
3. **记录操作上下文**：包含菜单路径、按钮文本等信息，便于关联
4. **验证操作结果**：确认审批操作成功执行
5. **不干扰后续越权测试**：正常执行审批，越权测试由 Security Agent 通过请求重放完成

---

## 加载要求

```yaml
## Skill加载规则（双通道）

# Form必须加载

1. 尝试: skill({ name: "workflow-operation-logging" })
2. 若失败: Read("skills/data/workflow-operation-logging/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```