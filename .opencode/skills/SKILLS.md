# WebTest Skills 知识库体系

> Skills 是可复用的方法论模块，所有 Agent 共享使用。每个 Skill 定义特定领域的规则、证据来源和执行约束。

---

## Skills 目录结构

```text
.opencode/skills/
├── core/
├── workflow/
├── data/
├── security/
└── browser/
```

## 双通道加载规则

```yaml
1. 尝试: skill({ name: "{skill-name}" })
2. 若失败: Read(".opencode/skills/{category}/{skill-name}/SKILL.md")
3. Skill 必须加载完成才能继续执行 Agent 任务
```

## 各 Agent 的 Skills 加载清单

| Agent | 必须加载的 Skills |
|-------|------------------|
| Coordinator | anti-hallucination, agent-contract, state-machine, test-rounds, mongodb-writer, progress-tracking, event-handling |
| Navigator | anti-hallucination, agent-contract, browser-use, shared-browser-state, page-navigation, page-analysis, api-discovery, browser-recovery, mongodb-writer, progress-tracking, auth-context-sync |
| Form | anti-hallucination, agent-contract, browser-use, shared-browser-state, form-handling, browser-recovery, mongodb-writer |
| Security | anti-hallucination, agent-contract, idor-testing, injection-testing, auth-context-sync, mongodb-writer, progress-tracking, vulnerability-rating, burpbridge-api-reference, sensitive-api-detection |
| Analyzer | anti-hallucination, agent-contract, vulnerability-rating, mongodb-writer |
| account_parser | anti-hallucination, agent-contract, excel-merged-cell-handler, permission-matrix-parser |

## 关键约定

- `browser-use` 官方 skill 负责 CLI 语义；项目内 browser skills 负责受管 Chrome、session、recovery 和 CDP 约束。
- Chrome 启动优先通过 `scripts/start-managed-chrome.ps1`，统一追加 `--no-first-run` 与 `--no-default-browser-check`。
- `browser-use` 语义以官方 skill 为准。
- 本项目只在其之上补充 Navigator 管理的受管 Chrome、代理和 CDP 约束。
- `session_name` 是浏览器操作主键；`cdp_url` 仅用于 `bootstrap/repair` attach。
- Windows 下浏览器命令优先通过 `scripts/browser-use-utf8.ps1`，以复用项目级 attach 兼容逻辑。
- 点击后必须执行 `tab list` 对账；不要仅凭原 tab URL 是否变化判断导航成功。
- 页面与表单交互的事实来源以 `browser-use state` 为主，必要时辅以 `get html`、`eval`、`get title`、`screenshot`。
- API 事实来源以 BurpBridge 历史为主；页面侧只能提供 API 线索。
- Cookie 同步职责属于 Navigator，不属于 Form。
- Scout 已合并到 Navigator，活跃运行面不再单列 Scout。

## 使用示例

### Navigator 进行页面分析

```yaml
# 加载 page-analysis 后，优先使用真实 CLI 输出

browser-use --session admin_001 state
browser-use --session admin_001 get html
browser-use --session admin_001 eval "location.href"
```

### Windows 下读取 browser-use 文本输出

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --attach-mode bootstrap --session admin_001 --cdp-url http://localhost:9222 open https://example.com
```

### API 发现边界

- 允许：记录页面里显式出现的 `/api/...` 线索
- 允许：从 BurpBridge 历史确认真实请求后写入 `apis`
- 禁止：依赖 `browser_network_requests` 等不存在的原语

## Skills 与 Agent 文件的分工

| 内容 | 位置 |
|------|------|
| 核心职责定义 | Agent 文件 |
| 任务接口定义 | Agent 文件 |
| Agent 协作流程 | Agent 文件 |
| 方法论与证据来源 | Skill 文件 |
| 工具使用规范 | Skill 文件 |
| 状态管理规则 | Skill 文件 |
| 输出格式规范 | Skill 文件 |
