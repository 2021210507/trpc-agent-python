# Automatic Code Review Agent 自动代码评审示例

本示例是 issue #92 的可验证自动代码评审 Agent：它审查 git diff、PR patch、工作区变更或指定文件，
通过受控 `code-review` Skill、Filter 与隔离 workspace 生成结构化 finding，并将任务、沙箱运行、
治理事件和最终报告持久化。确定性规则负责检出；LLM 只能在显式启用时增强摘要和修复建议，不能改变
finding 的身份、严重级别、置信度或分桶。

## 规格依据

同目录的 [`DEV_SPEC.md`](DEV_SPEC.md) 是唯一规格源，定义字段契约、安全预算、AC1–AC8、
排期和测试方法；本 README 是面向使用者与验收官的导航摘要。若文档冲突，以 `DEV_SPEC.md` 为准。

## 关键特性

- **受控 Skill 规则**：[`skills/code-review/SKILL.md`](skills/code-review/SKILL.md) 与
  [`manifest.json`](skills/code-review/scripts/manifest.json) 固定可执行脚本、参数、摘要和预算；规则覆盖
  security、async-errors、resource-leak、db-lifecycle、missing-tests 和 secrets。
- **四种输入模式**：支持 `--diff-file`、`--repo-path`、`--files` 和 `--fixture`；diff/repo 仅审查变更行，
  files 为显式全文件 snapshot 扫描。
- **两条明确入口**：`review` 直接调用唯一 `ReviewPipeline`；`user-query` 会让 SDK
  `LlmAgent + SkillToolSet` 真实产生 `skill_load → skill_run` 工具事件。受控 `skill_run`
  只接收宿主签发的一次性 request id，再委托同一 pipeline，不向模型暴露 diff、命令、环境变量或宿主路径。
- **安全沙箱与 Filter**：生产默认 Container 且验证 `network_mode=none`；local 必须显式选择并产生告警；
  Cube 缺少机器可验证网络证明时默认拒绝。DENY / NEEDS_HUMAN_REVIEW 不会创建 sandbox；单次输出上限
  **1 MiB**、整次评审输出上限 **2 MiB**，并受 30 秒单次超时和 90 秒累计沙箱预算约束。
- **可回放的结构化结果**：canonical JSON 经 schema 校验和全出口脱敏后生成 Markdown；默认 SQLite 的五张
  `cr_*` 表支持按 task id 查询 task、sandbox run、Filter event、finding 和 report。
- **可观察且受限的终端日志**：默认 `INFO` 仅写 stderr，显示阶段、计数、耗时、实际 Docker container ID 和
  报告位置；SDK 原始日志被静默，原始 diff、evidence、环境变量、凭据和 workspace/request ID 不会输出。
- **可复现质量门禁**：8 条 `_simple` fixture、8 条 `_complex` 工程样例、公开代理语料、fake model 与显式
  local sandbox 共同构成离线验证链路。

## 交付物总览

以下交付物共同构成可复现的审查闭环；运行命令、16 个 fixture 和维护者验收步骤集中在
[`OPERATIONS.md`](OPERATIONS.md)。

### 审查链路与关键文件

```text
CLI direct ──────────────────────────────────────────────┐
CLI user-query ───────→ SDK LlmAgent + SkillToolSet      │
                         │ skill_load → 受控 skill_run    │
                         └────────────────────────────────┤
                                                          ▼
输入解析 → Filter 决策 → SDK workspace sandbox → 去重/分桶/脱敏
                         ▼
              ReviewPipeline → canonical review_report.json
                         ├── review_report.md
                         ├── SQLite cr_* tables
                         └── Metrics / Telemetry（仅白名单字段）
```

关键文件：

- [`run_agent.py`](run_agent.py)：`review`、`user-query`、`show`、`list`、`init-db` 五个 CLI 子命令；成功时输出
  `task_id`、`entrypoint`、实际 `skill_tools`、`sandbox` 和 `report_files` 的完整位置。
- [`agent/agent.py`](agent/agent.py) 与 [`agent/tools.py`](agent/tools.py)：SDK `LlmAgent`、
  `SkillRepository`、`SkillToolSet` 及一次性 request id 约束的 Agent 入口。
