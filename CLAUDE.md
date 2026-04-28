# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI-Agent Web渗透测试系统，采用 **Coordinator + Subagent + Skill** 三层架构。系统自主探索Web应用，发现表单和导航路径，并执行安全测试（越权检测、注入测试）。

## Agent 架构

### 概述

本系统采用 **Coordinator + Subagent + Skill** 三层架构：
- **Primary Agent**: Coordinator - 工作流调度、状态管理
- **Subagents**: Navigator, Form, Security, Analyzer, AccountParser
- **Skills**: 可复用方法论模块，位于 `.opencode/skills/`

**注意**: Scout 功能已合并到 Navigator，系统现为 **6 个 Agent**（1 Coordinator + 5 subagents）。

### 强制委派规则

Coordinator 必须使用 `@{agent_name}` 调用 subagent，禁止直接使用底层工具。

| 操作类型 | subagent | 要求 |
|---------|---------|---------|
| 浏览器操作 | @navigator | 使用browser-use cli + skill, chrome命令 |
| Chrome管理 | @navigator | 使用browser-use cli + skill, chrome命令 |
| 表单处理 | @form | 使用browser-use cli + skill |
| 安全测试 | @security | 使用mcp__burpbridge__* |
| 账号解析 | @account_parser | 禁止直接读取Excel |
| 结果分析 | @analyzer | — |

详见 **AGENTS.md** 的 MANDATORY DELEGATION RULES 章节。

### Agent 参考

- **AGENTS.md** - 完整 Agent 定义和工作流
- **.opencode/skills/SKILLS.md** - Skills 系统文档

## Skills 系统

Skills 是可复用的方法论模块，被 Agent 加载使用：

### 核心 Skills（所有 Agent 必加载）
- anti-hallucination: 防幻觉规则，数据真实性验证
- agent-contract: 输出格式标准，截断检测
- shared-browser-state: 浏览器状态共享机制

### 分类 Skills
- **Workflow**: state-machine, test-rounds, event-handling
- **Security**: idor-testing, injection-testing, vulnerability-rating
- **Browser**: page-navigation, form-handling, page-analysis, api-discovery, browser-recovery
- **Data**: mongodb-writer, progress-tracking, permission-matrix-parser

详见 **`.opencode/skills/SKILLS.md`**。

## Quick Start

### 启动测试会话

```
/coordinator
目标URL: https://www.example.com
请开始规划并执行Web探索测试。
```

### 前置条件检查

```bash
# 1. MongoDB 运行中
ps | Select-String mongo

# 2. BurpBridge MCP 已启动

# 3. browser-use CLI 已安装
browser-use doctor
```

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| **Agent框架** | Claude Code | 基于 Prompt 的角色扮演 |
| **浏览器自动化** | browser-use CLI + Skill | 支持多Chrome实例 |
| **安全测试** | BurpBridge MCP | BurpSuite插件，请求重放 |
| **数据存储** | MongoDB | BurpBridge依赖 |

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
│   └── accounts.json     # 账号配置
├── result/               # 测试输出 (不提交git)
│   ├── chrome_instances.json
│   ├── sessions.json
│   ├── events.json
│   ├── pages.json
│   ├── forms.json
│   ├── apis.json
│   ├── workflow_config.json
│   └── vulnerabilities.json
├── AGENTS.md             # Agent 权威参考
├── CLAUDE.md             # 本文件
└── README.md             # 项目概览
```

## Browser-use CLI 使用

### 调用方式

通过项目包装脚本调用 browser-use CLI：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

项目约束说明：

- `browser-use` 命令语义以官方 skill 为准
- 本项目通常由 Navigator 先启动带代理的受管 Chrome，再按项目方式接入 session
- `session_name` 是浏览器操作主键
- `--cdp-url` 仅用于 bootstrap/repair attach，不应写成所有命令的固定前缀
- Windows 下优先通过 `scripts/browser-use-utf8.ps1` 执行，以自动处理 attach 兼容和 UTF-8 输出

### 核心命令

| 命令 | 说明 |
|------|------|
| `browser-use open <url>` | 打开 URL |
| `browser-use close` | 关闭当前 session |
| `browser-use sessions` | 列出所有活跃 session |

### 代理配置

**重要**: browser-use CLI 必须通过启动 Chrome 时指定 `--proxy-server` 参数配置代理。

```powershell
# Windows
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
Start-Process $chromePath -ArgumentList @(
  "--proxy-server=http://127.0.0.1:8080",
  "--remote-debugging-port=9222",
  "--user-data-dir=C:\temp\chrome-{session_name}"
)
```

### 多实例管理

| Session 名 | CDP 端口 | User Data Dir | 用途 |
|-----------|---------|---------------|------|
| admin_001 | 9222 | C:\temp\chrome-admin-001 | 管理员账号 |
| user_001 | 9223 | C:\temp\chrome-user-001 | 普通用户账号 |

## BurpBridge MCP 使用

### 核心工具

| 工具名 | 用途 |
|--------|------|
| `mcp__burpbridge__check_burp_health` | 检查 BurpBridge 服务状态 |
| `mcp__burpbridge__sync_proxy_history_with_filters` | 同步代理历史到数据库 |
| `mcp__burpbridge__list_paginated_http_history` | 分页查询历史记录 |
| `mcp__burpbridge__get_http_request_detail` | 获取请求详情 |
| `mcp__burpbridge__configure_authentication_context` | 配置角色认证凭据 |
| `mcp__burpbridge__list_configured_roles` | 列出已配置角色 |
| `mcp__burpbridge__replay_http_request_as_role` | 重放请求 |
| `mcp__burpbridge__get_replay_scan_result` | 获取重放结果 |

### BurpBridge MCP 调用格式

**重要**: 所有 BurpBridge MCP 工具需要 `input` 参数包装。

#### 正确调用方式

```javascript
// 无参数工具
mcp__burpbridge__check_burp_health(input: {})
mcp__burpbridge__list_configured_roles(input: {})

