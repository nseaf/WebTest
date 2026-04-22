---
name: form-handling
description: "表单处理方法论，Form Agent使用。表单识别、智能填写、验证码检测、登录执行。"
---

# Form Handling Skill

> 表单处理方法论 — 表单识别、智能填写、验证码检测、登录执行

---

## 表单类型识别

| 类型 | 识别规则 | 处理策略 |
|------|---------|---------|
| **登录表单** | 包含username/password字段 | 使用accounts.json配置 |
| **注册表单** | 包含多个字段+密码确认 | 智能填写测试数据 |
| **搜索表单** | 包含search/query字段 | 简单查询测试 |
| **联系表单** | 包含name/email/message | 填写测试信息 |
| **数据表单** | 包含多个业务字段 | 按字段类型智能填写 |

### 登录表单识别

```javascript
const loginIndicators = [
  "input[type='password']",
  "input[name*='password']",
  "input[name*='passwd']",
  "input[name*='pwd']",
  "input[placeholder*='密码']",
  "input[name*='username']",
  "input[name*='email']",
  "input[name*='login']"
];

function isLoginForm(form) {
  // 必须有密码字段
  const hasPassword = form.querySelector(loginIndicators.slice(0, 5));
  
  // 必须有用户名/邮箱字段
  const hasUsername = form.querySelector(loginIndicators.slice(5));
  
  return hasPassword && hasUsername;
}
```

---

## 智能填写策略

### 字段类型与测试数据

```javascript
const fieldTestData = {
  // 文本字段
  "text": {
    username: "testuser_" + timestamp(),
    name: "测试用户",
    title: "测试标题",
    subject: "测试主题",
    message: "这是一条测试消息",
    default: "test_value_" + timestamp()
  },
  
  // 邮箱字段
  "email": "test_" + timestamp() + "@example.com",
  
  // 密码字段
  "password": {
    weak: "123456",
    medium: "password123",
    strong: "Test@123456",
    confirm: true  // 确认密码字段需要与密码一致
  },
  
  // 数值字段
  "number": {
    age: 25,
    count: 10,
    price: 100,
    default: 1
  },
  
  // 电话字段
  "tel": "13800138000",
  
  // URL字段
  "url": "https://example.com",
  
  // 日期字段
  "date": formatDate(new Date()),
  
  // 选择框
  "select": "firstOption",  // 选择第一个选项
  
  // 复选框
  "checkbox": true,  // 默认勾选
  
  // 隐藏字段
  "hidden": null  // 不修改
};
```

### 字段识别函数

```javascript
function identifyFieldType(field) {
  const type = field.type;
  const name = field.name?.toLowerCase() || "";
  const placeholder = field.placeholder?.toLowerCase() || "";
  
  // 按type属性判断
  if (type === "password") return "password";
  if (type === "email") return "email";
  if (type === "number") return "number";
  if (type === "tel") return "tel";
  if (type === "url") return "url";
  if (type === "date") return "date";
  if (type === "checkbox") return "checkbox";
  if (type === "hidden") return "hidden";
  
  // 按name属性判断
  if (name.includes("username") || name.includes("user")) return "text.username";
  if (name.includes("email")) return "email";
  if (name.includes("password") || name.includes("pwd")) return "password";
  if (name.includes("name")) return "text.name";
  if (name.includes("phone") || name.includes("tel")) return "tel";
  if (name.includes("message") || name.includes("content")) return "text.message";
  
  // 按placeholder判断
  if (placeholder.includes("邮箱")) return "email";
  if (placeholder.includes("密码")) return "password";
  if (placeholder.includes("手机")) return "tel";
  
  return "text.default";
}
```

---

## 登录执行流程

```
┌─────────────────────────────────────────────────────────────┐
│  Form Agent 登录流程                                          │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  1. 读取账号配置                                              │
│     Read("config/accounts.json")                             │
│     → 获取账号、密码、角色                                     │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  2. 获取CDP连接                                               │
│     Read("result/sessions.json")                             │
│     → browser_use_session, cdp_url                           │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  3. 导航到登录页面                                            │
│     browser-use open {login_url}                             │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  4. 获取页面快照                                              │
│     browser_snapshot(depth=2)                                │
│     → 定位表单元素                                            │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  5. 检测验证码                                                │
│     检查是否有验证码元素                                       │
│     → 有：创建CAPTCHA_DETECTED事件，等待用户                   │
│     → 无：继续填写                                            │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  6. 填写表单                                                  │
│     browser_fill_form(fields)                                │
│     或 browser_type逐个填写                                   │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  7. 提交表单                                                  │
│     browser_click(submit_button)                             │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  8. 验证登录结果                                              │
│     检查页面变化                                              │
│     → 成功：同步Cookie                                        │
│     → 失败：创建LOGIN_FAILED事件                              │
└─────────────────────────────────────────────────────────────┐
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  9. 同步Cookie到BurpBridge                                    │
│     cookies get → sessions.json → configure_auth_context     │
└─────────────────────────────────────────────────────────────┐
```

---

## 验证码检测

### 检测规则

```javascript
const captchaIndicators = [
  // 图片验证码
  "img[src*='captcha']",
  "img[alt*='验证码']",
  "img[class*='captcha']",
  
  // 验证码输入框
  "input[name*='captcha']",
  "input[placeholder*='验证码']",
  
  // 滑块验证码
  "div[class*='slider']",
  "div[class*='captcha-slider']",
  
  // 点击验证码
  "div[class*='click-captcha']",
  
  // 第三方验证码
  "iframe[src*='recaptcha']",
  "div[id*='geetest']"
];

function detectCaptcha(snapshot) {
  for (const indicator of captchaIndicators) {
    if (snapshotContains(snapshot, indicator)) {
      return {
        detected: true,
        type: identifyCaptchaType(indicator),
        element: indicator
      };
    }
  }
  
  return { detected: false };
}

function identifyCaptchaType(indicator) {
  if (indicator.includes("img")) return "image";
  if (indicator.includes("slider")) return "slider";
  if (indicator.includes("click")) return "click";
  if (indicator.includes("recaptcha") || indicator.includes("geetest")) return "third_party";
  return "unknown";
}
```

### 验证码处理流程

```
检测到验证码:
  ↓
创建CAPTCHA_DETECTED事件
  ↓
通知Coordinator
  ↓
暂停登录流程
  ↓
等待用户手动完成验证码
  ↓
用户回复"done"
  ↓
继续登录流程
```

---

## 使用browser-use填写表单

推荐使用/browser-use Skill描述任务：

```yaml
/browser-use描述任务:
"请帮我填写登录表单：
- 在用户名输入框中输入 admin_001
- 在密码输入框中输入 password123
- 点击登录按钮
- 等待页面跳转完成"

browser-use自动：
- 定位元素
- 填写字段
- 点击提交
- 等待响应
```

或使用CLI命令：

```bash
# 逐个填写
browser-use --session admin_001 type "#username" "admin_001"
browser-use --session admin_001 type "#password" "password123"
browser-use --session admin_001 click "button[type='submit']"
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Form 必须加载

1. 尝试: skill({ name: "form-handling" })
2. 若失败: Read("skills/browser/form-handling/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```