- [`codereview/pipeline.py`](codereview/pipeline.py)：唯一检测与报告编排链路。
- [`codereview/governance.py`](codereview/governance.py) 与 [`codereview/sandbox.py`](codereview/sandbox.py)：
  manifest 驱动的 Filter 治理、SDK runtime、超时和输出上限。
- [`codereview/store/models.py`](codereview/store/models.py)、[`review_store.py`](codereview/store/review_store.py)：
  可替换 SQL 后端与默认 SQLite 五表。
- [`schemas/review_report.schema.json`](schemas/review_report.schema.json) 与 [`codereview/report.py`](codereview/report.py)：
  JSON schema、原子写入和从 JSON 派生 Markdown。
- [`tests/fixtures/diffs/`](tests/fixtures/diffs/) 与
  [`tests/e2e/test_fixtures_e2e.py`](tests/e2e/test_fixtures_e2e.py)：8 simple + 8 complex 公开样例和 E2E 合同。

## 环境与运行

### 环境要求

- Python 3.10+，所有命令必须使用仓库 `.venv`。
- Windows PowerShell 的解释器为 `.venv\Scripts\python.exe`；Linux/macOS Bash 的解释器为
  `.venv/bin/python`。
- `--sandbox container` 需要 Docker Desktop 或可用 Docker daemon；`--sandbox local` 不需要 Docker，
  但只能作为显式开发 fallback。
- 真实模型仅在显式 `--model-mode real` 时需要 `.env` 配置。

本示例没有新增专属 pip 包，不提供 `examples/code_review_agent/requirements.txt`。依赖统一由根
[`pyproject.toml`](../../pyproject.toml) 与既有根 `requirements*.txt` 声明，避免局部 requirements 发生
版本漂移。维护者新建环境可按根项目安装：

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -e ".[dev]"
```

```bash
py=".venv/bin/python"
"$py" -m pip install -e ".[dev]"
```

### 真实模型配置

从 [`.env.example`](.env.example) 创建项目目录 `.env` 后，仅可填写以下三项；`.env` 已被 Git 忽略，
绝不提交。进程环境变量优先于 `.env`。

Windows PowerShell：

```powershell
Copy-Item examples/code_review_agent/.env.example examples/code_review_agent/.env
```

Linux/macOS Bash：

```bash
cp examples/code_review_agent/.env.example examples/code_review_agent/.env
```

```dotenv
TRPC_AGENT_API_KEY=<由使用者提供>
TRPC_AGENT_BASE_URL=<兼容 OpenAI 的服务地址>
TRPC_AGENT_MODEL_NAME=<模型名称>
```

模型 Key、token、password 不会进入 sandbox、日志、Telemetry、JSON、Markdown 或 SQLite。
`--sandbox`、网络策略、`--output-dir` 和 `--db-url` 必须显式写在命令中，不能藏进 `.env`。

### 快速开始

Windows PowerShell：

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py examples/code_review_agent/run_agent.py review --fixture 02_security_simple --sandbox local --dry-run --output-dir out/review_quickstart --db-url sqlite+pysqlite:///out/review_quickstart/review.db
```

Linux/macOS Bash：

```bash
py=".venv/bin/python"
"$py" examples/code_review_agent/run_agent.py review --fixture 02_security_simple --sandbox local --dry-run --output-dir out/review_quickstart --db-url sqlite+pysqlite:///out/review_quickstart/review.db
```

`--dry-run` 强制 fake model，但不会把沙箱自动改成 local。要验证 SDK Agent 入口，使用带结构化输入的
`user-query`：

```powershell
& $py examples/code_review_agent/run_agent.py user-query "请使用 code-review Skill 审查这个 fixture" --fixture 01_clean_simple --sandbox local --dry-run --log-level INFO --output-dir out/review_user_query --db-url sqlite+pysqlite:///out/review_user_query/review.db
```

```bash
"$py" examples/code_review_agent/run_agent.py user-query "Use the code-review Skill to review this fixture" --fixture 01_clean_simple --sandbox local --dry-run --log-level INFO --output-dir out/review_user_query --db-url sqlite+pysqlite:///out/review_user_query/review.db
```

