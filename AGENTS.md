# WebTest — Project Instructions

> AI-Agent Web渗透测试系统 | AI-Agent Web Penetration Testing System
> 支持场景: Web探索 / 越权测试 / 注入测试 / 流程审批测试
> 版本: 1.5 | 更新: 2026-05-09

---

## ⛔ MANDATORY DELEGATION RULES

**违反以下规则将导致流程失败，必须立即停止并询问用户。**

### 操作-委派映射表

| 操作类型 | dispatch subagent | 要求 |
|---------|-----------|---------------|
| 浏览器操作 | @navigator | 使用 `browser-use` CLI + browser skills |
| Chrome管理 | @navigator | 使用 `scripts/start-managed-chrome.ps1` |
| 登录与会话恢复 | @navigator | 统一复用 `session_name`，不得交给 `@form` |
| 复杂业务表单填写 | @form | 仅处理业务表单，不负责登录 |
| 安全测试 | @security | 使用 `mcp__burpbridge__*` |
| 账号解析 | @account_parser | 禁止直接读取Excel |
| 结果分析 | @analyzer | 无（纯分析Agent） |

### 前置输出验证（强制执行）

**每个委派步骤执行前必须输出**：

```text
@{agent_name}
[TASK] {任务描述}
[FORBIDDEN] {禁止事项}
```

### 违规中断机制

**如果你发现自己正在直接使用禁止的工具，立即停止并输出**：

```text
[VIOLATION] 检测到违规操作: {违规行为}
[CORRECT] 正确方式: @{agent_name}
[STOP] 请用户确认是否继续
```

---

## System Architecture Overview

本系统采用 **Coordinator + Subagent + Skill** 三层架构，实现自主 Web 探索和安全测试。

```text
Coordinator
  ├─ navigator      浏览器管理、登录、会话恢复、测绘、Cookie同步
  ├─ form           复杂业务表单填写
  ├─ security       BurpBridge 测试、认证失效检测、断点续跑
  ├─ analyzer       重放结果分析
  └─ account_parser 账号/权限文档解析
```

共享状态层：
- `result/*.json`
- MongoDB（BurpBridge 数据）

---

## Agents Reference

| Agent | 模式 | 角色 | 功能 | 调度者 |
|-------|------|------|------|--------|
| **Coordinator** | primary | Web渗透测试主控制器 | 工作流调度、状态管理、异常处理、全貌测绘规划 | — |
| Navigator | subagent | 页面导航与会话管理专家 | Chrome管理、登录、会话判活、快速复登、全貌测绘、Cookie同步 | Coordinator |
| Form | subagent | 复杂业务表单处理专家 | 复杂表单识别、业务字段填写、多步骤业务提交流 | Coordinator |
| Security | subagent | 安全测试执行专家 | IDOR测试、注入测试、历史记录分析、认证失效检测、BurpBridge集成 | Coordinator |
| Analyzer | subagent | 安全测试结果分析专家 | 重放结果分析、漏洞判定、严重性评级 | Coordinator |
| AccountParser | subagent | 账号文档解析专家 | 多格式账号解析、权限矩阵提取、流程配置生成 | Coordinator |

### 关键职责边界

#### Navigator
- 统一负责首次登录、会话判活、登录过期后的原 `session_name` 快速复登
- 登录成功后统一执行 `sync_cookies`，刷新 BurpBridge 认证上下文
- 登录恢复后必须回到原 `resume_target_url` / `pending_urls` / 原模块上下文

#### Form
- 只处理复杂业务表单
- 不负责登录
- 不负责验证码处理
- 不负责会话恢复

#### Security
- 只负责 replay / 越权 / 注入测试
- 发现认证失效时创建 `AUTH_CONTEXT_STALE`
- 保存断点并等待 `navigator` 完成认证刷新
- 不直接登录、不直接操作浏览器

---

## Workflow Summary

### 默认链路

1. `@account_parser` 解析账号文档（如需要）
2. `@security init_security`
3. `@navigator create_instance`
4. `@navigator login_or_resume`
5. `@navigator survey/explore`
6. `@security test`

### 复杂业务表单

仅在探索或流程操作中遇到复杂业务表单时：

1. `@form process_complex_form`
2. 返回 `@navigator` 继续导航或恢复探索

### 认证失效恢复

当 `@security` 在 replay 中发现 302 到登录页、401/403、未认证响应或数据明显退化时：

