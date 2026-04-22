# WebTest — Project Instructions

> AI-Agent Web渗透测试系统 | AI-Agent Web Penetration Testing System
> 支持场景: Web探索 / 越权测试 / 注入测试 / 流程审批测试
> 版本: 1.1 | 更新: 2026-04-22

---

## System Architecture Overview

本系统采用 **Coordinator + Subagent + Skill** 三层架构，实现自主Web探索和安全测试。

```
┌────────────────────────────────────────────────────────────────────────┐
│                    webtest (Coordinator / Primary Agent)                 │
│  职责: 规划 → 调度 → 事件处理 → 状态监控 → 人机交互代理                    │
└──────────────────────────┬──────────────────────────────────────────────┘
                          │ dispatch
       ┌──────────┬────────┼────────┬────────┬────────┐
       ▼          ▼        ▼        ▼        ▼        ▼
   navigator    scout    form   security  analyzer  account_parser
   (导航)      (分析)   (表单)   (安全)    (分析)    (解析)
       │                                            │
       └────────────────────────────────────────────┘
                          │
              共享状态层: result/*.json + MongoDB
```

- **Agent 定义**: `.opencode/agents/` — 包含 webtest (主调度器) 及 6 个专业 Subagent
- **Skill 知识库**: `.opencode/skills/` — 可复用的方法论模块 (24 个 Skills)
- **数据存储**: `result/` — JSON 文件存储，MongoDB 用于 BurpBridge 数据

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
| workflow-operation-logging | `.opencode/skills/data/workflow-operation-logging/` | 流程审批操作记录方法论 |

### Security Skills

| Skill | 路径 | 功能 |
|-------|------|------|
| idor-testing | `.opencode/skills/security/idor-testing/` | 越权测试方法论 |
| injection-testing | `.opencode/skills/security/injection-testing/` | 注入测试方法论 |
| auth-context-sync | `.opencode/skills/security/auth-context-sync/` | 认证上下文同步 |
| vulnerability-rating | `.opencode/skills/security/vulnerability-rating/` | 漏洞严重性评级 |
| burpbridge-api-reference | `.opencode/skills/security/burpbridge-api-reference/` | BurpBridge REST API完整参考 |
| workflow-authorization-testing | `.opencode/skills/security/workflow-authorization-testing/` | 流程审批越权测试方法论 |
| sensitive-api-detection | `.opencode/skills/security/sensitive-api-detection/` | 敏感API识别规则 |

### Workflow Skills (补充)

| Skill | 路径 | 功能 |
|-------|------|------|
| security-error-handling | `.opencode/skills/workflow/security-error-handling/` | Security Agent错误处理 |

### Browser Skills

| Skill | 路径 | 功能 |
|-------|------|------|
| page-navigation | `.opencode/skills/browser/page-navigation/` | 页面导航方法论 |
| form-handling | `.opencode/skills/browser/form-handling/` | 表单处理方法论 |
| page-analysis | `.opencode/skills/browser/page-analysis/` | 页面分析方法论 |
| api-discovery | `.opencode/skills/browser/api-discovery/` | API发现方法论 |

---

## Agents Reference (Agent 清单)

| Agent | 模式 | 职责 | 调度者 |
|-------|------|------|--------|
| **webtest** | primary | 主控制器：规划、调度、事件处理、人机交互 | — |
| navigator | subagent | Chrome实例管理、页面导航、会话监控 | webtest |
| scout | subagent | 页面分析、链接发现、API端点识别 | webtest |
| form | subagent | 表单处理、登录执行、Cookie同步 | webtest |
| security | subagent | 越权测试、注入测试、认证上下文管理 | webtest |
| analyzer | subagent | 响应分析、漏洞判别、建议生成 | webtest |
| account_parser | subagent | 账号文档解析、权限矩阵提取 | webtest |

---

## Quick Start (快速开始)

### 启动测试会话

```
/webtest
目标URL: https://www.example.com
请开始规划并执行Web探索测试。
```

### 前置条件检查

```bash
# 1. MongoDB 运行中
docker ps | grep mongo

# 2. Burp Suite 已启动，代理监听 127.0.0.1:8080
curl http://localhost:8090/health

# 3. browser-use CLI 已安装
pip show browser-use
```

---

## Tool Priority Strategy (工具优先级策略)

### 主Agent委派规则

**重要**：webtest (Coordinator) 必须通过Task委派操作，禁止直接执行以下操作：

| 禁止操作 | 必须委派给 | 原因 |
|---------|-----------|------|
| 浏览器操作 | Navigator / Form | 多实例管理需要browser-use CLI |
| 账号解析 | AccountParser | 专业解析逻辑 |
| 页面分析 | Scout | 专业分析逻辑 |
| 安全测试 | Security | BurpBridge集成 |

### 工具使用优先级

```
Priority 1: Browser Automation
├─ browser-use CLI (Chrome CDP, 多实例管理) ← Navigator Agent 使用
└─ Playwright MCP (备用，更灵活) ← 仅特殊情况下使用

Priority 2: Security Testing
├─ BurpBridge MCP (请求同步、重放、认证上下文)
└─ MongoDB (历史记录、重放结果存储)

Priority 3: Data Management
├─ JSON Files (result/*.json)
└─ MongoDB (burpbridge collections)
```

### Playwright MCP 使用策略

```
Playwright MCP 使用规则:
├─ 主要使用者: Navigator Agent (备用方案)
├─ Coordinator: 禁止直接使用
└─ 特殊情况: 当browser-use不可用时，Navigator可选择使用Playwright
```

### 委派日志

所有委派行为记录在 `result/delegation_log.json`：

```json
{
  "delegations": [
    {
      "timestamp": "2026-04-22T10:00:00Z",
      "from_agent": "webtest",
      "to_agent": "navigator",
      "task_type": "create_instance",
      "status": "success"
    }
  ],
  "violations": []
}
```

---

## Tool Usage Principles (工具使用原则)

**Playwright MCP 性能优化**:
- 使用 `depth` 参数限制快照深度
- 使用 `filename` 参数保存大响应到文件
- 避免频繁完整快照

**BurpBridge MCP 调用格式**:
```javascript
// 所有工具需要 input 参数包装
burpbridge_check_burp_health(input: {})
burpbridge_list_paginated_http_history(input: { "host": "example.com" })
```

---

## Permissions / Execution Policy (权限策略)

```
权限策略:
├─ 只读 (默认): 源代码、配置、文档
├─ 可执行: browser-use, docker, curl
├─ 可写: result/*.json, config/accounts.json
└─ Agent调度: 仅 webtest 可调度子Agent

安全原则:
- 仅测试授权目标
- 越权测试通过请求重放，不影响原流程状态
- Cookie/Token 脱敏显示
```

---

## Version

- **Current**: 1.0
- **Updated**: 2026-04-22

### v1.0 (Initial Release)
- 7 个 Agent (webtest + 6 subagents)
- 17 个 Skills (5 类别)
- Browser-use CLI 集成
- BurpBridge MCP 集成
- 流程审批场景支持