# WebTest Skills 知识库体系

> Skills是可复用的方法论模块，所有Agent共享使用。每个Skill定义特定领域的方法论、规则和最佳实践。

---

## Skills目录结构

```
.opencode/skills/
├── core/                          # 核心方法论（所有Agent必加载）
│   ├── anti-hallucination/        # 防幻觉规则
│   ├── agent-contract/            # Agent合约模板（输出格式、截断检测）
│   └── shared-browser-state/      # 共享浏览器状态机制
│
├── workflow/                      # 流程控制类Skills
│   ├── state-machine/             # 状态机定义与门控机制
│   ├── test-rounds/               # 三轮测试模型
│   └── event-handling/            # 事件处理规范
│
├── data/                          # 数据管理类Skills
│   ├── mongodb-writer/            # 实时数据库写入
│   ├── progress-tracking/         # 访问跟踪与进度控制
│   ├── api-categorization/        # API模块划分与分类
│   ├── excel-merged-cell-handler/ # Excel合并单元格处理器
│   └── permission-matrix-parser/  # 权限矩阵Excel解析
│
├── security/                      # 安全测试类Skills
│   ├── idor-testing/              # 越权测试方法论
│   ├── injection-testing/         # 注入测试方法论
│   ├── auth-context-sync/         # 认证上下文同步
│   └── vulnerability-rating/       # 漏洞严重性评级
│
└── browser/                       # 浏览器操作类Skills
    ├── page-navigation/           # 页面导航方法论
    ├── form-handling/             # 表单处理方法论
    ├── page-analysis/             # 页面分析方法论
    └── api-discovery/             # API发现方法论
```

---

## Skills加载方式

### 双通道加载模式

```yaml
加载规则：
1. 尝试: skill({ name: "{skill-name}" })
2. 若失败: Read(".opencode/skills/{category}/{skill-name}/SKILL.md")
3. Skill必须加载完成才能继续执行Agent任务
```

### 各Agent的Skills加载清单

| Agent | 必须加载的Skills |
|-------|-----------------|
| **webtest (Coordinator)** | anti-hallucination, agent-contract, state-machine, test-rounds, mongodb-writer, progress-tracking, event-handling |
| **Navigator** | anti-hallucination, agent-contract, shared-browser-state, page-navigation |
| **Scout** | anti-hallucination, agent-contract, page-analysis, api-discovery, mongodb-writer, progress-tracking, api-categorization |
| **Form** | anti-hallucination, agent-contract, shared-browser-state, form-handling, auth-context-sync, mongodb-writer |
| **Security** | anti-hallucination, agent-contract, idor-testing, injection-testing, auth-context-sync, mongodb-writer, progress-tracking, vulnerability-rating |
| **Analyzer** | anti-hallucination, agent-contract, vulnerability-rating, mongodb-writer |
| **account_parser** | anti-hallucination, agent-contract, excel-merged-cell-handler, permission-matrix-parser |

---

## 核心Skills说明

### anti-hallucination（防幻觉规则）

**核心原则**：宁可漏报，不可误报

**规则**：
- API端点必须来自实际网络请求
- 请求ID必须来自BurpBridge查询结果
- Cookie值必须来自browser-use实际输出
- 漏洞判定必须基于实际重放结果

### agent-contract（Agent合约模板）

**功能**：
- 定义Agent输出格式（HEADER + TRANSFER BLOCK + AGENT_OUTPUT_END）
- 截断检测与恢复机制
- Token预算管理
- 门控条件定义

### state-machine（状态机）

**状态**：
- INIT → PHASE_1_EXPLORE → ROUND_N_TEST → ROUND_N_EVALUATION → NEXT_ROUND/REPORT → END

**门控条件**：
- 每个状态转换有明确的验证条件
- 三问法则判定是否继续下一轮

### mongodb-writer（实时数据库写入）

**核心原则**：每发现一个数据立即写入，不等Agent完成

**Collections**：
- test_sessions、findings、apis、pages、events、progress

### progress-tracking（进度控制）

**功能**：
- API模块自动划分
- 测试状态跟踪
- 三问法则判定

---

## Skills设计原则

### 1. 单一职责

每个Skill专注于一个特定领域，不跨领域定义规则。

### 2. 可复用

多个Agent可以加载同一Skill，共享方法论。

### 3. 独立更新

修改Skill不影响Agent核心逻辑，便于维护。

### 4. 知识沉淀

方法论固化在Skill中，减少Agent文件冗余。

---

## Skills vs Agent文件

| 内容 | 位置 |
|------|------|
| 核心职责定义 | Agent文件 |
| 任务接口定义 | Agent文件 |
| Agent协作流程 | Agent文件 |
| 详细方法论 | Skill文件 |
| 工具使用规范 | Skill文件 |
| 状态管理规则 | Skill文件 |
| 输出格式规范 | Skill文件 |


---

## 使用示例

### webtest (Coordinator) Agent加载Skills

```yaml
# 在.opencode/agents/coordinator.md中定义

## Skill 加载规则（双通道，必须执行）

加载顺序：
1. anti-hallucination: skill({ name: "anti-hallucination" }) 或 Read(".opencode/skills/core/anti-hallucination/SKILL.md")
2. agent-contract: skill({ name: "agent-contract" }) 或 Read(".opencode/skills/core/agent-contract/SKILL.md")
3. state-machine: skill({ name: "state-machine" }) 或 Read(".opencode/skills/workflow/state-machine/SKILL.md")
...
```

### Scout Agent使用page-analysis Skill

```yaml
# Scout Agent加载page-analysis后，使用其中的方法

# 性能优化（来自page-analysis Skill）
browser_snapshot({ depth: 2 })  # 限制深度，避免上下文溢出

# 元素分类（来自page-analysis Skill）
识别登录入口 → 优先级P1
识别用户中心 → 优先级P1
```

---

## 维护指南

### 新增Skill

1. 创建目录：`.opencode/skills/{category}/{skill-name}/`
2. 编写SKILL.md文件
3. 在Agent文件中添加加载声明
4. 更新SKILLS.md总览

### 修改Skill

1. 直接修改SKILL.md文件
2. 不需要修改Agent文件（除非加载清单变化）
3. 测试验证修改效果

### 删除Skill

1. 删除目录和文件
2. 从Agent加载声明中移除
3. 更新SKILLS.md总览