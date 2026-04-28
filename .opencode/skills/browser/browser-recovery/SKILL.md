---
name: browser-recovery
description: "项目级浏览器恢复规则：session 配置冲突、tab 偏移、DOM 变更、空白页、登录回跳、modal 阻断、外域跳转与测绘权限阻断。"
---

# Browser Recovery Skill

> Navigator 和 Form 在遇到浏览器异常时，必须先按本 Skill 自查并尝试恢复，再决定是否上报 Coordinator。

## 恢复总原则

- 先收集真实证据，再选择动作
- 优先小范围恢复，不扩大为“关闭所有实例”
- 能在当前 session/tab 内恢复就不要重建实例
- 恢复后必须重新验证 URL、title、state 和 tab 状态
- 默认最多尝试两轮本地恢复；第二轮失败再升级

## 恢复矩阵

### 1. `SESSION_CONFIG_CONFLICT`

1. 确认是否为已 attach session
2. 降级为 `attach_mode=reuse`
3. 忽略重复传入的 `--cdp-url`
4. 重试原命令

### 1.1 `HEADLESS_FALLBACK_DETECTED`

1. 如果 create_instance 后无法证明已 attach 到外部可见 Chrome，立即视为异常
2. 检查是否缺失 `cdp_url`、`chrome_pid` 或 visible browser 证据
3. 优先回到显式启动 Chrome + bootstrap attach
4. 不允许保留无头 session 继续主流程

### 2. `NEW_TAB_OPENED`

1. 执行 `tab list`
2. 切到新 tab 或最匹配目标的 tab
3. 用 `get title`、`eval "location.href"`、`state` 验证
4. 更新 `sessions.json` 和 `windows.json`

### 3. `DOM_CHANGED_WITHOUT_URL_CHANGE`

1. 重新获取 `state`
2. 读取 `get title`
3. 必要时 `get html`
4. 若 DOM 已进入新上下文，标记导航成功

### 4. `PAGE_BLANK_OR_TIMEOUT`

1. 再次读取 `state`
2. `get title`
3. 尝试 `open 当前 URL` 或回到入口 URL
4. 仍失败则标记 `PAGE_LOAD_FAILED`

### 5. `REDIRECTED_TO_LOGIN`

1. 验证 session 是否过期
2. 通知 Form 用当前 `session_name` 重新登录
3. 恢复后回到中断前 URL 或 `pending_urls`

### 6. `MODAL_BLOCKING_FLOW`

1. 通过 `state` 识别关闭/取消/遮罩层交互点
2. 优先关闭 modal
3. 重新执行上一步动作

### 7. `EXTERNAL_DOMAIN_SKIPPED`

1. 记录外域 URL、来源页面、来源入口
2. 若为新 tab，关闭该 tab 并切回上一安全 tab
3. 若为当前 tab，回到上一安全 URL 或入口 URL
4. 标记该入口为“已检查但外域跳转”
5. 生成 `EXTERNAL_DOMAIN_SKIPPED` 事件

### 8. `ACCESS_SCOPE_BLOCKED`

1. 记录当前角色、模块、入口、阻断证据
2. 不重试同一入口超过两次
3. 如其他角色未验证，建议 `verify_role_access`
4. 生成 `ACCESS_SCOPE_BLOCKED` 或 `SURVEY_GAP_DETECTED`

### 9. `CAPTCHA_DETECTED`

1. 记录验证码类型与 URL
2. Navigator/Form 停止自动提交
3. 批量登录场景继续处理其他账号
4. 最终汇总给 Coordinator

## 恢复结果记录

```json
{
  "issue": "EXTERNAL_DOMAIN_SKIPPED",
  "attempt": 1,
  "action": "tab close + tab switch 0",
  "result": "recovered",
  "verified_url": "https://example.com/dashboard"
}
```

## 需要上报 Coordinator 的情况

- 恢复动作需要跨 Agent 协作
- 需要用户介入
- 同一问题连续两轮恢复失败
- 会话状态已无法信任，需要重新创建实例

## 加载要求

```yaml
1. 尝试: skill({ name: "browser-recovery" })
2. 若失败: Read(".opencode/skills/browser/browser-recovery/SKILL.md")
3. Navigator 与 Form 必须加载本 Skill
```
