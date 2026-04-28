# AI-Agent Web渗透测试系统

## 项目概述

本项目是一个基于 Claude Code 的多Agent Web渗透测试系统。通过 **Coordinator + Subagent + Skill** 三层架构，利用AI技术模拟人工前端Web测试，实现自主探索、安全测试和漏洞发现。

## 系统架构

### 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│                 Coordinator (Primary Agent)                 │
│         工作流调度 · 状态管理 · 强制委派                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ @{agent_name} 委派
        ┌────────┬─────────┼─────────┬────────┐
        ▼        ▼         ▼         ▼        ▼
   Navigator   Form   Security  Analyzer  AccountParser
   (导航+分析)  (表单)   (安全)    (分析)      (解析)
        │
        └──────────────────────────────────────┘
                           │
              共享状态: result/*.json + MongoDB
```

**注意**: Navigator 已合并 Scout 功能，系统现为 **6 个 Agent**（1 Coordinator + 5 subagents）。

### Agent 清单

| Agent | 模式 | 角色 |
|-------|------|------|
| **Coordinator** | primary | 主控制器，工作流调度、状态管理、异常处理 |
| Navigator | subagent | 页面导航、页面分析、API发现与 Cookie 同步（已合并Scout）|
| Form | subagent | 表单识别、登录执行、验证码处理 |
| Security | subagent | IDOR测试、注入测试、BurpBridge集成 |
| Analyzer | subagent | 重放结果分析、漏洞判定、严重性评级 |
| AccountParser | subagent | 账号文档解析、权限矩阵提取、流程配置生成 |

### 强制委派规则

Coordinator 必须通过 `@{agent_name}` 调用 subagent，禁止直接使用底层工具。

| 操作类型 | 委派目标 | 要求 |
|---------|---------|---------|
| 浏览器操作 | @navigator | 使用browser-use cli + skill, chrome命令 |
| 表单处理 | @form | 使用browser-use cli + skill |
| 安全测试 | @security | mcp__burpbridge__* |
| 账号解析 | @account_parser | 禁止直接读取excel |
| 结果分析 | @analyzer | — |

详见 **AGENTS.md** 的 MANDATORY DELEGATION RULES 章节。

### Skills 系统

Skills 是可复用的方法论模块，位于 `.opencode/skills/`：

- **Core**: anti-hallucination, agent-contract, shared-browser-state
- **Workflow**: state-machine, test-rounds, event-handling
- **Security**: idor-testing, injection-testing, vulnerability-rating
- **Browser**: page-navigation, form-handling, page-analysis, api-discovery, browser-recovery
- **Data**: mongodb-writer, progress-tracking, permission-matrix-parser

详见 **`.opencode/skills/SKILLS.md`**。

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| **Agent框架** | Claude Code | 基于 Prompt 的角色扮演 |
| **浏览器自动化** | browser-use CLI + wrapper | 支持多Chrome实例、会话复用与Windows下统一输出 |
| **安全测试** | BurpBridge MCP | BurpSuite插件，请求重放 |
| **数据存储** | MongoDB | BurpBridge依赖 |

## 关键特性

- **多Chrome实例管理** - 每个账号独立Chrome实例和CDP端口，首次 attach 后统一复用 `session_name`
- **登录态保持** - Cookie管理、验证码检测、会话过期处理
- **智能标签页处理** - 点击后自动执行 tab 对账与切换验证
- **API发现** - 网络请求分析、API模式识别、敏感数据检测
- **并行架构** - Security Agent与探索Agent并行运行
- **流程审批测试** - 权限文档解析、请求重放越权测试（不影响原流程）

## 目录结构

```
WebTest/
├── .opencode/            # Agent 和 Skill 定义
│   ├── agents/           # Agent 定义文件
│   │   ├── coordinator.md
│   │   ├── navigator.md
│   │   ├── form.md
│   │   ├── security.md
│   │   ├── analyzer.md
│   │   └── account_parser.md
│   └── skills/           # Skills 知识库
│       ├── core/         # 核心 Skills
│       ├── workflow/     # 工作流 Skills
│       ├── browser/      # 浏览器 Skills
│       ├── security/     # 安全测试 Skills
│       └── data/         # 数据处理 Skills
├── config/               # 配置文件
├── result/               # 测试输出 (不提交git)
├── AGENTS.md             # Agent 权威参考
├── CLAUDE.md             # Claude Code 项目指导
└── README.md             # 本文件
```

## 快速开始

### 前置条件

```bash
# 启动 MongoDB
ps | Select-String mongo

# BurpBridge MCP 已连接

# browser-use CLI 可用
browser-use doctor
```

### 启动测试

```
/coordinator
目标URL: https://www.example.com
请开始规划并执行Web探索测试。
```

## 文档链接

| 文档 | 用途 |
|------|------|
| **AGENTS.md** | 完整 Agent 定义和工作流 |
| **.opencode/skills/SKILLS.md** | Skills 系统文档 |
| **CLAUDE.md** | Claude Code 项目指导 |

## 事件类型

| 事件类型 | 说明 |
|----------|------|
| `CAPTCHA_DETECTED` | 验证码检测 |
| `SESSION_EXPIRED` | 会话过期 |
| `LOGIN_FAILED` | 登录失败 |
| `EXPLORATION_SUGGESTION` | 探索建议 |
| `VULNERABILITY_FOUND` | 漏洞发现 |
| `API_DISCOVERED` | API发现 |
| `WORKFLOW_NODE_COMPLETED` | 审批节点完成 |

## 故障排查

### Burp 同步记录为空

1. 确保 Burp Suite Intercept 模式已关闭
2. 检查 chrome实例 是否配置了 `--proxy-server` 参数
3. 确认 BurpBridge MCP 已连接正常
4. 确认 MongoDB 运行中

### MCP 连接失败

1. 运行 `/mcp` 查看 MCP 服务状态
2. 检查 `.mcp.json` 配置格式
3. 重启 Claude Code 会话重新加载配置

## 安全声明

本项目仅用于授权的安全测试和研究目的。请确保在合法授权范围内使用。
