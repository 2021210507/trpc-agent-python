<!-- Generated from DEV_SPEC.md. Do not edit directly. -->

## 3. 技术栈

### 3.1 运行环境

- Python `>=3.10`（与项目 `pyproject.toml` 一致），开发与 CI 推荐 3.12；示例代码和 Skill 脚本不得使用 3.12 专属语法。开发环境使用仓库根 `.venv`。
- 沙箱生产默认 Docker（container runtime）；开发主机已具备 Docker 与真实模型 Key，container 路径与 real 模式都必须实测

### 3.2 依赖原则

- `skills/code-review/scripts/` 下只允许 Python 标准库（保证沙箱内零安装可跑）
- `codereview/` 应用层可用 SDK 及其既有依赖（SQLAlchemy、pydantic）；不新增其他第三方依赖
- 模型接入：`trpc_agent_sdk.models.OpenAIModel`，读 `TRPC_AGENT_API_KEY/BASE_URL/MODEL_NAME`

### 3.3 SDK 对接要点（已核实，实施时按此写）

| 对接点 | 位置 | 处理 |
|--------|------|------|
| skill_run 默认超时 300s | `trpc_agent_sdk/skills/tools/_skill_run.py` L437 | 经 run_tool_kwargs 覆盖为 30s |
| 工具结果 stdout/stderr 各截断 16KB | `_skill_run.py` 输出处理 | 与本项目 1MiB/2MiB 文件预算是两层限制，实现与文档明确区分 |
| workspace 输出限额 | `trpc_agent_sdk/code_executors/_types.py` L251-257 `WorkspaceOutputSpec.max_files/max_file_bytes/max_total_bytes` | 显式设置为本项目预算 |
| container 创建参数默认断网 | `trpc_agent_sdk/code_executors/container/_container_cli.py` L160 `network_mode="none"`；其 `describe()` 仍返回 `network_allowed=True` | `network_allowed` 不作为有效状态证明；验证本次实际配置未覆盖 `network_mode=none` 后才放行 |
| cube 声明 network_allowed=True | `trpc_agent_sdk/code_executors/cube/_runtime.py` L456；当前配置类型未暴露可验证出口策略 | 视为“可能具备网络能力”而非“网络已开启”；本期无可验证无出口/受控网关证明时默认拒绝 |
| local 声明 network_allowed=True | `trpc_agent_sdk/code_executors/local/_local_ws_runtime.py` L702 | 仅显式 dev 降级放行，并将隔离与网络策略不可强制证明写入 warnings |
| Skill 仓库 | `trpc_agent_sdk.skills.create_default_skill_repository` + `SkillToolSet` | 两个入口都经 SkillRepository 解析/stage skill |
| Filter | `trpc_agent_sdk` 的 `BaseFilter` / `run_filters` | governance.py 基于真实 Filter 链实现 |

### 3.4 能力复用边界（SDK 复用 vs 自研，实现时必须遵守）

> 原则：**框架能力全部复用 SDK，只有「代码评审」业务领域的逻辑自研**。禁止绕开 SDK 机制自己造轮子（这是两个已有 PR #212/#201 被质疑最多的点）；也禁止把 SDK 已有能力重写一遍。

| 能力 | SDK 提供的部分（直接复用） | 我们自己写的部分 |
|------|--------------------------|----------------|
| Skills | `create_default_skill_repository`、`SkillToolSet`、`skill_load`/`skill_run` 工具、skill stage 进 workspace 的整套机制（`trpc_agent_sdk/skills/`） | 只写 skill 的**内容**：SKILL.md、6 篇规则文档、`scripts/` 下的检查脚本 |
| 沙箱执行 | container / cube / local 三种 workspace runtime、超时参数、输出截断、`WorkspaceOutputSpec` 限额及能力描述（`trpc_agent_sdk/code_executors/`） | `sandbox.py` 作为薄工厂选择后端、填充预算和环境变量，并向治理层提供本次最终生效网络配置/证明；不得用 `network_allowed` 代替有效状态校验 |
| Filter 治理 | `BaseFilter` / `run_filters` 的过滤器链机制 | manifest allowlist、参数模板、脚本摘要、禁止路径、环境/网络、预算和 runtime 能力的**判定逻辑** |
| 监控审计 | telemetry 模块的 span/trace 机制（`trpc_agent_sdk/telemetry/`） | `MetricsCollector` 轻量汇总器（生成 2.9 定义的不可变指标快照并落库） |
| Agent 入口 | `LlmAgent`、`Runner`、`OpenAIModel`、Session 服务 | 只写 prompts 和组装代码 |
| 数据库 | 复用 SDK 已有的 SQLAlchemy 依赖（SDK `storage/_sql.py` 即基于它）与可移植列类型写法 | 5 张 `cr_*` 表自己定义——SDK 的 storage 表是给 Session/Memory 用的，没有现成「评审任务」表，属于题目要求的「设计并实现最小 schema」 |

真正**从零自研**的只有三块，均为题目明确要求的业务交付物：

1. 规则引擎（`scripts/lib/` 的正则 + AST 检测）
2. 脱敏模块（检/脱同源正则表 + 熵检测）
3. 评审领域数据处理（去重分桶、finding 结构、报告八段式）

对应的排期硬约束：C1 治理必须走真实 `BaseFilter` 链、C2 沙箱必须走 SDK workspace runtime、D2 Agent 入口必须经 SkillRepository 加载 skill——这三个任务的验收标准均以此为准，不得用纯 Python 直调绕开。

### 3.5 设计模式

- 配置驱动：所有预算、阈值、路径集中在 `ReviewConfig`（dataclass/pydantic），不硬编码
- 可插拔：`ReviewStore` ABC（换 SQL 后端）、`create_sandbox_runtime` 工厂（换沙箱后端）、`ReportRenderer`（换报告格式）、`model-mode` 三态（换模型行为）
- 失败即数据：任何执行异常转记录行 + warnings，不抛出到 CLI 顶层
- 可复现：ChangeSet、ExecutionManifest、ReviewReport schema 和不可变 MetricsSnapshot 都有显式版本/摘要，稳定排序后再持久化
