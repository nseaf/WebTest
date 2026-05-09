# 共享状态文件规范

本文档定义 Agent 间通信使用的核心状态文件格式、读写时机和注意事项。

---

## 文件路径总览

| 文件 | 路径 | 用途 | 模板位置 |
|------|------|------|----------|
| 事件队列 | `result/events.json` | Agent间异步通信 | `memory/templates/events_template.json` |
| 全貌测绘 | `result/site_survey.json` | 首轮测绘与补测聚合快照 | `memory/templates/site_survey_template.json` |
| 窗口注册 | `result/windows.json` | 多标签页管理 | `memory/templates/windows_template.json` |
| 会话状态 | `result/sessions.json` | 浏览器登录状态、认证上下文、恢复上下文 | `memory/templates/sessions_template.json` |
| API发现 | `result/apis.json` | 发现的API端点 | `memory/templates/apis_template.json` |
| 页面记录 | `result/pages.json` | 访问过的页面 | `memory/discoveries/pages.json` |
| 表单记录 | `result/forms.json` | 发现的表单 | `memory/discoveries/forms.json` |
| 链接记录 | `result/links.json` | 发现的链接 | `memory/discoveries/links.json` |
| 漏洞记录 | `result/vulnerabilities.json` | 发现的漏洞 | `memory/discoveries/vulnerabilities.json` |

---

## 1. 事件队列 (events.json)

### 事件类型定义

| 事件类型 | 来源 Agent | 优先级 | 需要用户操作 |
|----------|-----------|--------|--------------|
| CAPTCHA_DETECTED | Form/Navigator | critical | ✅ 是 |
| SESSION_EXPIRED | Navigator | high | ❌ 否 |
| SESSION_STALE | Navigator | normal | ❌ 否 |
| AUTH_CONTEXT_STALE | Security | high | ❌ 否 |
| AUTO_SYNC_DRIFT | Security | high | ❌ 否 |
| LOGIN_FAILED | Navigator | high | ❌ 否 |
| EXPLORATION_SUGGESTION | Security/Analyzer | normal | ❌ 否 |
| VULNERABILITY_FOUND | Security | high | ❌ 否 |
| API_DISCOVERED | Navigator | normal | ❌ 否 |
| FORM_SUBMISSION_ERROR | Form | normal | ❌ 否 |
| EXTERNAL_DOMAIN_SKIPPED | Navigator | normal | ❌ 否 |
| ACCESS_SCOPE_BLOCKED | Navigator | normal | ❌ 否 |
| SURVEY_GAP_DETECTED | Navigator/Coordinator | high | ❌ 否 |
| RECOVERY_ATTEMPTED | Navigator | normal | ❌ 否 |

---

## 2. 会话状态 (sessions.json)

### 会话记录格式

```json
{
  "session_name": "admin_001",
  "account_id": "admin_001",
  "role": "admin",
  "window_id": "window_0",
  "status": "active",
  "attach_status": "attached",
  "attach_mode": "reuse",
  "cdp_url": "http://127.0.0.1:9222",
  "chrome_pid": 12345,
  "last_verified_url": "https://example.com/dashboard",
  "last_verified_title": "Dashboard",
  "last_auth_check_at": "2026-05-09T10:00:00Z",
  "last_activity_at": "2026-05-09T10:30:00Z",
  "auth_state": {
    "needs_reauth": false,
    "relogin_attempts": 0,
    "expires_at": null,
    "last_refresh_at": "2026-05-09T10:00:00Z"
  },
  "resume_context": {
    "task_type": "survey_site",
    "module": "dashboard",
    "resume_target_url": "https://example.com/dashboard",
    "pending_urls": []
  }
}
```

### 会话状态定义

| 状态 | 说明 |
|------|------|
| pending | 待登录或待attach |
| active | 会话有效，可正常使用 |
| stale | 会话需要快速确认或预刷新 |
| expired | 会话已过期，需要重新登录 |
| failed | 登录失败 |
| closed | 会话已关闭，仅保留历史记录 |

### 运行时控制字段

```json
{
  "runtime_control": {
    "auto_sync_expected": true,
    "auto_sync_verified_at": "2026-05-09T10:02:00Z",
    "auto_sync_last_repair_at": null,
    "auto_sync_owner": "security"
  }
}
```

---

## 3. 初始化建议

测试会话开始前，Coordinator 应初始化核心状态文件：

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
