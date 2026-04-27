---
name: progress-tracking
description: "访问跟踪与进度控制，按模块划分API，记录测试完成度。支持三问法则判定是否继续测试。"
---

# Progress Tracking Skill

> 访问跟踪与进度控制 — API模块划分、测试状态跟踪、三问法则

---

## 核心功能

```
1. API模块自动划分
   - 根据URL路径自动归类到功能模块
   - 支持自定义模块分类规则
   
2. 测试状态跟踪
   - discovered → pending → testing → tested → analyzed → skipped
   - 每个API记录完整的测试生命周期
   
3. 进度可视化
   - 生成实时进度报告
   - 支持Coordinator决策
   
4. 三问法则
   - 判断是否需要继续下一轮测试
```

---

## API模块划分

### 自动分类规则

根据URL路径自动归类API到功能模块：

```javascript
const modulePatterns = {
  "user": [
    "/api/users/*",
    "/api/profile/*",
    "/api/account/*",
    "/api/member/*"
  ],
  "admin": [
    "/api/admin/*",
    "/api/settings/*",
    "/api/config/*",
    "/api/system/*"
  ],
  "order": [
    "/api/orders/*",
    "/api/cart/*",
    "/api/payment/*",
    "/api/transaction/*",
    "/api/billing/*"
  ],
  "content": [
    "/api/posts/*",
    "/api/articles/*",
    "/api/comments/*",
    "/api/media/*",
    "/api/files/*"
  ],
  "workflow": [
    "/api/workflow/*",
    "/api/approval/*",
    "/api/process/*",
    "/api/task/*"
  ],
  "auth": [
    "/api/auth/*",
    "/api/login/*",
    "/api/token/*",
    "/api/session/*",
    "/api/oauth/*"
  ],
  "data": [
    "/api/data/*",
    "/api/export/*",
    "/api/import/*",
    "/api/report/*"
  ],
  "other": [
    "/api/*"  // 兜底分类
  ]
};
```

### 分类优先级

```
1. 精确匹配优先（如 /api/users/{id} → user）
2. 通配符匹配次优先（如 /api/users/* → user）
3. 兜底分类最后（如 /api/xxx → other）
```

### 分类函数

```javascript
function classifyApi(endpoint) {
  for (const [module, patterns] of modulePatterns) {
    for (const pattern of patterns) {
      if (matchPattern(endpoint, pattern)) {
        return module;
      }
    }
  }
  return "other";
}

function matchPattern(endpoint, pattern) {
  // 将 pattern 中的 * 转换为正则
  const regex = pattern.replace(/\*/g, ".*").replace(/\//g, "\\/");
  return new RegExp(`^${regex}$`).test(endpoint);
}
```

---

## 测试状态定义

### 状态流转图

```
discovered → pending → testing → tested → analyzed → skipped
                        ↓
                      failed
```

### 状态说明

| 状态 | 说明 | 触发条件 | 下一步 |
|------|------|---------|--------|
| **discovered** | 新发现，未加入测试队列 | Navigator发现API | 加入pending队列 |
| **pending** | 在测试队列中等待 | Coordinator分配任务 | Security开始测试 |
| **testing** | 正在测试 | Security执行重放 | 等待测试完成 |
| **tested** | 测试完成，等待分析 | Security完成重放 | Analyzer分析 |
| **analyzed** | 分析完成 | Analyzer判定结果 | 记录漏洞或标记安全 |
| **skipped** | 跳过测试 | 非敏感API或配置跳过 | 不再测试 |
| **failed** | 测试失败 | 重放错误或超时 | 记录原因 |

---

## Progress Collection结构

```javascript
{
  _id: ObjectId,
  session_id: "session_20260422",
  
  // 模块级进度
  modules: [
    {
      module_name: "user",
      module_priority: "high",            // 模块优先级
      apis: [
        {
          api_id: "api_001",
          endpoint: "/api/users/{id}",
          method: "GET",
          test_status: "tested",
          tested_by: "Security",
          tested_at: Date,
          vulnerabilities: ["IDOR_001"],
          skip_reason: null
        },
        {
          api_id: "api_002",
          endpoint: "/api/users/profile",
          method: "GET",
          test_status: "pending",
          tested_by: null,
          tested_at: null,
          vulnerabilities: [],
          skip_reason: null
        }
      ],
      stats: {
        total: 2,
        discovered: 0,
        pending: 1,
        testing: 0,
        tested: 1,
        analyzed: 0,
        skipped: 0,
        failed: 0,
        vulnerabilities: 1
      }
    }
  ],
  
  // 总体统计
  overall_stats: {
    total_apis: 10,
    discovered: 0,
    pending: 7,
    testing: 0,
    tested: 3,
    analyzed: 0,
    skipped: 0,
    failed: 0,
    vulnerabilities_found: 2,
    coverage_percentage: 30.0           // tested/total
  },
  
  // 敏感API统计
  sensitive_apis: {
    total: 5,
    tested: 2,
    untested: ["api_003", "api_004", "api_005"]
  },
  
  last_updated: Date,
  next_action: "test pending apis"      // Coordinator建议
}
```

