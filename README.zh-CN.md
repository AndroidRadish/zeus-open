# Zeus

[![语言](https://img.shields.io/badge/language-English%20%7C%20中文-blue)](README.md)
[![v3](https://img.shields.io/badge/v3-stable-success)](#)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#)
[![许可证](https://img.shields.io/badge/license-MIT-lightgrey)](#LICENSE)

**AI 驱动的任务编排引擎，适合长期迭代的软件项目。**

Zeus 管理项目的全生命周期任务——规划、执行、记录、反馈。告别手工记进度或翻聊天记录，一个命令加一个网页控制台就够了。

```
                       ┌──────────────────────────┐
  "执行下一个 task"     │                          │  控制台 / CLI
  ───────────────────▶ │   Zeus 引擎               │
  "现在进度怎么样？"    │   (调度器 + 工作器)       │
  ◀─────────────────── │                          │
                       └──────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              ┌──────────┐     ┌──────────────────┐
              │  state   │     │    工作区         │
              │  (SQLite) │     │  (隔离副本)       │
              └──────────┘     └──────────────────┘
```

---

## 快速开始

```bash
# 1. 初始化项目
python .zeus/v3/scripts/run.py --project-root . --init

# 2. 启动网页控制台
python .zeus/v3/scripts/run.py --mode serve

# 3. 打开 http://localhost:8234/dashboard
# 4. 规划任务、执行、看日志——全部在控制台或通过 AI 完成
```

Zeus 支持**所有 AI 平台**（DeepSeek、GPT、Claude、Kimi、Gemini）。不需要插件，不需要斜杠命令，告诉 AI 你想干什么就行。

---

## 为什么用 Zeus？

| 你遇到的情况 | Zeus 怎么解决 |
|-------------|-------------|
| "还有哪些 task 没做？" | 数据库记录一切，`--status` 或控制台直接看 |
| "上次跑过了吗，到底过没过？" | 每个 task 记录测试结果、改了什么文件、agent 输出、commit SHA |
| "10 个 task 哪些能一起跑？" | task 声明依赖，调度器自动保证顺序 + 最大化并行 |
| "新来的 AI 不认识项目历史" | `ai-logs/` 自动记录每次执行，agent 不需要翻聊天记录 |
| "想同时让多个 AI 干活" | `--dispatch` 分发单个 task 给不同 agent，各干各的互不干扰 |

---

## 用法

### CLI 命令

| 命令 | 作用 |
|------|------|
| `python .zeus/v3/scripts/run.py --init` | 初始化新项目的 `.zeus/v3/` 结构 |
| `python .zeus/v3/scripts/run.py --status` | 查看任务统计（完成/待办/失败） |
| `python .zeus/v3/scripts/run.py --mode serve` | 启动网页控制台（端口 8234） |
| `python .zeus/v3/scripts/run.py` | 执行所有待办任务 |
| `python .zeus/v3/scripts/run.py --wave 2` | 只执行 Wave 2 的任务 |
| `python .zeus/v3/scripts/run.py --dispatch T-005` | 分发一个 task 给子 agent |
| `python .zeus/v3/scripts/run.py --finalize T-005` | 子 agent 完成后收集结果 |

### 自然语言交互

AI 读取 `.zeus/ZEUS_AGENT.md`，你说人话它干活：

| 你说 | Zeus 做 |
|------|---------|
| "初始化这个项目" | 创建配置 + 任务模板 |
| "看看进度" | 报告完成/待办/失败 |
| "设计一下登录模块" | 写一份 spec |
| "规划下一波任务" | 拆成带依赖顺序的 task |
| "跑一下 T-003" | 执行一个 task |
| "用户说登录很慢" | 记录反馈，归因到对应 task |

---

## 架构

### 框架 / 业务项目分离

Zeus 分成两层，框架只装一次，业务项目可以有无数个：

```
zeus-open/                        ← 框架仓库（装一次）
└── .zeus/v3/
    ├── scripts/                  ← 引擎（调度器、工作器、API、分发器）
    ├── web/                      ← 控制台前端
    └── templates/                ← 任务规划模板

my-project/                       ← 你的项目（可以有多个）
└── .zeus/v3/
    ├── config.json               ← 项目配置
    ├── task.json                 ← 任务定义
    ├── state.db                  ← 运行时状态（SQLite，自动创建）
    ├── ai-logs/                  ← 执行日志（自动生成）
    └── agent-workspaces/         ← 隔离工作区
```

框架一处更新，所有项目自动生效。

### 目录结构

```
.zeus/v3/scripts/
├── run.py              ← 主入口（--status、--serve、--dispatch 等）
├── core/
│   ├── worker.py       ← task 执行循环
│   ├── scheduler.py    ← 依赖感知的调度器
│   ├── dispatch.py     ← 手动分发子 agent
│   └── ai_logger.py    ← 自动生成执行日志
├── api/
│   └── server.py       ← FastAPI 服务 + 控制台
├── store/              ← 状态存储（SQLAlchemy / SQLite / Postgres）
├── dispatcher/         ← 子 agent 分发器（mock、CLI、docker）
├── workspace/          ← 工作区隔离
├── db/                 ← 数据库模型
├── schemas/            ← Pydantic 模型（Agent 结果协议）
└── tests/              ← 73/73 测试通过
```

---

## 部署

### Docker Compose

```bash
cd .zeus/v3
docker compose up --build
```

服务组成：`api`（端口 8000）+ `scheduler` + `worker`（2 副本）+ `redis`。

### Kubernetes

```bash
cd .zeus/v3/k8s
kubectl apply -f namespace.yaml -f pvc.yaml -f redis.yaml \
              -f zeus-api.yaml -f zeus-scheduler.yaml -f zeus-worker.yaml
```

Worker 配置了 HPA（2–10 副本，CPU 70%）。

---

## 常见问题

| 症状 | 解决 |
|------|------|
| AI 不认识 Zeus | 引导它阅读 `.zeus/ZEUS_AGENT.md` |
| Runner 卡住了 | 检查 `python .zeus/v3/scripts/run.py --status` |
| 端口 8234 被占用了 | `python .zeus/v3/scripts/run.py --mode serve --port 8235` |
| Windows 下报 DLL 错误 | 安装 [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |

---

## 许可证

MIT — 见 [LICENSE](LICENSE)。
