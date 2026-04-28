---
name: state-machine
description: "状态机定义，控制测试流程的状态转换和门控条件。现版本新增 SITE_SURVEY 状态，用于显式全貌测绘。"
---

# State Machine Skill

> 状态机定义：先全貌测绘，再定向探索，再安全测试，最后评估与报告。

## 状态定义

| 状态 | 说明 | 主要 Agent | 输出产物 |
|------|------|-----------|---------|
| `INIT` | 初始化环境 | Coordinator 调度 | `accounts.json`, `chrome_instances.json`, `sessions.json` |
| `SITE_SURVEY` | 全站 breadth-first 测绘 | `@navigator` | `site_survey.json`, `pages/apis/progress` |
| `EXPLORATION_RUNNING` | 模块深挖与角色差异验证 | `@navigator` | 模块探索记录、角色可达矩阵 |
| `SECURITY_TESTING` | 安全测试 | `@security` + `@analyzer` | `findings collection` |
| `EVALUATION` | 进度评估 | Coordinator | 下一步决策 |
| `REPORT` | 生成报告 | Coordinator | 报告文件 |
| `END` | 测试结束 | Coordinator | 最终状态 |

## 状态属性

```javascript
const stateProperties = {
  INIT: {
    timeout: 60000,
    outputs: ["accounts.json", "chrome_instances.json", "sessions.json"]
  },
  SITE_SURVEY: {
    timeout: 180000,
    agent: "@navigator",
    outputs: ["site_survey.json", "pages collection", "apis collection", "progress collection"]
  },
  EXPLORATION_RUNNING: {
    timeout: 180000,
    agent: "@navigator",
    outputs: ["progress.modules[].exploration_status", "role_access_matrix"]
  },
  SECURITY_TESTING: {
    timeout: 300000,
    agents: ["@security", "@analyzer"],
    outputs: ["findings collection", "progress.modules[].security_status"]
  },
  EVALUATION: {
    timeout: 30000,
    agent: "Coordinator",
    outputs: ["next_action decision"]
  },
  REPORT: {
    timeout: 60000,
    agent: "Coordinator",
    outputs: ["report file"]
  },
  END: {
    timeout: 0,
    outputs: ["final stats"]
  }
};
```

## 状态持久化

### `test_sessions` 最小字段

```javascript
{
  session_id: "session_20260425_001",
  target_host: "example.com",
  current_state: "SITE_SURVEY",
  status: "running",
  updated_at: Date.now(),
  state_history: [
    {
      from: "INIT",
      to: "SITE_SURVEY",
      timestamp: Date.now(),
      reason: "gate1 passed"
    }
  ]
}
```

### `result/sessions.json` 最小字段

```javascript
{
  session_name: "admin_001",
  current_state: "SITE_SURVEY",
  attach_mode: "reuse",
  attach_status: "attached",
  cdp_url: "http://127.0.0.1:9222",
  chrome_pid: 12345,
  active_tab_index: 0,
  last_verified_url: "https://example.com/dashboard",
  last_verified_title: "Dashboard"
}
```

### 状态写入原则

- 每次状态迁移必须同时更新 `test_sessions.current_state` 和 `state_history`
- 关键浏览器态必须同步写回 `result/sessions.json`
- 超时、异常、用户介入都必须留下可恢复的状态记录

## 状态转换图

```text
INIT
  ↓ gate1
SITE_SURVEY
  ↓ gate2
EVALUATION
  ├─ continue survey       → SITE_SURVEY
  ├─ deep module explore   → EXPLORATION_RUNNING → EVALUATION
  ├─ security testing      → SECURITY_TESTING   → EVALUATION
  └─ report                → REPORT → END
```

## 门控条件

### gate1: INIT → SITE_SURVEY

```javascript
const gate1 = {
  name: "初始化完成",
  conditions: [
    "accounts.json 已生成",
    "Chrome 实例启动成功",
    "BurpBridge 健康检查通过",
    "auto_sync 已启用",
    "登录成功（如需要）"
  ],
  onPass: () => updateSessionState("SITE_SURVEY", "gate1 passed")
};
```

### gate2: SITE_SURVEY → EVALUATION

```javascript
const gate2 = {
  name: "测绘轮次完成",
  triggerConditions: [
    "Navigator 返回 success 或 partial",
    "site_map_report 已生成",
    "recovery_actions 已回传",
    "requires_user_action = false 或已完成用户操作"
  ],
  onPass: () => updateSessionState("EVALUATION", "site survey round completed")
};
```

### gate3: EXPLORATION_RUNNING → EVALUATION

