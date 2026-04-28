# WebTest — Project Instructions

> AI-Agent Web渗透测试系统 | AI-Agent Web Penetration Testing System
> 支持场景: Web探索 / 越权测试 / 注入测试 / 流程审批测试
> 版本: 1.4 | 更新: 2026-04-28

---

## ⛔ MANDATORY DELEGATION RULES (强制委派规则)

**违反以下规则将导致流程失败，必须立即停止并询问用户。**

### 操作-委派映射表

| 操作类型 | dispatch subagent | 要求 |
|---------|-----------|---------------|
| 浏览器操作 | @navigator | 使用browser-use cli + skill, chrome命令 |
| Chrome管理 | @navigator | 使用 chrome 命令管理和维护浏览器实例 |
| 表单处理 | @form | 使用browser-use |
| 安全测试 | @security | mcp__burpbridge__* |
| 账号解析 | @account_parser | 禁止直接读取Excel |
| 结果分析 | @analyzer | 无（纯分析Agent） |

### 前置输出验证（强制执行）

**每个委派步骤执行前必须输出**：

```
@{agent_name}
[TASK] {任务描述}
[FORBIDDEN] {禁止事项}
```

### 违规中断机制

**如果你发现自己正在直接使用禁止的工具，立即停止并输出**：

```
[VIOLATION] 检测到违规操作: {违规行为}
[CORRECT] 正确方式: @{agent_name}
[STOP] 请用户确认是否继续
```

---

## System Architecture Overview

本系统采用 **Coordinator + Subagent + Skill** 三层架构，实现自主Web探索和安全测试。

```
┌────────────────────────────────────────────────────────────────────────┐
│                     Coordinator / Primary Agent                        │
│  职责: 规划 → 调度 → 事件处理 → 状态监控 → 人机交互代理                    │
└──────────────────────────┬──────────────────────────────────────────────┘
                          │ dispatch via Task tool
       ┌──────────┬────────┼────────┬────────┬────────┐
       ▼          ▼        ▼        ▼        ▼        ▼
   navigator    form   security  analyzer  account_parser
   (导航+分析)  (表单)   (安全)    (分析)      (解析)
       │                                            │
       └────────────────────────────────────────────┘
                          │
              共享状态层: result/*.json + MongoDB
```

**注意**: Scout功能已合并到Navigator，系统现为6个Agent（1个主控 + 5个子Agent）。

- **Agent 定义**: `.opencode/agents/` — 包含 Coordinator (主调度器) 及 5 个专业 Subagent
- **Skill 知识库**: `.opencode/skills/` — 可复用的方法论模块
- **数据存储**: `result/` — JSON 文件存储，MongoDB 用于 BurpBridge 数据

---

## Agents Reference (Agent 清单)

| Agent | 模式 | 角色 | 功能 | 调度者 |
|-------|------|------|------|--------|
| **Coordinator** | primary | Web渗透测试主控制器 | 工作流调度、状态管理、异常处理、进度评估 | — |
| Navigator | subagent | 页面导航与探索专家 | Chrome管理、页面导航、页面分析、API发现、Cookie同步 | Coordinator |
| Form | subagent | 表单处理与登录专家 | 表单识别、智能填写、批量登录执行 | Coordinator |
| Security | subagent | 安全测试执行专家 | IDOR测试、注入测试、历史记录分析、BurpBridge集成 | Coordinator |
| Analyzer | subagent | 安全测试结果分析专家 | 重放结果分析、漏洞判定、严重性评级 | Coordinator |
| AccountParser | subagent | 账号文档解析专家 | 多格式账号解析、权限矩阵提取、流程配置生成 | Coordinator |

### Agent 身份定义详情

#### Coordinator
- **角色**：Web渗透测试主控制器
- **功能**：工作流调度、状态管理、异常处理、进度评估
- **目的**：协调多Agent完成Web应用的自动化安全测试
- **核心原则**：Coordinator决定"做什么"和"谁来做"，将具体工作交给subagent

#### Navigator
- **角色**：页面导航与探索专家
- **功能**：Chrome实例管理、页面导航、页面分析、API发现、Cookie同步
- **目的**：自主探索Web应用，发现页面和API端点，返回详细报告
- **特点**：已合并Scout功能，探索一定量页面后主动退出；统一管理浏览器状态（含Cookie）

#### Form
- **角色**：表单处理与登录专家
- **功能**：表单识别、智能填写、批量登录执行
- **目的**：自动化处理Web表单，建立测试会话的认证状态
- **特点**：批量处理多账号登录，遇验证码继续处理下一个，最后汇总返回

#### Security
- **角色**：安全测试执行专家
- **功能**：IDOR测试、注入测试、历史记录分析、BurpBridge集成
- **目的**：发现Web应用的安全漏洞，验证访问控制缺陷

#### Analyzer
- **角色**：安全测试结果分析专家
- **功能**：重放结果分析、漏洞判定、严重性评级、测试建议生成
- **目的**：通过语义级对比，精准识别数据泄露和安全漏洞

#### AccountParser
- **角色**：账号文档解析专家
- **功能**：多格式账号解析、权限矩阵提取、流程配置生成
- **目的**：将账号和权限文档转换为标准化的测试配置

---

## Skills Reference (技能模块)

### Core Skills（所有 Agent 必加载）

| Skill | 路径 | 功能 |
|-------|------|------|
| anti-hallucination | `.opencode/skills/core/anti-hallucination/` | 防幻觉规则：数据真实性验证 |
| agent-contract | `.opencode/skills/core/agent-contract/` | Agent合约：输出格式、截断检测 |
| shared-browser-state | `.opencode/skills/core/shared-browser-state/` | 共享浏览器状态机制 |

### Workflow Skills