---

## 进度可视化报告

### 文本报告格式

```
=== Test Progress Report ===
Session: session_20260422
Target: www.example.com
State: ROUND_1_TEST
Last Updated: 2026-04-22T10:30:00Z

Module Progress:
| Module    | APIs | Tested | Pending | Vulns | Priority |
|-----------|------|--------|---------|-------|----------|
| user      | 5    | 3      | 2       | 1     | high     |
| admin     | 3    | 0      | 3       | 0     | high     |
| order     | 4    | 1      | 3       | 1     | medium   |
| auth      | 2    | 2      | 0       | 0     | high     |
| content   | 3    | 0      | 3       | 0     | low      |
| workflow  | 2    | 0      | 2       | 0     | high     |

Overall: 6/19 APIs tested (31.6%)
Sensitive APIs: 2/5 tested (40%)
Vulnerabilities: 2 found

Next Action: Test pending sensitive APIs in user/admin modules
```

### 生成报告函数

```javascript
function generateProgressReport(progress) {
  const lines = [];
  lines.push("=== Test Progress Report ===");
  lines.push(`Session: ${progress.session_id}`);
  lines.push(`State: ${progress.current_state}`);
  lines.push("");
  lines.push("Module Progress:");
  lines.push("| Module    | APIs | Tested | Pending | Vulns | Priority |");
  lines.push("|-----------|------|--------|---------|-------|----------|");
  
  for (const module of progress.modules) {
    const row = [
      module.module_name.padEnd(10),
      module.stats.total.toString().padEnd(5),
      module.stats.tested.toString().padEnd(7),
      module.stats.pending.toString().padEnd(8),
      module.stats.vulnerabilities.toString().padEnd(6),
      module.module_priority
    ].join(" | ");
    lines.push(`| ${row} |`);
  }
  
  lines.push("");
  lines.push(`Overall: ${progress.overall_stats.tested}/${progress.overall_stats.total} APIs tested (${progress.overall_stats.coverage_percentage}% )`);
  lines.push(`Vulnerabilities: ${progress.overall_stats.vulnerabilities_found} found`);
  
  return lines.join("\n");
}
```

---

## 三问法则（判定继续测试）

用于Coordinator判断是否需要进入下一轮测试：

### Q1: 有未访问的重要路径？

```javascript
function checkQ1(progress) {
  // 检查敏感API未测试列表
  const untestedSensitive = progress.sensitive_apis.untested;
  
  if (untestedSensitive.length > 0) {
    return {
      answer: "YES",
      reason: `有${untestedSensitive.length}个敏感API未测试`,
      action: "NEXT_ROUND → 测试敏感API"
    };
  }
  
  // 检查高优先级模块未测试API
  for (const module of progress.modules) {
    if (module.module_priority === "high" && module.stats.pending > 0) {
      return {
        answer: "YES",
        reason: `${module.module_name}模块有${module.stats.pending}个API待测试`,
        action: "NEXT_ROUND → 测试高优先级模块"
      };
    }
  }
  
  return {
    answer: "NO",
    reason: "所有敏感和高优先级API已测试",
    action: "继续Q2判定"
  };
}
```

### Q2: 关键端点是否都测试了？

