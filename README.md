# Zeus

[![Language](https://img.shields.io/badge/language-English%20%7C%20中文-blue)](README.zh-CN.md)
[![v3](https://img.shields.io/badge/v3-stable-success)](#)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](#)
[![License](https://img.shields.io/badge/license-MIT-lightgrey)](#LICENSE)

**An AI-powered task orchestrator for long-running software projects.**

Zeus manages your project's task lifecycle across multiple AI coding assistants. Instead of manually tracking what's done, what's next, and what broke, you get a database-backed execution engine with a real-time dashboard.

```
                       ┌──────────────────────────┐
  "Run the next task"  │                          │  Dashboard / CLI
  ───────────────────▶ │   Zeus Engine             │
  "What's the status?" │   (scheduler + workers)   │
  ◀─────────────────── │                          │
                       └──────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              ┌──────────┐     ┌──────────────────┐
              │  state   │     │  agent workspace  │
              │   (SQLite) │     │  (isolated copy) │
              └──────────┘     └──────────────────┘
```

---

## Quick Start

```bash
# 1. Initialize a project
python .zeus/v3/scripts/run.py --project-root . --init

# 2. Start the dashboard
python .zeus/v3/scripts/run.py --mode serve

# 3. Open http://localhost:8234/dashboard
# 4. Plan tasks and execute — all from the UI or your AI assistant
```

That's it. Zeus works with **any AI platform** (DeepSeek, GPT, Claude, Kimi, Gemini). No plugins, no slash commands — just tell your AI what you want.

---

## Why Zeus?

| Problem | How Zeus solves it |
|---------|-------------------|
| "What tasks are left?" | Database-backed state, not sticky notes. `--status` or Dashboard shows everything. |
| "Did it actually pass?" | Every task records test results, changed files, agent output, and a commit SHA. |
| "I have 10 tasks, which can run in parallel?" | Tasks declare dependencies; the scheduler runs them in the right order and maximizes parallelism. |
| "My AI assistant doesn't know the project history" | `ai-logs/` captures every execution automatically — agent doesn't need to remember. |
| "I want to split work across multiple AIs" | Dispatch individual tasks to separate agent sessions. Each gets an isolated workspace and a clear prompt. |

---

## Usage

### CLI

| Command | What it does |
|---------|-------------|
| `python .zeus/v3/scripts/run.py --init` | Create `.zeus/v3/` scaffold for a new project |
| `python .zeus/v3/scripts/run.py --status` | Show task summary (completed/pending/failed) |
| `python .zeus/v3/scripts/run.py --mode serve` | Start web dashboard on port 8234 |
| `python .zeus/v3/scripts/run.py` | Execute all pending tasks (scheduler + worker pool) |
| `python .zeus/v3/scripts/run.py --wave 2` | Execute only wave 2 tasks |
| `python .zeus/v3/scripts/run.py --dispatch T-005` | Prepare task for manual sub-agent execution |
| `python .zeus/v3/scripts/run.py --finalize T-005` | Collect results after sub-agent finishes |

### Natural Language

No slash commands. Your AI reads `.zeus/ZEUS_AGENT.md` and maps your intent:

| You say | Zeus does |
|---------|-----------|
| "Initialize this project" | Creates config + task template |
| "What's the status?" | Reports completed / pending / failed |
| "Design the auth module" | Writes a spec |
| "Plan the next wave" | Splits spec into dependency-ordered tasks |
| "Run T-003" | Executes a single task |
| "Login is slow (feedback)" | Records signal and attributes to task |

---

## Architecture

### Framework / Project Separation

Zeus is designed as two layers:

```
zeus-open/                        ← install once (this repo)
└── .zeus/v3/
    ├── scripts/                  ← engine (scheduler, worker, API, dispatcher)
    ├── web/                      ← dashboard frontend
    └── templates/                ← task planning templates

my-project/                       ← your project (any number)
└── .zeus/v3/
    ├── config.json               ← project settings
    ├── task.json                 ← task definitions
    ├── state.db                  ← runtime state (SQLite, auto-created)
    ├── ai-logs/                  ← execution logs (auto-generated)
    └── agent-workspaces/         ← isolated agent work directories
```

Update `zeus-open` once — all projects pick up the changes automatically.

### File Layout

```
.zeus/v3/scripts/
├── run.py              ← CLI entry point (--status, --serve, --dispatch, ...)
├── core/
│   ├── worker.py       ← task execution loop
│   ├── scheduler.py    ← dependency-aware scheduling
│   ├── dispatch.py     ← manual sub-agent support
│   └── ai_logger.py    ← auto-generates execution logs
├── api/
│   └── server.py       ← FastAPI server + dashboard
├── store/              ← state storage (SQLAlchemy / SQLite / Postgres)
├── dispatcher/         ← sub-agent dispatchers (mock, CLI, docker)
├── workspace/          ← isolated workspace management
├── db/                 ← database models
├── schemas/            ← Pydantic models for ARP (Agent Result Protocol)
└── tests/              ← 73/73 passing
```

---

## Deployment

### Docker Compose

```bash
cd .zeus/v3
docker compose up --build
```

Services: `api` (port 8000) + `scheduler` + `worker` (2 replicas) + `redis`.

### Kubernetes

```bash
cd .zeus/v3/k8s
kubectl apply -f namespace.yaml -f pvc.yaml -f redis.yaml \
              -f zeus-api.yaml -f zeus-scheduler.yaml -f zeus-worker.yaml
```

Includes HPA for workers (2–10 replicas, 70% CPU).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| AI doesn't recognize Zeus | Point it to `.zeus/ZEUS_AGENT.md` |
| Runner stalls | Check `python .zeus/v3/scripts/run.py --status` |
| Port 8234 in use | `python .zeus/v3/scripts/run.py --mode serve --port 8235` |
| `DLL load failed` on Windows | Install [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) |

---

## License

MIT — see [LICENSE](LICENSE).
