---
name: agent-contract
description: "Agent 合约模板：统一输出格式、门控字段、会话上下文和截断检测，保证多 Agent 协作可追踪。"
---

# Agent Contract Skill

> Coordinator 在调度 subagent 前必须注入 Agent Contract。对于浏览器相关任务，contract 需要显式表达 session、attach 模式、活动 tab 和探索目标。

## Contract 字段

### 通用字段

```text
---Agent Contract---
[Session ID]       {session_id}
[Target Host]      {target_host}
[Task Type]        {task_type}
[Current State]    {current_state}
[Gate Condition]   {gate_condition}
[Output Format]    HEADER + TRANSFER BLOCK + AGENT_OUTPUT_END
[Token Budget]     输出≤2000字
---End Contract---
```

### 浏览器任务附加字段

```text
[Session Name]     {session_name}
[Attach Mode]      {bootstrap|reuse|repair}
[Active Tab]       {active_tab_index}
[Exploration Goal] {test_focus 或当前探索目标}
[Entry URLs]       {入口URL摘要}
[Pending URLs]     {待访问URL摘要}
[Visited Summary]  {已访问摘要}
[Workflow Context] {审批/业务上下文，没有则写 none}
```

规则：

- `Session Name` 是浏览器操作主键
- `Attach Mode` 决定是否允许携带 `cdp_url`
- `Active Tab` 必须与 `windows.json` / `sessions.json` 中的已知状态保持一致
- `Exploration Goal` 不可留空；没有显式目标时写“same-domain prioritized exploration”

## 输出格式规范

所有 Agent 必须使用以下输出框架：

```text
=== HEADER START ===
STATE: {current_state}
COVERAGE: pages={N}/{max}, apis={N}/{target}, tests={N}/{total}
UNCHECKED: [待处理项]
STATS: tools={N}, time=~{N}min
=== HEADER END ===

=== TRANSFER BLOCK START ===
PAGES_ANALYZED: {url}:{结论}
APIS_DISCOVERED: {endpoint}:{method}:{status}
SESSION_STATE: {session_name}:{attach_mode}:{active_tab}:{url}
RECOVERY_ACTIONS: {issue}:{action}:{result}
COOKIE_SYNCED: {role}:{status}
=== TRANSFER BLOCK END ===

=== AGENT_OUTPUT_END ===
```

浏览器相关任务至少要填 `SESSION_STATE`；发生恢复时至少要填一条 `RECOVERY_ACTIONS`。

## 截断检测与恢复

- 必须以 `=== AGENT_OUTPUT_END ===` 结尾
- 若输出被截断：
  - 先提取 HEADER 中的 `UNCHECKED` 与 `STATS`
  - 再提取 `SESSION_STATE` 与 `RECOVERY_ACTIONS`
  - 若恢复信息缺失，优先 resume 让 Agent 只补 `TRANSFER BLOCK`

## Navigator 合同示例

```text
---Agent Contract---
[Session ID] session_20260428_001
[Target Host] example.com
[Task Type] explore
[Current State] EXPLORATION_RUNNING
[Gate Condition] max_pages reached or all pending_urls resolved
[Session Name] admin_001
[Attach Mode] reuse
[Active Tab] 1
[Exploration Goal] 审批入口与导出入口优先
[Entry URLs] /dashboard, /approval
[Pending URLs] /profile, /settings
[Visited Summary] 已访问登录页、首页、工作台
[Workflow Context] software_nre_approval
---End Contract---
```

## Form 合同示例

```text
---Agent Contract---
[Session ID] session_20260428_001
[Target Host] example.com
[Task Type] execute_logins
[Current State] INIT
[Gate Condition] login success or captcha detected
[Session Name] user_001
[Attach Mode] reuse
[Active Tab] 0
[Exploration Goal] 建立认证态
[Entry URLs] /login
[Pending URLs] none
[Visited Summary] 浏览器实例已创建，待登录
[Workflow Context] none
---End Contract---
```

## 加载要求

```yaml
1. 尝试: skill({ name: "agent-contract" })
2. 若失败: Read(".opencode/skills/core/agent-contract/SKILL.md")
3. 本 Skill 必须加载完成才能继续执行
```