```javascript
function checkQ2(progress) {
  // 定义关键端点标准
  const criteria = {
    sensitive_coverage: 80,    // 敏感API覆盖率≥80%
    high_module_coverage: 70   // 高优先级模块覆盖率≥70%
  };
  
  // 计算敏感API覆盖率
  const sensitiveCoverage = (progress.sensitive_apis.tested / progress.sensitive_apis.total) * 100;
  
  if (sensitiveCoverage < criteria.sensitive_coverage) {
    return {
      answer: "NO",
      reason: `敏感API覆盖率${sensitiveCoverage}% < ${criteria.sensitive_coverage}%`,
      action: "NEXT_ROUND → 补充敏感API测试"
    };
  }
  
  // 检查高优先级模块
  for (const module of progress.modules) {
    if (module.module_priority === "high") {
      const moduleCoverage = (module.stats.tested / module.stats.total) * 100;
      if (moduleCoverage < criteria.high_module_coverage) {
        return {
          answer: "NO",
          reason: `${module.module_name}模块覆盖率${moduleCoverage}% < ${criteria.high_module_coverage}%`,
          action: "NEXT_ROUND → 补充模块测试"
        };
      }
    }
  }
  
  return {
    answer: "YES",
    reason: "关键端点覆盖率达标",
    action: "继续Q3判定"
  };
}
```

### Q3: 发现的漏洞是否可能组合攻击？

```javascript
function checkQ3(findings) {
  // 只有≥2个高危漏洞才考虑组合
  const highVulns = findings.filter(f => f.severity === "High" || f.severity === "Critical");
  
  if (highVulns.length < 2) {
    return {
      answer: "NO",
      reason: "高危漏洞数量不足，无组合可能",
      action: "REPORT → 生成报告"
    };
  }
  
  // 检查漏洞间依赖关系
  const combinations = analyzeCombinations(highVulns);
  
  if (combinations.length > 0) {
    return {
      answer: "YES",
      reason: `发现${combinations.length}个潜在攻击链组合`,
      action: "ROUND_3 → 验证攻击链"
    };
  }
  
  return {
    answer: "NO",
      reason: "漏洞间无明显组合关系",
      action: "REPORT → 生成报告"
    };
}

function analyzeCombinations(vulns) {
  const combinations = [];
  
  // IDOR + 信息泄露 → 账户接管
  const idor = vulns.find(v => v.type === "IDOR");
  const infoLeak = vulns.find(v => v.result.sensitive_data_exposed?.length > 0);
  if (idor && infoLeak) {
    combinations.push({
      type: "account_takeover",
      vulns: [idor.vuln_id, infoLeak.vuln_id],
      description: "IDOR获取敏感数据，可能实现账户接管"
    });
  }
  
  // 认证绕过 + 权限提升 → 完全控制
  const authBypass = vulns.find(v => v.endpoint.includes("auth") || v.endpoint.includes("login"));
  const privEscalation = vulns.find(v => v.endpoint.includes("admin") && v.tested_role !== "admin");
  if (authBypass && privEscalation) {
    combinations.push({
      type: "full_control",
      vulns: [authBypass.vuln_id, privEscalation.vuln_id],
      description: "认证绕过 + 权限提升，可能获得完全控制"
    });
  }
  
  return combinations;
}
```

---

## MongoDB操作示例

### 更新API状态

```javascript
// 发现API时
mongodb-mcp-server_update-many({
  database: "webtest",
  collection: "progress",
  filter: { session_id: "session_20260422" },
  update: {
    $push: {
      "modules.$[elem].apis": {
        api_id: "api_001",
        endpoint: "/api/users/{id}",
        test_status: "pending"
      }
    },
    $inc: {
      "modules.$[elem].stats.total": 1,
      "modules.$[elem].stats.pending": 1,
      "overall_stats.total_apis": 1,
      "overall_stats.pending": 1
    },
    $set: { last_updated: Date.now() }
  },
  arrayFilters: [{ "elem.module_name": "user" }]
})

// 测试完成时
mongodb-mcp-server_update-many({
  database: "webtest",
  collection: "progress",
  filter: { session_id: "session_20260422" },
  update: {
    $set: {
      "modules.$[module].apis.$[api].test_status": "tested",
      "modules.$[module].apis.$[api].tested_by": "Security",
      "modules.$[module].apis.$[api].tested_at": Date.now(),
      last_updated: Date.now()
    },
    $inc: {
      "modules.$[module].stats.tested": 1,
      "modules.$[module].stats.pending": -1,
      "overall_stats.tested": 1,
      "overall_stats.pending": -1
    }
  },
  arrayFilters: [
    { "module.module_name": "user" },
    { "api.api_id": "api_001" }
  ]
})
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Coordinator、Security 必须加载

1. 尝试: skill({ name: "progress-tracking" })
2. 若失败: Read("skills/data/progress-tracking/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```
