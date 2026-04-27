---
name: form-handling
description: "表单处理方法论，Form Agent使用。基于 browser-use state/input/click 的表单识别、登录执行和验证码检测。"
---

# Form Handling Skill

> Form 负责识别与填写表单，并报告登录结果；Cookie 同步由 Navigator 执行。

## 核心原则

- 先 `state` 获取元素索引，再执行 `input` / `click`。
- 不使用 `browser_fill_form`、`browser_type(...)` 等伪原语。
- 不把选择器式命令当作主示例。
- Windows 下读取 `state` 时优先使用 `scripts/browser-use-utf8.ps1`。

## 登录执行流程

1. 读取 `config/accounts.json` 获取账号信息。
2. 使用既有 session 打开登录页。
3. 运行 `state` 识别用户名框、密码框和提交按钮索引。
4. 检测验证码。
5. 使用 `input <index> "text"` 填写凭据。
6. 使用 `click <index>` 提交。
7. 使用 `state`、`get title`、`eval "location.href"` 判断是否登录成功。
8. 返回成功、失败或需要人工处理的结果给 Coordinator。

## 推荐命令

### Windows 读取状态

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

### 登录示例

```bash
browser-use --session admin_001 open https://example.com/login
browser-use --session admin_001 state
browser-use --session admin_001 input 3 "admin@example.com"
browser-use --session admin_001 input 4 "password123"
browser-use --session admin_001 click 5
browser-use --session admin_001 wait text "控制台"
browser-use --session admin_001 get title
```

## 表单类型识别

- 登录表单：同时出现账号输入与密码输入
- 搜索表单：搜索框、过滤器、查询按钮
- 注册或资料表单：多个输入框与确认按钮
- 审批或业务表单：提交、同意、驳回、保存等动作

识别证据来源：

- `state`
- `get html`
- `eval "document.forms.length"`

## 验证码检测

可通过以下证据判断：

- `state` 中出现验证码、滑块、验证、recaptcha、geetest 相关文字
- `get html` 中出现 `captcha`、`recaptcha`、`geetest`
- 页面出现验证码 iframe 或专用容器

处理原则：

- Form 记录 `CAPTCHA_DETECTED`
- 尽量继续其他账号
- 不尝试绕过验证码

## 职责边界

- Form 负责：识别表单、填写、提交、判断结果、汇总验证码需求
- Navigator 负责：浏览器实例管理、Cookie 同步、受管 Chrome 状态维护
- Security 负责：通过 BurpBridge 消费认证上下文进行安全测试

## 加载要求

```yaml
1. 尝试: skill({ name: "form-handling" })
2. 若失败: Read(".opencode/skills/browser/form-handling/SKILL.md")
3. 此 Skill 必须加载完成才能继续执行
```
