# WebTest - 项目说明

> AI-Agent Web 渗透测试系统  
> 支持场景：Web 探索 / 越权测试 / 注入测试 / 流程审批测试  
> 版本：1.6  
> 更新：2026-05-11

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
  - MongoDB（BurpBridge 数据）
```

Coordinator 负责决策与调度，subagent 负责具体执行。

---

## Agent 说明

| Agent | 模式 | 角色 | 主要职责 |
|---|---|---|---|
| Coordinator | primary | 主调度器 | 规划、委派、异常处理、进度跟踪 |
| Navigator | subagent | 浏览器/会话专家 | Chrome 管理、登录、会话判活、认证恢复、站点测绘、Cookie 同步 |
| Form | subagent | 复杂业务表单专家 | 复杂业务表单填写与提交流程 |
| Security | subagent | Replay 测试专家 | IDOR、注入、重放编排、`AUTH_CONTEXT_STALE`、CSRF 续链 |
| Analyzer | subagent | 结果分析专家 | 稳定 replay 分析、漏洞判定、严重性评级 |
| AccountParser | subagent | 账号解析专家 | 解析账号文档、提取角色与权限 |

### 边界总结

#### Navigator
- 统一负责首次登录、会话判活、会话恢复与认证刷新；
- 负责将浏览器 auth context 同步到 BurpBridge；
- 认证恢复后负责回到原始导航上下文。

#### Form
- 只处理复杂业务表单；
- 不负责登录；
- 不负责认证恢复。

#### Security
- 负责 replay 驱动测试；
- 负责识别 `AUTH_CONTEXT_STALE`；
- 负责识别 `CSRF_TOKEN_STALE` 并在 Security 内部完成续链；
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
3. `@navigator create_instance`
4. `@navigator login_or_resume`
5. `@navigator sync_cookies`
6. `@navigator survey/explore`
7. `@security test`
8. 仅在 replay 稳定后调度 `@analyzer`

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
  - MongoDB collections
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
- `last_auth_check_at`
- `auth_context.headers`
- `auth_context.cookies`
- `auth_context.last_synced_at`
- `auth_state.needs_reauth`
- `auth_state.relogin_attempts`
- `resume_context.task_type`
- `resume_context.resume_target_url`
- `resume_context.pending_urls`

Security 可以把它当作 BurpBridge auth context 的本地镜像。  
Security 在刷新 CSRF header 时，必须先本地合并，再整份回写。

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

---

## 更新记录

### v1.6 (2026-05-11)
- 新增 Security 自主管理的 `csrf-replay-recovery`
- 明确 BurpBridge auth 更新按“本地 snapshot 合并后整份回写”处理
- 新增 `CSRF_TOKEN_STALE`、`CSRF_TOKEN_REFRESHED`、`CSRF_REFRESH_FAILED`、`AUTH_CONTEXT_SNAPSHOT_MISSING`
- 明确 Analyzer 不参与首轮 CSRF 快速恢复

### v1.5 (2026-05-09)
- 登录职责统一收敛到 Navigator
- Form 收缩为复杂业务表单专用 Agent
- 增加 `AUTH_CONTEXT_STALE` 认证恢复闭环
