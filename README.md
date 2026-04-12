# AI-Agent Web渗透测试系统

## 项目概述

本项目是一个基于Claude Code的多Agent Web渗透测试系统。通过层级式多Agent架构，利用AI技术模拟人工前端Web测试，为后续的渗透测试能力奠定基础。

## 系统架构

```
Coordinator Agent (协调者)
    ├── Scout Agent (侦查)
    ├── Form Agent (表单处理)
    └── Navigator Agent (导航)
```

### Agent职责

1. **Coordinator Agent**: 任务规划、分配、监控、决策协调
2. **Scout Agent**: 页面分析、元素识别、链接发现
3. **Form Agent**: 表单识别、智能填写、提交处理
4. **Navigator Agent**: 页面导航、链接跟踪、状态管理

## 技术栈

- **Agent框架**: Claude Code (对话式Agent)
- **浏览器控制**: Playwright (通过MCP)
- **数据存储**: MongoDB (Phase 2)
- **测试目标**: baidu.com

## 目录结构

```
WebTest/
├── .claude/              # Claude配置
├── agents/               # Agent定义文件
├── memory/               # 测试记忆
├── discoveries/          # 发现记录
├── screenshots/          # 截图存储
├── reports/              # 测试报告
└── README.md            # 项目说明
```

## 快速开始

### Phase 1: 环境准备

1. 配置Playwright MCP到Claude Code
2. 确认导航能力可用

### 使用方法

通过Claude Code对话启动Coordinator Agent进行渗透测试。

## 开发进度

- [x] Phase 1: 环境准备
- [ ] Phase 2: Coordinator Agent开发
- [ ] Phase 3: Navigator Agent开发
- [ ] Phase 4: Scout Agent开发
- [ ] Phase 5: Form Agent开发
- [ ] Phase 6: 百度实战测试

## 安全声明

本项目仅用于授权的安全测试和研究目的。请确保在合法授权范围内使用。
