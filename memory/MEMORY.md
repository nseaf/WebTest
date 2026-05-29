# WebTest Project Memory

## 项目概述

WebTest 是一个 AI-Agent Web 渗透测试系统，采用 Coordinator + Subagent + Skill 三层架构，默认按 permission-first 工作流执行 Web 探索、越权 replay、注入测试和流程审批测试。

## 当前 Agent 架构

- **Coordinator**: 主调度器，负责规划、委派、异常处理、进度跟踪和全局审视。
- **Navigator**: 浏览器/会话专家，负责 Chrome 管理、登录、会话恢复、页面探索、接口样本发现和 Cookie 同步。
- **Form**: 复杂业务表单专家，仅处理复杂业务表单，不负责登录。
- **Security**: Replay 测试专家，负责绑定 `history_entry_id`、执行 denied replay、处理 auth/CSRF 恢复。
- **Analyzer**: 只读分析专家，只分析稳定 replay 结果。
- **AccountParser**: 账号解析专家，负责解析账号、角色和权限矩阵。

## 核心状态文件

```
result/
├── permission_targets.json  # 权限中心，包含 api_evidence_samples 与 replay_matrix
├── sessions.json            # 浏览器 session 与 auth context 镜像
├── apis.json                # API 反向索引，包含 sample_ids/history_entry_ids/source_accounts
├── site_survey.json         # 测绘快照与覆盖缺口
├── events.json              # 跨 Agent 事件
└── vulnerabilities.json     # 漏洞结果
```

## 当前工作流

1. Coordinator 初始化权限中心和当前账号轮次。
2. Navigator 登录当前账号，只探索当前账号有权限的页面、操作和接口。
3. Navigator 按 `permission_key` 回填 `api_evidence_samples`；若暂时没有 Burp history，允许 `history_entry_id=null`，但必须保留 `request_fingerprint`。
4. Security 先执行 `bind_history_samples`，把 Navigator 样本绑定为稳定 `history_entry_id`。
5. Security 再消费 `api_evidence_samples[replay_ready=true]` 中当前账号应无权限的 denied backlog。
6. Replay 结果写入 `replay_matrix[permission_key|sample_id|target_account_id]`。
7. Coordinator 按 `permission_key + sample_id + target_account_id` 管理补轮次和恢复。

## 关键约束

- Navigator 进行探索和接口样本回填，不执行 replay。
- Security 进行 history 绑定和安全测试，不操作浏览器。
- 不允许所有账号先跑 Navigator、最后统一跑 Security。
- 每个账号轮次必须先 Navigator，再 Security，之后才允许切换账号。
