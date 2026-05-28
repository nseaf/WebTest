# WebTest - 项目说明

> AI-Agent Web 渗透测试系统  
> 支持场景：Web 探索 / 越权测试 / 注入测试 / 流程审批测试  
> 版本：1.7  
> 更新：2026-05-19

---

## 强制委派规则

违反以下规则意味着流程不正确，应立即纠正。

### 操作与 Subagent 映射

| 操作类型 | Subagent | 要求 |
|---|---|---|
| 浏览器操作 | `@navigator` | 使用 `browser-use` 与 browser skills |
| Chrome 生命周期管理 | `@navigator` | 使用 managed Chrome 脚本 |
| 登录与会话恢复 | `@navigator` | 复用 `session_name`，不得交给 `@form` |
| 复杂业务表单 | `@form` | 仅处理业务表单，不负责登录 |
| 安全测试 | `@security` | 使用 BurpBridge MCP |
| 账号解析 | `@account_parser` | 禁止直接读取 Excel |
| 结果分析 | `@analyzer` | 只做只读语义分析 |

### 委派前置输出

每次委派前必须输出：

```text
@{agent_name}
[TASK] {任务描述}
[FORBIDDEN] {禁止事项}
```

### 违规中断规则

若检测到直接走了错误工具路径，应立即输出：

```text
[VIOLATION] Detected forbidden operation: {operation}
[CORRECT] Correct path: @{agent_name}
[STOP] Ask the user whether to continue
```

---

## 架构概览

系统采用三层结构：

```text
Coordinator
  |- navigator
  |- form
  |- security
  |- analyzer
  `- account_parser

