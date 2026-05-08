# AGENTS.md — zeus-open

> 适用于 **DeepSeek、GPT/Codex、Gemini、Kimi、GLM** 等任何没有 `claude` CLI 的 AI 编程助手。
> 这不是一本要你读完的书。**按意图跳转，只读你需要的章节。**

---

## 意图路由

| 你的任务 | 跳到 |
|---------|------|
| 首次初始化项目 / Setup Zeus | [§2 初始化](#-2-初始化-init) |
| 查看当前进度 / Status | [§3 查看状态](#-3-查看状态-status) |
| 扫描已有代码库 | [§4 代码发现](#-4-代码发现-discover) |
| 设计方案 / 拆任务 | [§5 设计与规划](#-5-设计与规划-brainstorm--plan) |
| 执行一个或多个 task | [§6 执行任务](#-6-执行任务-execute) |
| 记录线上反馈 | [§7 收集反馈](#-7-收集反馈-feedback) |
| 版本演进 | [§8 版本演进](#-8-版本演进-evolve) |
| 出问题了 / 卡住了 | [§9 故障排查](#-9-故障排查) |

---

## §1 通用原则（所有意图都适用）

以下三条是铁律，不分项目、不分意图，始终生效。

### 1.1 动手前四问

动手写代码前，必须显式回答：

1. **我做了什么假设？** — 用户需求中哪些信息是我推测的？推测可能出错就先问。
2. **是否存在多种理解方式？** — 有歧义时列出所有解释让用户选，禁止默默选一个开干。
3. **有没有更简单的做法？** — 发现更简单的方案必须提出，不要为了"好架构"增加复杂度。
4. **我对哪里感到困惑？** — 接口、依赖、业务逻辑不清楚就停下来问，禁止蒙混过关。

### 1.2 代码简洁三原则

默认规则：**用最小代码解决当前问题。不为未来做 speculation。**

- **原则 1**：只实现明确要求的功能 + 让它能跑通的最小配套代码。不要提前加配置开关、通用接口。
- **原则 2**：不为一行代码建抽象。同一个逻辑出现第 3 次再考虑提取。
- **原则 3**：不写不可能触发的错误处理。拿不准时先实现最简单路径，标记 `# TODO`。

**自检**：提交前问自己——"如果资深工程师 review 这段代码，会不会说过度设计？"

### 1.3 手术式修改规范

**只碰必须碰的，只清理自己制造的。**

- 不顺手重构相邻代码、不改无关注释/格式/引号
- 匹配现有风格（引号、类型提示、异常处理、命名惯例）
- 你的修改导致的无用 import/变量 → **必须删除**；已有的死代码 → **不要动**
- diff 自检：每一行改动都能追溯到当前请求。不能的就撤销。

### 1.4 规则冲突优先级

| 优先级 | 规则 | 举例 |
|--------|------|------|
| **P0** | 动手前四问 | 有歧义就该问，不问就是错 |
| **P1** | 简洁三原则 | 代码能跑 + 没有废代码，就够了 |
| **P2** | 手术式修改 | 即使你发现历史代码写得烂，也不顺手修 |

数字越小的优先级越高。P0 永远覆盖一切——不确定就必须问，不问就是违规。

---

## §2 初始化（init）

> 当一个全新项目刚刚创建，还没有 `.zeus/` 目录时，走这个流程。

### 2.1 前置检查

```powershell
python .zeus/v3/scripts/run.py --status
```
- 如果返回 task 数据 → 系统已初始化过，跳到 [§3](#-3-查看状态-status)
- 如果报错 / 返回空 → 走初始化流程

### 2.2 初始化步骤

```powershell
# 1. 创建 .zeus/v3/ 目录结构
python .zeus/v3/scripts/run.py --project-root <项目路径> --init

# 2. 编辑 task.json 填入任务计划
# 3. 导入任务到 state.db
python .zeus/v3/scripts/run.py --project-root <项目路径> --import-only

# 4. 验证
python .zeus/v3/scripts/run.py --project-root <项目路径> --status
```

### 2.3 框架与业务项目分离

ZeusOpen v3 的核心设计：**框架代码只在 `zeus-open` 仓库维护，业务项目只保留配置和数据。**

业务项目 `.zeus/v3/` 下应该只有：
`config.json` + `task.json` + `state.db` + `agent-workspaces/` + `ai-logs/` + `start.ps1` + `.framework`

**不应存在**（已迁移到框架仓库）：
`scripts/` ❌ — 核心框架代码
`web/` ❌ — Dashboard 源码

---

## §3 查看状态（status）

```powershell
# v3 推荐
python .zeus/v3/scripts/run.py --status

# v2 / main
python .zeus/scripts/zeus_runner.py --status
```

输出解读完成后，告诉用户：
- 已完成/待执行/运行中/失败的数量
- 根据状态推荐下一步操作（继续执行 / 重试失败任务 / 规划下一波）

---

## §4 代码发现（discover）

> 只有接入了已有代码库的老项目才需要。新项目跳过本节。

告诉用户：
```
"扫一下现有代码，然后用发现的结果初始化 Zeus。"
```

- 扫描项目结构（顶层目录、技术栈识别）
- 生成 `.zeus/{version}/codebase-map.json`
- 生成 `.zeus/{version}/existing-modules.json`

---

## §5 设计与规划（brainstorm & plan）

### 5.1 设计方案

1. 阅读已有 spec 和 PRD（如有）
2. 一次问用户一个问题：范围、约束、优先级
3. 写 `.zeus/{version}/specs/{feature}.md`

### 5.2 拆解任务

1. 读 spec → 提取验收条件 → 创建 story（`US-NNN`）→ 创建 task（`T-NNN`）
2. 计算依赖 DAG → 分配 wave

**DAG 设计要点（高并发）**：
- 每波至少 2-3 个独立任务，而不是单个大任务
- 用扇形依赖：`T-001/T-002/T-003` 并行 → `T-004/T-005` 并行 → `T-006` 集成
- 一个 task 需要改 10+ 个文件 → 按模块拆成多个独立 task

3. 写 `task.json`

---

## §6 执行任务（execute）

> 这是最常被调用的章节。每个执行任务前读一遍。

### 6.1 开工前

1. **读 task.json** — `task.json` 现在始终与运行时状态同步。每次 task 执行后自动回写，`git diff` 可以看到所有状态变更。
2. 如果状态异常，先修复再继续
3. **一次只做一个 task**

### 6.2 v3 状态管理规则

- **双重保障**：启动引擎（`run.py`）时，`state.db` 是运行时事实源。不跑引擎时，`task.json` 始终是最新的 diff 友好快照。
- 每次 task 执行完毕或 `--finalize` 完成后，引擎自动将运行时状态回写到 `task.json`。无需手动 `--export`。
- **允许直接改 task.json** 的运行时字段（status/passes/commit_sha）——改完后下次跑引擎会用 importer 重新同步。
- 子 Agent 完成后必须在工作区写 `zeus-result.json`，Worker 自动同步到数据库和 task.json。
- **Dispatcher 模式**：`config.json` 中 `subagent.dispatcher` 控制任务如何执行
  - `auto`（默认）— 自动检测 kimi/claude CLI，找不到时降级 mock 并报警告
  - `human` — 不自动执行，标记 task 为 pending，等人手动 `--finalize`
  - `mock` — 测试用，伪造完成结果
  - `kimi`/`claude` — 强制使用指定 CLI

### 6.3 验证原则

**只跑与改动有直接因果关系的验证。** 不加区分跑全量测试是违规。

| 修改类型 | 必须验证 |
|---------|---------|
| 纯前端 / UI | `npm run build` 通过；有前端单测则跑 |
| 纯后端 / API | 相关后端测试文件通过 |
| DB model / store | 相关 store 测试通过 |
| 文档 / 配置 | 语法/格式合法即可 |

### 6.4 子 Agent 协作（手动分发模式）

当通过 `opencode` 等工具手动 launch 子 agent 执行 task 时，走 dispatch/finalize 流程确保 DB 和日志有完整记录。

**分三步：**

1. **Dispatch** — 准备工作区 + 标记 running
   ```powershell
   python .zeus/v3/scripts/run.py --dispatch T-XXX
   ```
   输出 workspace 路径和一条**可复制给子 agent 的指令**，包含任务描述、涉及文件、进度上报要求。

2. **启动子 agent** — 把 dispatch 输出的指令复制给子 agent。子 agent 在执行过程中应**每完成一个步骤向 workspace 的 `progress.jsonl` 追加一行**：
   ```json
   {"ts": "2026-05-04T15:30:00Z", "step": "writing", "message": "正在实现登录逻辑"}
   ```
   最终**必须在 workspace 根目录写入 `zeus-result.json`**：
   ```json
   {
     "status": "completed",
     "changed_files": ["src/foo.py"],
     "test_summary": {"passed": 5, "failed": 0, "skipped": 0},
     "commit_sha": "abc1234",
     "artifacts": {}
   }
   ```

3. **Finalize** — 收集成果物，生成 ai-log
   ```powershell
   python .zeus/v3/scripts/run.py --finalize T-XXX
   ```
   自动扫 workspace（优先 zeus-result.json，其次 git diff 兜底），写入 `ai-logs/` 并更新 `ai_log_ref`。

**查看可分发的 task：**
```powershell
python .zeus/v3/scripts/run.py --dispatch-list
```

### 6.5 多步骤计划格式

改动涉及多个文件时，动手前写计划：

```
1. [步骤] → 验证：[如何确认这一步成功]
2. [步骤] → 验证：[如何确认这一步成功]
```

### 6.6 完成定义

以下条件同时满足才算 done：

- [ ] 目标行为已实现
- [ ] 相关验证已通过（见 §6.3）
- [ ] Lint / 类型检查无错误（如有配置）
- [ ] task.json 已同步（手动将 status 改为 completed，或跑 `--finalize` 自动回写）
- [ ] diff 自检通过（每一行改动都能追溯到当前 task）
- [ ] 已 `git commit`（格式：`feat(T-001): description`）（如有 git）

> ⚠️ 如果项目没有测试、没有 lint、没有 git，跳过对应的检查项。

**> 完成以上步骤后，必须运行 `--finalize` 或确保 ai-log 已写入 `.zeus/{version}/ai-logs/{task_id}.md`。这是任务的最后一步，漏掉等于没完成。**

### 6.7 常用命令

```powershell
# 查看状态
python .zeus/v3/scripts/run.py --status

# 查看执行计划
python .zeus/v3/scripts/run.py --plan

# 执行当前 wave
python .zeus/v3/scripts/run.py

# 执行指定 wave
python .zeus/v3/scripts/run.py --wave 2

# 手动分发 task 给子 agent
python .zeus/v3/scripts/run.py --dispatch T-XXX

# 子 agent 完成后收集结果
python .zeus/v3/scripts/run.py --finalize T-XXX

# 查看可分发 task
python .zeus/v3/scripts/run.py --dispatch-list

# 启动 Dashboard
python .zeus/v3/scripts/run.py --mode serve --port 8234
```

---

## §7 收集反馈（feedback）

- 问用户：线上发生了什么？指标变化？用户投诉？
- 归因到具体 task
- 写 `feedback/{date}.json` + 更新 `evolution.md`

---

## §8 版本演进（evolve）

- 分析已完成任务 + 反馈 → 判断是否需要新版本
- 创建 `.zeus/vN/` 结构
- 迁移未完成任务
- 写 evolution 记录

---

## §9 故障排查

### 如果 runner 报错

1. 检查 `.zeus/main/task.json` 格式是否合法 JSON
2. 检查 `.zeus/main/config.json` 是否存在且包含 `project.name`
3. 查看 `ai-logs/` 中最近一次记录

### 如果遇到 blocker

1. 停止当前工作
2. 标记相关 task 为失败（passes: false）并添加备注
3. 选择另一个独立 task 继续
