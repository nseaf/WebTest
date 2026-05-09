---
name: form-handling
description: "复杂业务表单处理方法论，基于 session 复用执行填写与提交，并结合 browser-recovery 处理 tab、回跳、验证码和阻断弹窗。"
---

# Form Handling Skill

> Form 负责识别、填写和提交复杂业务表单，但不负责登录，也不负责创建浏览器实例。所有操作默认复用 Navigator 已建立的 `session_name`。

## 核心原则

- 业务表单处理默认使用 `attach_mode=reuse`
- 先 `state` 获取索引，再 `input/click/select`
- 所有 Windows 命令优先通过 `scripts/browser-use-utf8.ps1`
- 提交后必须重新核验 URL、title、DOM 和 tab 状态
- 遇到恢复型问题先调用 browser-recovery 规则，再决定是否上报 Coordinator
- 若处理过程中发现登录态失效，只能把恢复上下文完整带回给 Navigator

## 标准命令模式

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 input 3 "测试标题"
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 click 5
```

## 复杂业务表单流程

1. 使用既有 `session_name` 进入目标表单页
2. `state` 识别字段、联动控件、提交按钮
3. 先检测验证码、阻断弹窗、新 tab 风险
4. 按业务语义填写表单并提交
5. 提交后验证：
   - `tab list`
   - `get title`
   - `eval "location.href"`
   - `state`
6. 判定结果：
   - 表单提交成功
   - 表单校验失败
   - 验证码待处理
   - 需由 Navigator 先恢复认证
7. 若需恢复：
   - 返回原任务 `resume_context`
   - 不改换 session，不跳去别的模块

## 任务接口约定

- `process_complex_form`: 以 `session_name` 为主，`form_selector` / `form_context` 为辅助上下文

兼容期规则：

- 如果旧任务仍传 `cdp_url`，可记录为“bootstrap-only compatibility field”
- 不要据此重新把所有命令改回 `--cdp-url`
- 如果任务带有 `resume_context`，必须在结果中保留该字段

## 验证码与恢复

遇到以下情况先按 browser-recovery 处理：

- 点击提交后新开 tab
- 被重定向回登录页
- modal/popup 挡住输入或提交
- 页面空白或加载超时
- session 配置冲突

仅在以下情况暂停并上报：

- 需要人工验证码
- 需要用户确认异常行为
- 多轮恢复后仍无法完成表单动作

## 导航边界

- Form 可以在“完成当前表单所必需”的范围内做最小导航
- 不承担站点探索职责
- 不承担登录职责
- 不创建新 Chrome 实例
- 不直接同步 Cookie 到 BurpBridge

## 建议输出

```json
{
  "form_result": {
    "session_name": "user_001",
    "attach_mode": "reuse",
    "active_tab_index": 0,
    "final_url": "https://example.com/workflow/detail/123",
    "recovery_actions": [],
    "captcha_required": false
  }
}
```

## 加载要求

```yaml
1. 尝试: skill({ name: "form-handling" })
2. 若失败: Read(".opencode/skills/browser/form-handling/SKILL.md")
3. 本 Skill 必须加载完成才能继续执行
```
