# Agent 快速参考

## 启动测试

```
/coordinator
目标URL: https://www.example.com
请开始规划并执行Web探索测试。
```

## Agent 清单 (1 Primary + 5 Subagents)

| Agent | mode | 角色 |
|-------|------|------|
| **Coordinator** | primary | 主控制器，工作流调度、状态管理 |
| Navigator | subagent | 页面导航+分析+登录/会话恢复（已合并Scout功能）|
| Form | subagent | 复杂业务表单处理 |
| Security | subagent | 安全测试、IDOR/注入测试、认证失效检测 |
| Analyzer | subagent | 结果分析、漏洞判定、严重性评级 |
| AccountParser | subagent | 账号文档解析、权限矩阵提取 |

## 强制规则（核心）

Coordinator 必须通过将对应工作交给 subagent 完成。Coordinator本身仅负责工作流调度、状态管理、异常处理、进度评估。

| 操作类型 | subagent | 要求 |
|---------|---------|---------|
| 浏览器操作 | @navigator | 使用browser-use cli + skill, chrome命令 |
| 登录与会话恢复 | @navigator | 统一复用 `session_name` |
| 复杂业务表单 | @form | 使用browser-use cli + skill, chrome命令 |
| 安全测试 | @security | 使用 mcp__burpbridge__* |
| 账号解析 | @account_parser | 禁止直接读取Excel |
| 结果分析 | @analyzer | — |

## Skills 系统

可复用的方法论模块，位于 `.opencode/skills/`。

详见 `.opencode/skills/SKILLS.md`。

## 完整文档

- **AGENTS.md** - 完整的 Agent 定义和工作流
- **.opencode/skills/SKILLS.md** - Skills 系统文档
