# Web渗透测试系统 - 功能规划

## 当前版本: v0.1

### 已实现功能

- [x] Coordinator Agent - 任务规划和协调
- [x] Navigator Agent - 页面导航和链接跟踪
- [x] Scout Agent - 页面结构分析
- [x] Form Agent - 表单识别和处理
- [x] 会话状态管理
- [x] 发现记录存储 (pages.json, forms.json, links.json)
- [x] 测试报告生成

### 性能优化

- [x] 使用 `depth` 参数控制快照深度
- [x] 使用 `filename` 参数保存大响应到文件

---

## 待实现功能

### 优先级 P0 - 核心功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 深度探索 | 支持配置探索深度和页面数量限制 | ✅ 已实现 |
| 去重机制 | URL规范化去重，避免重复访问 | ✅ 已实现 |
| 错误处理 | 导航失败、表单提交失败的处理 | ✅ 已实现 |

### 优先级 P1 - 增强功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 登录态保持 | 支持Cookie管理，保持登录状态 | 待实现 |
| API发现 | 分析网络请求，发现隐藏API | 待实现 |
| 安全检测 | XSS/SQL注入/CSRF等基础检测 | 待实现 |
| 多标签页处理 | 处理新窗口/标签页打开 | 待实现 |

### 优先级 P2 - 辅助功能

| 功能 | 描述 | 状态 |
|------|------|------|
| 截图功能 | 页面/元素截图存档 | 暂不启用 |
| 代理支持 | 支持HTTP/SOCKS代理 | 待实现 |
| 移动端模拟 | 模拟移动设备访问 | 待实现 |
| 并行探索 | 多页面并行探索 | 待实现 |

---

## 功能说明

### 截图功能 (暂不启用)

**状态**: 已移除，后续按需添加

**原因**:
- 截图占用较多存储空间
- 截图可能增加token消耗
- 当前阶段以文本分析为主

**恢复方式**:
当需要截图功能时，可在以下文件中恢复相关代码:
- `agents/scout.md` - 页面截图规范
- `agents/navigator.md` - 导航截图记录
- `agents/form.md` - 表单提交前后截图

**Playwright MCP 截图能力**:
```javascript
// 整页截图
browser_take_screenshot({ filename: "page.png", type: "png" })

// 元素截图
browser_take_screenshot({
  element: "搜索框",
  ref: "e35",
  filename: "element.png"
})

// 全页滚动截图
browser_take_screenshot({ fullPage: true, filename: "full.png" })
```

---

## 架构设计

### Agent 通信流程

```
┌─────────────────────────────────────────────────────┐
│                  Coordinator Agent                   │
│  (规划、协调、监控)                                   │
└─────────────────┬───────────────────────────────────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Navigator│ │  Scout  │ │   Form  │
   │  Agent  │ │  Agent  │ │  Agent  │
   └─────────┘ └─────────┘ └─────────┘
        │         │         │
        └─────────┼─────────┘
                  ▼
         ┌────────────────┐
         │  Result Store  │
         │  (result/)     │
         └────────────────┘
```

### 数据存储结构

```
WebTest/
├── agents/                 # Agent定义 (提交git)
├── memory/                 # 模板文件 (提交git)
│   ├── sessions/
│   │   └── session_template.json
│   └── discoveries/
│       ├── pages.json      # 空模板
│       ├── forms.json      # 空模板
│       └── links.json      # 空模板
├── reports/                # 报告模板 (提交git)
│   └── report_template.md
├── result/                 # 测试结果 (不提交git)
│   ├── session_xxx.json    # 测试会话状态
│   ├── pages.json          # 发现的页面
│   ├── forms.json          # 发现的表单
│   ├── links.json          # 发现的链接
│   └── xxx_report.md       # 测试报告
└── ROADMAP.md              # 功能规划
```

---

## 更新日志

### 2026-04-12
- 初始版本发布
- 完成百度探索测试
- 移除截图功能（暂不启用）
- 添加性能优化策略文档
- 重构数据存储结构：测试数据移至 `result/` 目录
- 明确 `memory/` 和 `reports/` 只保留模板文件
