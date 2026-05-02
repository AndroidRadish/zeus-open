# Zeus - AI 项目演化操作系统

[![语言](https://img.shields.io/badge/language-English%20%7C%20%E4%B8%AD%E6%96%87-blue)](README.md)
[![工作流](https://img.shields.io/badge/workflow-init%E2%86%92brainstorm%E2%86%92plan%E2%86%92execute%E2%86%92feedback-green)](#工作流)
[![v3](https://img.shields.io/badge/v3-stable-success)](#v3-控制台)
[![许可证](https://img.shields.io/badge/license-MIT-lightgrey)](#许可证)

用于长期项目交付的结构化、版本化 AI 研发框架。

Zeus 核心能力：
- **意图驱动** — 说"看看进度"或"执行下一个 task"，不需要斜杠命令
- **波次执行** — 任务按依赖顺序运行，可并行处并行
- **反馈闭环** — 线上信号驱动版本演化

语言切换：[English](README.md) | [简体中文](README.zh-CN.md)

---

## 快速开始（v3）

Zeus 支持**所有 AI 平台**（DeepSeek、GPT、Claude、Gemini、Kimi、GLM）。用自然语言跟你的 AI 交流即可。

### 1) 初始化项目

```bash
python .zeus/v3/scripts/run.py --project-root . --init
```

生成 `.zeus/v3/config.json`、`task.json`、`state.db`——业务项目仅需这 3 个文件。

### 2) 规划任务

编辑 `.zeus/v3/task.json` 填入任务，或者直接告诉 AI：

> "帮我规划一下这个 landing page 的任务"

Zeus 会自动把 spec 拆成带依赖关系的任务 DAG。

### 3) 导入 & 验证

```bash
python .zeus/v3/scripts/run.py --project-root . --import-only
python .zeus/v3/scripts/run.py --project-root . --status
```

### 4) 启动控制台

```bash
python .zeus/v3/scripts/run.py --mode serve --host 0.0.0.0 --port 8234
```

打开 `http://127.0.0.1:8234/dashboard`。

### 5) 执行

```bash
# 执行所有待办任务
python .zeus/v3/scripts/run.py --project-root . --max-workers 3

# 只执行某个 wave
python .zeus/v3/scripts/run.py --project-root . --wave 2 --max-workers 3
```

AI 会读取 `.zeus/ZEUS_AGENT.md` 学习 Zeus 协议，自动处理后续步骤。

---

## 核心概念

### 工作流

```
init → discover → brainstorm → plan → execute → feedback → evolve
         ↑                                              |
         └──────────────────────────────────────────────┘
```

1. **init** — 初始化北极星指标与项目配置
2. **discover** *（可选）* — 为老项目扫描已有代码
3. **brainstorm** — 写 spec 到 `.zeus/{version}/specs/*.md`
4. **plan** — 将 spec 拆为 story、task、wave DAG
5. **execute** — 调度器 + Worker 池按依赖顺序执行
6. **feedback** — 采集线上信号，归因到具体 task
7. **evolve** — 基于学习创建新版本轨道

### 自然语言意图

| 意图 | 示例 | 执行内容 |
|------|------|---------|
| **init** | "初始化这个项目" | 创建配置、北极星指标、演化基线 |
| **status** | "看看进度" | 报告已完成/待执行/运行中/失败 |
| **discover** | "扫一下现有代码" | 生成 codebase-map.json |
| **brainstorm** | "设计鉴权模块" | 写结构化 spec |
| **plan** | "拆一下任务" | 创建 story、task、wave |
| **execute** | "执行当前 wave" | 调度器 + Worker 池执行 |
| **feedback** | "登录很慢" | 归因信号到 task |
| **evolve** | "创建 v3 轨道" | 新版本迁移 |

AI 以 `.zeus/ZEUS_AGENT.md` 为操作手册。

### 框架与业务项目分离

**核心设计原则**：框架代码只在 `zeus-open` 仓库维护，业务项目只保留配置和数据。

业务项目 `.zeus/v3/` 下应该只有：
`config.json` `task.json` `state.db` `agent-workspaces/` `ai-logs/` `start.ps1` `.framework`

**不应存在**：❌ `scripts/` ❌ `web/`

框架一处更新，所有业务项目通过 `.framework` 指针自动生效。

---

## v3 控制台

Zeus v3 提供基于 Vite + Vue 3 的实时控制台，由内置 FastAPI 服务器驱动：

- **概览** — 实时指标、任务列表、SSE 事件流
- **任务** — 内联操作（重试 / 取消 / 暂停 / 恢复 / 隔离 / 日志）
- **任务详情** — 滑出面板展示完整字段、依赖关系、活动日志、自动生成的 ai-log
- **事件** — 可搜索的实时 SSE 事件历史
- **指标** — 瓶颈分析、阻塞链、单任务耗时
- **依赖图** — SVG / Mermaid / ECharts
- **阶段** — 阶段与里程碑的增删改查
- **邮箱** — AgentBus 点对点消息
- **控制** — 调度器 / 工作器管理，一键全局运行
- **热重载** — 自动监听 `task.json` 变更，无需重启

```bash
python .zeus/v3/scripts/run.py --mode serve --host 0.0.0.0 --port 8234
# 打开 http://127.0.0.1:8234/dashboard
```

---

## 目录结构

```
zeus-open/                        ← 框架仓库
├── .zeus/
│   ├── ZEUS_AGENT.md             ← Agent 协议（全平台通用）
│   ├── v3/
│   │   ├── scripts/              ← 核心引擎（Python）
│   │   │   ├── run.py            ← 主入口
│   │   │   ├── core/             ← worker、scheduler、ai_logger
│   │   │   ├── api/              ← FastAPI 服务 + 控制台
│   │   │   ├── dispatcher/       ← mock、CLI、docker 调度器
│   │   │   ├── workspace/        ← 工作区隔离
│   │   │   ├── store/            ← 状态存储（SQLAlchemy）
│   │   │   ├── schemas/          ← Pydantic 模型
│   │   │   ├── db/               ← SQLite/Postgres 模型
│   │   │   └── tests/            ← 73/73 测试通过
│   │   ├── web/                  ← Vite + Vue 3 控制台源码
│   │   ├── templates/            ← 高并发规划模板
│   │   ├── ai-logs/              ← 自动生成的执行日志
│   │   └── state.db              ← 运行时状态（SQLite）
│   ├── v1/                       ← 已归档
│   ├── schemas/                  ← JSON schema 定义
│   └── hooks/                    ← git hooks（commit-msg）
└── README.md

my-project/                       ← 业务项目
└── .zeus/v3/
    ├── config.json
    ├── task.json
    ├── state.db
    ├── start.ps1
    ├── .framework                ← 指向 zeus-open
    ├── ai-logs/
    └── agent-workspaces/
```

---

## CLI 命令

| 命令 | 说明 |
|------|------|
| `python .zeus/v3/scripts/run.py --status` | 查看项目状态 |
| `python .zeus/v3/scripts/run.py --plan` | 预览执行计划 |
| `python .zeus/v3/scripts/run.py` | 执行所有待办任务 |
| `python .zeus/v3/scripts/run.py --wave 2` | 执行指定 wave |
| `python .zeus/v3/scripts/run.py --task T-001` | 执行单个任务 |
| `python .zeus/v3/scripts/run.py --mode serve` | 启动控制台 |
| `python .zeus/v3/scripts/run.py --import-only` | 导入 task.json 到数据库 |
| `python .zeus/v3/scripts/run.py --init` | 初始化项目结构 |
| `python .zeus/v3/scripts/run.py --trace` | 启用 OpenTelemetry 追踪 |
| `python .zeus/scripts/zeus_runner.py --status` | 旧版 v2 状态检查 |

---

## 部署

### Docker

```bash
cd .zeus/v3
docker compose up --build
```

服务组成：`redis` + `zeus-api`（端口 8000）+ `zeus-scheduler` + `zeus-worker`（2 副本）。

扩展工作器：
```bash
docker compose up --scale zeus-worker=4
```

### Kubernetes

```bash
cd .zeus/v3/k8s
kubectl apply -f namespace.yaml
kubectl apply -f pvc.yaml
kubectl apply -f redis.yaml
kubectl apply -f zeus-api.yaml
kubectl apply -f zeus-scheduler.yaml
kubectl apply -f zeus-worker.yaml
```

Worker 配置了 HPA（2-10 副本，CPU 70%）。

---

## v2（旧版）

v2 提供由 `zeus_server.py`（FastAPI）驱动的零构建 Web UI。仍可使用但不再活跃开发。

```bash
python .zeus/v2/scripts/zeus_server.py --port 8234 --project-dir .
# 打开 http://localhost:8234/web
```

详见 [`docs/zeus-v2-gui-quickstart.md`](docs/zeus-v2-gui-quickstart.md)。

---

## AI 日志

v3 起，**ai-log 由 worker 在每次 task 执行后自动生成**。每个 task 会生成一个结构化 markdown（`.zeus/{version}/ai-logs/{task_id}.md`），包含：

- 执行摘要（改动的文件、测试结果、commit SHA）
- 进度步骤（来自 `progress.jsonl`）
- Agent 原始输出（最后 200 行）
- 事件时间线（来自数据库）
- 错误详情（如有）

无需手动写日志。控制台通过 `GET /tasks/{task_id}/logs` 直接展示。

---

## 故障排查

- **AI 不认识 Zeus？** — 指引它阅读 `.zeus/ZEUS_AGENT.md`
- **Runner 卡住？** — 检查 `python .zeus/v3/scripts/run.py --status`
- **Task 更新失败？** — 通过 Dashboard 或 `--status` 检查数据库状态
- **Windows 下 greenlet DLL 报错？** — 安装 Visual C++ Redistributable

### 遇到 Blocker

1. 停止当前工作
2. 标记相关 task 为失败并注明原因
3. 选择另一个独立 task 继续

---

## 许可证

MIT License — 见 [LICENSE](LICENSE)。
