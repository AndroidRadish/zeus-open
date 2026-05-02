# ZeusOpen v3 Evolution Record

## 2026-05-02 — v3 Post-Stabilization Polish

**Trigger**: bionicrootSaaS 项目初始化实践中发现文档陈旧、日志空缺、环境兼容性问题。

### Changes

| # | Area | Change | Motivation |
|---|------|--------|------------|
| 1 | **AGENTS.md** | 重构为意图路由 + 渐进式披露结构 | 342 行线性文档导致 agent 每次必读全量，80% 内容无关 |
| 2 | **AGENTS.md** | 新增规则冲突优先级（P0 > P1 > P2） | 解决"动手前四问"与"直接开干"的矛盾 |
| 3 | **AGENTS.md** | 合并"完成定义"与"收尾流程" | 语义重叠，agent 分不清参考哪个 |
| 4 | **AGENTS.md** | 移除 Kimi 2.6 特化节 | 用户已切换模型，特化规则不通用 |
| 5 | **AGENTS.md** | 移除冗余的"常用命令"表 | 与 ZEUS_AGENT.md 重复，三副本维护成本高 |
| 6 | **ZEUS_AGENT.md** | node → python 优先 | 用户普遍有 python 无 node |
| 7 | **core/ai_logger.py** | 新增模块，worker 后置钩子自动生成 ai-log | ai-logs/ 此前完全靠手动写，自动化管道有缺口 |
| 8 | **core/worker.py** | 4 个出口路径（成功/异常/无效结果/部分失败）均接入 ai_logger | 无论成败都应有日志 |
| 9 | **api/server.py** | /tasks/{task_id}/logs 优先返回 ai_log_ref 文件；补上 app.state.project_root | API 一致性与可用性 |
| 10 | **workspace/base.py** | 清除 Kimi 2.6 Token 效率铁律节 | 同 AGENTS.md |
| 11 | **README.md** | 重写，v3 升级为主角，v2 压入附录，新增框架-业务分离说明 | 旧文档以 v2 为中心，v3 仍标 Beta |
| 12 | **README.zh-CN.md** | 同上，中文版同步更新 | — |

### Signals Attributed

- F-001: bionicrootSaaS 初始化 6 个信号，全部已修复
- No open items.

### Next

- 监控 ai_logger 在实际 worker 执行中的表现，确认文件写入路径与 ai_log_ref 同步正确
