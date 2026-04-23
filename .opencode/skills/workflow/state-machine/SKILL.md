---
name: state-machine
description: "状态机定义，控制测试流程的状态转换和门控条件。简化版：6个状态，串行执行。"
---

# State Machine Skill

> 状态机定义 — 简化版状态、转换、门控条件

---

## 状态定义（简化版）

### 状态列表

| 状态 | 说明 | 主要Agent | 输出产物 |
|------|------|----------|---------|
| **INIT** | 初始化环境 | Coordinator调度 | accounts.json, chrome_instances.json |
| **EXPLORATION_RUNNING** | 探索阶段 | @navigator | pages/apis collection |
| **SECURITY_TESTING** | 安全测试 | @security + @analyzer | findings collection |
| **EVALUATION** | 进度评估 | Coordinator判断 | next_action决策 |
| **REPORT** | 生成报告 | Coordinator | 报告文件 |
| **END** | 测试结束 | Coordinator | 最终状态 |

### 状态属性

```javascript
const stateProperties = {
  INIT: {
    description: "初始化测试环境",
    timeout: 60000,
    steps: [
      "@account_parser → 解析账号",
      "环境检查 → MongoDB/BurpBridge",
      "@navigator → 创建Chrome实例",
      "@form → 执行登录（如需要）",
      "@security → 初始化安全测试"
    ],
    outputs: ["accounts.json", "chrome_instances.json", "sessions.json"]
  },
  EXPLORATION_RUNNING: {
    description: "探索页面和API",
    timeout: 180000,
    agent: "@navigator",
    outputs: ["pages collection", "apis collection", "progress collection"]
  },
  SECURITY_TESTING: {
    description: "安全测试",
    timeout: 300000,
    agents: ["@security", "@analyzer"],
    outputs: ["findings collection"]
  },
  EVALUATION: {
    description: "进度评估",
    timeout: 30000,
    agent: "Coordinator",
    outputs: ["next_action决策"]
  },
  REPORT: {
    description: "生成报告",
    timeout: 60000,
    agent: "Coordinator",
    outputs: ["报告文件"]
  },
  END: {
    description: "测试完成",
    timeout: 0,
    outputs: ["最终统计"]
  }
};
```

---

## 状态转换图（简化版）

```
                    ┌─────────┐
                    │  INIT   │
                    └────┬────┘
                         │ 门控1
                         ↓
              ┌──────────────────┐
              │EXPLORATION_RUNNING│
              └─────────┬────────┘
                        │ 门控2
                        ↓
              ┌──────────────────┐
              │ SECURITY_TESTING │
              └─────────┬────────┘
                        │ 门控3
                        ↓
              ┌──────────────────┐
              │    EVALUATION    │
              └─────────┬────────┘
                        │
                ┌───────┴───────┐
                │ 三问法则判定    │
                └───────┬───────┘
          ┌─────────────┼─────────────┐
          ↓             ↓             ↓
    ┌───────────┐ ┌───────────┐ ┌─────────────┐
    │继续探索   │ │继续测试   │ │   REPORT    │
    │(回到EXPLO)| │(回到SEC)  │ │             │
    └───────────┘ └───────────┘ └──────┬──────┘
                                            │ 门控5
                                            ↓
                                      ┌─────────────┐
                                      │    END      │
                                      └─────────────┘
```

---

## 门控条件详细定义

### 门控1: INIT → EXPLORATION_RUNNING

```javascript
const gate1 = {
  name: "初始化完成",
  conditions: [
    {
      check: "accounts.json已生成",
      verify: () => fileExists("config/accounts.json")
    },
    {
      check: "Chrome实例启动成功",
      verify: () => {
        const instances = readJson("result/chrome_instances.json");
        return instances.length > 0 && instances[0].status === "running";
      }
    },
    {
      check: "登录成功（有登录需求）",
      verify: () => {
        const accounts = readJson("config/accounts.json");
        const needsLogin = accounts?.accounts?.length > 0;
        if (!needsLogin) return true;
        
        const sessions = readJson("result/sessions.json");
        return sessions.some(s => s.status === "active");
      }
    },
    {
      check: "BurpBridge健康检查通过",
      verify: async () => {
        const health = await burpbridge_check_burp_health(input: {});
        return health.status === "ok";
      }
    },
    {
      check: "Security已初始化",
      verify: async () => {
        const status = await burpbridge_get_auto_sync_status(input: {});
        return status.enabled === true;
      }
    }
  ],
  
  onPass: () => {
    updateSessionState("EXPLORATION_RUNNING");
    coordinatorOutput("[STATE] → EXPLORATION_RUNNING");
  },
  
  onFail: (failedConditions) => {
    coordinatorOutput("[INIT FAILED] " + failedConditions);
    handleInitFailure(failedConditions);
  }
};
```

### 门控2: EXPLORATION_RUNNING → SECURITY_TESTING

```javascript
const gate2 = {
  name: "探索完成",
  
  triggerConditions: [
    {
      check: "Navigator主动退出",
      verify: (navigatorResult) => {
        return navigatorResult.status === "completed" || 
               navigatorResult.status === "partial";
      }
    },
    {
      check: "Navigator无异常需处理",
      verify: (navigatorResult) => {
        const needsUserAction = navigatorResult.requires_user_action;
        return needsUserAction === false;
      }
    },
    {
      check: "发现敏感API",
      verify: async () => {
        const progress = await mongodbFind({ 
          collection: "progress", 
          filter: { session_id: currentSessionId } 
        });
        return progress.sensitive_apis?.total > 0;
      }
    }
  ],
  
  onPass: () => {
    updateSessionState("SECURITY_TESTING");
    coordinatorOutput("[STATE] → SECURITY_TESTING");
  },
  
  onException: (navigatorResult) => {
    // Navigator返回异常，Coordinator处理
    handleNavigatorException(navigatorResult);
  }
};
```

