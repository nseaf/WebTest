---
name: test-rounds
description: "三轮测试模型，定义每轮的目标和方法。R1覆盖面，R2深度，R3攻击链验证。"
---

# Test Rounds Skill

> 三轮测试模型 — R1/R2/R3目标、方法、门控条件

---

## 三轮模型概述

| 轮次 | 目标函数 | 方法 | 主要Agent | 输出 |
|------|---------|------|----------|------|
| **R1** | max(覆盖面) | 快速导航 + API发现 + 基础测试 | Navigator + Scout + Security | pages/apis/findings |
| **R2** | max(深度) | 关键端点深度测试 + 参数变异 | Security + Analyzer | 深度findings |
| **R3** | max(关联度) | 攻击链验证 + 组合测试 | Security + Analyzer | attack_chains |

---

## Round 1: 快速探索与基础测试

### 目标

```
max(覆盖面)
- 访问尽可能多的页面
- 发现尽可能多的API端点
- 执行基础越权测试（敏感API）
- 识别高风险端点
```

### 流程

```
┌─────────────────────────────────────────────────────────────┐
│  R1 快速探索流程                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. Navigator 导航首页                                       │
│     - 加载目标URL                                            │
│     - 等待页面稳定                                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Form Agent 执行登录（如需要）                             │
│     - 填写登录表单                                           │
│     - 处理验证码                                             │
│     - 同步Cookie到BurpBridge                                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Scout Agent 分析页面                                     │
│     - browser_snapshot(depth=2-3)                            │
│     - 发现链接、表单、API                                     │
│     - 实时写入MongoDB                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Navigator 跟踪重要链接                                   │
│     - 按优先级排序                                           │
│     - 跳过已访问URL                                          │
│     - 控制深度≤max_depth                                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. Security Agent 基础测试                                  │
│     - 识别敏感API                                            │
│     - 执行单角色越权测试                                      │
│     - 实时写入findings                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
                    循环直到门控条件达成
```

### 门控条件

```javascript
const r1Gate = {
  name: "R1完成判定",
  
  conditions: [
    {
      name: "页面数达标",
      check: (progress) => progress.overall_stats.total_pages >= config.max_pages,
      weight: 0.3
    },
    {
      name: "深度达标",
      check: (progress) => progress.current_depth >= config.max_depth,
      weight: 0.2
    },
    {
      name: "API发现达标",
      check: (progress) => progress.overall_stats.total_apis >= config.min_apis,
      weight: 0.3
    },
    {
      name: "无新发现",
      check: (progress) => progress.last_new_discovery_age > 30000,  // 30秒无新发现
      weight: 0.2
    }
  ],
  
  evaluate: (progress) => {
    const score = conditions.reduce((sum, c) => {
      return sum + (c.check(progress) ? c.weight : 0);
    }, 0);
    
    return {
      pass: score >= 0.5,  // 达到50%权重即通过
      details: conditions.map(c => ({
        name: c.name,
        passed: c.check(progress),
        weight: c.weight
      }))
    };
  }
};
```

### R1输出要求

```
R1完成后必须产出：

1. pages collection
   - 所有访问过的页面记录
   - 页面类型分类
   
2. apis collection
   - 所有发现的API端点
   - 模块分类
   - test_status标记
   
3. findings collection（初步）
   - 明显的越权漏洞
   - 高置信度漏洞
   
4. progress collection
   - R1统计数据
   - 待测试API列表
```

---

## Round 2: 深度测试

### 目标

```
max(深度)
- 对R1发现的敏感API进行深度测试
- 多角色越权测试（所有配置角色）
- 参数变异测试
- 验证漏洞真实性
```

### 流程

```
┌─────────────────────────────────────────────────────────────┐
│  R2 深度测试流程                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. Security Agent 筛选测试目标                              │
│     - 从progress.pending获取待测试API                        │
│     - 按模块优先级排序                                       │
│     - 优先敏感API                                            │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 多角色越权测试                                           │
│     for each sensitive API:                                  │
│       for each role:                                         │
│         replay_http_request_as_role                          │
│         → Analyzer分析响应                                   │
│         → 写入findings                                       │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 参数变异测试（可选）                                      │
│     - 修改ID参数（如 id=1 → id=2）                           │
│     - 修改请求体字段                                         │
│     - 使用modifications参数                                  │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Analyzer Agent 分析结果                                  │
│     - 状态码对比                                             │
│     - 响应体相似度                                           │
│     - 敏感字段检测                                           │
│     - 判定漏洞并生成建议                                      │
└─────────────────────────────────────────────────────────────┘
```

