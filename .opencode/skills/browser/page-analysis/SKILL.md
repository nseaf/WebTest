---
name: page-analysis
description: "页面分析方法论，Navigator Agent使用。基于 browser-use state/get html/eval 提取页面结构与交互线索。"
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
- 发现 API 时，页面侧只能提供线索；可测试的 API 事实应以 BurpBridge 历史为准。
- Navigator 负责页面分析，因为 Scout 已合并到 Navigator。

## 分析流程

1. 读取当前页面状态：

```bash
browser-use --session admin_001 state
browser-use --session admin_001 get title
```

2. 需要更多结构信息时读取 HTML：

```bash
browser-use --session admin_001 get html
```

3. 需要精确读取当前 URL、表单数量或页面变量时使用 `eval`：

```bash
browser-use --session admin_001 eval "location.href"
browser-use --session admin_001 eval "document.forms.length"
```

4. 记录链接、表单、按钮、潜在敏感功能入口。
5. 将页面发现写入 `pages` collection，并为下一轮导航或安全测试生成建议。

## 元素识别建议

从 `state` 中重点关注：

- 登录入口
- 个人中心、账户、用户管理
- 设置、配置、审批、导出
- 表格、列表、详情页入口
- 提交按钮、搜索框、过滤器

从 `get html` 或 `eval` 中补充：

- 表单 `action`
- 隐藏字段
- 页面中的显式 API 路径、下载链接、审批节点标识

## 推荐命令模式

### Windows 文本读取

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

### 结构补充

```bash
browser-use --session admin_001 get html
browser-use --session admin_001 eval "Array.from(document.querySelectorAll('form')).map(f => ({ action: f.action, method: f.method }))"
```

### 视觉确认

```bash
browser-use --session admin_001 screenshot
```

## API 线索与边界

允许记录的页面侧 API 线索：

- 页面文本或 HTML 中直接出现的 `/api/...`、`/v1/...` 路径
- 表单 `action`
- 前端配置中的接口前缀

不允许把以下内容当作“已证实 API”：

- 猜测的接口路径
- 并未被 BurpBridge 捕获的网络请求
- 来自伪工具输出的请求列表

## 页面分析结果建议格式

```json
{
  "page_url": "https://example.com/dashboard",
  "page_title": "Dashboard",
  "page_type": "dashboard",
  "links": [
    {
      "label": "个人中心",
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
  "api_hints": [
    {
      "path": "/api/users/list",
      "source": "page_html"
    }
  ]
}
```

## 加载要求

```yaml
1. 尝试: skill({ name: "page-analysis" })
2. 若失败: Read(".opencode/skills/browser/page-analysis/SKILL.md")
3. 此 Skill 必须加载完成才能继续执行
```
