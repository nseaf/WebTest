---
name: browser-recovery
description: "项目级浏览器恢复规则：session 配置冲突、tab 偏移、DOM 变更、空白页、登录回跳、modal 阻断与验证码中断。"
---

# Browser Recovery Skill

> Navigator 和 Form 在遇到浏览器异常时，必须先按本 Skill 自查并尝试恢复，再决定是否上报 Coordinator。

## 恢复总原则

- 先收集真实证据，再选择动作
- 优先小范围恢复，不扩大为“关闭所有实例”
- 能在当前 session/tab 内恢复就不要重建实例
- 恢复后必须重新验证 URL、title、state 和 tab 状态

## 恢复矩阵

### 1. `SESSION_CONFIG_CONFLICT`

症状：

- `browser-use` 提示 session 已存在但配置不同

处理：

1. 确认是否为已 attach session
2. 将当前命令降级为 `attach_mode=reuse`
3. 忽略重复传入的 `--cdp-url`
4. 重新执行原命令

上报条件：

- 忽略 `--cdp-url` 后仍失败

### 2. `NEW_TAB_OPENED`

症状：

- 点击后 URL 未变
- `tab list` 显示新增 tab 或活动 tab 改变

处理：

1. 执行 `tab list`
2. 切到新 tab 或最匹配目标的 tab
3. 用 `get title`、`eval "location.href"`、`state` 验证
4. 更新 `sessions.json` 和 `windows.json`

### 3. `DOM_CHANGED_WITHOUT_URL_CHANGE`

症状：

- URL 不变
- 但 title、主要按钮、表单数量或页面结构发生变化

处理：

1. 重新获取 `state`
2. 读取 `get title`
3. 必要时 `get html`
4. 若 DOM 已进入新上下文，标记导航成功

### 4. `PAGE_BLANK_OR_TIMEOUT`

症状：

- 页面空白
- `state` 无有效元素
- 长时间未出现预期内容

处理：

1. 再次读取 `state`
2. `get title`
3. 尝试 `open 当前URL` 或返回入口 URL
4. 若仍失败，标记 `PAGE_LOAD_FAILED`

### 5. `REDIRECTED_TO_LOGIN`

症状：

- 操作中被重定向回登录页

处理：

1. 验证 session 是否过期
2. 通知 Form 用当前 `session_name` 执行重新登录
3. 恢复后回到中断前 URL 或 `pending_urls`

### 6. `MODAL_BLOCKING_FLOW`

症状：

- modal/popup 覆盖页面，导致无法点击或输入

处理：

1. 通过 `state` 识别关闭按钮、取消按钮、遮罩层交互点
2. 优先关闭 modal
3. 再重新执行上一步动作

### 7. `CAPTCHA_DETECTED`

症状：

- 页面出现验证码组件、滑块、iframe 或相关文本

处理：

1. 记录验证码类型与 URL
2. Navigator/Form 停止自动提交
3. 若是批量登录，继续尝试其他账号
4. 最终汇总给 Coordinator

## 恢复结果记录

恢复后必须记录：

```json
{
  "issue": "NEW_TAB_OPENED",
  "action": "tab switch 1",
  "result": "recovered",
  "verified_url": "https://example.com/profile"
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
