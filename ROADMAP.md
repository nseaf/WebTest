# Web渗透测试系统 - 功能规划

## 当前版本: v0.3

### 已实现功能

#### 核心Agent
- [x] Coordinator Agent - 任务规划、事件队列管理、并行调度
- [x] Navigator Agent - 页面导航、多窗口管理、会话状态监控
- [x] Scout Agent - 页面分析、元素识别、API发现
- [x] Form Agent - 表单处理、登录执行、验证码检测
- [x] Security Agent - 越权测试、注入测试、并行监控模式
- [x] Analyzer Agent - 响应分析、漏洞判定、建议生成

#### 架构特性
- [x] 并行架构 - Security Agent与探索流水线并行运行
- [x] 事件驱动通信 - 7种事件类型，Agent间异步通信
- [x] 多窗口支持 - 多标签页管理、窗口注册表
- [x] 登录态保持 - Cookie管理、会话过期检测、自动重新登录
- [x] 验证码处理 - 检测验证码并触发人机交互流程
- [x] 共享浏览器状态 - 所有Agent共享同一Chrome实例，通过CDP连接访问
- [x] 任务接口标准化 - 所有子Agent统一任务输入输出格式
- [x] 职责边界清晰化 - Coordinator专注调度，子Agent负责实现细节

#### 数据存储
- [x] 会话状态管理 (sessions.json)
- [x] 窗口注册表 (windows.json)
- [x] 事件队列 (events.json)
- [x] API发现记录 (apis.json)
- [x] 漏洞记录 (vulnerabilities.json)
- [x] 发现记录存储 (pages.json, forms.json, links.json)

#### 性能优化
- [x] 使用 `depth` 参数控制快照深度
- [x] 使用 `filename` 参数保存大响应到文件

---

## 待实现功能

### 优先级 P0 - 核心功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 深度探索 | 支持配置探索深度和页面数量限制 | ✅ 已实现 |
| 去重机制 | URL规范化去重，避免重复访问 | ✅ 已实现 |
| 错误处理 | 导航失败、表单提交失败的处理 | ✅ 已实现 |

### 优先级 P1 - 增强功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 登录态保持 | Cookie管理，保持登录状态 | ✅ 已实现 |
| API发现 | 分析网络请求，发现隐藏API | ✅ 已实现 |
| 安全检测 | XSS/SQL注入/CSRF等基础检测 | ✅ 已实现 |
| 多标签页处理 | 多窗口管理、越权测试支持 | ✅ 已实现 |
| 验证码处理 | 检测并触发人机交互 | ✅ 已实现 |

### 优先级 P2 - 辅助功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 截图功能 | 页面/元素截图存档 | 暂不启用 |
| 代理支持 | 支持HTTP/SOCKS代理 | ✅ Burp代理已配置 |
| 移动端模拟 | 模拟移动设备访问 | 待实现 |
| 并行探索 | 多页面并行探索 | 待实现 |

---

## 架构设计

### 共享浏览器状态机制

所有子Agent共享同一个Chrome实例和页面状态：

```
┌─────────────────────────────────────────────────────────────────┐
│                     Chrome 浏览器实例                             │
│                    (Navigator 创建并管理)                         │
│                                                                 │
│   当前页面状态: URL, DOM, Cookie                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ CDP 连接 (记录在 sessions.json)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   Navigator   │    │    Scout      │    │     Form      │
│   (导航)      │    │   (分析)      │    │   (表单)      │
└───────────────┘    └───────────────┘    └───────────────┘
```

**关键点**：
- Navigator 导航后，页面已加载在 Chrome 中
- Scout 和 Form 通过相同的 CDP 连接访问当前页面
- **无需重新导航**，直接操作当前页面
- 通信通过 `sessions.json` 共享连接信息

### Agent职责边界

| Agent | 能力 | 边界 |
|-------|------|------|
| Coordinator | 调度、协调、决策、监控 | 不执行具体实现细节 |
| Navigator | Chrome实例管理、页面导航、会话监控 | 不处理页面内容分析、不填写表单 |
| Scout | 页面分析、链接发现、API发现 | 不导航、不提交表单、不执行安全测试 |
| Form | 表单处理、登录执行、Cookie同步 | 不导航、不分析页面结构、不执行安全测试 |
| Security | 越权测试、注入测试、认证上下文管理 | 不操作浏览器、不分析页面结构 |
| Analyzer | 响应分析、漏洞判别、建议生成 | 不执行任何操作、只分析数据 |

