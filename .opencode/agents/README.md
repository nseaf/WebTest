# Agent 快速启动指南

## 启动 Coordinator Agent

作为Coordinator Agent启动测试流程，请按以下步骤操作：

### 1. 初始化测试会话

首先创建一个新的会话文件：
```bash
# 复制模板创建新会话
cp memory/sessions/session_template.json memory/sessions/session_$(date +%Y%m%d_%H%M%S).json
```

### 2. 启动测试

在Claude Code中输入以下指令启动Coordinator：

```
你现在扮演Coordinator Agent角色。

请阅读 /Users/fizz/projects/WebTest/agents/coordinator.md 了解你的职责。

目标URL: https://www.baidu.com

请开始规划并执行Web探索测试。
```

### 3. Coordinator 工作流程

Coordinator应该按以下顺序调用子Agent：

1. **Navigator Agent** - 访问目标URL
   ```
   请扮演Navigator Agent。
   阅读 /Users/fizz/projects/WebTest/agents/navigator.md
   任务: 导航到 https://www.baidu.com
   ```

2. **Scout Agent** - 分析页面
   ```
   请扮演Scout Agent。
   阅读 /Users/fizz/projects/WebTest/agents/scout.md
   任务: 分析当前页面，发现链接和表单
   ```

3. **Form Agent** - 处理表单
   ```
   请扮演Form Agent。
   阅读 /Users/fizz/projects/WebTest/agents/form.md
   任务: 处理发现的表单
   ```

### 4. 记录发现

每次发现后，更新相应的记录文件：
- 新页面: `memory/discoveries/pages.json`
- 新表单: `memory/discoveries/forms.json`
- 新链接: `memory/discoveries/links.json`

## Playwright MCP 工具

可用的浏览器操作工具：

| 工具 | 用途 |
|------|------|
| `mcp__playwright__playwright_navigate` | 导航到URL |
| `mcp__playwright__playwright_screenshot` | 页面截图 |
| `mcp__playwright__playwright_click` | 点击元素 |
| `mcp__playwright__playwright_fill` | 填写输入框 |
| `mcp__playwright__playwright_get_html` | 获取HTML |
| `mcp__playwright__playwright_evaluate` | 执行JavaScript |

## 测试检查点

### Phase 1 验证
- [ ] 能成功导航到百度首页
- [ ] 能截取页面截图
- [ ] 能获取页面HTML内容

### Phase 2 验证
- [ ] Coordinator能制定探索计划
- [ ] Coordinator能调用子Agent
- [ ] 能发现首页的主要链接

### 最终验证
- [ ] 自主发现5个以上页面
- [ ] 识别并测试搜索功能
- [ ] 发现登录/注册入口
- [ ] 生成完整的探索报告
