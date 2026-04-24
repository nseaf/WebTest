# Agent 快速参考

## 启动测试

```
/coordinator
目标URL: https://www.example.com
请开始规划并执行Web探索测试。
```

## Agent 清单 (1 Primary + 5 Subagents)

| Agent | 模式 | 角色 |
|-------|------|------|
| **Coordinator** | primary | 主控制器，工作流调度、状态管理 |
| Navigator | subagent | 页面导航+分析（已合并Scout功能）|
| Form | subagent | 表单处理、登录执行 |
| Security | subagent | 安全测试、IDOR/注入测试 |
| Analyzer | subagent | 结果分析、漏洞判定、严重性评级 |
| AccountParser | subagent | 账号文档解析、权限矩阵提取 |

## 强制委派规则（核心）

Coordinator 必须通过 `@{agent_name}` 调用 subagent。

| 操作类型 | 委派目标 | 禁止使用 |
|---------|---------|---------|
| 浏览器操作 | @navigator | mcp__playwright__* |
| 表单处理 | @form | mcp__playwright__browser_type |
| 安全测试 | @security | mcp__burpbridge__* |
| 账号解析 | @account_parser | 直接读取Excel |
| 结果分析 | @analyzer | — |

## Skills 系统

可复用的方法论模块，位于 `.opencode/skills/`。

详见 `.opencode/skills/SKILLS.md`。

## 完整文档

- **AGENTS.md** - 完整的 Agent 定义和工作流
- **.opencode/skills/SKILLS.md** - Skills 系统文档
