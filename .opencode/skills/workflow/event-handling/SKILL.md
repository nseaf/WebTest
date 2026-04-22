---
name: event-handling
description: "事件处理规范，定义事件类型、优先级、处理流程。Coordinator Agent使用。"
---

# Event Handling Skill

> 事件处理规范 — 事件类型、优先级、处理流程

---

## 事件类型定义

| 事件类型 | 来源Agent | 优先级 | 需要用户操作 | 说明 |
|----------|----------|--------|--------------|------|
| **CAPTCHA_DETECTED** | Form/Navigator | critical | ✅ 是 | 检测到验证码，需要人工处理 |
| **SESSION_EXPIRED** | Navigator/Security | high | ❌ 否 | 会话过期，触发重新登录 |
| **LOGIN_FAILED** | Form | high | ❌ 否 | 登录失败，尝试其他账号 |
| **COOKIE_CHANGED** | Navigator | normal | ❌ 否 | Cookie变化，同步到BurpBridge |
| **VULNERABILITY_FOUND** | Security | high | ❌ 否 | 发现漏洞，记录到findings |
| **API_DISCOVERED** | Scout | normal | ❌ 否 | 发现API，加入测试队列 |
| **EXPLORATION_SUGGESTION** | Security/Analyzer | normal | ❌ 否 | 测试建议，加入待测试项 |
| **BURPBRIDGE_ERROR** | Security | high | ❌ 否 | BurpBridge服务异常 |

---

## 事件优先级处理

### 优先级定义

```javascript
const priorityHandling = {
  critical: {
    action: "立即处理",
    pause_other_tasks: true,
    notify_user: true
  },
  high: {
    action: "尽快处理",
    insert_queue_front: true,
    notify_user: false
  },
  normal: {
    action: "正常排队",
    queue_order: "append",
    notify_user: false
  }
};
```

### 处理顺序

```
事件队列处理顺序：

1. critical事件 → 立即处理，暂停其他任务
2. high事件 → 插队到队列前端
3. normal事件 → 正常排队

事件队列示例：
[
  { event_type: "CAPTCHA_DETECTED", priority: "critical", ... },  ← 优先处理
  { event_type: "SESSION_EXPIRED", priority: "high", ... },       ← 其次
  { event_type: "API_DISCOVERED", priority: "normal", ... },      ← 最后
  { event_type: "EXPLORATION_SUGGESTION", priority: "normal", ... }
]
```

---

## 事件格式

### MongoDB events collection文档结构

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",
  event_id: "evt_20260422_103000_001",
  event_type: "CAPTCHA_DETECTED",
  source_agent: "Form Agent",
  priority: "critical",
  status: "pending",        // pending/processing/handled/failed
  payload: {
    window_id: "window_0",
    login_url: "https://example.com/login",
    captcha_type: "image"
  },
  created_at: Date,
  handled_at: null,
  result: null,
  error: null
}
```

### 创建事件函数

```javascript
function createEvent(eventType, sourceAgent, priority, payload) {
  return {
    session_id: currentSessionId,
    event_id: `evt_${Date.now()}_${randomString(3)}`,
    event_type: eventType,
    source_agent: sourceAgent,
    priority: priority,
    status: "pending",
    payload: payload,
    created_at: Date.now(),
    handled_at: null,
    result: null
  };
}

async function saveEvent(event) {
  await mongodb-mcp-server_insert-many({
    database: "webtest",
    collection: "events",
    documents: [event]
  });
}
```

---

## 各事件处理流程

### CAPTCHA_DETECTED

```
┌─────────────────────────────────────────────────────────────┐
│  CAPTCHA_DETECTED 处理流程                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. 读取事件详情                                              │
│     获取 window_id, login_url, captcha_type                  │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 暂停当前登录流程                                          │
│     标记 window 状态为 waiting_captcha                        │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 通知用户                                                  │
│     "检测到验证码({captcha_type})，请前往 {login_url} 手动完成│
│      验证。完成后请回复 'done' 继续"                           │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 等待用户确认                                              │
│     超时时间：60秒                                            │
│     用户回复 "done"                                           │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. 更新事件状态                                              │
│     status = "handled"                                       │
│     result = { user_action: "captcha_completed" }            │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  6. 通知 Form Agent 继续                                      │
│     继续登录流程                                              │
└─────────────────────────────────────────────────────────────┐
```

### SESSION_EXPIRED

```
处理流程：
1. 读取事件详情
   → 获取 account_id, window_id
   
2. 检查重新登录配置
   → max_relogin_attempts
   
3. 尝试重新登录
   → 调用 Form Agent 执行登录
   
4a. 登录成功
   → 更新会话状态，继续任务
   
4b. 登录失败
   → 尝试其他账号或通知用户
   → 如果超过max_relogin_attempts，创建LOGIN_FAILED事件
```

### API_DISCOVERED

```
处理流程：
1. 读取事件详情
   → 获取 api_id, endpoint, method
   
2. 检查API敏感度
   → sensitive_fields是否非空
   
3. 加入测试队列
   → 更新 progress collection
   → 标记 test_status = "pending"
   
4. 如果敏感API
   → 优先级提升，尽快测试
```

---

## 状态流转

```
事件状态流转图：

pending → processing → handled
                    ↘ failed

状态说明：
- pending: 新创建，等待处理
- processing: 正在处理
- handled: 处理完成
- failed: 处理失败
```

---

## 事件轮询机制

```javascript
async function pollEvents() {
  // 查询pending事件，按优先级排序
  const events = await mongodb-mcp-server_find({
    database: "webtest",
    collection: "events",
    filter: { session_id: currentSessionId, status: "pending" },
    sort: { priority: -1, created_at: 1 },  // critical优先，早创建优先
    limit: 10
  });
  
  for (const event of events) {
    // 更新状态为processing
    await mongodb-mcp-server_update-many({
      database: "webtest",
      collection: "events",
      filter: { event_id: event.event_id },
      update: { $set: { status: "processing" } }
    });
    
    // 处理事件
    try {
      const result = await handleEvent(event);
      
      // 更新为handled
      await mongodb-mcp-server_update-many({
        database: "webtest",
        collection: "events",
        filter: { event_id: event.event_id },
        update: {
          $set: {
            status: "handled",
            handled_at: Date.now(),
            result: result
          }
        }
      });
    } catch (error) {
      // 更新为failed
      await mongodb-mcp-server_update-many({
        database: "webtest",
        collection: "events",
        filter: { event_id: event.event_id },
        update: {
          $set: {
            status: "failed",
            handled_at: Date.now(),
            error: error.message
          }
        }
      });
    }
  }
}
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Coordinator 必须加载

1. 尝试: skill({ name: "event-handling" })
2. 若失败: Read("skills/workflow/event-handling/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```