1. `@security pause_on_auth_stale`
2. `@navigator refresh_auth_session`
3. `@navigator sync_cookies`
4. `@security resume_from_cursor`

---

## Survey-First Workflow

- 新会话默认先进入 `SITE_SURVEY`
- `Navigator` 首轮执行 `survey_site`
- 后续可由 `Coordinator` 调度：
  - `continue_survey`
  - `deep_explore_module`
  - `verify_role_access`
- 测绘上下文需显式传递：
  - `allowed_hosts`
  - `role_access_matrix`
  - `coverage_gaps`

---

## Tool Priority Strategy

```text
Priority 1: Browser Automation
└─ browser-use CLI + scripts/browser-use-utf8.ps1 + scripts/start-managed-chrome.ps1

Priority 2: Security Testing
├─ BurpBridge MCP
└─ MongoDB

Priority 3: Data Management
├─ JSON Files (result/*.json)
└─ MongoDB
```

### 工具使用约束

| Agent | 推荐工具 | 要求 |
|-------|---------|---------|
| Navigator | browser-use CLI + wrapper | Windows 下优先使用 `scripts/browser-use-utf8.ps1`；首次 attach 才允许 `--cdp-url` |
| Form | browser-use CLI + wrapper | 只复用现有 `session_name`，不处理登录 |
| Security | BurpBridge MCP | 不操作浏览器 |
| Analyzer | Read/Grep工具 | 禁止执行任何操作（仅分析数据） |
| Coordinator | `@` 调用 subagent | 禁止直接使用 `mcp__burpbridge__*` |

---

## BurpBridge MCP 调用格式

**重要**: BurpBridge MCP 工具已移除 `input` 包装，需直接传参：

```javascript
burpbridge_check_burp_health({})
burpbridge_list_paginated_http_history({ "host": "example.com" })
burpbridge_replay_http_request_as_role({ "history_entry_id": "xxx", "target_role": "admin" })
```

---

## 不可逆操作测试流程

对删除、审批通过、撤销、提交终止等不可逆操作，默认走“拦截优先”分支：

1. `@security` 调用 `start_one_shot_intercept`
2. `@navigator` 或 `@form` 触发真实页面动作
3. `@security` 调用 `get_one_shot_intercept_status`
4. 命中后立即基于 `matched_history_id` 重放
5. 未命中则 `stop_one_shot_intercept` 并记录为可恢复异常

---

## 状态与事件

### 核心会话字段

`result/sessions.json` 统一维护以下运行时字段：

- `session_name`
- `account_id`
- `role`
- `last_auth_check_at`
- `auth_state.needs_reauth`
- `auth_state.relogin_attempts`
- `resume_context.task_type`
- `resume_context.resume_target_url`
- `resume_context.pending_urls`

### 关键事件类型

- `SESSION_EXPIRED`
- `SESSION_STALE`
- `AUTH_CONTEXT_STALE`
- `SURVEY_GAP_DETECTED`
- `EXTERNAL_DOMAIN_SKIPPED`
- `RECOVERY_ATTEMPTED`

---

## Permissions / Execution Policy

```text
权限策略:
├─ 只读 (默认): 源代码、配置、文档
├─ 可执行: browser-use, docker, curl
├─ 可写: result/*.json, config/accounts.json
└─ Agent调度: 仅 Coordinator 可调度 subagent

安全原则:
- 仅测试授权目标
- 越权测试通过请求重放，不影响原流程状态
- 删除、审批通过、撤销等不可逆操作优先通过单次拦截保存请求，再执行重放
- Cookie/Token 脱敏显示
- `session_name` 为浏览器操作主键，`cdp_url` 仅用于 bootstrap/repair
```

---

## Version

- **Current**: 1.5
- **Updated**: 2026-05-09

### 更新日志

#### v1.5 (2026-05-09)
- 登录职责收敛到 Navigator，Form 不再参与登录
- 新增认证恢复闭环：`pause_on_auth_stale -> refresh_auth_session -> sync_cookies -> resume_from_cursor`
- 收缩 Form 为复杂业务表单专用 agent
- 扩展会话状态模型与事件类型，支持 `AUTH_CONTEXT_STALE`

#### v1.4 (2026-04-28)
- 新增项目级 browser-recovery skill，支持 session 冲突恢复、tab 切换和常见浏览器异常恢复
- 统一浏览器会话模型：`session_name` 为主，`cdp_url` 仅用于首次 attach 或 repair
- 强化 Navigator/Form 的标签页处理与分层探索策略
