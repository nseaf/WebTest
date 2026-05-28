---
name: progress-tracking
description: "访问跟踪与进度控制，按账号双阶段轮次记录 Navigator 取证、Security denied replay 与补轮次进度。"
---

# Progress Tracking Skill

> 进度控制不再只看单轮页面数，而是跟踪模块、子模块、角色覆盖、当前账号双阶段执行状态与补轮次状态。

## 核心功能

1. 模块 / 子模块自动归类
2. 当前账号 `navigator phase` / `security phase` 双阶段状态跟踪
3. 角色覆盖与可达性跟踪
4. 未完成 `permission_key + role/account` 驱动的下一轮决策

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
  current_round: {
    account_id: "test1020",
    role: "manager",
    permission_key: "workflow.approval.submit",
    navigator_phase: "completed",
    security_phase: "pending",
    negative_backlog_count: 1,
    security_skip_reason: null
  },
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
  pending_role_permission_pairs: [
    {
      permission_key: "workflow.approval.submit",
      role: "employee",
      account_id: "test2040",
      pending_stage: "security_phase",
      reason: "AUTH_CONTEXT_STALE"
    }
  ],
  sensitive_apis: {
    total: 5,
    tested: 2,
    untested: ["api_003", "api_004", "api_005"]
  },
  history_progress: {
    "workflow.approval.submit|employee": {
      main_scan: {
        current_page: 3,
        last_processed_timestamp_ms: 1714090000000,
        last_processed_history_id: "65f1a2b3c4d5e6f7a8b9c0d1",
        last_scan_at: ISODate("2026-04-28T10:10:00Z")
      },
      reverse_probes: [
        {
          trigger_reason: "sensitive-api-detection:high",
          target_pattern: "/api/workflow/*",
          started_from_page: 9,
          pages_checked: 2,
          matched_history_ids: ["65f1a2b3c4d5e6f7a8b9c0d9"],
          finished_at: ISODate("2026-04-28T10:12:00Z")
        }
      ]
    }
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

- 每个账号轮次都必须显式记录 `navigator phase` 与 `security phase`，不能只看全局 survey/exploration/security 状态。
- 第一轮首个账号若没有 denied backlog，也必须把 `security phase` 记录为 `no_targets`，而不是缺失。
- 第一轮中每个账号只需要处理“自己 + 前序账号”已经形成证据链的权限点，不能把后续账号尚未探索的权限点提前计入当前轮 backlog。
- 每轮结束后必须整理未完成的 `permission_key + role/account`，作为后续补轮次输入。

## 历史扫描规则

- `main_scan` 是 Security 的默认主线，必须按页顺序从旧到新推进
- `reverse_probes` 只在高危接口或高风险模块触发时创建
- reverse probe 的页码、命中记录和结束时间必须独立记录
- reverse probe 不得覆盖 `main_scan.current_page` 或其 watermark
- `history_progress` 的主键应能映射到 `permission_key + 当前被测 denied role`，避免同一 denied replay 被重复执行

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

- 当前账号 denied backlog 是否已完成或合法 `no_targets`
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
  if (progress.current_round?.navigator_phase !== "completed") {
    return { answer: "YES", action: "继续当前账号 navigator phase" };
  }

  const needs = progress.modules.some(m =>
    m.exploration_status !== "completed" ||
    (m.role_coverage || []).some(r => r.status === "unverified")
  );
  return needs ? { answer: "YES", action: "EXPLORATION_RUNNING" } : { answer: "NO" };
}
```

### Q3: 关键端点是否都测试了？

保留敏感 API 覆盖率和高优先级模块安全状态判定，同时补充：
- 当前账号 `security phase` 是否已完成
- `pending_role_permission_pairs` 是否仍存在
- denied replay 是否已经写回对应 `permission_key`

## 加载要求

```yaml
1. 尝试: skill({ name: "progress-tracking" })
2. 若失败: Read(".opencode/skills/data/progress-tracking/SKILL.md")
3. Coordinator、Navigator、Security 必须加载本 Skill
```
