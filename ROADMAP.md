# WebTest 功能规划

## 当前基线

WebTest 当前采用 Coordinator + 5 个 subagent 的三层架构：Navigator、Form、Security、Analyzer、AccountParser。Scout 能力已合并到 Navigator，不再作为独立 Agent 调度。

默认工作流为 permission-first：

1. AccountParser 解析账号、角色和权限矩阵。
2. Coordinator 初始化 `permission_targets.json` 并按权限板块/账号轮次调度。
3. Navigator 登录当前账号，探索当前账号有权限的页面、操作和接口。
4. Navigator 按 `permission_key` 回填 `api_evidence_samples`。
5. Security 执行 `bind_history_samples`，绑定 Burp `history_entry_id`。
6. Security 消费 ready 样本执行 denied replay。
7. Coordinator 按 `permission_key + sample_id + target_account_id` 管理补轮次、deferred 和 final stage。

## 已实现能力

- Coordinator 强制委派与全局审视。
- Navigator 统一负责 Chrome 生命周期、登录、会话恢复、站点测绘、接口样本发现和 Cookie 同步。
- Form 收缩为复杂业务表单专用 Agent，不负责登录。
- Security 负责 history 样本绑定、replay 测试、`AUTH_CONTEXT_STALE`、CSRF 续链。
- Analyzer 只分析稳定 replay 结果。
- `result/permission_targets.json` 作为权限中心运行态，包含 `api_evidence_samples` 与 `replay_matrix`。
- `result/apis.json` 支持 `sample_ids`、`history_entry_ids`、`source_accounts`、`source_roles` 反向索引。
- 项目级 MongoDB 数据库约定为 `webtest_<project_key>`。

## 下一步重点

| 优先级 | 任务 | 说明 |
|---|---|---|
| P0 | 身份索引完善 | 建立权限-角色-账号多对多快速索引，支持账号多角色与角色多权限 |
| P0 | 样本绑定稳定性 | 强化 `bind_history_samples` 的匹配规则、时间窗口和冲突处理 |
| P1 | 补轮次规划 | 基于 `replay_matrix` 自动生成第二轮/第三轮反向补测 |
| P1 | MongoDB 查询镜像 | 将 `api_evidence_samples`、`replay_matrix`、round progress 镜像写入项目库 |
| P2 | 报告增强 | 报告中展示权限点覆盖率、接口样本覆盖率和账号 replay 矩阵 |

## 关键约束

- 不允许所有账号先跑 Navigator、最后统一跑 Security。
- 每个账号轮次必须执行 Navigator -> Security history binding -> Security denied replay。
- Navigator 不执行 replay；Security 不操作浏览器。
- 不可逆动作使用 final stage 的 intercept-first 流程。