`user-query` 的自然语言只表达审查意图；`--diff-file`、`--repo-path`、`--files` 或 `--fixture` 必须显式选择一个。
格式错误的 diff、路径逃逸、非 UTF-8 文件和疑似凭据 query 会在创建 Agent 前拒绝。
完整的四输入模式、16 fixture、off/fake/real、local/container/Cube 和双平台命令见
[`OPERATIONS.md`](OPERATIONS.md)。

需要在终端观察受控 Agent 流程时，增加 `--trace`。trace 以 JSON Lines 写入 **stderr**，stdout 仍只输出
最终 JSON，因此 CI 可以继续直接解析 stdout。它显示 query 解析、SDK `skill_load` / `skill_run` 事件、
Filter、sandbox、Pipeline 和报告落库；不显示模型私有推理、原始 query/diff、代码/evidence、request id、
命令、环境变量或临时路径。

## 运行结果与报告定位

每次成功的 `review` 都在终端输出一行脱敏 JSON。`report_files.json` 和 `report_files.markdown` 是可直接
打开的完整报告路径；路径只显示在当前终端，不写入 report、数据库、日志或 Telemetry。

```json
{
  "task_id": "review-...",
  "entrypoint": "pipeline",
  "skill_tools": [],
  "sandbox": "local",
  "status": "completed_with_warnings",
  "report_files": {
    "json": "<output-dir>/review_report.json",
    "markdown": "<output-dir>/review_report.md"
  }
}
```

JSON 是规范源；Markdown 只能从已校验 JSON 渲染。可查看
[`sample_output/review_report.json`](sample_output/review_report.json) 和
[`sample_output/review_report.md`](sample_output/review_report.md)。通过 `show <task_id>`、`list`、`init-db`
查询或初始化数据库的完整命令也在 [`OPERATIONS.md`](OPERATIONS.md)。
样例由 `user-query` 的 fake model + 显式 local sandbox 生成，报告中 `metrics.tool_call_count=2`，可直接佐证
`skill_load → skill_run` 的 Agent/Skill 链路；其中的 local 告警是该开发 fallback 的预期安全语义。

## 验证与验收

常规回归、公开代理评测和静态规范检查：

```powershell
& $py -m pytest examples/code_review_agent/tests -q -m "not container and not real_llm" -p no:cacheprovider
& $py examples/code_review_agent/evaluate.py --sandbox local --output-dir out/eval_local
& $py -m flake8 examples/code_review_agent
```

`evaluate.py --sandbox local` 是 fake model 的离线**公开代理**评测；它可以提供 AC2 的可重复证据，
但**不证明**官方隐藏样本的检出率或误报率。Container 与 real 模型测试分别标记为 `container`、
`real_llm`，只在已具备 Docker 或真实模型配置时运行。

| 验收项 | 当前可验证证据 |
|---|---|
| AC1 | 8 个 simple fixture 和 8 个 complex 配对样例逐条生成 JSON、Markdown 与 SQLite bundle。 |
| AC2 | `evaluate.py` 计算公开代理语料的高危 Recall 与 finding 级 FP；**官方隐藏样本待官方验收**。 |
| AC3 | SQLite 五表保存 task、run、Filter event、finding 与 report，并按 task id 查询。 |
| AC4 | manifest、Filter 与 sandbox 将 timeout、截断、预算和非零退出记录为数据，不中断报告。 |
| AC5 | 同源 detect/redact 与全出口扫描阻止明文凭据持久化。 |
| AC6 | 8 条 public fixture 均以 fake + local 的独立 Agent 审查运行；每条限制为 120 秒，聚合评测耗时仅记录。 |
| AC7 | DENY / NEEDS_HUMAN_REVIEW 在 sandbox 前短路并记录原因。 |
| AC8 | canonical JSON/Markdown 包含 findings、人工复核、治理、运行、监控和修复建议。 |

### 2026-07-28 独立 Agent 实测基准