| Skill | 路径 | 功能 |
|-------|------|------|
| state-machine | `.opencode/skills/workflow/state-machine/` | 状态机定义与门控机制 |
| test-rounds | `.opencode/skills/workflow/test-rounds/` | 三轮测试模型 |
| event-handling | `.opencode/skills/workflow/event-handling/` | 事件处理规范 |

### Data Skills

| Skill | 路径 | 功能 |
|-------|------|------|
| mongodb-writer | `.opencode/skills/data/mongodb-writer/` | 实时数据库写入 |
| progress-tracking | `.opencode/skills/data/progress-tracking/` | 访问跟踪与进度控制 |
| api-categorization | `.opencode/skills/data/api-categorization/` | API模块划分与分类 |
| excel-merged-cell-handler | `.opencode/skills/data/excel-merged-cell-handler/` | Excel合并单元格处理 |
| permission-matrix-parser | `.opencode/skills/data/permission-matrix-parser/` | 权限矩阵解析 |

### Security Skills

| Skill | 路径 | 功能 |
|-------|------|------|
| idor-testing | `.opencode/skills/security/idor-testing/` | 越权测试方法论 |
| injection-testing | `.opencode/skills/security/injection-testing/` | 注入测试方法论 |
| auth-context-sync | `.opencode/skills/security/auth-context-sync/` | 认证上下文同步 |
| vulnerability-rating | `.opencode/skills/security/vulnerability-rating/` | 漏洞严重性评级 |
| burpbridge-api-reference | `.opencode/skills/security/burpbridge-api-reference/` | BurpBridge REST API参考 |
| workflow-authorization-testing | `.opencode/skills/security/workflow-authorization-testing/` | 流程审批越权测试 |
| sensitive-api-detection | `.opencode/skills/security/sensitive-api-detection/` | 敏感API识别规则 |

### Browser Skills

| Skill | 路径 | 功能 |
|-------|------|------|
| page-navigation | `.opencode/skills/browser/page-navigation/` | 页面导航方法论 |
| form-handling | `.opencode/skills/browser/form-handling/` | 表单处理方法论 |
| page-analysis | `.opencode/skills/browser/page-analysis/` | 页面分析方法论 |
| api-discovery | `.opencode/skills/browser/api-discovery/` | API发现方法论 |
| browser-recovery | `.opencode/skills/browser/browser-recovery/` | 浏览器异常恢复与tab切换方法论 |

---

## Quick Start (快速开始)

### 启动测试会话

```
/coordinator
目标URL: https://www.example.com
请开始规划并执行Web探索测试。
```

### 前置条件检查


# 1. MongoDB 运行中
ps | Select-String mongo

# 2. BurpBridge MCP 已启动

# 3. browser-use CLI 已安装
browser-use doctor

---

## Tool Priority Strategy (工具优先级策略)

### 工具使用优先级

```
Priority 1: Browser Automation
└─ browser-use CLI + scripts/browser-use-utf8.ps1 (Chrome CDP, 多实例管理, attach兼容) ← Navigator使用

Priority 2: Security Testing
├─ BurpBridge MCP (请求同步、重放、认证上下文)
└─ MongoDB (历史记录、重放结果存储)

Priority 3: Data Management
├─ JSON Files (result/*.json)
└─ MongoDB (burpbridge collections)
```

### 工具使用约束

| Agent | 推荐工具 | 要求 |
|-------|---------|---------|
| Navigator | browser-use CLI + wrapper | Windows 下优先使用 `scripts/browser-use-utf8.ps1`；首次 attach 才允许 `--cdp-url` |
| Form | browser-use CLI + wrapper | 以 `session_name` 为主，默认复用会话，不重复传 `--cdp-url` |
| Security | BurpBridge MCP | — |
| Analyzer | Read/Grep工具 | 禁止执行任何操作（仅分析数据） |
| Coordinator | `@` 调用 subagent | 禁止直接使用 mcp__burpbridge__* |

---

## BurpBridge MCP 调用格式

**重要**: 所有 BurpBridge MCP 工具需要 `input` 参数包装：

```javascript
// 正确调用方式
burpbridge_check_burp_health(input: {})
burpbridge_list_paginated_http_history(input: { "host": "example.com" })
burpbridge_replay_http_request_as_role(input: { "history_entry_id": "xxx", "target_role": "admin" })

// 错误调用方式
burpbridge_check_burp_health()  // 缺少 input 参数
```

---

## Permissions / Execution Policy (权限策略)

```
权限策略:
├─ 只读 (默认): 源代码、配置、文档
├─ 可执行: browser-use, docker, curl
├─ 可写: result/*.json, config/accounts.json
└─ Agent调度: 仅 Coordinator 可调度 subagent

安全原则:
- 仅测试授权目标
- 越权测试通过请求重放，不影响原流程状态
- Cookie/Token 脱敏显示
- `session_name` 为浏览器操作主键，`cdp_url` 仅用于 bootstrap/repair
```

---

## Version

- **Current**: 1.4
- **Updated**: 2026-04-28

### 更新日志

#### v1.4 (2026-04-28)
- 新增项目级 browser-recovery skill，支持 session 冲突恢复、tab 切换和常见浏览器异常恢复
- 统一浏览器会话模型：`session_name` 为主，`cdp_url` 仅用于首次 attach 或 repair
- 强化 Navigator/Form 的标签页处理与分层探索策略

#### v1.3 (2026-04-23)
- Scout功能合并到Navigator，系统精简为6个Agent
- 更新强制委派规则，添加违规中断机制
- 更新各Agent身份定义

#### v1.0 (Initial Release)
- 7 个 Agent (Coordinator + 6 subagents)
- Browser-use CLI 集成
- BurpBridge MCP 集成
- 流程审批场景支持
