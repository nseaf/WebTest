---
name: state-machine
description: "状态机定义，控制测试流程的状态转换和门控条件。确保流程可控、便于调试。"
---

# State Machine Skill

> 状态机定义 — 状态、转换、门控条件、状态判断

---

## 状态定义

### 状态列表

| 状态 | 说明 | 主要Agent | 输出产物 |
|------|------|----------|---------|
| **INIT** | 初始化环境 | Coordinator | chrome_instances.json, sessions.json |
| **PHASE_1_EXPLORE** | 快速探索 | Navigator + Scout + Form | pages/apis collection |
| **ROUND_N_TEST** | 安全测试 | Security + Analyzer | findings collection |
| **ROUND_N_EVALUATION** | 评估决策 | Coordinator | next_action决策 |
| **NEXT_ROUND** | 补漏迭代 | Scout + Security | 补充测试 |
| **REPORT** | 生成报告 | Coordinator | 报告文件 |
| **END** | 测试结束 | Coordinator | 最终状态 |

### 状态属性

```javascript
const stateProperties = {
  INIT: {
    description: "初始化测试环境",
    timeout: 60000,           // 超时时间（毫秒）
    required_agents: ["Coordinator"],
    outputs: ["chrome_instances.json", "sessions.json", "test_sessions collection"]
  },
  PHASE_1_EXPLORE: {
    description: "快速探索，发现页面和API",
    timeout: 180000,
    required_agents: ["Navigator", "Scout", "Form"],
    outputs: ["pages collection", "apis collection", "progress collection"]
  },
  ROUND_N_TEST: {
    description: "安全测试，越权和注入",
    timeout: 300000,
    required_agents: ["Security", "Analyzer"],
    outputs: ["findings collection"]
  },
  ROUND_N_EVALUATION: {
    description: "评估测试结果，决定下一步",
    timeout: 30000,
    required_agents: ["Coordinator"],
    outputs: ["next_action decision"]
  },
  NEXT_ROUND: {
    description: "补充测试",
    timeout: 120000,
    required_agents: ["Scout", "Security"],
    outputs: ["补充的findings"]
  },
  REPORT: {
    description: "生成最终报告",
    timeout: 60000,
    required_agents: ["Coordinator"],
    outputs: ["report file"]
  },
  END: {
    description: "测试完成",
    timeout: 0,
    required_agents: [],
    outputs: ["final statistics"]
  }
};
```

---

## 状态转换图

```
                    ┌─────────┐
                    │  INIT   │
                    └────┬────┘
                         │ 门控1
                         ↓
              ┌──────────────────┐
              │ PHASE_1_EXPLORE  │
              └─────────┬────────┘
                        │ 门控2
                        ↓
              ┌──────────────────┐
              │  ROUND_1_TEST    │
              └─────────┬────────┘
                        │ 门控3
                        ↓
              ┌──────────────────┐
              │ ROUND_1_EVALUATION │
              └─────────┬────────┘
                        │
                ┌───────┴───────┐
                │ 三问法则判定    │
                └───────┬───────┘
          ┌─────────────┴─────────────┐
          ↓                           ↓
    ┌─────────────┐            ┌─────────────┐
    │ NEXT_ROUND  │            │   REPORT    │
    └──────┬──────┘            └──────┬──────┘
           │                          │ 门控5
           ↓                          ↓
    ┌──────────────────┐         ┌─────────────┐
    │  ROUND_N_TEST    │         │    END      │
    └─────────┬────────┘         └─────────────┘
              │ 门控4
              ↓
    ┌──────────────────┐
    │ROUND_N_EVALUATION│
    └─────────┬────────┘
              │
      （循环回到NEXT_ROUND或REPORT）
```

---

## 门控条件详细定义

### 门控1: INIT → PHASE_1_EXPLORE