以下数据用于维护者复现实测，不是跨机器、跨网络或跨模型服务的性能承诺。每一个单元格都是一个**独立的**
`user-query` 进程：显式 `--sandbox local`，使用独立输出目录和 SQLite；成功项均已验证
`entrypoint=agent`、工具序列 `skill_load → skill_run`，以及 JSON、Markdown、SQLite 三类产物。
`dry-run` 使用 `--dry-run`（强制 fake model），`real` 使用 `.env` 已配置的 `--model-mode real`，因此
真实模型时间包含模型服务响应，且不属于 AC6 的硬门禁。

真实模型调用统一设置为单次 HTTP 请求最多 30 秒；在尚未生成内容的 API 瞬时失败时，SDK 最多额外重试
3 次，固定退避 5、10、20 秒。重试不会重复已经进入 `skill_run` 的 pipeline。

simple fixture：

| Fixture | dry-run（fake） | real model | 说明 |
|---|---:|---:|---|
| 01_clean_simple | 26.780 s | 48.095 s | 两组均完成 |
| 02_security_simple | 25.067 s | 53.337 s | 两组均完成 |
| 03_async_leak_simple | 25.617 s | 53.265 s | 两组均完成 |
| 04_db_lifecycle_simple | 27.312 s | 45.767 s | 两组均完成 |
| 05_missing_tests_simple | 25.669 s | 48.538 s | 两组均完成 |
| 06_duplicate_finding_simple | 27.092 s | 48.515 s | 两组均完成 |
| 07_sandbox_failure_simple | 25.685 s | 43.544 s | 两组均完成；预期 sandbox warning 被持久化 |
| 08_secret_redaction_simple | 25.886 s | 60.336 s | 两组均完成；只使用合成凭据 |

simple dry-run 最大值为 **27.312 s**，8/8 均低于 AC6 的单条 **120 s** 限制；simple real 的 8 条均完成且
观测范围为 43.544–60.336 s，但 real 不作为 AC6 证据。

complex fixture：

| Fixture | dry-run（fake） | real model | 说明 |
|---|---:|---:|---|
| 01_clean_complex | 28.814 s | 46.149 s | 两组均完成 |
| 02_security_complex | 25.637 s | 56.394 s | 两组均完成 |
| 03_async_leak_complex | 25.673 s | 53.816 s | 两组均完成 |
| 04_db_lifecycle_complex | 25.899 s | 50.062 s | 两组均完成 |
| 05_missing_tests_complex | 25.664 s | 52.292 s | 两组均完成 |
| 06_duplicate_finding_complex | 25.424 s | 49.985 s | 重试策略修复后复测完成 |
| 07_sandbox_failure_complex | 26.039 s | 46.804 s | 重试策略修复后复测完成；预期 sandbox warning 被持久化 |
| 08_secret_redaction_complex | 27.605 s | 60.422 s | 重试策略修复后复测完成；只使用合成凭据 |

complex dry-run 最大值为 **28.814 s**，8/8 完成。首次 complex real 观测曾出现两条 exit 2 与一条
198.858 s 长尾，确认其不来自 fixture 的 fake E2E 后，加入上述模型调用超时/退避策略；仅重跑的三条均已
完成，complex real 当前为 8/8，范围 46.149–60.422 s。它仍是当前真实模型服务条件下的诊断记录，**不**可
替代、也不影响 AC6 的 simple fake/local 门禁。复现命令与输出定位方式见 [`OPERATIONS.md`](OPERATIONS.md)。

架构取舍、安全边界、风险和逐项 AC 核对见 [`DESIGN.md`](DESIGN.md)。维护者的完整 PR 验收步骤、
16 个 fixture、Docker/real model 实测和故障排查见 [`OPERATIONS.md`](OPERATIONS.md)。

## 适用场景建议

- 需要快速验证 git diff / PR patch 的确定性风险检出、报告和 SQLite 回放：使用本示例。
- 需要验证 Skill、Filter、Container sandbox、脱敏和监控如何组成审查闭环：使用本示例。
- 需要在 CI 中对高危 finding 阻断合并：结合 `--fail-on-severity high` 与本项目 CLI。
- 需要运行目标仓库测试、SARIF、多语言规则、LLM 语义补审或在线评测平台：这些属于
  [`DEV_SPEC.md`](DEV_SPEC.md) 第 7 章未来工作，不由当前 CLI 隐式执行。
