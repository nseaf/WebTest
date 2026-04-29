---
name: test-rounds
description: "测试轮次模型，适配串行流程。定义探索和测试的迭代机制。"
---

# Test Rounds Skill

> 测试轮次模型 — 串行执行、迭代控制

---

## 测试模式

| 模式 | 探索轮次 | 测试轮次 | 说明 |
|------|---------|---------|------|
| quick | 1 | 1 | 基础扫描，快速完成 |
| standard | 2-3 | 2-3 | 标准测试，覆盖主要功能 |
| deep | 3-5 | 3-5 | 深度测试+攻击链验证 |

---

## 迭代模型

### 迭代N: 探索 → 测试 → 评估

```
迭代N流程:
┌─────────────────────────────────────────────────────────────┐
│  1. @navigator explore                                       │
│     - 探索N个页面                                            │
│     - 发现API                                               │
│     - 主动退出返回报告                                        │
│     - duration: ~5min                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. @security test                                           │
│     - 分析历史记录                                           │
│     - 执行IDOR测试                                           │
│     - 返回replay_ids                                         │
│     - duration: ~3min                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. @analyzer analyze                                        │
│     - 分析重放结果                                           │
│     - 判定漏洞                                               │
│     - 评级严重性                                             │
│     - duration: ~1min                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Coordinator评估                                          │
│     - 三问法则判定                                           │
│     - 决定继续或进入报告                                      │
│     - duration: ~30sec                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                继续迭代              进入报告
```

---

## 探索阶段（Navigator）

### 目标

```
max(覆盖面)
- 访问尽可能多的页面
- 发现尽可能多的API端点
- 重点访问测试重点路径（如用户个人中心）
- 记录表单和异常情况
```

### Navigator任务参数

```json
{
  "task": "explore",
  "parameters": {
    "max_pages": 10,
    "max_depth": 3,
    "cdp_url": "http://localhost:9222",
    "test_focus": "用户个人中心",
    "iteration": 1
  }
}
```

### Navigator返回判断

| status | Coordinator处理 |
|--------|----------------|
| completed | 正常进入测试 |
| partial | 检查原因，判断继续或测试 |
| exception | 处理异常，可能暂停 |

---

## 安全测试阶段（Security + Analyzer）

### 目标

```
max(深度)
- 对发现的敏感API进行测试
- 多角色越权测试
- 参数变异测试（可选）
- 验证漏洞真实性
```

### Security任务参数

```json
{
  "task": "test",
  "parameters": {
    "target_host": "edu.hicomputing.huawei.com",
    "iteration": 1
  }
}
```

### 增量规则

```
每个迭代只测试上一轮未完成的API：

✗ 禁止重复测试
  - 跳过 test_status === "tested" 的API
  - 跳过已发现漏洞的API（除非需要深度验证）
  
✓ 只测试缺口
  - pending 状态的API
  - discovered 但未测试的敏感API
  - Navigator新发现的API
  - 主扫描从 `history_progress.main_scan.current_page` 恢复
  - 高危接口可触发独立 reverse probe，但不得修改主扫描游标
```

---

## 评估阶段（Coordinator）

### 三问法则

```
Q1: 有未访问的重要路径？
    检查:
    - Navigator返回的pending_urls
    - 测试重点路径是否已访问
    判定:
    - pending_urls.length > 0 → YES → 继续探索

Q2: 关键端点是否都测试了？
    检查:
    - progress.sensitive_apis.tested / total
    - 高优先级模块覆盖率
    判定:
    - 覆盖率 < 80% → NO → 继续测试

Q3: 漏洞是否需要组合验证？
    检查:
    - findings中高危漏洞数量
    - 漏洞跨模块分布
    判定:
    - 高危≥2且跨模块 → YES → attack_chain_test

Q4: 是否达标？
    检查:
    - 覆盖率达标
    - 测试完成
    - 三问判定完成
    判定:
    - 全部达标 → YES → 进入报告
```

---

## 轮次硬上限

| 模式 | 探索上限 | 测试上限 | 轮次上限 |
|------|---------|---------|---------|
| quick | 5 pages | 1轮 | 1 |
| standard | 30 pages | 3轮 | 3 |
| deep | 50 pages | 5轮 | 5 |

---

## 迭代终止判定

```javascript
function shouldContinueIteration(iteration, mode) {
  const limits = {
    quick: { max_iteration: 1 },
    standard: { max_iteration: 3 },
    deep: { max_iteration: 5 }
  };
  
  // 轮次上限
  if (iteration >= limits[mode].max_iteration) {
    return { continue: false, reason: "达到轮次上限" };
  }
  
  // 三问法则判定
  const q1 = checkQ1();
  const q2 = checkQ2();
  const q3 = checkQ3();
  const q4 = checkQ4();
  
  if (q1.answer === "YES") {
    return { continue: true, action: "@navigator continue_explore" };
  }
  
  if (q2.answer === "NO") {
    return { continue: true, action: "@security test" };
  }
  
  if (q3.answer === "YES") {
    return { continue: true, action: "@security attack_chain_test" };
  }
  
  if (q4.answer === "YES") {
    return { continue: false, action: "REPORT" };
  }
  
  return { continue: false, action: "REPORT" };
}
```

---

## 时间线可视化

```
迭代1:
时间 →
┌────────────────────────────────────────────────────┐
│ [Navigator explore] ─────→ 返回                   │
│                      ↓                             │
│ [Security test] ────────→ 返回                    │
│                      ↓                             │
│ [Analyzer analyze] ─────→ 返回                    │
│                      ↓                             │
│ [Coordinator evaluate] → 决策                     │
└────────────────────────────────────────────────────┘
           │
           ↓ 继续探索

迭代2:
时间 →
┌────────────────────────────────────────────────────┐
│ [Navigator continue_explore] ──→ 返回             │
│                      ↓                             │
│ [Security test] ────────────────→ 返回            │
│                      ↓                             │
│ [Analyzer analyze] ─────────────→ 返回            │
│                      ↓                             │
│ [Coordinator evaluate] ─────────→ 决策            │
└────────────────────────────────────────────────────┘
           │
           ↓ 进入报告

REPORT:
时间 →
┌────────────────────────────────────────────────────┐
│ [Coordinator report] ─────→ 报告生成              │
│                      ↓                             │
│ [Navigator close] ────────→ 实例关闭              │
│                      ↓                             │
│ END                                               │
└────────────────────────────────────────────────────┘
```

---

## 加载要求

```yaml
## Skill 加载规则

# Coordinator 必须加载

1. 尝试: skill({ name: "test-rounds" })
2. 若失败: Read(".opencode/skills/workflow/test-rounds/SKILL.md")
```