### 门控3: SECURITY_TESTING → EVALUATION

```javascript
const gate3 = {
  name: "测试完成",
  
  conditions: [
    {
      check: "Security测试完成",
      verify: (securityResult) => {
        return securityResult.status === "success";
      }
    },
    {
      check: "Analyzer分析完成",
      verify: (analyzerResult) => {
        return analyzerResult.status === "success";
      }
    }
  ],
  
  onPass: () => {
    updateSessionState("EVALUATION");
    coordinatorOutput("[STATE] → EVALUATION");
  },
  
  onTimeout: () => {
    createEvent("TEST_TIMEOUT", { priority: "high" });
    updateSessionState("EVALUATION");
  }
};
```

### 门控4: EVALUATION → 下一步决策

```javascript
const gate4 = {
  name: "三问法则判定",
  
  evaluate: async () => {
    const progress = await mongodbFind({ collection: "progress" });
    const findings = await mongodbFind({ collection: "findings" });
    
    // Q1: 有未访问的重要路径？
    const q1 = checkQ1(progress);
    if (q1.answer === "YES") {
      return { 
        nextState: "EXPLORATION_RUNNING", 
        reason: q1.reason,
        action: "@navigator continue_explore"
      };
    }
    
    // Q2: 关键端点是否都测试了？
    const q2 = checkQ2(progress);
    if (q2.answer === "NO") {
      return { 
        nextState: "SECURITY_TESTING", 
        reason: q2.reason,
        action: "@security test"
      };
    }
    
    // Q3: 漏洞是否需要组合验证？
    const q3 = checkQ3(findings);
    if (q3.answer === "YES") {
      return { 
        nextState: "SECURITY_TESTING", 
        reason: q3.reason,
        action: "@security attack_chain_test"
      };
    }
    
    // Q4: 是否达标？
    return { 
      nextState: "REPORT", 
      reason: "三问法则判定完成，进入报告阶段"
    };
  },
  
  onDecision: (decision) => {
    updateSessionState(decision.nextState);
    coordinatorOutput("[DECISION] → " + decision.nextState);
    coordinatorOutput("[REASON] " + decision.reason);
    coordinatorOutput("[ACTION] " + decision.action);
  }
};
```

### 门控5: REPORT → END

```javascript
const gate5 = {
  name: "报告完成",
  
  conditions: [
    {
      check: "报告文件生成成功",
      verify: () => {
        const reportPath = `result/${session_id}_report_${date}.md`;
        return fileExists(reportPath);
      }
    },
    {
      check: "Chrome实例已关闭",
      verify: () => {
        const instances = readJson("result/chrome_instances.json");
        return instances.every(i => i.status === "closed");
      }
    }
  ],
  
  onPass: () => {
    updateSessionState("END");
    updateSessionStatus("completed");
    coordinatorOutput("[STATE] → END");
    coordinatorOutput("[STATUS] 测试完成");
  }
};
```

---

## 状态转换实现

### Coordinator状态管理

```javascript
let currentState = "INIT";
let stateEnteredAt = Date.now();

function updateSessionState(newState) {
  const oldState = currentState;
  currentState = newState;
  stateEnteredAt = Date.now();
  
  // 更新MongoDB
  mongodbUpdate({
    database: "webtest",
    collection: "test_sessions",
    filter: { session_id: currentSessionId },
    update: {
      $set: {
        current_state: newState,
        updated_at: Date.now()
      },
      $push: {
        state_history: {
          from: oldState,
          to: newState,
          timestamp: Date.now()
        }
      }
    }
  });
  
  // 更新sessions.json
  updateSessionsJson({ current_state: newState });
}

function checkStateTimeout() {
  const elapsed = Date.now() - stateEnteredAt;
  const timeout = stateProperties[currentState].timeout;
  
  if (elapsed >= timeout && timeout > 0) {
    coordinatorOutput("[TIMEOUT] State " + currentState + " timeout");
    
    if (currentState === "EXPLORATION_RUNNING") {
      // Navigator超时，强制进入测试
      updateSessionState("SECURITY_TESTING");
    } else if (currentState === "SECURITY_TESTING") {
      // Security超时，强制进入评估
      updateSessionState("EVALUATION");
    }
  }
}
```

---

## 子Agent返回后的状态判断

```javascript
function handleAgentReturn(agentResult, agentName) {
  // 检查status
  if (agentResult.status === "exception") {
    // 异常处理
    handleException(agentResult.exceptions);
    return;
  }
  
  // 检查requires_user_action
  if (agentResult.requires_user_action) {
    // 需要用户介入
    coordinatorOutput("[USER ACTION REQUIRED] " + agentResult.user_action_prompt);
    pauseSession();
    return;
  }
  
  // 根据当前状态判断下一步
  switch (currentState) {
    case "EXPLORATION_RUNNING":
      if (agentName === "navigator") {
        // Navigator完成后进入SECURITY_TESTING
        updateSessionState("SECURITY_TESTING");
      }
      break;
      
    case "SECURITY_TESTING":
      if (agentName === "analyzer") {
        // Analyzer完成后进入EVALUATION
        updateSessionState("EVALUATION");
      }
      break;
      
    case "EVALUATION":
      // 执行三问法则判定
      const decision = gate4.evaluate();
      gate4.onDecision(decision);
      break;
  }
}
```

---

## 加载要求

```yaml
## Skill 加载规则

# Coordinator 必须加载

1. 尝试: skill({ name: "state-machine" })
2. 若失败: Read(".opencode/skills/workflow/state-machine/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```