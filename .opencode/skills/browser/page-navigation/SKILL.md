---
name: page-navigation
description: "页面导航方法论，包含显式 URL 导航、索引点击、tab 对账、域名边界判定、导航成功判定与模块化测绘顺序。"
---

# Page Navigation Skill

> Navigator 和 Form 在 Windows 下都应优先通过 `scripts/browser-use-utf8.ps1` 访问 `browser-use`，以复用项目级 session/attach 逻辑。

## 核心原则

- 先 `state`，再交互。
- 优先显式 URL 导航，其次才是索引点击。
- 所有交互默认使用 `--session {name}`；只有 `bootstrap/repair` 场景才允许 `--cdp-url`。
- `create_instance` 之前必须已经 attach 到一个可见的普通 Chrome；不接受无头会话作为前提。
- 点击后不能只看“当前 tab URL 是否变化”，必须做 tab 对账。
- 每次导航成功判定前，先执行域名边界判定。
- 外部域跳转只记录、不扩散。

## 标准命令模式

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 open https://example.com/dashboard
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 click 5
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 tab list
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 tab switch 1
```

## 点击后 tab 对账流程

### Step 1: 点击前快照

记录以下信息：
- `tab list`
- `get title`
- `eval "location.href"`
- 当前 `state`
- `windows.json` 里的 `known_tabs`

### Step 2: 执行点击

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 click 5
```

### Step 3: 点击后重新取证

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 tab list
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 get title
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 eval "location.href"
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

### Step 4: 域名边界判定

根据 `target_host + allowed_hosts` 判定：

- 命中目标主域或批准子域：继续验证导航成功
- 命中外部域名：触发 `EXTERNAL_DOMAIN_SKIPPED`
  - 若为新 tab：优先关闭新 tab 并切回安全 tab
  - 若为当前 tab：回退到上一安全 URL 或入口 URL
  - 记录外域、来源入口、恢复动作

### Step 5: tab 切换候选优先级

若出现以下任一情况，必须进入 tab 切换流程：
- URL 未变，但 tab 数量变化
- 出现新 tab
- 活动 tab 变化
- title 或 DOM 仍停留在旧页面，但点击目标明显应打开新页

尝试顺序：
1. 新出现的 tab
2. 标题/URL 最接近点击目标的 tab
3. 最近更新时间最新的非当前 tab

## 导航成功判定

满足以下任一组合即可：
- URL 变化且 title/DOM 与目标一致
- URL 未明显变化，但 DOM 明显进入新上下文
- 新 tab 切换后，title/URL/DOM 一致
- 同页局部跳转，但主要元素集合已变化

不要仅因为“原 tab URL 未变”就判定跳转失败。

## 模块化测绘顺序

每轮探索前先构建优先队列：

1. `module_targets`
2. `coverage_gaps`
3. 明确指定的 `entry_urls`
4. 登录后高价值页面
5. 角色差异相关页面
6. 历史 `pending_urls`
7. 页面分析新发现的高优先级入口
8. 低价值页面

## 去重与跳过规则

- 已访问且无新增状态价值的页面不重复进入
- 同域去重，保留不同业务语义的 query/path
- 跳过登出、下载、静态资源、明显无测试价值的外链
- 命中 `pending_urls` 时优先解决历史未完成项
- 命中外部域时只记录并回退

## 建议输出

```json
{
  "navigation_result": {
    "session_name": "admin_001",
    "attach_mode": "reuse",
    "active_tab_index": 1,
    "previous_url": "https://example.com/dashboard",
    "verified_url": "https://example.com/profile",
    "verification_signals": ["title_changed", "state_changed", "tab_switched"],
    "domain_boundary": {
      "target_host": "example.com",
      "allowed_hosts": ["example.com", "sso.example.com"],
      "decision": "allowed|external_skipped"
    },
    "recovery_actions": []
  }
}
```

## 加载要求

```yaml
1. 尝试: skill({ name: "page-navigation" })
2. 若失败: Read(".opencode/skills/browser/page-navigation/SKILL.md")
3. Navigator 与 Form 必须加载本 Skill
```
