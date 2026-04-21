# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI-Agent Web渗透测试系统，采用层级式多Agent架构。系统自主探索Web应用，发现表单和导航路径，并执行安全测试（越权检测、注入测试）。当前测试目标为 www.baidu.com。

## Agent 架构

系统使用6个专业Agent，定义在 `agents/*.md` 中：

1. **Coordinator Agent** (`agents/coordinator.md`) - 主控制器，负责规划、调度、事件队列管理和人机交互代理
2. **Navigator Agent** (`agents/navigator.md`) - 处理页面导航、URL跟踪、多窗口管理、会话状态监控
3. **Scout Agent** (`agents/scout.md`) - 分析页面结构，发现链接、表单和API端点
4. **Form Agent** (`agents/form.md`) - 识别、填写和提交Web表单，执行登录操作，验证码检测
5. **Security Agent** (`agents/security.md`) - 执行安全测试（越权、注入），并行监控模式
6. **Analyzer Agent** (`agents/analyzer.md`) - 分析重放结果，判断漏洞，生成探索建议

### 架构图

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Coordinator Agent                                 │
│                   (主控制器 + 事件调度中心)                                │
└───────────────┬──────────────────────────┬─────────────────────────────┘
                │                          │
    ┌───────────┴───────────┐    ┌────────┴────────────┐
    │   探索流水线 (串行)    │    │  安全测试 (并行)     │
    │  Navigator→Scout→Form │    │  Security + Analyzer │
    └───────────────────────┘    └──────────────────────┘
                │                          │
                └──────────┬───────────────┘
                           ↓
    ┌─────────────────────────────────────────────────────────────────────┐
    │  共享状态层: chrome_instances.json | sessions.json | events.json   │
    └─────────────────────────────────────────────────────────────────────┘
