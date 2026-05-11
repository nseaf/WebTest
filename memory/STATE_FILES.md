# 共享状态文件说明

本文档定义 Coordinator 与各 subagent 共用的 JSON 状态文件。

---

## 文件总览

| 文件 | 路径 | 作用 | 模板 |
|---|---|---|---|
| 事件队列 | `result/events.json` | 跨 Agent 异常与建议 | `memory/templates/events_template.json` |
| 站点测绘 | `result/site_survey.json` | 首轮 breadth-first 测绘与缺口记录 | `memory/templates/site_survey_template.json` |
| 窗口注册表 | `result/windows.json` | 受管浏览器窗口状态 | `memory/templates/windows_template.json` |
| 会话状态 | `result/sessions.json` | 浏览器 session 状态与 BurpBridge auth 镜像 | `memory/templates/sessions_template.json` |
| API 记录 | `result/apis.json` | 已确认与推断出的 API | `memory/templates/apis_template.json` |
| 页面记录 | `result/pages.json` | 已访问页面 | `memory/discoveries/pages.json` |
| 表单记录 | `result/forms.json` | 已发现表单 | `memory/discoveries/forms.json` |
| 链接记录 | `result/links.json` | 已发现链接 | `memory/discoveries/links.json` |
| 漏洞记录 | `result/vulnerabilities.json` | 已确认或待确认漏洞 | `memory/discoveries/vulnerabilities.json` |

---

## 1. 事件队列（`events.json`）

### 事件类型

| 事件类型 | 来源 | 优先级 | 需要用户 | 含义 |
|---|---|---|---|---|
| `CAPTCHA_DETECTED` | Form/Navigator | critical | yes | 需要人工协助 |
| `SESSION_EXPIRED` | Navigator | high | no | 浏览器 session 已失效 |
| `SESSION_STALE` | Navigator | normal | no | 浏览器 session 需要快速确认 |
| `AUTH_CONTEXT_STALE` | Security | high | no | BurpBridge auth context 已失效 |
| `CSRF_TOKEN_STALE` | Security | normal | no | Security 识别到可续链的 CSRF token 过期 |
| `CSRF_TOKEN_REFRESHED` | Security | normal | no | Security 已刷新 token 并重放 |
| `CSRF_REFRESH_FAILED` | Security | high | no | 有界 CSRF 续链失败 |
| `AUTH_CONTEXT_SNAPSHOT_MISSING` | Security | high | no | Security 需要 Navigator 重新同步 auth context |
| `AUTO_SYNC_DRIFT` | Security | high | no | BurpBridge auto-sync 漂移 |
| `LOGIN_FAILED` | Navigator | high | no | 登录失败 |
| `EXPLORATION_SUGGESTION` | Security/Analyzer | normal | no | 建议的后续探索或测试方向 |
| `VULNERABILITY_FOUND` | Security/Analyzer | high | no | 漏洞已确认 |
| `API_DISCOVERED` | Navigator | normal | no | 发现 API |
| `FORM_SUBMISSION_ERROR` | Form | normal | no | 业务表单提交失败 |
| `EXTERNAL_DOMAIN_SKIPPED` | Navigator | normal | no | 跳过范围外域名 |
| `ACCESS_SCOPE_BLOCKED` | Navigator | normal | no | 当前角色无法访问某模块/路由 |
| `SURVEY_GAP_DETECTED` | Navigator/Coordinator | high | no | 仍有高价值 survey 缺口 |
| `RECOVERY_ATTEMPTED` | Navigator | normal | no | 记录了一次恢复动作 |

优先级规则：
- `AUTH_CONTEXT_STALE` 高于 `CSRF_TOKEN_STALE`。

---

## 2. 会话状态（`sessions.json`）

### 单条会话结构

```json
{
  "session_name": "admin_001",
  "account_id": "admin_001",
  "role": "admin",
  "window_id": "window_0",
  "status": "active",
  "attach_mode": "reuse",
  "attach_completed": true,
  "visible_browser_verified": true,
  "last_verified_url": "https://example.com/dashboard",
  "last_verified_title": "Dashboard",
  "last_auth_check_at": "2026-05-11T09:00:00Z",
  "last_activity_at": "2026-05-11T09:15:00Z",
  "auth_context": {
    "headers": {
      "X-CSRF-Token": "abc123"
    },
    "cookies": {
      "session": "admin_session_abc"
    },
    "last_synced_at": "2026-05-11T09:00:00Z"
  },
  "auth_state": {
    "needs_reauth": false,
    "relogin_attempts": 0,
    "expires_at": null,
    "last_refresh_at": "2026-05-11T09:00:00Z"
  },
  "resume_context": {
    "task_type": "survey_site",
    "module": "dashboard",
    "resume_target_url": "https://example.com/dashboard",
    "pending_urls": []
  }
}
```

### 关键规则

- Navigator 负责写入浏览器来源的 session snapshot。
- `auth_context` 是 BurpBridge replay auth state 的本地镜像。
- Security 可以读取该镜像做 replay 恢复。
- Security 在刷新 CSRF header 时，必须先本地合并，再整份回写。
- 不允许在 snapshot 不完整时直接覆盖 BurpBridge auth context。

### 会话状态定义

| 状态 | 含义 |
|---|---|
| `pending` | 等待登录或 attach |
| `active` | 当前 session 可用 |
| `stale` | 需要快速确认或预刷新 |
| `expired` | 需要重新认证 |
| `failed` | 登录或恢复失败 |
| `closed` | 会话已关闭，仅保留历史信息 |

### 运行时控制字段

```json
{
  "runtime_control": {
    "auto_sync_expected": true,
    "auto_sync_verified_at": "2026-05-11T09:02:00Z",
    "auto_sync_last_repair_at": null,
    "auto_sync_owner": "security"
  }
}
```

---

## 3. 初始化建议

新测试会话启动前，Coordinator 应初始化核心状态文件：

```bash
mkdir -p result
echo '{"$schema":"events_schema","allowed_hosts":[],"events":[]}' > result/events.json
echo '{"$schema":"windows_schema","windows":[]}' > result/windows.json
echo '{"$schema":"sessions_schema","sessions":[],"runtime_control":{"auto_sync_expected":false,"auto_sync_verified_at":null,"auto_sync_last_repair_at":null,"auto_sync_owner":null},"history_progress":{}}' > result/sessions.json
echo '{"$schema":"apis_schema","apis":[]}' > result/apis.json
echo '{"$schema":"discovered_pages_schema","pages":[]}' > result/pages.json
echo '{"$schema":"site_survey_schema","allowed_hosts":[],"modules":[],"submodules":[],"entry_points":[],"role_access_matrix":[],"confirmed_apis":[],"api_hints":[],"coverage_gaps":[],"external_domains":[],"recommended_next_actions":[]}' > result/site_survey.json
echo '{"$schema":"discovered_forms_schema","forms":[]}' > result/forms.json
echo '{"$schema":"discovered_links_schema","links":[]}' > result/links.json
echo '{"$schema":"vulnerabilities_schema","vulnerabilities":[],"statistics":{"total":0,"by_severity":{"critical":0,"high":0,"medium":0,"low":0},"by_type":{"IDOR":0,"XSS":0,"SQLI":0,"COMMAND_INJECTION":0,"CSRF":0,"OTHER":0}}}' > result/vulnerabilities.json
```