```javascript
const gate3 = {
  name: "模块深挖完成",
  triggerConditions: [
    "Navigator 返回 success 或 partial",
    "目标模块 exploration_status 已更新"
  ],
  onPass: () => updateSessionState("EVALUATION", "module exploration round completed")
};
```

### gate4: SECURITY_TESTING → EVALUATION

```javascript
const gate4 = {
  name: "安全测试完成",
  conditions: [
    "Security 测试完成",
    "Analyzer 分析完成"
  ],
  onPass: () => updateSessionState("EVALUATION", "security testing completed")
};
```

### gate5: EVALUATION → 下一步

```javascript
const gate5 = {
  name: "覆盖与风险判定",
  evaluate: async ({ progress, survey, findings }) => {
    if (survey.coverage_gaps.some(g => g.priority === "critical" || g.priority === "high")) {
      return {
        nextState: "SITE_SURVEY",
        action: "@navigator continue_survey",
        reason: "仍有高价值测绘缺口"
      };
    }

    const needsExploration = progress.modules.some(m =>
      m.exploration_status !== "completed" ||
      (m.role_coverage || []).some(r => r.status === "unverified")
    );
    if (needsExploration) {
      return {
        nextState: "EXPLORATION_RUNNING",
        action: "@navigator deep_explore_module|verify_role_access",
        reason: "仍有模块深挖或角色差异待验证"
      };
    }

    const needsSecurity = progress.modules.some(m => m.security_status !== "completed") ||
      progress.sensitive_apis?.tested < progress.sensitive_apis?.total;
    if (needsSecurity) {
      return {
        nextState: "SECURITY_TESTING",
        action: "@security test",
        reason: "关键端点尚未完成安全测试"
      };
    }

    const needsChainValidation = findings.some(f => ["High", "Critical"].includes(f.severity));
    if (needsChainValidation) {
      return {
        nextState: "SECURITY_TESTING",
        action: "@security attack_chain_test",
        reason: "需要进一步验证高危组合风险"
      };
    }

    return {
      nextState: "REPORT",
      reason: "测绘、探索和安全测试均已达标"
    };
  }
};
```

### gate6: REPORT → END

```javascript
const gate6 = {
  name: "报告完成",
  conditions: [
    "报告文件生成成功",
    "受管 Chrome 实例已关闭"
  ],
  onPass: () => updateSessionState("END", "report completed")
};
```

## 超时与异常

- `SITE_SURVEY` 超时：进入 `EVALUATION`，并带上当前 `coverage_gaps`
- `EXPLORATION_RUNNING` 超时：进入 `EVALUATION`，由 Coordinator 判断是否继续深挖
- `SECURITY_TESTING` 超时：进入 `EVALUATION`，避免流程卡死
- 任何状态若 `requires_user_action=true`，先暂停流程等待用户
- 超时发生时必须写入 `test_sessions.current_state`、`updated_at` 和对应 `state_history.reason`
- 用户介入暂停时必须把会话标记为 `paused_waiting_user`

## 子 Agent 返回后的状态判断

```javascript
let currentState = "INIT";

function updateSessionState(newState, reason) {
  mongodbUpdate({
    collection: "test_sessions",
    filter: { session_id: currentSessionId },
    update: {
      $set: {
        current_state: newState,
        updated_at: Date.now()
      },
      $push: {
        state_history: {
          from: currentState,
          to: newState,
          timestamp: Date.now(),
          reason: reason
        }
      }
    }
  });

  updateSessionsJson({
    current_state: newState,
    updated_at: Date.now()
  });
}

function handleAgentReturn(agentResult, agentName, currentState) {
  if (agentResult.status === "exception") {
    handleException(agentResult.exceptions);
    return;
  }

  if (agentResult.requires_user_action) {
    markTestSessionPaused("paused_waiting_user", agentResult.user_action_prompt);
    pauseSession();
    return;
  }

  if (currentState === "SITE_SURVEY" && agentName === "navigator") {
    updateSessionState("EVALUATION");
    return;
  }

  if (currentState === "EXPLORATION_RUNNING" && agentName === "navigator") {
    updateSessionState("EVALUATION");
    return;
  }

  if (currentState === "SECURITY_TESTING" && agentName === "analyzer") {
    updateSessionState("EVALUATION");
  }
}
```

## 加载要求

```yaml
1. 尝试: skill({ name: "state-machine" })
2. 若失败: Read(".opencode/skills/workflow/state-machine/SKILL.md")
3. Coordinator 必须加载本 Skill
```
