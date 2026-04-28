---
name: api-discovery
description: "API 发现方法论。以 BurpBridge 历史为主来源，页面分析线索为辅，并同步输出 confirmed_apis 与 api_hints。"
---

# API Discovery Skill

> API 发现必须建立在真实证据上。本项目中，可用于测试和分析的 API 事实以 BurpBridge 已捕获历史为主。

## 核心原则

- 不使用不存在的 `browser_network_requests`。
- 页面侧只提供 API 线索，不提供“已证实请求”。
- 真正进入测试队列的 API，必须来自 BurpBridge 历史、重放记录或已保存的真实请求详情。
- `Navigator` 输出中必须区分：
  - `site_map_report.confirmed_apis`
  - `site_map_report.api_hints`

## 发现来源优先级

1. BurpBridge HTTP history
2. BurpBridge request detail / replay detail
3. 页面 HTML、表单 action、前端配置中的接口线索

## Navigator 侧可做的辅助发现

Navigator 可以通过以下方式收集“待验证线索”：

```bash
browser-use --session admin_001 state
browser-use --session admin_001 get html
browser-use --session admin_001 eval "Array.from(document.querySelectorAll('form')).map(f => f.action)"
```

可以记录为：
- `/api/...`
- `/v1/...`
- `/workflow/...`
- `/approval/...`
- `/export/...`

这些只能进入 `api_hints`，不能直接写成 `confirmed_apis`。

## 输出边界

### `confirmed_apis`

必须满足以下任一条件：
- 已在 BurpBridge 历史中出现
- 已存在真实请求详情
- 已有安全测试或重放记录可引用

### `api_hints`

适用于以下场景：
- 页面文本直接出现接口路径
- HTML 中出现表单 `action`
- 前端配置中出现 API 前缀
- 由页面结构推导出的待验证入口

## 常见 API 模式

| 模式 | 示例 | 测试优先级 |
|------|------|-----------|
| `/api/users/{id}` | `/api/users/123` | Critical |
| `/api/orders/{id}` | `/api/orders/456` | High |
| `/api/admin/*` | `/api/admin/config` | High |
| `/api/profile/*` | `/api/profile/me` | Medium |
| `/api/workflow/*` | `/api/workflow/tasks` | High |
| `/api/data/*` | `/api/data/export` | Medium |

## 模块分类建议

- `user`: `/api/users`, `/api/profile`, `/api/account`
- `admin`: `/api/admin`, `/api/settings`, `/api/system`
- `order`: `/api/orders`, `/api/cart`, `/api/payment`
- `workflow`: `/api/workflow`, `/api/approval`, `/api/process`
- `auth`: `/api/auth`, `/api/login`, `/api/token`, `/api/session`
- `data`: `/api/data`, `/api/export`, `/api/import`, `/api/report`

## 写入建议

- `confirmed_apis` 应尽快写入 `apis` collection，并同步更新 `progress`
- `api_hints` 应写入 `site_survey.json` 或 Navigator 返回结果，等待后续验证

事件示例：

```json
{
  "event_type": "API_DISCOVERED",
  "source_agent": "Navigator Agent",
  "priority": "high",
  "payload": {
    "endpoint": "/api/users/123",
    "method": "GET",
    "module": "user",
    "evidence_source": "burp_history",
    "target_field": "confirmed_apis"
  }
}
```

## 边界说明

- 如果只有页面文字线索，没有 BurpBridge 实际请求，不要把该 API 写成“已验证请求”。
- 如果需要具体请求头、请求体、响应体，交由 Security 从 BurpBridge 历史读取。

## 加载要求

```yaml
1. 尝试: skill({ name: "api-discovery" })
2. 若失败: Read(".opencode/skills/browser/api-discovery/SKILL.md")
3. Navigator 必须加载本 Skill
```
