# AI-Agent Web渗透测试系统

## 项目概述

本项目是一个基于Claude Code的多Agent Web渗透测试系统。通过层级式多Agent架构，利用AI技术模拟人工前端Web测试，实现自主探索、安全测试和漏洞发现。

## 系统架构

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

### Agent职责

| Agent | 职责 |
|-------|------|
| **Coordinator Agent** | 任务规划、事件队列管理、人机交互代理、并行调度 |
| **Navigator Agent** | 页面导航、链接跟踪、多窗口管理、会话状态监控 |
| **Scout Agent** | 页面分析、元素识别、链接发现、API发现 |
| **Form Agent** | 表单识别、智能填写、登录执行、验证码检测 |
| **Security Agent** | 越权测试(IDOR)、注入测试、并行监控模式 |
| **Analyzer Agent** | 重放结果分析、漏洞判定、探索建议生成 |

## 技术栈

- **Agent框架**: Claude Code (基于Prompt的角色扮演)
- **浏览器控制**: Playwright MCP
- **安全测试**: BurpBridge MCP (BurpSuite插件)
- **数据存储**: MongoDB (BurpBridge依赖)
- **测试目标**: www.baidu.com

## 关键特性

- **登录态保持**: Cookie管理、自动重新登录、验证码人机交互
- **API发现**: 网络请求分析、API模式识别、敏感数据检测
- **并行架构**: Security Agent与探索Agent并行运行
- **多标签页支持**: 多窗口多账号管理、越权测试场景
- **事件驱动通信**: Agent间通过事件队列异步通信

## 目录结构

```
WebTest/
├── .claude/              # Claude配置
├── agents/               # Agent定义文件 (6个)
│   ├── coordinator.md
│   ├── navigator.md
│   ├── scout.md
│   ├── form.md
│   ├── security.md
│   └── analyzer.md
├── config/               # 配置文件
│   └── accounts.json     # 账号配置模板
├── memory/               # 模板文件
│   ├── sessions/
│   └── discoveries/
├── result/               # 测试输出 (不提交git)
│   ├── events.json       # 事件队列
│   ├── windows.json      # 窗口注册表
│   ├── sessions.json     # 会话状态
│   ├── apis.json         # API发现记录
│   └── vulnerabilities.json
├── reports/              # 报告模板
└── README.md
```

## 快速开始

### 1. 环境准备

```bash
# 启动 MongoDB
docker run -d --name mongodb -p 27017:27017 mongo:latest

# 构建 BurpBridge 插件
cd /path/to/BurpBridge && mvn clean package

# 在 Burp Suite 中加载插件
# 加载 target/BurpBridge-1.0-SNAPSHOT.jar
```

### 2. 启动测试

```
你现在扮演Coordinator Agent角色。
请阅读 agents/coordinator.md 了解你的职责。
目标URL: https://www.baidu.com
请开始规划并执行Web探索测试。
```

## 开发进度

- [x] Phase 1: 环境准备
- [x] Phase 2: Coordinator Agent开发
- [x] Phase 3: Navigator Agent开发
- [x] Phase 4: Scout Agent开发
- [x] Phase 5: Form Agent开发
- [x] Phase 6: Security Agent开发
- [x] Phase 7: Analyzer Agent开发
- [x] Phase 8: 架构升级（并行、事件驱动、多窗口）
- [ ] Phase 9: 实战测试与优化

## 安全声明

本项目仅用于授权的安全测试和研究目的。请确保在合法授权范围内使用。