```javascript
const gate1 = {
  name: "初始化完成",
  conditions: [
    {
      check: "Chrome实例启动成功",
      verify: () => {
        const instances = readJson("result/chrome_instances.json");
        return instances.length > 0 && instances[0].status === "running";
      }
    },
    {
      check: "accounts.json存在或无需登录",
      verify: () => {
        try {
          readJson("config/accounts.json");
          return true;
        } catch {
          // 无账号配置，使用无需登录模式
          return true;
        }
      }
    },
    {
      check: "MongoDB连接正常",
      verify: async () => {
        const result = await mongodb-mcp-server_list-databases();
        return result.includes("webtest") || result.includes("burpbridge");
      }
    },
    {
      check: "BurpBridge健康检查通过",
      verify: async () => {
        const health = await burpbridge_check_burp_health(input: {});
        return health.status === "ok";
      }
    }
  ],
  
  onPass: () => {
    updateSessionState("PHASE_1_EXPLORE");
    startPhase1Explore();
  },
  
  onFail: (failedConditions) => {
    reportInitFailure(failedConditions);
    pauseSession();
  }
};
```

### 门控2: PHASE_1_EXPLORE → ROUND_1_TEST

```javascript
const gate2 = {
  name: "探索完成",
  conditions: [
    {
      check: "登录成功（有登录需求）或首页已分析（无需登录）",
      verify: () => {
        const sessions = readJson("result/sessions.json");
        const loginRequired = readJson("config/accounts.json").accounts?.length > 0;
        
        if (loginRequired) {
          return sessions.some(s => s.status === "active" && s.logged_in_at);
        } else {
          // 无登录需求，检查首页是否已分析
          const pages = mongodbFind({ collection: "pages", filter: { type: "home" } });
          return pages.length > 0;
        }
      }
    },
    {
      check: "发现≥N个页面/API（可配置阈值）",
      verify: async () => {
        const progress = await mongodbFind({ collection: "progress" });
        const threshold = config.explore_threshold || 5;  // 默认5个
        return progress.overall_stats.total_apis >= threshold || 
               progress.overall_stats.total_pages >= threshold;
      },
      soft: true  // 软性条件，可配置跳过
    }
  ],
  
  onPass: () => {
    updateSessionState("ROUND_1_TEST");
    startRound1Test();
  },
  
  onFail: (reason) => {
    if (reason.includes("登录")) {
      // 登录失败，触发重新登录或人工介入
      createEvent("LOGIN_FAILED", { priority: "high" });
    } else {
      // 继续探索
      continuePhase1Explore();
    }
  }
};
```

### 门控3: ROUND_N_TEST → ROUND_N_EVALUATION

```javascript
const gate3 = {
  name: "测试完成",
  conditions: [
    {
      check: "关键端点测试完成或达到timeout",
      verify: async () => {
        const progress = await mongodbFind({ collection: "progress" });
        const session = await mongodbFind({ collection: "test_sessions" });
        
        // 检查敏感API覆盖率
        const sensitiveCoverage = (progress.sensitive_apis.tested / progress.sensitive_apis.total) * 100;
        
        // 检查是否超时
        const elapsed = Date.now() - session.current_state_entered_at;
        const timeout = stateProperties.ROUND_N_TEST.timeout;
        
        return sensitiveCoverage >= 80 || elapsed >= timeout;
      }
    }
  ],
  
  onPass: () => {
    updateSessionState("ROUND_N_EVALUATION");
    startEvaluation();
  },
  
  onTimeout: () => {
    // 超时强制进入评估
    createEvent("TEST_TIMEOUT", { priority: "high" });
    updateSessionState("ROUND_N_EVALUATION");
    startEvaluation();
  }
};
```

### 门控4: ROUND_N_EVALUATION → NEXT_ROUND 或 REPORT