### 并行架构

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
    │  共享状态层: events.json | sessions.json | windows.json            │
    └─────────────────────────────────────────────────────────────────────┘
```

### 事件驱动通信

| 事件类型 | 来源 | 需要用户操作 |
|----------|------|--------------|
| CAPTCHA_DETECTED | Form/Navigator | ✅ 是 |
| SESSION_EXPIRED | Navigator/Security | ❌ 否 |
| LOGIN_FAILED | Form | ❌ 否 |
| EXPLORATION_SUGGESTION | Security/Analyzer | ❌ 否 |
| VULNERABILITY_FOUND | Security | ❌ 否 |
| API_DISCOVERED | Scout | ❌ 否 |
| FORM_SUBMISSION_ERROR | Form | ❌ 否 |

### 数据存储结构

```
WebTest/
├── agents/                 # Agent定义 (提交git)
│   ├── coordinator.md
│   ├── navigator.md
│   ├── scout.md
│   ├── form.md
│   ├── security.md
│   ├── analyzer.md
│   └── account_parser.md   # 账号解析Agent
├── config/                 # 配置文件 (提交git)
│   └── accounts.json       # 账号配置模板
├── memory/                 # 模板文件 (提交git)
│   ├── sessions/
│   │   └── session_template.json
│   └── discoveries/
│       └── vulnerabilities.json
├── reports/                # 报告模板 (提交git)
│   └── report_template.md
├── result/                 # 测试结果 (不提交git)
│   ├── events.json         # 事件队列
│   ├── windows.json        # 窗口注册表
│   ├── sessions.json       # 会话状态
│   ├── apis.json           # API发现
│   ├── pages.json          # 发现的页面
│   ├── forms.json          # 发现的表单
│   ├── links.json          # 发现的链接
│   ├── vulnerabilities.json # 发现的漏洞
│   ├── workflow_config.json # 流程审批配置
│   └── xxx_report.md       # 测试报告
└── ROADMAP.md              # 功能规划
```

---

## 更新日志

### 2026-04-21 - v0.3 Agent协同优化
- **Coordinator Agent 大幅简化**
  - 删除Chrome启动命令、端口分配规则、PID获取方法等实现细节
  - 删除MongoDB MCP调用代码示例
  - 删除认证上下文同步流程图和代码
  - 删除流程审批调度代码实现
  - 保留并强化核心调度逻辑和事件处理决策
- **新增"共享浏览器状态机制"文档**
  - 明确所有Agent共享同一Chrome实例的设计
  - 说明Navigator创建实例，其他Agent通过CDP连接
  - 避免页面重复加载，提升效率
- **子Agent职责增强**
  - Navigator: 明确"成对关闭"原则（browser-use session + Chrome进程）
  - Form: 明确登录后Cookie同步到BurpBridge职责
  - Security: 明确自主管理自动同步配置职责
- **任务接口标准化**
  - 所有子Agent统一添加"任务接口定义"部分
  - 标准化任务输入格式：`{task, parameters}`
  - 标准化返回格式：`{status, report, events_created, next_suggestions}`
- **新增AccountParser Agent文档**
  - 支持解析多种格式的账号信息文档
  - 支持合并单元格处理
  - 生成标准accounts.json和workflow_config.json

### 2026-04-15 - v0.2 架构升级
- 新增 Analyzer Agent，负责响应分析和漏洞判定
- 重构为并行架构：Security Agent与探索流水线并行运行
- 新增事件驱动通信机制，7种事件类型
- 新增多窗口管理，支持多账号越权测试
- 新增登录态保持功能：Cookie管理、会话过期检测、自动重新登录
- 新增验证码检测和人机交互流程
- 新增API发现功能：网络请求分析、API模式识别
- 新增数据文件：events.json, windows.json, sessions.json, apis.json
- 更新所有Agent定义文件

### 2026-04-12 - v0.1 初始版本
- 初始版本发布
- 完成百度探索测试
- 移除截图功能（暂不启用）
- 添加性能优化策略文档
- 重构数据存储结构：测试数据移至 `result/` 目录
