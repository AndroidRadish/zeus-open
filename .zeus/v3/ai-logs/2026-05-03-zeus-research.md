# 2026-05-03 zeus-research — 框架开源友好化与开发体验增强

## 目标

对 `zeus-open` 仓库进行开源友好化和开发体验改进，降低社区贡献门槛，提升 Dashboard 日志可读性与 AI Agent 协作流畅度。

## 实现

| 领域 | 改动 | 文件 |
|------|------|------|
| 文档开源化 | README 整体重构，补充英文镜像，精简商业色彩表达 | `README.md`（-409/+211），`README.zh-CN.md` |
| ai-log 格式增强 | 引入表格排版、emoji 状态徽章、可折叠原始负载 | `core/ai_logger.py`（+85/-53） |
| Dashboard 日志渲染 | 接入 github-markdown-css + highlight.js，日志弹窗和抽屉改为 markdown 渲染 | 10 个前端文件（+213/-196） |
| dispatch 修复 | brace 转义、wave-advance CLI 兼容、ws_manager 分离初始化 | `core/dispatch.py`, `run.py` |
| 自动 wave advance | ai-log 粗体完成标记、Agent 进度指令嵌入、结束后自动推进 | `core/dispatch.py`（+87），`AGENTS.md` |

### Commits

| SHA | Message |
|-----|---------|
| `021965b` | docs: rewrite README for open-source clarity, add zh-CN mirror |
| `9cae6e6` | feat(v3): rich ai-log format with tables, emoji badges, collapsible raw payloads |
| `f6fb283` | feat(v3-dashboard): github-markdown-css + highlight.js for log readability |
| `3602e2c` | fix(v3-dispatch): fix brace escaping, wave-advance CLI, separate ws_manager init |
| `dbfde55` | feat(v3): ai-log bold in completion, agent progress instruction, auto wave advance |

## 验证

- README 双语镜像内容完整，语法检查通过
- `npm run build` 零错误，Dashboard 日志渲染正常
- `python .zeus/v3/scripts/run.py --status` 输出正常，现存 22 个 task 状态不变
