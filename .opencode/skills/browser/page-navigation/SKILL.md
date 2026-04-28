---
name: page-navigation
description: "页面导航方法论，包含显式 URL 导航、索引点击、tab 对账、导航成功判定与分层探索顺序。"
---

# Page Navigation Skill

> Navigator 和 Form 在 Windows 下都应优先通过 `scripts/browser-use-utf8.ps1` 访问 `browser-use`，以复用项目级 session/attach 逻辑。

## 核心原则

- 先 `state`，再交互。
- 优先显式 URL 导航，其次才是索引点击。
- 所有交互默认使用 `--session {name}`；只有 `bootstrap/repair` 场景才允许 `--cdp-url`。
- 点击后不能只看“当前 tab URL 是否变化”，必须做 tab 对账。
- 导航成功判定使用联合证据：URL、title、DOM 状态、tab 变化。

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

### Step 3: 点击后短等待并重新取证

```powershell
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 tab list
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 get title
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 eval "location.href"
powershell -ExecutionPolicy Bypass -File scripts/browser-use-utf8.ps1 --session admin_001 state
```

### Step 4: 判定与动作

若出现以下任一情况，必须进入 tab 切换候选流程：

- URL 未变，但 tab 数量变化
- 出现新 tab
- 活动 tab 变化
- title 或 DOM 仍停留在旧页面，但点击目标明显应打开新页

### Step 5: tab 切换候选优先级

按以下顺序尝试切换并验证：

1. 新出现的 tab
2. `tab list` 中标题/URL 最接近点击目标的 tab
3. 非当前 tab 中最近更新时间最新的 tab

切换后必须重新执行：

- `get title`
- `eval "location.href"`
- `state`

验证成功后更新：

- `sessions.json.active_tab_index`
- `sessions.json.last_verified_url`
- `sessions.json.last_verified_title`
- `windows.json.known_tabs[*]`

## 导航成功判定

导航成功满足以下任一组合即可：

- URL 变化且 title/DOM 与目标一致
- URL 未明显变化，但 DOM 明显进入新上下文
- 新 tab 被切换后，title/URL/DOM 一致
- 同页局部跳转，但页面关键元素、表单数量、主要按钮集合已变化

不要仅因为“原 tab URL 未变”就判定跳转失败。

## 分层探索顺序

Navigator 每轮探索前先构建优先队列：

1. Coordinator 或用户显式指定的路径
2. 登录后高价值页面：个人中心、设置、审批、导出、管理后台
3. 历史 `pending_urls`
4. 页面分析新发现的高优先级入口
5. 低价值页面：帮助、关于、纯展示页

## 去重与跳过规则

- 已访问且无新增状态价值的页面不重复进入
- 同域去重，保留不同业务语义的 query/path
- 跳过登出、下载、静态资源、明显无测试价值的外链
- 命中 `pending_urls` 时优先解决历史未完成项

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
    "recovery_actions": []
  }
}
```

## 加载要求

```yaml
1. 尝试: skill({ name: "page-navigation" })
2. 若失败: Read(".opencode/skills/browser/page-navigation/SKILL.md")
3. 本 Skill 必须加载完成才能继续执行
```