// 带参数工具
mcp__burpbridge__list_paginated_http_history(input: {"host": "example.com", "page": 1})
mcp__burpbridge__replay_http_request_as_role(input: {"history_entry_id": "xxx", "target_role": "admin"})
```

### 使用场景

1. **越权测试（IDOR）**
   - 同步历史请求到 MongoDB
   - 配置不同角色的认证凭据
   - 重放请求并分析响应差异

2. **注入测试**
   - 通过重放请求在表单中注入payload
   - 观察响应判断是否存在漏洞

## 流程审批测试指南

### 测试策略

流程审批场景采用**请求重放测试**策略：
- 不实际执行审批操作
- 捕获请求后用其他角色的Cookie重放
- 分析响应判断是否存在越权漏洞
- 不影响原流程状态

### 关键文件

| 文件 | 用途 |
|------|------|
| `config/accounts.json` | 账号配置 |
| `result/workflow_config.json` | 流程审批节点配置 |
| `result/workflow_test_matrix.json` | 越权测试矩阵 |

详见 `.opencode/skills/security/workflow-authorization-testing/` Skill。

## 测试配置

默认参数：
- `max_depth`: 3（探索深度）
- `max_pages`: 50（最大访问页面数）
- `timeout_ms`: 30000
- `same_domain_only`: true

## 故障排查

### Burp 同步记录为空

**检查项**：
1. **Burp Suite Intercept 模式**: 确保 Proxy -> Intercept 是关闭状态
2. **Chrome 代理配置**: 检查 Chrome 启动时是否使用了 `--proxy-server` 参数
3. **BurpBridge REST API**: 运行 `curl http://localhost:8090/health` 确认服务正常
4. **MongoDB 服务**: 运行 `ps | Select-String mongo` 确认 MongoDB 正在运行
5. **Burp Suite Proxy History**: 在 Burp Suite 界面中查看 HTTP History 是否有记录

### MCP 连接失败

1. 运行 `/mcp` 查看 MCP 服务状态
2. 检查 `.mcp.json` 配置格式是否正确
3. 重启 Claude Code 会话重新加载 MCP 配置

### MongoDB 连接失败

1. 运行 `ps | Select-String mongo` 确认运行中
2. 查看mongoDB日志

## 验证清单

在开始测试前，请确认以下条件：

- [ ] MongoDB 运行中 (`ps | Select-String mongo`)
- [ ] Burp Suite 已启动，代理监听 127.0.0.1:8080
- [ ] BurpBridge MCP已加载
- [ ] browser-use CLI 已安装 (`browser-use doctor`)
- [ ] Chrome 浏览器已安装
- [ ] MCP 服务已重启加载最新配置

## 安全声明

本系统仅用于授权的安全测试和研究目的。测试任何目标前请确保获得适当授权。
