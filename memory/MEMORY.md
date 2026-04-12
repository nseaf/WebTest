# WebTest Project Memory

## 项目概述
这是一个AI-Agent Web渗透测试系统，使用层级式多Agent架构进行自动化Web安全测试。

## 系统架构
- **Coordinator Agent**: 任务规划与协调（主控制器）
- **Scout Agent**: 页面分析与元素识别
- **Form Agent**: 表单处理与智能填写
- **Navigator Agent**: 页面导航与状态管理

## Agent定义文件
- `/agents/coordinator.md` - 协调者Agent定义
- `/agents/scout.md` - 侦查Agent定义
- `/agents/form.md` - 表单Agent定义
- `/agents/navigator.md` - 导航Agent定义

## 数据存储结构
```
memory/
├── sessions/          # 测试会话记录
├── discoveries/       # 发现记录
│   ├── pages.json    # 页面发现
│   ├── forms.json    # 表单发现
│   └── links.json    # 链接发现
```

## 工作流程
1. Coordinator接收目标URL
2. Navigator访问目标页面
3. Scout分析页面结构
4. Form处理发现的表单
5. 循环直到探索完成

## 测试目标
- 主目标: www.baidu.com
- 验证目标: 能自主发现并访问至少5个页面

## 配置参数
- max_depth: 3
- max_pages: 50
- timeout_ms: 30000
- same_domain_only: true

## 开发阶段
- [x] Phase 1: 环境准备
- [ ] Phase 2: Coordinator Agent
- [ ] Phase 3: Navigator Agent
- [ ] Phase 4: Scout Agent
- [ ] Phase 5: Form Agent
- [ ] Phase 6: 百度实战测试