```javascript
const gate4 = {
  name: "三问法则判定",
  
  evaluate: async () => {
    const progress = await mongodbFind({ collection: "progress" });
    const findings = await mongodbFind({ collection: "findings" });
    
    // 加载三问法则Skill
    const threeQuestions = loadSkill("progress-tracking");
    
    // 执行三问
    const q1Result = threeQuestions.checkQ1(progress);
    if (q1Result.answer === "YES") {
      return { nextState: "NEXT_ROUND", reason: q1Result.reason };
    }
    
    const q2Result = threeQuestions.checkQ2(progress);
    if (q2Result.answer === "NO") {
      return { nextState: "NEXT_ROUND", reason: q2Result.reason };
    }
    
    const q3Result = threeQuestions.checkQ3(findings);
    if (q3Result.answer === "YES") {
      return { nextState: "ROUND_3_ATTACK_CHAIN", reason: q3Result.reason };
    }
    
    return { nextState: "REPORT", reason: "三问法则判定完成，生成报告" };
  },
  
  onDecision: (decision) => {
    updateSessionState(decision.nextState);
    if (decision.nextState === "NEXT_ROUND") {
      startNextRound(decision.reason);
    } else if (decision.nextState === "REPORT") {
      startReport();
    }
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
      },
      soft: true  // 可选，允许报告后再关闭
    }
  ],
  
  onPass: () => {
    updateSessionState("END");
    updateSessionStatus("completed");
    cleanupSession();
  }
};
```

---

## 状态转换实现

### Coordinator状态管理

```javascript
// Coordinator维护当前状态
let currentState = "INIT";
let stateEnteredAt = Date.now();

function updateSessionState(newState) {
  const oldState = currentState;
  currentState = newState;
  stateEnteredAt = Date.now();
  
  // 更新MongoDB
  mongodb-mcp-server_update-many({
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
  
  // 记录事件
  createEvent("STATE_CHANGE", {
    priority: "normal",
    payload: { from: oldState, to: newState }
  });
}

function checkGateConditions(gate) {
  const results = [];
  for (const condition of gate.conditions) {
    const passed = condition.verify();
    results.push({
      check: condition.check,
      passed: passed,
      soft: condition.soft
    });
  }
  
  const allPassed = results.every(r => r.passed || r.soft);
  return { allPassed, results };
}
```

---

## 状态超时处理

```javascript
function checkStateTimeout() {
  const elapsed = Date.now() - stateEnteredAt;
  const timeout = stateProperties[currentState].timeout;
  
  if (elapsed >= timeout) {
    createEvent("STATE_TIMEOUT", {
      priority: "high",
      payload: {
        state: currentState,
        elapsed: elapsed,
        timeout: timeout
      }
    });
    
    // 根据状态决定超时处理
    if (currentState === "PHASE_1_EXPLORE") {
      // 强制进入测试
      updateSessionState("ROUND_1_TEST");
    } else if (currentState === "ROUND_N_TEST") {
      // 强制进入评估
      updateSessionState("ROUND_N_EVALUATION");
    }
  }
}
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Coordinator 必须加载

1. 尝试: skill({ name: "state-machine" })
2. 若失败: Read("skills/workflow/state-machine/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```

---

## 🔄 委派验证机制

### INIT状态委派验证

在INIT状态进入PHASE_1_EXPLORE前，**必须验证**Coordinator已正确委派任务给子Agent：

```javascript
const delegationVerification = {
  name: "初始化委派验证",
  
  verification_checklist: [
    {
      check: "account_parser任务已调用（如需要）",
      verify: () => {
        const accountsConfig = readJson("config/accounts.json");
        const needsParsing = !accountsConfig || Object.keys(accountsConfig).length === 0;
        if (!needsParsing) return true;
        
        // 检查是否有解析日志
        const delegationLog = readJson("result/delegation_log.json");
        return delegationLog?.delegations?.some(
          d => d.to_agent === "account_parser" && d.status === "success"
        );
      }
    },
    {
      check: "navigator create_instance任务已调用",
      verify: () => {
        // 检查Chrome实例是否由Navigator创建
        const instances = readJson("result/chrome_instances.json");
        const delegationLog = readJson("result/delegation_log.json");
        
        return instances?.length > 0 && delegationLog?.delegations?.some(
          d => d.to_agent === "navigator" && 
               d.task_type === "create_instance" && 
               d.status === "success"
        );
      }
    },
    {
      check: "form execute_login任务已调用（如需要登录）",
      verify: () => {
        const accountsConfig = readJson("config/accounts.json");
        const needsLogin = accountsConfig?.accounts?.length > 0;
        if (!needsLogin) return true;
        
        const delegationLog = readJson("result/delegation_log.json");
        return delegationLog?.delegations?.some(
          d => d.to_agent === "form" && 
               d.task_type === "execute_login" && 
               d.status === "success"
        );
      }
    },
    {
      check: "security init_security任务已调用",
      verify: () => {
        const delegationLog = readJson("result/delegation_log.json");
        return delegationLog?.delegations?.some(
          d => d.to_agent === "security" && 
               d.task_type === "init_security" && 
               d.status === "success"
        );
      }
    },
    {
      check: "Coordinator没有直接使用Playwright MCP",
      verify: () => {
        const delegationLog = readJson("result/delegation_log.json");
        const violations = delegationLog?.violations || [];
        return !violations.some(v => v.tool?.startsWith("mcp__playwright__"));
      }
    }
  ],
  
  onViolation: (violations) => {
    createEvent("DELEGATION_VIOLATION", {
      priority: "high",
      payload: {
        violations: violations,
        message: "Coordinator违反了委派规则，请检查架构设计"
      }
    });
  }
};
```

