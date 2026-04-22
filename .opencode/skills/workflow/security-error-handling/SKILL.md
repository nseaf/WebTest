---
name: security-error-handling
description: "Security Agent错误处理方法论。BurpBridge调用失败处理、同步验证、降级策略、重试配置。"
---

# Security Error Handling Skill

> Security Agent错误处理 — BurpBridge调用失败处理、同步验证、降级策略

---

## 基本错误处理表

| 错误类型 | 处理方式 |
|---------|---------|
| BurpBridge连接失败 | 检查Burp Suite状态，通知Coordinator |
| MongoDB连接失败 | 检查MongoDB服务，建议用户启动 |
| 角色未配置 | 跳过该角色的测试，记录警告 |
| 重放失败 | 记录错误，继续其他测试 |
| 会话过期 | 创建SESSION_EXPIRED事件 |

---

## BurpBridge调用失败处理

### 1. 健康检查失败

```
错误: BurpBridge REST API无响应
处理:
  1. 记录错误到事件队列
  2. 创建BURPBRIDGE_ERROR事件通知Coordinator
  3. 暂停安全测试流水线
  4. 等待Coordinator指示
```

### 2. 同步失败

```
错误: sync_proxy_history_with_filters返回错误
处理:
  1. 记录详细错误信息（包括错误码和消息）
  2. 等待5秒后重试一次
  3. 若仍失败:
     - 创建SYNC_WARNING事件
     - 通知用户检查Burp Suite代理配置
     - 继续探索任务，暂停安全测试
```

### 3. 重放失败

```
错误: replay_http_request_as_role返回错误
处理:
  1. 记录失败的history_entry_id和target_role
  2. 继续处理队列中的下一个测试
  3. 在测试报告中标注失败项
```

---

## 同步状态验证流程

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 调用configure_auto_sync启用同步                              │
│     enabled: true, host: target_host                             │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  2. 等待浏览器产生流量                                            │
│     sleep(5000)                                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  3. 检查同步状态                                                  │
│     get_auto_sync_status()                                       │
└─────────────────────────────────────────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ↓                               ↓
     synced_count > 0                  synced_count = 0
               │                               │
               ↓                               ↓
     ┌─────────────────┐           ┌─────────────────────────┐
     │ 同步正常         │           │ 创建SYNC_WARNING事件     │
     │ 继续安全测试     │           │ 通知用户检查代理配置     │
     └─────────────────┘           └─────────────────────────┘
```

---

## 降级策略

当BurpBridge完全不可用时：

1. **暂停越权测试**：无法获取历史记录和重放请求，跳过越权测试
2. **继续页面探索**：Navigator、Scout、Form Agent继续工作
3. **手动测试建议**：创建EXPLORATION_SUGGESTION事件，建议用户手动测试
4. **记录状态**：在会话状态中标记`security_testing_paused: true`

```json
{
  "event_type": "EXPLORATION_SUGGESTION",
  "source_agent": "Security Agent",
  "priority": "high",
  "payload": {
    "suggestion_type": "manual_test_required",
    "reason": "BurpBridge不可用，建议手动测试以下端点",
    "endpoints": [
      { "url": "/api/users/{id}", "method": "GET", "test_type": "IDOR" }
    ]
  }
}
```

---

## 重试配置

```json
{
  "retry_config": {
    "max_retries": 1,
    "retry_delay_ms": 5000,
    "retryable_errors": [
      "SYNC_FAILED",
      "TIMEOUT",
      "CONNECTION_ERROR"
    ],
    "non_retryable_errors": [
      "INVALID_PARAMETER",
      "ROLE_NOT_FOUND",
      "HISTORY_NOT_FOUND"
    ]
  }
}
```

---

## 加载要求

```yaml
## Skill加载规则（双通道）

# Security必须加载

1. 尝试: skill({ name: "security-error-handling" })
2. 若失败: Read("skills/workflow/security-error-handling/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```