### R2增量规则

```
R2只测试R1未完成的API：

✗ 禁止重复测试已测试的API
  - 跳过test_status === "tested"的API
  - 跳过R1已发现漏洞的API（除非需要深度验证）
  
✓ 只测试R1缺口
  - pending状态的API
  - discovered但未测试的敏感API
  - R1标记为"needs_deep_test"的API
```

### 门控条件

```javascript
const r2Gate = {
  name: "R2完成判定",
  
  conditions: [
    {
      name: "敏感API测试完成",
      check: (progress) => {
        const sensitiveCoverage = progress.sensitive_apis.tested / progress.sensitive_apis.total;
        return sensitiveCoverage >= 0.9;  // 90%敏感API测试完成
      }
    },
    {
      name: "高优先级模块测试完成",
      check: (progress) => {
        for (const module of progress.modules) {
          if (module.module_priority === "high") {
            const coverage = module.stats.tested / module.stats.total;
            if (coverage < 0.7) return false;
          }
        }
        return true;
      }
    },
    {
      name: "timeout",
      check: () => elapsed >= config.r2_timeout,
      soft: true
    }
  ]
};
```

---

## Round 3: 攻击链验证

### 目标

```
max(关联度)
- 分析漏洞间依赖关系
- 构建攻击链
- 验证组合攻击可行性
- 发现更高危的组合漏洞
```

### 触发条件

```javascript
function shouldTriggerR3(findings) {
  const highVulns = findings.filter(f => 
    f.severity === "High" || f.severity === "Critical"
  );
  
  // 需要≥2个高危漏洞才触发R3
  if (highVulns.length < 2) return false;
  
  // 检查是否存在跨模块漏洞
  const modules = new Set(highVulns.map(v => getModuleFromEndpoint(v.endpoint)));
  if (modules.size < 2) return false;  // 至少跨2个模块
  
  return true;
}
```

### 流程

```
┌─────────────────────────────────────────────────────────────┐
│  R3 攻击链验证流程                                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. 分析漏洞关系                                             │
│     - 按模块分组                                             │
│     - 分析依赖关系                                           │
│     - 识别可能的组合                                         │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 构建攻击链                                               │
│     Example:                                                 │
│     IDOR获取用户数据 → 信息泄露Token → 权限提升 → 完全控制    │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 验证攻击链可行性                                         │
│     - 使用实际漏洞进行组合测试                                │
│     - 记录每一步的结果                                       │
│     - 评估整体风险                                           │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 更新漏洞严重性                                           │
│     - 组合漏洞升级为Critical                                 │
│     - 记录攻击链详情                                         │
└─────────────────────────────────────────────────────────────┐
```

### 攻击链模式库

```javascript
const attackChainPatterns = [
  {
    name: "账户接管",
    steps: [
      { vuln_type: "IDOR", endpoint_pattern: "/api/users/*", data: "email/password_hash" },
      { vuln_type: "InfoLeak", data: "reset_token" },
      { vuln_type: "AuthBypass", endpoint_pattern: "/api/auth/reset" }
    ],
    result: "完全控制目标账户",
    severity_boost: "+2"  // High → Critical
  },
  {
    name: "权限提升",
    steps: [
      { vuln_type: "AuthBypass", endpoint_pattern: "/api/login" },
      { vuln_type: "IDOR", endpoint_pattern: "/api/admin/*" }
    ],
    result: "获得管理员权限",
    severity_boost: "+1"  // Medium → High
  },
  {
    name: "数据批量泄露",
    steps: [
      { vuln_type: "IDOR", endpoint_pattern: "/api/users/{id}", loop: true },
      { vuln_type: "RateLimitBypass" }
    ],
    result: "批量获取所有用户数据",
    severity_boost: "+1"
  }
];
```

---

## 轮次终止判定

### 三问法则

```
Q1: 有未访问的重要路径？
    → YES = NEXT_ROUND (R1或R2继续)

Q2: 关键端点是否都测试了？
    → NO = NEXT_ROUND (R2继续)

Q3: 发现的漏洞是否可能组合攻击？
    → YES = R3攻击链验证
    → NO = REPORT
```

### 轮次硬上限

| 模式 | 轮次上限 | 说明 |
|------|---------|------|
| quick | 1 | 仅R1基础扫描 |
| standard | 2 | R1 + R2深度测试 |
| deep | 3 | R1 + R2 + R3攻击链 |

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Coordinator、Security 必须加载

1. 尝试: skill({ name: "test-rounds" })
2. 若失败: Read("skills/workflow/test-rounds/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```