```

### 启动测试会话

```
你现在扮演Coordinator Agent角色。
请阅读 agents/coordinator.md 了解你的职责。
目标URL: https://www.baidu.com
请开始规划并执行Web探索测试。
```

## 技术栈

- **Agent框架**: Claude Code（基于Prompt的角色扮演，非注册Agent）
- **浏览器自动化**:
  - **主要**: browser-use CLI + Skill（通过 Chrome CDP 连接，支持多实例管理）
  - **备用**: Playwright MCP（特殊情况使用，更灵活）
- **安全测试**: BurpBridge MCP (BurpSuite 插件)
- **数据存储**: 基于文件的JSON存储，位于 `result/`

## Browser-use CLI 使用

### 调用方式

通过 `/browser-use` Skill 调用 browser-use CLI：

```
/browser-use --session {session_name} --cdp-url {cdp_url} open {url}
```

或直接通过 Bash 工具执行 CLI 命令：

```bash
browser-use --session admin_001 --cdp-url http://localhost:9222 open https://example.com
```

### 核心命令

| 命令 | 说明 |
|------|------|
| `browser-use open <url>` | 打开 URL |
| `browser-use close` | 关闭当前 session |
| `browser-use sessions` | 列出所有活跃 session |
| `browser-use --session <name> ...` | 指定 session 名称 |
| `browser-use --cdp-url <url> ...` | 连接到指定 CDP 端点 |

### 代理配置

**重要**: browser-use CLI 必须通过启动 Chrome 时指定 `--proxy-server` 参数配置代理。

#### 正确配置

1. **手动启动带代理的 Chrome**
   ```powershell
   # Windows
   $chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
   Start-Process $chromePath -ArgumentList @(
     "--proxy-server=http://127.0.0.1:8080",
     "--remote-debugging-port=9222",
     "--user-data-dir=C:\temp\chrome-{session_name}"
   )
   ```

2. **通过 browser-use 连接**
   ```bash
   browser-use --session {session_name} --cdp-url http://localhost:9222 open https://example.com
   ```

#### 多实例管理

| Session 名 | CDP 端口 | User Data Dir | 用途 |
|-----------|---------|---------------|------|
| admin_001 | 9222 | C:\temp\chrome-admin-001 | 管理员账号 |
| user_001 | 9223 | C:\temp\chrome-user-001 | 普通用户账号 |

#### 关闭流程

**必须成对关闭**：
1. 先关闭 browser-use session: `browser-use --session {name} close`
2. 再关闭对应的 Chrome（通过 PID）: `taskkill /PID {pid} /F`

**禁止**：不要使用 `taskkill /F /IM chrome.exe`，这会关闭所有 Chrome 实例。

### Chrome 路径配置

Agent 在运行时自动检测 Chrome 路径，优先级：
1. 环境变量 `CHROME_PATH`
2. Windows 默认安装位置
3. 用户目录下的 Chrome

也可以在 `config/accounts.json` 中为每个账号预定义 Chrome 配置。

## Playwright MCP 使用（备用）

### 核心工具
- `mcp__playwright__browser_navigate` - 导航到URL
- `mcp__playwright__browser_snapshot` - 获取可访问性树（主要分析方法）
- `mcp__playwright__browser_click` - 点击元素
- `mcp__playwright__browser_type` - 向输入框输入文本
- `mcp__playwright__browser_fill_form` - 填写多个表单字段
- `mcp__playwright__browser_network_requests` - 获取网络请求列表（API发现）
- `mcp__playwright__browser_tabs` - 多标签页管理

### 性能优化

Playwright MCP响应可能超过50k tokens，务必优化：

1. **使用 `depth` 参数**: `browser_snapshot({ depth: 2 })` 进行浅层分析
2. **使用 `filename` 参数**: 将大响应保存到文件，而非返回到上下文
3. **避免完整快照**: 仅在需要交互时请求详细数据

### 代理配置

**重要**: Playwright MCP 必须通过 `--proxy-server` 命令行参数配置代理，环境变量方式对浏览器进程无效。

#### 正确配置（.mcp.json）

```json
"playwright": {
  "command": "npx",
  "args": [
    "@playwright/mcp@latest",
    "--proxy-server", "http://127.0.0.1:8080"
  ]
}
```

#### 错误配置（环境变量不生效）

```json
// ❌ 这种配置对浏览器无效！
"playwright": {
  "command": "npx",
  "args": ["@playwright/mcp@latest"],
  "env": {
    "HTTP_PROXY": "http://127.0.0.1:8080",
    "HTTPS_PROXY": "http://127.0.0.1:8080"
  }
}
```

**前置条件**:
- 在 Burp Suite 中安装 CA 证书到系统信任列表，否则 HTTPS 请求会失败
- 建议关闭 Burp 的 "Intercept" 模式，避免请求被拦截
- 修改 `.mcp.json` 后需要重启 MCP 服务才能生效

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

### BurpBridge MCP 调用格式

**重要**: 所有 BurpBridge MCP 工具需要 `input` 参数包装，即使是无参数的工具也需要传入空对象 `{}`。

#### 正确调用方式

```
// 无参数工具
mcp__burpbridge__check_burp_health(input: {})
mcp__burpbridge__list_configured_roles(input: {})
mcp__burpbridge__get_auto_sync_status(input: {})

// 带参数工具
mcp__burpbridge__list_paginated_http_history(input: {"host": "example.com", "page": 1})
mcp__burpbridge__configure_auto_sync(input: {"enabled": true, "host": "www.example.com"})
mcp__burpbridge__replay_http_request_as_role(input: {"history_entry_id": "xxx", "target_role": "admin"})
```

#### 错误调用方式

```
mcp__burpbridge__check_burp_health()  // ❌ 缺少 input 参数
mcp__burpbridge__list_paginated_http_history({"host": "example.com"})  // ❌ 缺少 input 包装
```

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
config/               # 配置文件
  accounts.json       # 账号配置（含 Chrome 配置）
memory/               # 模板文件（提交git）
  sessions/           # 会话模板
  discoveries/        # 空模板JSON文件
    vulnerabilities.json  # 漏洞发现模板
result/               # 测试输出（不提交git）
  chrome_instances.json # Chrome 实例注册表
  sessions.json       # 会话状态（含 browser-use session）
  pages.json          # 发现的页面
  forms.json          # 发现的表单
  links.json          # 发现的链接
  apis.json           # 发现的API端点
  events.json         # 事件队列
  windows.json        # 窗口注册表
  vulnerabilities.json # 发现的漏洞
  *_report_*.md       # 测试报告
.tmp/                 # 临时文件（不提交git）
  snapshots/          # 页面快照 (Scout Agent)
  logs/               # 调试日志 (各 Agent)
  cache/              # 缓存数据 (各 Agent)
  debug/              # 其他临时文件
reports/              # 报告模板（提交git）
```

