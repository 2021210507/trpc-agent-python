# Automatic Code Review Agent

这是 issue #92 的可验证自动代码评审原型：确定性 Skill 规则负责检出，LLM 只在显式启用时增强修复建议与摘要，不能新增、删除或修改 finding 的身份、严重级别、置信度和分桶。

## 快速开始

所有命令使用仓库根目录的虚拟环境：

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py examples/code_review_agent/run_agent.py review --fixture 02_security --sandbox local --dry-run --output-dir out --db-url sqlite+pysqlite:///out/review.db
```

生产默认是 `--sandbox container`；本机调试必须显式传入 `--sandbox local`，报告会标记本机隔离与网络无法强制证明。Cube 在无法机器验证受控网络时由 Filter 拒绝。评审运行期间保持网络拒绝策略，不能临时下载依赖或回退宿主执行。

支持四种互斥输入：

```powershell
& $py examples/code_review_agent/run_agent.py review --diff-file change.diff --sandbox local --dry-run
& $py examples/code_review_agent/run_agent.py review --repo-path . --sandbox local --dry-run
& $py examples/code_review_agent/run_agent.py review --files src/app.py --input-root . --sandbox local --dry-run
& $py examples/code_review_agent/run_agent.py review --fixture 02_security --sandbox local --dry-run
```

`--dry-run` 强制使用 fake model，但不会替你把沙箱切换为 local。`--files` 是全文件 snapshot 扫描；`--diff-file` 与 `--repo-path` 只审查变更行。

## 真实模型配置

真实模型必须显式写 `--model-mode real`，CLI 才会从本项目 `.env` 的白名单读取以下变量；`.env` 已被 Git 忽略，绝不提交：

```dotenv
TRPC_AGENT_API_KEY=<由使用者提供>
TRPC_AGENT_BASE_URL=<兼容 OpenAI 的服务地址>
TRPC_AGENT_MODEL_NAME=<模型名称>
```

进程环境优先于 `.env`。变量不会进入 sandbox、日志、Telemetry、JSON、Markdown 或 SQLite。没有完整配置时 real 增强降级为脱敏 warning，确定性审查结果仍可交付。

## 执行与输出边界

受控脚本只能由 `skills/code-review/scripts/manifest.json` 通过 `script_id + structured_args` 解析。Filter 会预先拦截未登记脚本、路径逃逸、网络不可验证、超预算和需要人工复核的请求；被拦截请求不会启动 sandbox。

默认预算为单次 30 秒、最多 10 次运行、评审 90 秒沙箱预算/110 秒总 deadline；单次输出上限 **1 MiB**，整次评审上限 **2 MiB**。输出目录包含 canonical `review_report.json`、由其渲染的 `review_report.md`，以及可查询五张 `cr_*` 表的 SQLite 数据库。示例见 [`sample_output`](sample_output/)。

## 验证与评测

```powershell
& $py -m pytest examples/code_review_agent/tests -q -m "not container and not real_llm"
& $py examples/code_review_agent/evaluate.py --sandbox local
& $py -m flake8 examples/code_review_agent
```

`evaluate.py --sandbox local` 是 fake model 的离线**公开代理**评测：它为 AC2 提供可重复证据，但**不证明**官方隐藏样本的检出率或误报率。真实模型和 Container 测试分别使用 `real_llm`、`container` 标记，仅在明确提供对应前置条件后运行。

`tests/fixtures/diffs/` 同时保留 8 条小型 smoke diff 和 8 条同名前缀、以
`_realistic` 结尾的工程化 diff。后者每条包含 60–150 行新增代码、至少两个文件，以及
安全实现、真实风险和易误判干扰项；两组样例均通过相同 E2E 入口校验 JSON、Markdown 和
SQLite bundle。`evaluate.py` 继续只统计原 8 条公开样例，保持 AC1/AC2 门禁口径稳定。

## 验收对照

| 验收项 | 当前可验证证据 |
|---|---|
| AC1 | 8 个公开 smoke fixture 及其 8 个 realistic 配对样例逐条生成 JSON、Markdown 与数据库 bundle。 |
| AC2 | 离线公开代理语料计算高危 Recall 与 finding 级 FP；不外推为隐藏样本结论。 |
| AC3 | SQLite 五表保存 task、run、Filter 事件、finding 与 report，并按 task id 查询。 |
| AC4 | manifest、Filter 与 sandbox 记录超时、截断、预算和非零退出而不中断报告。 |
| AC5 | 同源 detect/redact 与全出口扫描阻止明文凭据持久化。 |
| AC6 | fake + local 的完整评测门禁限制在 120 秒内。 |
| AC7 | DENY/NEEDS_HUMAN_REVIEW 在 sandbox 前短路并记录原因。 |
| AC8 | JSON/Markdown 统一来自 canonical report，包含发现、人工复核、治理、运行与监控摘要。 |

设计取舍、风险和逐项验收说明见 [DESIGN.md](DESIGN.md)。
