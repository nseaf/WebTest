# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI-Agent Web渗透测试系统，采用层级式多Agent架构。系统自主探索Web应用，发现表单和导航路径，并进行基础安全测试。当前测试目标为 www.baidu.com。

## Agent 架构

系统使用4个专业Agent，定义在 `agents/*.md` 中：

1. **Coordinator Agent** (`agents/coordinator.md`) - 主控制器，负责规划、调度和监控测试
2. **Navigator Agent** (`agents/navigator.md`) - 处理页面导航和URL跟踪
3. **Scout Agent** (`agents/scout.md`) - 分析页面结构，发现链接和表单
4. **Form Agent** (`agents/form.md`) - 识别、填写和提交Web表单

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

## 目录结构

```
agents/               # Agent定义文件（提交git）
memory/               # 模板文件（提交git）
  sessions/           # 会话模板
  discoveries/        # 空模板JSON文件
result/               # 测试输出（不提交git）
  session_*.json      # 会话状态
  pages.json          # 发现的页面
  forms.json          # 发现的表单
  links.json          # 发现的链接
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
