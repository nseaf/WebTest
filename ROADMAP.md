# Web渗透测试系统 - 功能规划

## 当前版本: v0.2

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
│   └── analyzer.md
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
│   └── xxx_report.md       # 测试报告
└── ROADMAP.md              # 功能规划
```

---

## 更新日志

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
