---
name: test-rounds
description: "测试轮次模型，适配串行流程。定义探索和测试的迭代机制。"
---

# Test Rounds Skill

> 测试轮次模型 — 以权限点为中心的串行执行与迭代控制

---

## 测试模式

| 模式 | 权限轮次 | 补测轮次 | 说明 |
|------|---------|---------|------|
| quick | 1 | 1 | 快速验证关键权限点 |
| standard | 2-3 | 1-2 | 标准测试，闭环主要权限点 |
| deep | 3-5 | 2-3 | 深度测试 + deferred 补测 + 不可逆专项 |

---

## 迭代模型

### 迭代N: 选择权限点 → 当前角色探索 → replay测试 → 评估

```
迭代N流程:
┌─────────────────────────────────────────────────────────────┐
│  1. Coordinator选择当前轮次 permission_key                    │
│     - 结合权限矩阵、已测状态、风险优先级                      │
│     - 只挑选一个最有价值的角色进入本轮                        │
│     - 不预登录全部账号                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. @navigator survey/explore                                │
│     - 围绕 permission_key 收集页面、入口与接口证据            │
│     - 发现API并回填 permission_targets                        │
│     - 可达性与角色差异验证                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. @security test                                           │
│     - 对当前 permission_key 做正向/反向 replay                │
│     - 有可用 auth 就立即跨角色验证                            │
│     - 无可用 auth 就记入 deferred_roles                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. @analyzer analyze                                        │
│     - 只分析稳定 replay                                       │
│     - 判定漏洞与严重性                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Coordinator评估                                          │
│     - 查看 permission_targets 的闭环率                        │
│     - 决定继续权限轮次、进入 deferred/final stage 或报告      │
│     - duration: ~30sec                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                继续权限轮次          进入报告
```

---

## 权限轮次阶段（Navigator）

### 目标

```
max(权限闭环率)
- 优先闭环高价值 permission_key
- 为当前权限点补齐页面、接口和请求样本
- 验证当前角色有权限点与邻近无权限点
- 记录表单、异常与 deferred 原因
```

### Navigator任务参数

```json
{
  "task": "survey_site|deep_explore_module|verify_role_access",
  "parameters": {
    "permission_key": "workflow.approval.submit",
    "round_role": "manager",
    "max_pages": 10,
    "max_depth": 3,
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
max(权限验证深度)
- 对当前权限点关联接口进行测试
- 立即利用现有 auth 做跨角色越权验证
- 将无法立即验证的角色记入 deferred
- 验证漏洞真实性
```

### Security任务参数

```json
{
  "task": "test",
  "parameters": {
    "target_host": "edu.hicomputing.huawei.com",
    "permission_key": "workflow.approval.submit",
    "round_role": "manager",
    "iteration": 1
  }
}
```

### 增量规则

```
每个迭代只测试上一轮未闭环的权限点或其关联API：

✗ 禁止重复测试
  - 跳过状态已 `closed` 的权限点
  - 跳过已稳定确认的关联API（除非需要深度验证）
  
✓ 只测试缺口
  - pending / deferred 状态的权限点
  - discovered 但未绑定充分证据的敏感API
  - Navigator 新发现且能关联到当前权限点的 API
  - 主扫描从 `history_progress[permission_key+role]` 恢复
  - 高危接口可触发独立 reverse probe，但不得修改主扫描游标
```

---

## 评估阶段（Coordinator）

### 三问法则

```
Q1: 有高价值 survey 缺口或权限证据缺口吗？
    检查:
    - Navigator返回的pending_urls
    - permission_targets.related_pages / related_apis 是否仍不足
    判定:
    - 有缺口 → YES → 继续探索

Q2: 关键权限点是否都闭环了？
    检查:
    - permission_targets.status
    - 高优先级权限点覆盖率
    判定:
    - 闭环率 < 80% → NO → 继续测试

Q3: 是否还有 deferred 或最终专项？
    检查:
    - deferred_roles 是否非空
    - final_stage_required 是否存在
    判定:
    - YES → 进入最终专项阶段

Q4: 漏洞是否需要组合验证？
    检查:
    - findings 中高危漏洞数量
    - 漏洞跨模块分布
    判定:
    - 高危≥2且跨模块 → YES → attack_chain_test

Q5: 是否达标？
    检查:
    - 权限点闭环率达标
    - deferred 已处理或确认延期
    - 不可逆专项完成
    - 前四问判定完成
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
  const q5 = checkQ5();
  
  if (q1.answer === "YES") {
    return { continue: true, action: "@navigator continue_explore" };
  }
  
  if (q2.answer === "NO") {
    return { continue: true, action: "@security test" };
  }
  
  if (q3.answer === "YES") {
    return { continue: true, action: "FINAL_STAGE" };
  }
  
  if (q4.answer === "YES") {
    return { continue: true, action: "@security attack_chain_test" };
  }

  if (q5.answer === "YES") {
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
│ [Coordinator choose permission_key] → 返回        │
│                      ↓                             │
│ [Navigator permission survey] ─→ 返回             │
│                      ↓                             │
│ [Security test] ─────────→ 返回                   │
│                      ↓                             │
│ [Analyzer analyze] ─────→ 返回                    │
│                      ↓                             │
│ [Coordinator evaluate] → 决策                     │
└────────────────────────────────────────────────────┘
           │
           ↓ 继续权限轮次

迭代2:
时间 →
┌────────────────────────────────────────────────────┐
│ [Navigator next permission round] ─→ 返回         │
│                      ↓                             │
│ [Security test] ────────────────→ 返回            │
│                      ↓                             │
│ [Analyzer analyze] ─────────────→ 返回            │
│                      ↓                             │
│ [Coordinator evaluate] ─────────→ 决策            │
└────────────────────────────────────────────────────┘
           │
           ↓ deferred/final stage 或进入报告

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
