---
name: progress-tracking
description: "访问跟踪与进度控制，按模块/子模块/角色覆盖记录 Survey、Exploration、Security 三类进度。"
---

# Progress Tracking Skill

> 进度控制不再只看单轮页面数，而是跟踪模块、子模块、角色覆盖和安全测试状态。

## 核心功能

1. 模块 / 子模块自动归类
2. Survey / Exploration / Security 三阶段状态跟踪
3. 角色覆盖与可达性跟踪
4. 关键缺口驱动的下一轮决策

## API 模块划分

继续沿用 URL 路径自动归类，但进度模型升级为模块级：
- `user`
- `admin`
- `order`
- `content`
- `workflow`
- `auth`
- `data`
- `other`

## 状态定义

### API 状态

```text
discovered -> pending -> testing -> tested -> analyzed -> skipped
```

### 模块阶段状态

```text
survey_status: pending|in_progress|completed|blocked
exploration_status: pending|in_progress|completed|blocked
security_status: pending|in_progress|completed|blocked
```

## Progress Collection 结构

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",
  modules: [
    {
      module_name: "workflow",
      module_priority: "high",
      survey_status: "completed",
      exploration_status: "in_progress",
      security_status: "pending",
      submodules: [
        {
          submodule_name: "workflow.approval-list",
          survey_status: "completed",
          exploration_status: "completed",
          security_status: "pending",
          entry_points: [
            {
              url: "https://example.com/workflow/list",
              source: "menu",
              role_access: [
                { role: "roleA", status: "visible_and_accessible" },
                { role: "roleB", status: "hidden" }
              ]
            }
          ]
        }
      ],
      role_coverage: [
        {
          role: "roleA",
          survey_status: "completed",
          exploration_status: "completed",
          status: "verified"
        },
        {
          role: "roleB",
          survey_status: "completed",
          exploration_status: "pending",
          status: "unverified"
        }
      ],
      apis: [
        {
          api_id: "api_001",
          endpoint: "/api/workflow/tasks",
          method: "GET",
          test_status: "pending"
        }
      ],
      coverage_gaps: [
        {
          type: "role_access_unverified",
          target: "roleB",
          priority: "high",
          reason: "角色 B 尚未验证审批详情页"
        }
      ],
      stats: {
        total: 1,
        pending: 1,
        tested: 0,
        vulnerabilities: 0
      }
    }
  ],
  overall_stats: {
    total_apis: 10,
    tested: 3,
    coverage_percentage: 30.0
  },
  sensitive_apis: {
    total: 5,
    tested: 2,
    untested: ["api_003", "api_004", "api_005"]
  },
  survey_summary: {
    modules_total: 6,
    modules_completed: 4,
    critical_gaps: 1
  },
  last_updated: Date,
  next_action: "continue_survey"
}
```

## 进度判定重点

### Survey

- 是否已覆盖一级模块
- 是否已识别关键子模块
- 是否仍有高优先级 `coverage_gaps`
- 角色不可达是否已正确标注

### Exploration

- 高风险模块是否已深挖
- 角色差异是否已验证
- 是否仍存在 `needs_form_submission` / `external_domain_redirect` 等真实阻断

### Security

- 敏感 API 覆盖率是否达标
- 高优先级模块 `security_status` 是否完成

## 三问法则升级

### Q1: 还有高价值测绘缺口吗？

```javascript
function checkSurveyGaps(progress) {
  const gaps = progress.modules.flatMap(m => m.coverage_gaps || []);
  if (gaps.some(g => ["critical", "high"].includes(g.priority))) {
    return {
      answer: "YES",
      action: "SITE_SURVEY -> continue_survey"
    };
  }
  return { answer: "NO" };
}
```

### Q2: 还有模块深挖或角色差异待验证吗？

```javascript
function checkExplorationNeeds(progress) {
  const needs = progress.modules.some(m =>
    m.exploration_status !== "completed" ||
    (m.role_coverage || []).some(r => r.status === "unverified")
  );
  return needs ? { answer: "YES", action: "EXPLORATION_RUNNING" } : { answer: "NO" };
}
```

### Q3: 关键端点是否都测试了？

保留敏感 API 覆盖率和高优先级模块安全状态判定。

## 加载要求

```yaml
1. 尝试: skill({ name: "progress-tracking" })
2. 若失败: Read(".opencode/skills/data/progress-tracking/SKILL.md")
3. Coordinator、Navigator、Security 必须加载本 Skill
```
