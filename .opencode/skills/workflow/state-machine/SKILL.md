---
name: state-machine
description: "状态机定义，控制测试流程的状态转换和门控条件。现版本新增 SITE_SURVEY 状态，用于显式全貌测绘。"
---

# State Machine Skill

> 状态机定义：先建立权限基线，再做权限相关测绘与探索，再执行按权限点驱动的安全测试，最后处理 deferred 与不可逆专项。

## 状态定义

| 状态 | 说明 | 主要 Agent | 输出产物 |
|------|------|-----------|---------|
| `INIT` | 初始化环境与权限基线 | Coordinator 调度 | `accounts.json`, `permission_targets.json`, `sessions.json` |
| `SITE_SURVEY` | 权限相关 breadth-first 测绘 | `@navigator` | `site_survey.json`, `pages/apis/progress` |
| `EXPLORATION_RUNNING` | 模块深挖与角色差异验证 | `@navigator` | 模块探索记录、角色可达矩阵 |
| `SECURITY_TESTING` | 按权限点安全测试 | `@security` + `@analyzer` | `findings collection`, `permission_targets status` |
| `FINAL_STAGE` | deferred 补测与不可逆专项 | `@security` + `@navigator` | `permission_targets final updates`, `workflow findings` |
| `EVALUATION` | 进度评估 | Coordinator | 下一步决策 |
| `REPORT` | 生成报告 | Coordinator | 报告文件 |
| `END` | 测试结束 | Coordinator | 最终状态 |

## 状态属性

```javascript
const stateProperties = {
  INIT: {
    timeout: 60000,
    outputs: ["accounts.json", "permission_targets.json", "sessions.json"]
  },
  SITE_SURVEY: {
    timeout: 180000,
    agent: "@navigator",
    outputs: ["site_survey.json", "permission_targets updates", "pages collection", "apis collection", "progress collection"]
  },
  EXPLORATION_RUNNING: {
    timeout: 180000,
    agent: "@navigator",
    outputs: ["progress.modules[].exploration_status", "role_access_matrix", "permission target evidence"]
  },
  SECURITY_TESTING: {
    timeout: 300000,
    agents: ["@security", "@analyzer"],
    outputs: ["findings collection", "progress.modules[].security_status", "permission_targets test status"]
  },
  FINAL_STAGE: {
    timeout: 300000,
    agents: ["@security", "@navigator"],
    outputs: ["deferred permission closures", "irreversible-action evidence"]
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
  project_key: "example_com",
  database_name: "webtest_example_com",
  target_host: "example.com",
  workflow_mode: "permission_first",
  current_role: "manager",
  current_permission_key: "workflow.approval.submit",
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
  ├─ deferred/final stage  → FINAL_STAGE        → EVALUATION
  └─ report                → REPORT → END
```

## 门控条件

### gate1: INIT → SITE_SURVEY

```javascript
const gate1 = {
  name: "初始化完成",
  conditions: [
    "accounts.json 已生成",
    "permission_targets.json 已初始化",
    "BurpBridge 健康检查通过",
    "auto_sync 已启用并验证",
    "sessions.runtime_control.auto_sync_expected = true"
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

### gate5: FINAL_STAGE → EVALUATION

```javascript
const gate5 = {
  name: "deferred 与不可逆专项完成",
  conditions: [
    "deferred permission roles 已处理或确认继续延期",
    "final_stage_required 目标已处理"
  ],
  onPass: () => updateSessionState("EVALUATION", "final stage completed")
};
```

### gate6: EVALUATION → 下一步

```javascript
const gate6 = {
  name: "覆盖与风险判定",
  evaluate: async ({ progress, survey, findings, permissionTargets }) => {
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

    const hasOpenPermissionTargets = permissionTargets.some(t =>
      !["closed", "deferred", "final_stage"].includes(t.status)
    );
    const needsSecurity = hasOpenPermissionTargets ||
      progress.modules.some(m => m.security_status !== "completed") ||
      progress.sensitive_apis?.tested < progress.sensitive_apis?.total;
    if (needsSecurity) {
      return {
        nextState: "SECURITY_TESTING",
        action: "@security test",
        reason: "仍有权限点或关键端点尚未完成安全测试"
      };
    }

    const hasDeferredOrIrreversible = permissionTargets.some(t =>
      t.status === "deferred" ||
      (t.deferred_roles || []).length > 0 ||
      t.final_stage_required === true
    );
    if (hasDeferredOrIrreversible) {
      return {
        nextState: "FINAL_STAGE",
        action: "@security test|intercept-first final stage",
        reason: "仍有 deferred 权限点或不可逆专项待处理"
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

### gate7: REPORT → END

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