### 门控1增强版：包含委派验证

```javascript
const gate1_withDelegation = {
  name: "初始化完成（含委派验证）",
  conditions: [
    // 原有条件...
    {
      check: "Chrome实例启动成功",
      verify: () => {
        const instances = readJson("result/chrome_instances.json");
        return instances.length > 0 && instances[0].status === "running";
      }
    },
    // 新增：委派验证
    ...delegationVerification.verification_checklist
  ],
  
  onPass: () => {
    updateSessionState("PHASE_1_EXPLORE");
    logDelegationSuccess();
    startPhase1Explore();
  },
  
  onFail: (failedConditions) => {
    // 检查是否为委派违规
    const delegationViolations = failedConditions.filter(
      c => c.check.includes("委派") || c.check.includes("Playwright")
    );
    
    if (delegationViolations.length > 0) {
      createEvent("DELEGATION_VIOLATION", {
        priority: "critical",
        payload: { violations: delegationViolations }
      });
    }
    
    reportInitFailure(failedConditions);
    pauseSession();
  }
};
```

---

## 📝 委派日志格式

### 文件位置
`result/delegation_log.json`

### 格式定义

```json
{
  "session_id": "session_20260422",
  "delegations": [
    {
      "timestamp": "2026-04-22T10:00:00Z",
      "from_agent": "webtest",
      "to_agent": "navigator",
      "task_type": "create_instance",
      "description": "创建Chrome实例",
      "status": "success",
      "result_summary": "Created Chrome instance on port 9222",
      "duration_ms": 5432
    },
    {
      "timestamp": "2026-04-22T10:00:10Z",
      "from_agent": "webtest",
      "to_agent": "form",
      "task_type": "execute_login",
      "description": "执行登录操作",
      "status": "success",
      "result_summary": "Login successful for admin_001",
      "duration_ms": 3210
    }
  ],
  "violations": [
    {
      "timestamp": "2026-04-22T09:55:00Z",
      "agent": "webtest",
      "tool": "mcp__playwright__browser_navigate",
      "reason": "Coordinator不应直接使用Playwright MCP",
      "should_delegate_to": "navigator"
    }
  ]
}
```

### 记录时机

1. **成功委派**：当Coordinator调用Task工具并收到成功返回时
2. **委派失败**：当Task调用返回失败时
3. **违规操作**：当检测到Coordinator直接使用禁止工具时

### 使用方法

Coordinator在调用Task工具后，应记录委派日志：

```javascript
function logDelegation(toAgent, taskType, description, status, result) {
  const log = readJson("result/delegation_log.json") || { delegations: [], violations: [] };
  
  log.delegations.push({
    timestamp: new Date().toISOString(),
    from_agent: "webtest",
    to_agent: toAgent,
    task_type: taskType,
    description: description,
    status: status,
    result_summary: result?.summary || "",
    duration_ms: result?.duration || 0
  });
  
  writeJson("result/delegation_log.json", log);
}

function logViolation(tool, reason, shouldDelegateTo) {
  const log = readJson("result/delegation_log.json") || { delegations: [], violations: [] };
  
  log.violations.push({
    timestamp: new Date().toISOString(),
    agent: "webtest",
    tool: tool,
    reason: reason,
    should_delegate_to: shouldDelegateTo
  });
  
  writeJson("result/delegation_log.json", log);
}
```