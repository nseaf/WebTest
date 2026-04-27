---
name: agent-contract
description: "Agent合约模板，定义输出格式、截断防御、门控条件。Coordinator调用subagent前注入，确保Agent行为可控、输出可追踪。"
---

# Agent Contract Skill

> Agent合约模板 — 输出格式、截断防御、门控条件、Token预算管理

---

## Agent合约字段

Coordinator调用subagent时注入以下合约参数：

```
---Agent Contract---
[Session ID]     {session_id}           ← 当前测试会话ID
[Target Host]    {target_host}          ← 目标主机名
[CDP URL]        {cdp_url}              ← Chrome CDP连接地址
[Max Depth]      {max_depth}            ← 探索深度限制
[Timeout]        {timeout_ms}           ← 超时时间（毫秒）
[Current State]  {current_state}        ← 状态机当前状态
[Gate Condition] {gate_condition}       ← 门控条件
[Output Format]  HEADER + TRANSFER BLOCK + AGENT_OUTPUT_END
[Token Budget]   输出≤5000字
[DB Write]       实时写入MongoDB，不等Agent完成
[Progress Track] 更新progress状态
---End Contract---
```

---

## 输出格式规范

所有Agent必须使用标准输出格式，便于截断检测和数据传递：

```
=== HEADER START ===
STATE: {current_state}
COVERAGE: pages={N}/{max}, apis={N}/{target}, tests={N}/{total}
UNCHECKED: [待处理项列表]
STATS: tools={N}, time=~{N}min
=== HEADER END ===

=== TRANSFER BLOCK START ===
PAGES_ANALYZED: {url1}:{结论} | {url2}:{结论}
APIS_DISCOVERED: {endpoint}:{method}:{test_status}
TESTED_APIS: {endpoint}:{role}:{result}
COOKIE_SYNCED: {role}:{status}
=== TRANSFER BLOCK END ===

=== AGENT_OUTPUT_END ===  ← 截断检测哨兵（必须存在）
```

---

## 截断检测与恢复机制

### 检测流程

```
对每个Agent的返回输出:
  1. 检查哨兵: 输出末尾是否包含 === AGENT_OUTPUT_END ===
     ├── YES → 输出完整，正常处理
     └── NO  → 截断发生，执行恢复流程
```

### 恢复流程

```
截断发生时:
  1. 检查HEADER是否存活
     ├── YES → 提取COVERAGE/UNCHECKED/STATS
     └── NO  → resume Agent请求仅输出HEADER
  
  2. TRANSFER BLOCK提取
     - 尝试提取PAGES_ANALYZED/APIS_DISCOVERED
     - 记录已完成的工作
  
  3. 发现表格补充（如截断）
     - findings_truncated = true
     - resume Agent补充发现表格
     - 缺失数≤3 → 接受损失并标注
     - 缺失数>3 → 再次resume或拆分任务
```

### 输出预算规则

```
- HEADER段: ≤400字
- TRANSFER BLOCK段: ≤400字
- 发现表格: 每条1行≤150字，最多20行
- 详情描述: 仅关键发现，每条≤10行
- 总输出目标: ≤5000字
- 禁止: 大段原始代码、完整响应内容、冗长描述
```

---

## Token节约策略

```
1. 定向获取
   - browser_snapshot({ depth: 2-3 }) 限制深度
   - browser_snapshot({ filename: ".tmp/snapshots/xxx.yaml" }) 保存到文件
   
2. 网络请求过滤
   - browser_network_requests({ static: false }) 排除静态资源
   - browser_network_requests({ filter: "/api/*" }) 只匹配API
   
3. 提前终止
   - 同类型发现≥5个时合并描述
   - 关键端点测试完成后立即汇报
   
4. 分批处理
   - 大量API分批测试，每批≤10个
   - 分批汇报，避免单次输出过大
```

---

## 门控条件定义

### 状态转换门控

| 状态转换 | 门控条件 | 验证方式 |
|---------|---------|---------|
| INIT → PHASE_1_EXPLORE | Chrome启动成功 + accounts.json存在 | 检查chrome_instances.json + config/accounts.json |
| PHASE_1_EXPLORE → ROUND_1_TEST | 登录成功 OR 无需登录 + 页面≥N | 检查sessions.json + progress.stats |
| ROUND_N_TEST → ROUND_N_EVALUATION | 关键端点测试完成 OR timeout | 检查progress.tested_apis比例 |
| ROUND_N_EVALUATION → NEXT_ROUND | 三问法则判定YES | 检查UNCHECKED列表 |
| ROUND_N_EVALUATION → REPORT | 三问法则判定NO | 无UNCHECKED项 |
| REPORT → END | 报告生成完成 | 检查report文件 |

### 三问法则

用于判断是否需要继续下一轮测试：

```
Q1: 有未访问的重要路径？
    - 检查 progress.pending APIs
    - 检查 Scout 发现的新链接
    - 有敏感API未测试 → YES = NEXT_ROUND
    
Q2: 关键端点是否都测试了？
    - 检查各模块 tested 比例
    - 敏感模块 tested < 50% → NO = NEXT_ROUND
    
Q3: 发现的漏洞是否可能组合攻击？
    - 检查 vulnerabilities 间依赖关系
    - 存在跨模块组合可能 → YES = 进入攻击链验证
```

---

## 各Agent的合约模板

### Scout Agent合约

```
---Agent Contract---
[Session ID] session_20260422
[Target Host] www.example.com
[CDP URL] http://localhost:9222
[Max Depth] 3
[Current State] PHASE_1_EXPLORE
[Gate Condition] 页面数≥20 OR 深度≥max_depth
[Output Format] HEADER + TRANSFER BLOCK + AGENT_OUTPUT_END
[DB Write] 发现API立即写入apis collection
[Progress Track] 更新pages/apis统计
---End Contract---
```

### Security Agent合约

```
---Agent Contract---
[Session ID] session_20260422
[Target Host] www.example.com
[Current State] ROUND_1_TEST
[Gate Condition] 关键端点测试完成 OR timeout
[Test Roles] admin, user, guest
[Output Format] HEADER + TRANSFER BLOCK + AGENT_OUTPUT_END
[DB Write] 发现漏洞立即写入findings collection
[Progress Track] 更新apis.test_status
---End Contract---
```

### Form Agent合约

```
---Agent Contract---
[Session ID] session_20260422
[CDP URL] http://localhost:9222
[Account ID] admin_001
[Login URL] https://example.com/login
[Current State] PHASE_1_EXPLORE
[Gate Condition] 登录成功 OR CAPTCHA_DETECTED
[Output Format] HEADER + TRANSFER BLOCK + AGENT_OUTPUT_END
[DB Write] 登录成功后更新sessions collection
[Progress Track] 更新login_status
---End Contract---
```

---

## 加载要求

此Skill由以下Agent加载：

```yaml
## Skill 加载规则（双通道）

# Coordinator、Navigator、Scout、Form、Security、Analyzer 必须加载

1. 尝试: skill({ name: "agent-contract" })
2. 若失败: Read("skills/core/agent-contract/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```
