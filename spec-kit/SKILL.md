---
name: spec-kit
description: >-
  GitHub Spec Kit 规范驱动开发（SDD）工作流。当用户想用 spec-driven development
  方式做需求/功能开发、写规格说明书（specification）、规划实现、生成任务、落地代码、
  收敛验收，或提到 /speckit.*、specify、spec kit、规范驱动、规格驱动 时使用。
  本机已安装 specify CLI 与项目 .specify 脚手架。本 skill 负责把用户的 /speckit.*
  意图路由到 .workbuddy/commands/ 下对应的命令文件并执行。
agent_created: true
---

# Spec Kit（规范驱动开发）

GitHub Spec Kit 是一个开源工具包，给 AI 编码助手提供结构化的规范驱动开发流程：
先写清楚「做什么、为什么」，再把规格说明转成计划、任务与可工作的代码。

## 本机已就绪的环境
- **specify CLI**：已通过 `uv tool install specify-cli` 安装，版本 1.2.4，
  `specify` 命令全局可用（位于 `~/.local/bin/specify.exe`）。
- **项目脚手架**：当前工作区已用 `codebuddy` 集成初始化，生成了 `.specify/`
  （模板 / 脚本 / 工作流）与命令文件。
- **命令文件位置**：`.workbuddy/commands/`（WorkBuddy 侧）与 `.codebuddy/commands/`
  （spec-kit 原生），两者内容一致。

## 可用命令（每个对应一个 .md 文件）
| 命令 | 作用 | 文件 |
|---|---|---|
| `/speckit.constitution` | 建立项目原则（principles / 宪法），每项目一次 | `.workbuddy/commands/speckit.constitution.md` |
| `/speckit.specify` | 创建基线规格说明（specification） | `speckit.specify.md` |
| `/speckit.clarify` | 澄清歧义（plan 之前可选） | `speckit.clarify.md` |
| `/speckit.plan` | 生成实现计划 | `speckit.plan.md` |
| `/speckit.analyze` | 跨产物一致性分析（tasks 之后可选） | `speckit.analyze.md` |
| `/speckit.checklist` | 生成质量检查清单（plan 之后可选） | `speckit.checklist.md` |
| `/speckit.tasks` | 生成可执行任务清单 | `speckit.tasks.md` |
| `/speckit.implement` | 执行实现 | `speckit.implement.md` |
| `/speckit.converge` | 评估代码库并补全剩余工作 | `speckit.converge.md` |
| `/speckit.taskstoissues` | 把任务转为 issue | `speckit.taskstoissues.md` |

## 标准工作流
1. 首次使用先跑 `/speckit.constitution` 建立项目宪法（每个项目一次）。
2. 每个功能重复以下循环，逐步推进、每步审阅结果后再继续：
   `specify → (clarify) → plan → (analyze / checklist) → tasks → implement → converge`
3. 反复 implement + converge，直到 `converge` 报告 `Converged`。

## 执行方式（重要）
当用户调用某个 `/speckit.*` 命令时：
1. 用 Read 工具读取 `.workbuddy/commands/speckit.<phase>.md`。
2. **严格按其内部指令执行**。命令文件通常会：
   - 读取 / 写入 `.specify/` 下的模板与产物（spec、plan、tasks 等）；
   - 必要时调用 `specify` CLI（如 `specify workflow ...`）；
   - 通过 `$ARGUMENTS` 接收用户输入。
3. 把每一步产出写入项目 `.specify/` 对应文件，并展示给用户审阅后再继续下一步。
4. 命令文件带有 frontmatter（`description`、`handoffs`），照做即可，
   **不要手动改写这些生成文件**（自定义请走 preset 或 project-local override）。

## 其它流程扩展
- Bug 修复：`specify extension add bug`，随后 `/speckit.bug.assess` / `.bug.fix` / `.bug.test`。
- 想法评估：`specify extension add assess`，随后 `/speckit.assess.*`。
- 安装后会把对应命令文件加入 `.codebuddy/commands/`，需要时在 `.workbuddy/commands/` 同步一份。

## 在其它项目 / 本机其它工作区启用
```bash
cd <项目目录>
specify init . --integration codebuddy --ignore-agent-tools --non-interactive --force
cp -r .codebuddy/commands/. .workbuddy/commands/
```

## 注意事项
- spec-kit 生成的命令 / 技能文件**不要手动编辑**。
- 不要把 `.specify/` 里含密钥的内容提交到公开仓库。
- 本集成用 `codebuddy` 集成桥接到 WorkBuddy（同生态、`.workbuddy` 目录），
  因 WorkBuddy 暂无官方 integration key，故用 `--ignore-agent-tools` 跳过 CodeBuddy CLI 存在性检查。
