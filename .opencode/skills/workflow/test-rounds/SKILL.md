---
name: test-rounds
description: "测试轮次模型，适配按账号双阶段权限轮次。定义当前账号先导航取证、再做 denied replay 的迭代机制。"
---

# Test Rounds Skill

> 测试轮次模型 — 以权限点为中心、按账号双阶段执行与补轮次控制

---

## 测试模式

| 模式 | 权限轮次 | 补测轮次 | 说明 |
|------|---------|---------|------|
| quick | 1 | 1 | 快速验证关键权限点 |
| standard | 2-3 | 1-2 | 标准测试，闭环主要权限点 |
| deep | 3-5 | 2-3 | 深度测试 + deferred 补测 + 不可逆专项 |

---

## 迭代模型

### 迭代N: 选择账号与权限重点 → 当前账号取证 → 当前账号 denied replay → 评估

```
迭代N流程:
┌─────────────────────────────────────────────────────────────┐
│  1. Coordinator选择当前账号与权限重点                         │
│     - 结合权限矩阵、已测状态、风险优先级                      │
│     - 只挑选一个账号/角色进入本轮                             │
│     - 不预登录全部账号                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. @navigator survey/explore                                │
│     - 只访问当前账号有权限的页面、接口与操作                  │
│     - 围绕 permission_key 回填正向证据                        │
│     - 明确哪些 permission_key 可交给本轮 Security             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. @security test                                           │
│     - 先绑定当前账号 Navigator 新增样本的 history_entry_id    │
│     - 再测试“前面已探索过，且当前账号应无权限”的样本 backlog  │
│     - 优先直接使用 permission_key + sample_id + history_id    │
│     - 无可用 auth 或样本不足就记入 deferred_roles             │
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
│     - 整理未完成的 permission_key + sample_id + target_account│
│     - 决定继续下一账号轮次、进入补轮次、final stage 或报告    │
│     - duration: ~30sec                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                继续权限轮次          进入报告
```

---

## 账号轮次阶段（Navigator）

### 目标

```
max(当前账号正向证据质量)
- 优先补齐当前账号有权限的高价值 permission_key
- 为当前权限点补齐页面、接口和 `api_evidence_samples`
- 记录 `allowed_roles / allowed_accounts / denied_roles`
- 产出本轮可交给 Security 的 denied backlog 候选
```

### Navigator任务参数

```json
{
  "task": "survey_site|deep_explore_module|verify_role_access",
  "parameters": {
    "permission_key": "workflow.approval.submit",
    "round_role": "manager",
    "round_account_id": "test1020",
    "max_pages": 10,
    "max_depth": 3,
    "iteration": 1
  }
}
```

### Navigator返回判断

| status | Coordinator处理 |
|--------|----------------|
| completed | 必须进入同一账号的 Security 子阶段 |
| partial | 检查原因，判断继续或测试 |
| exception | 处理异常，可能暂停 |

---

## 当前账号安全阶段（Security + Analyzer）

### 目标

```
max(当前账号 denied replay 覆盖)
- 只测试前序账号已确认有权限、且当前账号应无权限的接口
- 当前账号 Security 子阶段先执行 history 样本绑定，再执行 denied replay
- 优先直接利用 `api_evidence_samples.replay_ready=true` 且已绑定的历史样本
- 以 `permission_key + sample_id + target_account_id` 作为 replay 与恢复主键
- 将无法立即验证的 denied role/account 记入 deferred
- 验证漏洞真实性
```

### Security任务参数

```json
{
  "task": "test",
  "parameters": {
    "target_host": "edu.hicomputing.huawei.com",
    "permission_key": "workflow.approval.submit",
    "sample_ids": ["sample_workflow_submit_001"],
    "round_role": "manager",
    "round_account_id": "test1020",
    "iteration": 1
  }
}
```

### 增量规则

```
每个账号轮次都要执行完 navigator + security 两个子阶段，之后才允许切到下一个账号：

✗ 禁止重复测试
  - 跳过状态已 `closed` 的权限点
  - 跳过已稳定确认的关联API（除非需要深度验证）
  - 禁止“所有账号先跑 Navigator，最后统一跑 Security”
  
✓ 只测试缺口
  - 前序账号已确认有权限、且当前账号应无权限的权限点
  - 当前账号本轮只对“自己 + 前序账号”已经形成证据链的权限点负责，不预支后续账号的 denied 测试
  - 当前账号轮次中断后未完成的 `permission_key + sample_id + target_account_id`
  - discovered 但未绑定充分证据的敏感API
  - Navigator 新发现且能关联到当前权限点的 API
  - 主扫描从 `history_progress[permission_key+sample_id+target_account_id]` 恢复
  - 高危接口可触发独立 reverse probe，但不得修改主扫描游标

✓ 第一轮特例
  - 首个账号也必须进入 Security 子阶段
  - 若 denied backlog 为空，返回 `success/no_targets`

✓ 补轮次规则
  - 每轮结束后整理未闭环的 `permission_key + sample_id + target_account_id`
  - 后续补轮次仍按“登录一个账号 → Navigator 取证 → Security denied replay”执行
  - 若中途因超时、失效或缺样本中断，恢复时优先继续原轮次未完成项
  - 对后续账号新发现且当前账号应无权限的 ready 样本，生成第二轮或第三轮反向补测
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

Q2: 当前账号轮次是否真正闭环了？
    检查:
    - 当前账号的 navigator phase 是否完成
    - 当前账号的 security phase 是否完成或合法 no_targets
    - 本轮是否仍有未完成的 permission_key + sample_id + target_account_id
    判定:
    - 任一未完成 → NO → 优先继续本账号轮次

Q3: 是否还有 deferred、补轮次或最终专项？
    检查:
    - deferred_roles 是否非空
    - 未完成补轮次队列是否非空
    - final_stage_required 是否存在
    判定:
    - YES → 进入补轮次或最终专项阶段

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
  
  // 当前账号双阶段必须先闭环
  if (currentRound.navigator_phase !== "completed") {
    return { continue: true, action: "@navigator survey_site|deep_explore_module|verify_role_access" };
  }

  if (!["completed", "no_targets"].includes(currentRound.security_phase)) {
    return { continue: true, action: "@security test" };
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
    return { continue: true, action: "deferred_round|FINAL_STAGE" };
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
