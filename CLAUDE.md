# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI-Agent Web渗透测试系统，采用层级式多Agent架构。系统自主探索Web应用，发现表单和导航路径，并执行安全测试（越权检测、注入测试）。当前测试目标为 www.baidu.com。

## Agent 架构

系统使用5个专业Agent，定义在 `agents/*.md` 中：

1. **Coordinator Agent** (`agents/coordinator.md`) - 主控制器，负责规划、调度和监控测试
2. **Navigator Agent** (`agents/navigator.md`) - 处理页面导航和URL跟踪
3. **Scout Agent** (`agents/scout.md`) - 分析页面结构，发现链接和表单
4. **Form Agent** (`agents/form.md`) - 识别、填写和提交Web表单
5. **Security Agent** (`agents/security.md`) - 执行安全测试（越权、注入）

### 启动测试会话

```
你现在扮演Coordinator Agent角色。
请阅读 agents/coordinator.md 了解你的职责。
目标URL: https://www.baidu.com
请开始规划并执行Web探索测试。
```

## 技术栈

- **Agent框架**: Claude Code（基于Prompt的角色扮演，非注册Agent）
- **浏览器自动化**: Playwright MCP (`@playwright/mcp@latest`)
- **安全测试**: BurpBridge MCP (BurpSuite 插件)
- **数据存储**: 基于文件的JSON存储，位于 `result/`

## Playwright MCP 使用

### 核心工具
- `mcp__playwright__browser_navigate` - 导航到URL
- `mcp__playwright__browser_snapshot` - 获取可访问性树（主要分析方法）
- `mcp__playwright__browser_click` - 点击元素
- `mcp__playwright__browser_type` - 向输入框输入文本
- `mcp__playwright__browser_fill_form` - 填写多个表单字段

### 性能优化

Playwright MCP响应可能超过50k tokens，务必优化：

1. **使用 `depth` 参数**: `browser_snapshot({ depth: 2 })` 进行浅层分析
2. **使用 `filename` 参数**: 将大响应保存到文件，而非返回到上下文
3. **避免完整快照**: 仅在需要交互时请求详细数据

### 代理配置

Playwright 浏览器配置使用 Burp Suite 代理（127.0.0.1:8080），确保所有 HTTP 流量被 Burp 捕获：

```json
// .mcp.json 中的代理配置
"env": {
  "HTTP_PROXY": "http://127.0.0.1:8080",
  "HTTPS_PROXY": "http://127.0.0.1:8080"
}
```

**注意**:
- 需要在 Burp Suite 中安装 CA 证书到系统信任列表，否则 HTTPS 请求会失败
- 建议关闭 Burp 的 "Intercept" 模式，避免请求被拦截

## BurpBridge MCP 使用

BurpBridge 是一个 Burp Suite 插件，通过 MCP 暴露 Burp 的能力给 AI Agent。

### 前置条件

1. **启动 MongoDB**
   ```bash
   docker run -d --name mongodb -p 27017:27017 mongo:latest
   ```

2. **构建并加载 BurpBridge 插件**
   ```bash
   cd /Users/fizz/projects/BurpBridge
   mvn clean package
   ```
   然后在 Burp Suite 中加载 `target/BurpBridge-1.0-SNAPSHOT.jar`

3. **启动 Burp Suite**
   - 确保代理监听 127.0.0.1:8080
   - BurpBridge REST API 默认在 http://localhost:8090

### 核心工具

| 工具名 | 用途 |
|--------|------|
| `mcp__burpbridge__check_burp_health` | 检查 BurpBridge 服务状态 |
| `mcp__burpbridge__sync_proxy_history_with_filters` | 同步代理历史到数据库 |
| `mcp__burpbridge__list_paginated_http_history` | 分页查询历史记录 |
| `mcp__burpbridge__get_http_request_detail` | 获取请求详情 |
| `mcp__burpbridge__configure_authentication_context` | 配置角色认证凭据 |
| `mcp__burpbridge__list_configured_roles` | 列出已配置角色 |
| `mcp__burpbridge__delete_authentication_context` | 删除角色配置 |
| `mcp__burpbridge__replay_http_request_as_role` | 重放请求 |
| `mcp__burpbridge__get_replay_scan_result` | 获取重放结果 |

### 使用场景

1. **越权测试（IDOR）**
   - 同步历史请求到 MongoDB
   - 配置不同角色的认证凭据
   - 重放请求并分析响应差异

2. **注入测试**
   - 通过 Playwright 在表单中提交 payload
   - 观察响应判断是否存在漏洞

## 目录结构

```
agents/               # Agent定义文件（提交git）
memory/               # 模板文件（提交git）
  sessions/           # 会话模板
  discoveries/        # 空模板JSON文件
    vulnerabilities.json  # 漏洞发现模板
result/               # 测试输出（不提交git）
  session_*.json      # 会话状态
  pages.json          # 发现的页面
  forms.json          # 发现的表单
  links.json          # 发现的链接
  vulnerabilities.json # 发现的漏洞
  *_report_*.md       # 测试报告
reports/              # 报告模板（提交git）
```

## 测试配置

默认参数（在 session_template.json 中）：
- `max_depth`: 3（探索深度）
- `max_pages`: 50（最大访问页面数）
- `timeout_ms`: 30000
- `same_domain_only`: true

## Agent 实现说明

本项目使用**基于Prompt的Agent**（Claude阅读`.md`文件并扮演角色），而非注册的系统Agent。所有Agent共享相同的上下文和工具权限。详见DESIGN.md中两种实现方式的说明及未来迁移路径。

## 安全声明

本系统仅用于授权的安全测试和研究目的。测试任何目标前请确保获得适当授权。