共享状态：
  - result/*.json
  - MongoDB（BurpBridge 数据 + WebTest 项目级数据库）
```

Coordinator 负责决策与调度，subagent 负责具体执行。

---

## Agent 说明

| Agent | 模式 | 角色 | 主要职责 |
|---|---|---|---|
| Coordinator | primary | 主调度器 | 规划、委派、异常处理、进度跟踪 |
| Navigator | subagent | 浏览器/会话专家 | Chrome 管理、登录、会话判活、认证恢复、站点测绘、当前账号有权限证据回填、Cookie 同步 |
| Form | subagent | 复杂业务表单专家 | 复杂业务表单填写与提交流程 |
| Security | subagent | Replay 测试专家 | IDOR、注入、当前账号 denied backlog 重放、`AUTH_CONTEXT_STALE`、CSRF 续链 |
| Analyzer | subagent | 结果分析专家 | 稳定 replay 分析、漏洞判定、严重性评级 |
| AccountParser | subagent | 账号解析专家 | 解析账号文档、提取角色与权限 |

### 边界总结

#### Navigator
- 统一负责首次登录、会话判活、会话恢复与认证刷新；
- 负责将浏览器 auth context 同步到 BurpBridge；
- 认证恢复后负责回到原始导航上下文；
- 只负责当前账号“有权限”的页面、接口与操作取证，不负责负向 replay。

#### Form
- 只处理复杂业务表单；
- 不负责登录；
- 不负责认证恢复。

#### Security
- 负责 replay 驱动测试；
- 负责识别 `AUTH_CONTEXT_STALE`；
- 负责识别 `CSRF_TOKEN_STALE` 并在 Security 内部完成续链；
- 默认消费 `permission_targets` 中“前序账号已确认有权限、且当前账号应无权限”的 denied backlog；
- 不直接操作浏览器。

#### Analyzer
- 只分析稳定的 replay 结果；
- 不负责首轮 CSRF 续链判断。

---

## Skills 说明

### Core Skills

| Skill | 路径 | 作用 |
|---|---|---|
| anti-hallucination | `.opencode/skills/core/anti-hallucination/` | 证据优先、防幻觉 |
| agent-contract | `.opencode/skills/core/agent-contract/` | Agent 输入输出契约 |
| shared-browser-state | `.opencode/skills/core/shared-browser-state/` | 共享浏览器状态模型 |

### Workflow Skills

| Skill | 路径 | 作用 |
|---|---|---|
| state-machine | `.opencode/skills/workflow/state-machine/` | 工作流状态控制 |
| test-rounds | `.opencode/skills/workflow/test-rounds/` | 多轮测试模型 |
| event-handling | `.opencode/skills/workflow/event-handling/` | 跨 Agent 事件路由 |
| security-error-handling | `.opencode/skills/workflow/security-error-handling/` | Security 恢复与降级策略 |

### Security Skills

| Skill | 路径 | 作用 |
|---|---|---|
| idor-testing | `.opencode/skills/security/idor-testing/` | 越权 replay 方法论 |
| injection-testing | `.opencode/skills/security/injection-testing/` | 注入测试方法论 |
| auth-context-sync | `.opencode/skills/security/auth-context-sync/` | 浏览器 auth context 同步与复用 |
| csrf-replay-recovery | `.opencode/skills/security/csrf-replay-recovery/` | Security 内部 CSRF 续链 |
| vulnerability-rating | `.opencode/skills/security/vulnerability-rating/` | 严重性评级参考 |
| burpbridge-api-reference | `.opencode/skills/security/burpbridge-api-reference/` | BurpBridge 接口参考 |
| workflow-authorization-testing | `.opencode/skills/security/workflow-authorization-testing/` | 流程审批 replay 测试 |
| sensitive-api-detection | `.opencode/skills/security/sensitive-api-detection/` | 敏感 API 识别规则 |

### Browser Skills

| Skill | 路径 | 作用 |
|---|---|---|
| page-navigation | `.opencode/skills/browser/page-navigation/` | 页面导航方法论 |
| form-handling | `.opencode/skills/browser/form-handling/` | 浏览器表单处理 |
| page-analysis | `.opencode/skills/browser/page-analysis/` | 页面分析 |
| api-discovery | `.opencode/skills/browser/api-discovery/` | API 线索发现 |
| browser-recovery | `.opencode/skills/browser/browser-recovery/` | 浏览器/Tab/Session 恢复 |

---

## 工作流摘要

### 默认路径

1. 如需账号解析，先执行 `@account_parser`
2. `@security init_security`
3. Coordinator 基于账号、角色与权限矩阵生成 `result/permission_targets.json`
4. 按权限点价值选择当前账号/角色轮次，并仅为该账号执行：
   - `@navigator create_instance`
   - `@navigator login_or_resume`
   - `@navigator sync_cookies`
5. `@navigator survey/explore/verify_role_access`
6. `@security test`
7. 仅在 replay 稳定后调度 `@analyzer`
8. Coordinator 整理本轮未完成的 `permission_key + role/account`
9. 常规账号轮次完成后，再处理：
   - deferred / 补轮次权限点
   - intercept-first 的不可逆专项

### 复杂表单路径

只有在探索过程中遇到复杂业务表单时才进入：

1. `@form process_complex_form`
2. `@navigator resume_navigation_context`

### 认证恢复路径

当 Security 返回 `AUTH_CONTEXT_STALE` 时：

1. `@security pause_on_auth_stale`
2. `@navigator refresh_auth_session`
3. `@navigator sync_cookies`
4. `@security resume_from_cursor`

### CSRF 续链路径

当 Security 返回 `CSRF_TOKEN_STALE` 时：

1. 保持重试在 `@security` 内部
2. `@security handle_csrf_retry`
3. 若 Security 返回 `AUTH_CONTEXT_SNAPSHOT_MISSING`：
   - `@navigator sync_cookies`
   - `@security handle_csrf_retry`
4. 只有 replay chain 稳定后，才调用 `@analyzer`

### Survey-First 规则

- 新会话默认先进入 `SITE_SURVEY`
- `Navigator` 首轮执行 `survey_site`
- 后续动作可以包括：
  - `continue_survey`
  - `deep_explore_module`
  - `verify_role_access`
- survey 上下文应显式包含：
  - `allowed_hosts`
  - `role_access_matrix`
  - `coverage_gaps`
  - `permission_targets`

### Permission-First 规则

- 默认不再预登录全部账号，也不以“当前已登录账号集合”推进测试。
- Coordinator 必须以 `permission_key` 作为默认调度单位，而不是以账号顺序作为默认主索引。
- 每个账号轮次都必须包含两个连续子阶段：
  - `@navigator` 负责当前账号有权限取证
  - `@security` 负责当前账号 denied backlog replay
- 在当前账号的 Security 子阶段结束前，不得切到下一个账号的 Navigator。
- 不允许“所有账号先跑 Navigator，最后统一跑 Security”。
- 每个权限点应聚合：
  - 允许角色/账号
  - 禁止角色
  - 关联页面与接口
  - 已测试角色
  - deferred 角色及原因
- Navigator 回填单位始终是 `permission_key`，而不是账号记录；一个 `permission_key` 下可以挂多个操作样本。
- 第一轮首个账号也必须进入 Security 子阶段；若 denied backlog 为空，则返回 `success/no_targets`，但轮次仍算完整执行。
- 第一轮中每个账号只处理“自己 + 前序账号”已经形成证据链的权限点，不预支后续账号尚未探索出的 denied 测试。
- 若某角色可立即用于 replay，则应立即验证；若目标角色缺少有效 auth snapshot，则记录为 deferred，不强制反复重登。
- 每轮结束后都要整理未完成的 `permission_key + role/account`，后续补轮次仍按“登录一个账号 -> Navigator 取证 -> Security replay”执行。
- 删除、审批通过、撤销、终止等不可逆动作应标记为最终专项，统一在最后处理。

### Coordinator 审视规则

- subagent 的 `suggestions` 与 `recommended_next_actions` 只作为建议输入，不得直接作为下一步动作执行。
- Coordinator 必须先结合全局 `permission_targets`、`coverage_gaps`、`deferred_roles`、`final_stage_required`、`history_progress` 做二次审视。
- 当 subagent 建议只覆盖局部最优，而全局仍有更高价值权限点或更高优先级缺口时，Coordinator 必须拒绝该建议并重排。
- Coordinator 的全局审视顺序固定为：
  - 高优先级 survey gap
  - 高价值未闭环 permission target
  - deferred / FINAL_STAGE
  - subagent suggestions

---

## 工具策略

### 优先级

```text
Priority 1: Browser Automation
  - browser-use CLI
  - scripts/browser-use-utf8.ps1
  - scripts/start-managed-chrome.ps1

Priority 2: Security Testing
  - BurpBridge MCP
  - MongoDB

Priority 3: Data Management
  - result/*.json
  - project-scoped MongoDB collections
```

### 工具约束

| Agent | 推荐工具 | 说明 |
|---|---|---|
| Navigator | browser-use + wrappers | `--cdp-url` 仅用于 bootstrap 或 repair |
| Form | browser-use + wrappers | 复用现有 session，不负责登录 |
| Security | BurpBridge MCP | 不直接控制浏览器 |
| Analyzer | Read/Grep | 只做分析 |
| Coordinator | `@` subagent dispatch | 不直接调用 BurpBridge MCP |

---

## BurpBridge MCP 调用规范

BurpBridge MCP 工具不再使用 `input` 包装，必须直接传参：

```javascript
burpbridge_check_burp_health({})
burpbridge_list_paginated_http_history({ "host": "example.com" })
burpbridge_replay_http_request_as_role({ "history_entry_id": "xxx", "target_role": "admin" })
```

---

## 不可逆操作测试

对于删除、审批通过、撤销、终止等动作，采用 intercept-first：

1. `@security start_one_shot_intercept`
2. `@navigator` 或 `@form` 触发真实页面动作
3. `@security get_one_shot_intercept_status`
4. 若命中，则基于 `matched_history_id` replay
5. 若未命中，则停止 intercept 并记录为可恢复异常

---

## 共享状态与事件

### `result/sessions.json`

Navigator 维护以下运行时会话字段：
- `session_name`
- `account_id`
- `role`
- `current_round_stage`
- `last_auth_check_at`
- `auth_context.headers`
- `auth_context.cookies`
- `auth_context.last_synced_at`
- `auth_state.needs_reauth`
- `auth_state.relogin_attempts`
- `permission_context.current_permission_key`
- `permission_context.pending_permission_keys`
- `permission_context.deferred_permission_keys`
- `resume_context.task_type`
- `resume_context.resume_target_url`
- `resume_context.pending_urls`
- `permission_context.pending_role_permission_pairs`
- `permission_context.negative_backlog_count`
- `permission_context.security_skip_reason`

Security 可以把它当作 BurpBridge auth context 的本地镜像。  
Security 在刷新 CSRF header 时，必须先本地合并，再整份回写。

`history_progress` 应支持按 `permission_key + role` 跟踪 replay 光标，而不是只保存单一全局进度。

### `result/permission_targets.json`

Coordinator 维护权限中心运行态，至少包含以下字段：

- `permission_key`
- `module_path`
- `menu_path`
- `permission_name`
- `baseline_source`
- `allowed_roles`
- `allowed_accounts`
- `denied_roles`
- `entry_points`
- `access_steps`
- `ui_locations`
- `related_pages`
- `related_apis`
- `evidence_history_ids`
- `matched_history_ids`
- `confirmed_request_samples`
- `tested_roles`
- `untested_roles`
- `deferred_roles`
- `deferred_reasons`
- `irreversible`
- `final_stage_required`
- `status`

该文件是默认调度中心，优先级高于“当前已登录账号列表”。

### 关键事件类型

- `SESSION_EXPIRED`
- `SESSION_STALE`
- `AUTH_CONTEXT_STALE`
- `CSRF_TOKEN_STALE`
- `CSRF_TOKEN_REFRESHED`
- `CSRF_REFRESH_FAILED`
- `AUTH_CONTEXT_SNAPSHOT_MISSING`
- `SURVEY_GAP_DETECTED`
- `EXTERNAL_DOMAIN_SKIPPED`
- `RECOVERY_ATTEMPTED`

优先级规则：
- `AUTH_CONTEXT_STALE` 高于 `CSRF_TOKEN_STALE`

---

## 权限 / 执行策略

```text
默认只读：
  - source code
  - config
  - docs

可写项目状态：
  - result/*.json
  - config/accounts.json

调度约束：
  - 只有 Coordinator 负责调度 subagent
```

安全原则：
- 只测试授权目标
- 优先通过 replay 做验证，避免影响真实业务流
- 对不可逆操作使用 intercept-first
- 报告中对 Cookie/token 做脱敏
- `session_name` 是浏览器会话主键

MongoDB 原则：
- WebTest 自有数据使用项目级数据库：`webtest_<project_key>`
- `project_key` 优先使用用户显式给出的项目标识；否则使用 `target_host` 归一化生成
- 不再通过清空单一 `webtest`/`WebTest` 数据库开始下一个项目
- BurpBridge 自身的 `history` / `replays` 不在本次数据库改造范围内

---

## 更新记录

### v1.7 (2026-05-19)
- 默认工作流切换为权限主导，Coordinator 以 `permission_key` 调度轮次
- 新增 `result/permission_targets.json` 作为权限中心运行态
- 明确 deferred 权限点补测与不可逆动作最终专项阶段
- 明确 WebTest 自有数据写入项目级数据库 `webtest_<project_key>`

### v1.6 (2026-05-11)
- 新增 Security 自主管理的 `csrf-replay-recovery`
- 明确 BurpBridge auth 更新按“本地 snapshot 合并后整份回写”处理
- 新增 `CSRF_TOKEN_STALE`、`CSRF_TOKEN_REFRESHED`、`CSRF_REFRESH_FAILED`、`AUTH_CONTEXT_SNAPSHOT_MISSING`
- 明确 Analyzer 不参与首轮 CSRF 快速恢复

### v1.5 (2026-05-09)
- 登录职责统一收敛到 Navigator
- Form 收缩为复杂业务表单专用 Agent
- 增加 `AUTH_CONTEXT_STALE` 认证恢复闭环