## 临时文件管理

所有 Agent 在工作中产生的临时文件必须存放在 `.tmp/` 目录下，确保项目文档不受干扰。

### 目录用途

| 目录 | 用途 | 使用 Agent |
|------|------|-----------|
| `.tmp/snapshots/` | 页面快照、DOM 树 | Scout |
| `.tmp/logs/` | 调试日志、运行日志 | 所有 Agent |
| `.tmp/cache/` | 缓存数据、中间结果 | Form, Security |
| `.tmp/debug/` | 其他临时文件 | Analyzer, 其他 |

### 命名规范

使用 `{agent}_{timestamp}_{purpose}.{ext}` 格式：
- 例：`scout_20260421_page1.yaml`, `navigator_20260421_debug.log`

### 使用示例

```javascript
// Scout Agent 保存页面快照
browser_snapshot({ filename: ".tmp/snapshots/scout_20260421_page1.yaml" })

// Navigator Agent 记录调试日志
write_file(".tmp/logs/navigator_20260421_debug.log", log_content)
```

### 清理机制

测试会话结束时，清理 `.tmp/` 目录下的临时文件（保留目录结构）。

## 关键特性

### 多 Chrome 实例管理
- 每个账号独立的 Chrome 实例
- 独立的 CDP 端口和用户数据目录
- browser-use session 与 Chrome 实例成对管理
- 成对关闭机制，避免误关其他实例

### 登录态保持
- Cookie管理和自动重新登录
- 验证码检测和人机交互
- 会话过期检测和处理

### API发现
- 分析网络请求，发现隐藏API
- API模式识别（如 /api/users/{id}）
- 敏感数据检测

### 并行架构
- Security Agent与探索Agent并行运行
- 事件队列驱动的Agent通信
- 实时漏洞发现

### 事件驱动通信
- CAPTCHA_DETECTED: 验证码检测
- SESSION_EXPIRED: 会话过期
- LOGIN_FAILED: 登录失败
- EXPLORATION_SUGGESTION: 探索建议
- VULNERABILITY_FOUND: 漏洞发现
- API_DISCOVERED: API发现

## 流程审批测试指南

### 概述

流程审批场景是 Web 应用中常见的安全测试场景，具有以下特点：
- 审批操作不可逆
- 需要多用户按顺序操作
- 传统越权测试会改变流程状态

### 测试策略：请求重放测试

**核心思路**：不实际执行审批操作，而是捕获请求并用其他角色的认证信息重放。

```
正常流程：
1. 账号A 执行审批操作
2. 请求通过 Burp 代理被捕获
3. BurpBridge 记录到 MongoDB

越权测试（不影响原流程）：
4. Security Agent 获取审批请求
5. 使用其他角色的 Cookie 重放
6. 分析响应判断是否存在越权
7. 原流程状态不变
```

### 配置文件

流程审批测试使用 `result/workflow_config.json`：

```json
{
  "workflows": [{
    "workflow_id": "approval_flow",
    "nodes": [{
      "node_id": "submit",
      "node_name": "提交审批",
      "required_roles": ["经理"],
      "api_endpoint": "/api/workflow/submit",
      "discovered": true
    }]
  }],
  "test_results": {
    "total_tests": 0,
    "vulnerabilities_found": []
  }
}
```

### 测试流程

#### 1. 权限文档解析

