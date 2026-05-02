# Zeus - AI Project Evolution Operating System

[![Language](https://img.shields.io/badge/language-English%20%7C%20中文-blue)](README.zh-CN.md)
[![Workflow](https://img.shields.io/badge/workflow-init%E2%86%92brainstorm%E2%86%92plan%E2%86%92execute%E2%86%92feedback-green)](#workflow)
[![v3](https://img.shields.io/badge/v3-stable-success)](#v3-dashboard)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#license)

Structured, version-aware AI delivery framework for long-running projects.

Zeus combines:
- **Intent-driven workflow** — say "check the status" or "run the next task", no slash commands
- **Wave-based execution** — tasks run in dependency order, parallel where possible
- **Feedback-to-evolution loop** — production signals drive the next version

Language: [English](README.md) | [简体中文](README.zh-CN.md)

---

## Quick Start (v3)

Zeus works with **any AI platform** (DeepSeek, GPT, Claude, Gemini, Kimi, GLM). Just talk naturally.

### 1) Initialize a project

```bash
python .zeus/v3/scripts/run.py --project-root . --init
```

Creates `.zeus/v3/config.json`, `task.json`, `state.db`. The **only** per-project files you need.

### 2) Plan some tasks

Edit `.zeus/v3/task.json` with your task list, or ask your AI:

> "Plan the landing page tasks for my project"

Zeus converts specs into a dependency-aware task DAG.

### 3) Import & check

```bash
python .zeus/v3/scripts/run.py --project-root . --import-only
python .zeus/v3/scripts/run.py --project-root . --status
```

### 4) Start the Dashboard

```bash
python .zeus/v3/scripts/run.py --mode serve --host 0.0.0.0 --port 8234
```

Open `http://127.0.0.1:8234/dashboard`.

### 5) Execute

```bash
# Run all pending tasks
python .zeus/v3/scripts/run.py --project-root . --max-workers 3

# Or run a specific wave
python .zeus/v3/scripts/run.py --project-root . --wave 2 --max-workers 3
```

Your AI reads `.zeus/ZEUS_AGENT.md` to learn the Zeus protocol and handles the rest.

---

## Core Concepts

### Workflow

```
init → discover → brainstorm → plan → execute → feedback → evolve
         ↑                                              |
         └──────────────────────────────────────────────┘
```

1. **init** — north-star metrics, project config
2. **discover** *(optional)* — map existing codebase for brownfield
3. **brainstorm** — write specs to `.zeus/{version}/specs/*.md`
4. **plan** — convert specs into stories, tasks, wave DAG
5. **execute** — scheduler + worker pool runs tasks in dependency order
6. **feedback** — capture production signals, attribute to tasks
7. **evolve** — spin up vN+1 track based on learnings

### Natural Language Intents

No slash commands needed. Just tell your AI what you want.

| Intent | Example | What happens |
|--------|---------|-------------|
| **init** | "Initialize this project" | Creates config, metrics, evolution baseline |
| **status** | "What's the status?" | Reports completed/pending/running/failed |
| **discover** | "Map the codebase" | Generates codebase-map.json |
| **brainstorm** | "Design the auth module" | Writes structured spec |
| **plan** | "Plan the next wave" | Creates stories, tasks, wave DAG |
| **execute** | "Run pending tasks" | Scheduler + worker pool execute |
| **feedback** | "Login is slow" | Attributes signal to task |
| **evolve** | "Create v3 track" | Creates new version, migrates tasks |

The AI uses `.zeus/ZEUS_AGENT.md` as its instruction manual.

### Framework vs Business Project Separation

**Core design principle**: framework code lives in `zeus-open` only. Business projects keep only config + data.

Business project `.zeus/v3/` contents:
`config.json` `task.json` `state.db` `agent-workspaces/` `ai-logs/` `start.ps1` `.framework`

**Never** in business projects: ❌ `scripts/` ❌ `web/`

Update the framework once, all projects pick it up automatically via the `.framework` pointer.

---

## v3 Dashboard

Zeus v3 provides a Vite + Vue 3 real-time dashboard served by the built-in FastAPI server:

- **Overview** — live metrics, task list, SSE event stream
- **Tasks** — inline actions (Retry / Cancel / Pause / Resume / Quarantine / Logs)
- **Task Detail** — slide-out panel with full fields, dependencies, activity logs, auto-generated ai-log
- **Events** — searchable real-time SSE event history
- **Metrics** — bottleneck analysis, blocked chains, per-task duration
- **Dependency Graph** — SVG / Mermaid / ECharts
- **Phases** — phase & milestone CRUD with drill-down
- **Mailbox** — AgentBus point-to-point messaging
- **Control** — scheduler / worker management, one-click global run
- **Hot Reload** — auto re-imports `task.json` changes without restart

```bash
python .zeus/v3/scripts/run.py --mode serve --host 0.0.0.0 --port 8234
# Open http://127.0.0.1:8234/dashboard
```

---

## File Layout

```
zeus-open/                        ← framework repository
├── .zeus/
│   ├── ZEUS_AGENT.md             ← agent protocol (all AI platforms)
│   ├── v3/
│   │   ├── scripts/              ← core engine (Python)
│   │   │   ├── run.py            ← main entry point
│   │   │   ├── core/             ← worker, scheduler, ai_logger
│   │   │   ├── api/              ← FastAPI server + dashboard
│   │   │   ├── dispatcher/       ← mock, CLI, docker dispatchers
│   │   │   ├── workspace/        ← workspace isolation
│   │   │   ├── store/            ← state store (SQLAlchemy)
│   │   │   ├── schemas/          ← Pydantic models
│   │   │   ├── db/               ← SQLite/Postgres models
│   │   │   └── tests/            ← 73/73 passing
│   │   ├── web/                  ← Vite + Vue 3 dashboard source
│   │   ├── templates/            ← high-concurrency planning templates
│   │   ├── ai-logs/              ← auto-generated execution logs
│   │   └── state.db              ← runtime state (SQLite)
│   ├── v1/                       ← archived
│   ├── schemas/                  ← JSON schema definitions
│   └── hooks/                    ← git hooks (commit-msg)
└── README.md

my-project/                       ← business project
└── .zeus/v3/
    ├── config.json
    ├── task.json
    ├── state.db
    ├── start.ps1
    ├── .framework                ← points to zeus-open
    ├── ai-logs/
    └── agent-workspaces/
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `python .zeus/v3/scripts/run.py --status` | Check project status |
| `python .zeus/v3/scripts/run.py --plan` | Preview execution plan |
| `python .zeus/v3/scripts/run.py` | Execute all pending tasks |
| `python .zeus/v3/scripts/run.py --wave 2` | Execute specific wave |
| `python .zeus/v3/scripts/run.py --task T-001` | Execute single task |
| `python .zeus/v3/scripts/run.py --mode serve` | Start Dashboard |
| `python .zeus/v3/scripts/run.py --import-only` | Import task.json to DB |
| `python .zeus/v3/scripts/run.py --init` | Initialize project scaffold |
| `python .zeus/v3/scripts/run.py --trace` | Enable OpenTelemetry tracing |
| `python .zeus/scripts/zeus_runner.py --status` | Legacy v2 status check |

---

## Deployment

### Docker

```bash
cd .zeus/v3
docker compose up --build
```

Services: `redis` + `zeus-api` (port 8000) + `zeus-scheduler` + `zeus-worker` (2 replicas).

Scale workers:
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

Includes HPA for workers (2-10 replicas, 70% CPU).

---

## v2 (Legacy)

v2 offers a zero-build Web UI served by `zeus_server.py` (FastAPI). It remains available but is no longer actively developed.

```bash
python .zeus/v2/scripts/zeus_server.py --port 8234 --project-dir .
# Open http://localhost:8234/web
```

For the full v2 guide, see [`docs/zeus-v2-gui-quickstart.md`](docs/zeus-v2-gui-quickstart.md).

---

## AI Logs

Since v3, **ai-logs are auto-generated** by the worker after every task execution. Each task produces a structured markdown file in `.zeus/{version}/ai-logs/{task_id}.md` containing:

- Execution summary (changed files, test results, commit SHA)
- Progress steps from `progress.jsonl`
- Agent stdout (last 200 lines)
- Event timeline from DB
- Error details (if failed)

No manual log writing required. The Dashboard serves these via `GET /tasks/{task_id}/logs`.

---

## Troubleshooting

- **AI doesn't recognize Zeus?** — Point it to `.zeus/ZEUS_AGENT.md`
- **Runner stalls?** — Check `python .zeus/v3/scripts/run.py --status`
- **Task update fails?** — Check DB state via Dashboard or `--status`
- **Greenlet DLL error on Windows?** — Install Visual C++ Redistributable (vc_redist.x64.exe)

### Blockers

1. Stop current work
2. Mark task as failed with reason
3. Pick another independent task

---

## License

MIT License — see [LICENSE](LICENSE).
