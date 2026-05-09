---
name: security-error-handling
description: "Security Agent错误处理方法论。BurpBridge调用失败处理、同步验证、认证失效暂停与降级策略。"
---

# Security Error Handling Skill

> Security Agent 错误处理：BurpBridge 调用失败处理、同步验证、认证失效暂停与降级策略。

## 基本错误处理表

| 错误类型 | 处理方式 |
|---------|---------|
| BurpBridge连接失败 | 检查Burp Suite状态，通知Coordinator |
| MongoDB连接失败 | 检查MongoDB服务，建议用户启动 |
| 角色未配置 | 跳过该角色的测试，记录警告 |
| 重放失败 | 记录错误，继续其他测试 |
| 认证上下文失效 | 创建AUTH_CONTEXT_STALE事件并保存断点 |
| 自动同步漂移 | 创建AUTO_SYNC_DRIFT事件，进入repair |

## BurpBridge调用失败处理

### 1. 健康检查失败

1. 记录错误到事件队列
2. 创建 `BURPBRIDGE_ERROR` 事件通知 Coordinator
3. 暂停安全测试流水线

### 2. 自动同步漂移

1. 创建 `AUTO_SYNC_DRIFT` 事件，记录期望配置与实际状态
2. 进入 repair 分支，最多重试一次
3. 若 repair 后仍异常，暂停依赖历史捕获的安全测试

### 3. 认证上下文失效

1. 记录失败的 `history_entry_id`、`target_role` 和响应摘要
2. 创建 `AUTH_CONTEXT_STALE` 事件
3. 保存当前测试游标，返回 `resume_token`
4. 等待 Coordinator 调度 Navigator 刷新认证
5. 禁止 Security 自行登录或操作浏览器

### 4. 重放失败

1. 记录失败的 `history_entry_id` 和 `target_role`
2. 继续处理队列中的下一个测试
3. 在测试报告中标注失败项

## 降级策略

当 BurpBridge 完全不可用时：

1. 暂停越权测试
2. 继续页面探索
3. 创建 `EXPLORATION_SUGGESTION` 事件，建议用户手动测试
4. 在会话状态中标记 `security_testing_paused: true`

## 加载要求

```yaml
1. 尝试: skill({ name: "security-error-handling" })
2. 若失败: Read("skills/workflow/security-error-handling/SKILL.md")
3. 此 Skill 必须加载完成才能继续执行
```