使用 AccountParser Agent 解析权限文档（如 Excel）：

```bash
# 解析权限矩阵文档
AccountParser Agent 解析 Excel 文件：
- Sheet "测试账号"：角色-账号-密码对应
- Sheet "权限-XXX"：功能-角色权限矩阵（√/×）
```

输出：
- `config/accounts.json`：标准化账号配置
- `result/workflow_config.json`：流程审批节点配置

#### 2. API 自动发现

在正常审批操作时自动发现 API：

```
Navigator Agent → 按流程操作
Form Agent → 执行审批
Scout Agent → 监控网络请求 → 发现 API
Security Agent → 记录到 workflow_config.json
```

#### 3. 批量越权测试

```javascript
// Security Agent 执行越权测试
for (const node of workflowConfig.nodes) {
  // 获取该节点的请求
  const request = await getApprovalRequest(node.api_endpoint);
  
  // 测试所有角色
  for (const role of configuredRoles) {
    await replayRequest(request.id, role);
  }
}
```

#### 4. 结果分析

| 场景 | 预期 | 判定 |
|------|------|------|
| 有权限角色 | 200 + 成功 | 正常 |
| 无权限角色 | 401/403 | 安全 |
| 无权限角色 | 200 + 成功 | **越权漏洞** |

### 关键文件

| 文件 | 用途 |
|------|------|
| `agents/account_parser.md` | 权限文档解析规则 |
| `agents/security.md` | 流程审批越权测试模式 |
| `result/workflow_config.json` | 流程审批节点配置 |
| `result/workflow_test_matrix.json` | 越权测试矩阵 |

### 最佳实践

1. **先解析权限文档**：明确每个节点需要的角色权限
2. **配置所有角色**：为每个角色配置认证凭据
3. **按流程操作**：正常执行审批流程，让 API 自动发现
4. **批量测试**：对每个审批节点测试所有角色
5. **不影响原流程**：越权测试只是请求重放，不会改变流程状态

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

## 故障排查

### Burp 同步记录为空

当 `mcp__burpbridge__list_paginated_http_history` 返回空列表时：

**检查项**：
1. **Burp Suite Intercept 模式**: 确保 Proxy -> Intercept 是关闭状态（"Intercept is off"）
2. **Playwright 代理配置**: 检查 `.mcp.json` 是否使用了 `--proxy-server` 参数
3. **BurpBridge REST API**: 运行 `curl http://localhost:8090/health` 确认服务正常
4. **MongoDB 服务**: 运行 `docker ps | grep mongo` 确认 MongoDB 正在运行
5. **Burp Suite Proxy History**: 在 Burp Suite 界面中查看 HTTP History 是否有记录

**常见原因**：
- Playwright 浏览器未通过代理（环境变量配置无效）
- MCP 服务未重启（修改配置后需要重启）
- BurpBridge 插件同步功能存在 Bug

### MCP 连接失败

**检查项**：
1. 运行 `/mcp` 查看 MCP 服务状态
2. 检查 `.mcp.json` 配置格式是否正确（使用 JSON 验证器）
3. 重启 Claude Code 会话重新加载 MCP 配置

### Playwright 浏览器无法启动

**检查项**：
1. 运行 `npx playwright install` 安装浏览器
2. 检查是否有防火墙阻止
3. 查看错误日志确定具体原因

### MongoDB 连接失败

**检查项**：
1. 运行 `docker ps` 确认容器运行中
2. 运行 `docker logs mongodb` 查看日志
3. 检查端口 27017 是否被占用

## 验证清单

在开始测试前，请确认以下条件：

- [ ] MongoDB 容器运行中 (`docker ps | grep mongo`)
- [ ] Burp Suite 已启动，代理监听 127.0.0.1:8080
- [ ] BurpBridge 插件已加载，REST API 正常 (`curl http://localhost:8090/health`)
- [ ] browser-use CLI 已安装 (`pip install browser-use`)
- [ ] Chrome 浏览器已安装
- [ ] MCP 服务已重启加载最新配置
