---
name: page-analysis
description: "页面分析方法论，Navigator Agent 使用。基于 browser-use state/get html/eval 提取页面结构、模块线索、角色可达性与 API 线索。"
---

# Page Analysis Skill

> 页面分析关注真实可执行的 CLI 输出；不要引用不存在的 `browser_snapshot` 或 `browser_network_requests`。

## 核心原则

- 页面元素事实来源优先级：
  - `browser-use state`
  - `browser-use get html`
  - `browser-use get title`
  - `browser-use eval "js code"`
  - `browser-use screenshot`
- 页面侧只能提供 API 线索；可测试的 API 事实仍以 BurpBridge 历史为准。
- 测绘阶段必须输出模块、子模块、入口和角色可达性，而不只是页面列表。

## 分析流程

1. 读取当前页面状态：

```bash
browser-use --session admin_001 state
browser-use --session admin_001 get title
browser-use --session admin_001 eval "location.href"
```

2. 需要更多结构信息时读取 HTML：

```bash
browser-use --session admin_001 get html
```

3. 需要精确读取上下文时使用 `eval`：

```bash
browser-use --session admin_001 eval "document.forms.length"
browser-use --session admin_001 eval "Array.from(document.querySelectorAll('nav a, aside a')).map(a => ({text:a.innerText, href:a.href}))"
```

4. 记录以下信息：
- 页面属于哪个模块/子模块
- 链接、表单、按钮、潜在敏感功能入口
- 当前角色是否可见、可点、可进入
- 页面侧 API 线索

5. 将页面发现写入 `pages` collection，并补充 `site_map_report`

## 元素识别建议

从 `state` 中重点关注：
- 一级导航、侧边栏、面包屑
- 个人中心、账户、用户管理
- 设置、配置、审批、导出、管理后台
- 列表、详情页入口
- 搜索框、过滤器、提交按钮

从 `get html` 或 `eval` 中补充：
- 表单 `action`
- 隐藏字段
- 页面中的显式 API 路径
- 板块标题、标签页、权限提示文本

## 模块化产出建议

### 模块识别

- `modules`: 一级业务板块，如 `workflow`, `admin`, `profile`
- `submodules`: 具体功能点，如 `workflow.approval-list`, `workflow.approval-detail`
- `entry_points`: 导航入口、按钮入口、直接 URL 入口

### 角色可达性

每个关键入口至少记录一种状态：
- `visible_and_accessible`
- `visible_but_blocked`
- `hidden`
- `readonly`
- `needs_form_or_search`

## 页面分析结果建议格式

```json
{
  "page_url": "https://example.com/dashboard",
  "page_title": "Dashboard",
  "page_type": "dashboard",
  "module": "workflow",
  "submodule": "workflow.approval-list",
  "links": [
    {
      "label": "审批管理",
      "interaction": "click index 5",
      "priority": "high"
    }
  ],
  "forms": [
    {
      "type": "search",
      "evidence": "state index 9"
    }
  ],
  "role_access": {
    "role": "user",
    "status": "visible_but_blocked",
    "evidence": "页面提示无权限"
  },
  "api_hints": [
    {
      "path": "/api/workflow/tasks",
      "source": "page_html"
    }
  ]
}
```

## site_map_report 补充规则

- `confirmed_apis`: 仅记录 BurpBridge 已证实接口
- `api_hints`: 页面侧线索
- `coverage_gaps`: 记录模块未完成原因，如：
  - `blocked_by_role`
  - `external_domain_redirect`
  - `needs_form_submission`
  - `page_load_failed`
  - `captcha_blocked`

## 加载要求

```yaml
1. 尝试: skill({ name: "page-analysis" })
2. 若失败: Read(".opencode/skills/browser/page-analysis/SKILL.md")
3. Navigator 必须加载本 Skill
```
