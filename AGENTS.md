# 自动代码评审 Agent 开发协议

## 1. 适用范围

本文件适用于仓库根目录及全部子目录。当前工作的主要交付范围是：

```text
examples/code_review_agent/
```

除非 `DEV_SPEC.md` 的当前排期任务明确要求修改共享 SDK，否则不得改动
`trpc_agent_sdk/` 或与 issue #92 无关的示例。发现必须修改共享 SDK 时，先说明证据、
影响面和替代方案；不得为了方便绕开 SDK 已有能力。

## 2. 项目目标

本项目为 issue #92 实现一个可验证的自动代码评审 Agent。它不是让 LLM 自由评论代码，
而是把以下能力串成可测试、可审计、可回放的工程闭环：

- code-review Skill 与确定性规则；
- unified diff、文件列表和 Git 工作区输入解析；
- Filter 前置治理与 SDK workspace runtime 沙箱执行；
- findings 去重、分桶、脱敏和结构化报告；
- SQLite 默认、可切换 SQL 后端的持久化；
- Metrics、Telemetry、Filter 事件和沙箱运行审计；
- fake model / dry-run 的无 Key 离线验证链路。

最终必须满足 `DEV_SPEC.md` 中 AC1–AC8。公开代理语料只能佐证 AC2，禁止宣称已经证明
官方隐藏样本达标。

## 3. 规范优先级与必读文件

### 3.1 单一真相源

1. `DEV_SPEC.md` 是产品范围、架构、字段契约、预算、验收标准和排期的唯一真相源。
2. `.github/skills/auto-coder/references/*.md` 和
   `.claude/skills/auto-coder/references/*.md` 是生成的导航副本，不得直接编辑。
3. `implementation_plan.md` 和其他计划文档只解释设计取舍；与 `DEV_SPEC.md` 冲突时，
   以 `DEV_SPEC.md` 为准。
4. `DEV_SPEC.md` 第 1.2 节的锁定决策不得在普通开发任务中重新设计。确需改变时必须先
   获得用户明确批准，并同步更新规格、排期和测试合同。
5. 第 7 章属于未来规划。除非用户明确要求并接受扩展范围，否则不得提前实现。

### 3.2 强制使用的两个 Skill

每次产品开发都必须遵循：

- `.claude/skills/auto-coder/SKILL.md`
- `.claude/skills/qa-tester/SKILL.md`

仓库同时保留 `.github/skills/auto-coder/` 和 `.github/skills/qa-tester/` 作为相同内容的
可执行镜像。两套 Skill 定义应保持一致；发现不一致时必须先报告，不得任意选择对自己
更宽松的一份。QA 命令统一使用 Skill 文档给出的 `.github/skills/...` 路径；规格引用和
QA 进度发生变更时，同一操作还必须同步更新 `.claude/skills/...` 镜像。

每次实施循环至少读取：

- `DEV_SPEC.md` 中目标任务相关章节；
- `.github/skills/auto-coder/references/06-schedule.md`；
- 目标任务行的前置任务、验收标准和测试方法；
- `.github/skills/qa-tester/QA_TEST_PLAN.md` 中与该任务对应的 QA case。

涉及报告、数据库、脱敏、Filter、沙箱或可选集成时，还必须读取：

- `.github/skills/qa-tester/references/test_patterns.md`。

## 4. 每次开发的强制流程

### 4.1 虚拟环境和同步规格

仓库存在 `.venv` 时，所有 Python 开发、同步、测试、评测和 QA 命令必须使用该虚拟环境。
PowerShell 手工执行可先激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

自动化命令优先直接调用虚拟环境解释器，避免不同 shell 调用之间丢失激活状态：

```powershell
.\.venv\Scripts\python.exe .github/skills/auto-coder/scripts/sync_spec.py
.\.venv\Scripts\python.exe .claude/skills/auto-coder/scripts/sync_spec.py
```

只有 `.venv` 不存在或 `.venv\Scripts\python.exe` 不可执行时，才允许临时使用已安装且
版本为 Python `>=3.10` 的 `python` 读取规格或做只读诊断；不得用系统 Python 作为测试
通过证据。Python 不可用时直接读取 `DEV_SPEC.md`，不得依赖可能过期的 references。

### 4.2 检查工作区和前置条件

编辑前必须：

1. 运行 `git status --short`，把所有已有修改视为用户工作并予以保留。
2. 确认目标任务的直接前置任务不仅标记完成，而且对应文件和行为真实存在。
3. 读取当前实现，不根据排期状态臆测代码已经存在。
4. 运行能建立当前基线的最小现有测试。
5. 明确本次要改的文件、公共输入输出、跨越的信任边界、验收断言和测试。

不得覆盖、回退或格式化无关修改；不得使用 `git reset --hard`、`git checkout --` 等
破坏性命令。

### 4.3 一次只做一个排期任务

- 用户指定 A1–E2 任务时，只实施该任务。
- 用户未指定时，先选择第一个 `[~]`，否则选择第一个 `[ ]`。
- 开始实质实施时将目标标记为 `[~]`；不得同时把多个任务置为进行中。
- 一个任务可以包含使其可测试所必需的小型配套改动，但不得悄悄实现后续任务。
- 前置任务真实缺失并造成阻塞时，停止并给出文件、测试或接口证据；不得静默合并多个
  排期任务。

### 4.4 测试先行

默认循环：

```text
失败的聚焦测试 → 最小实现 → 聚焦测试通过 → 相关回归
```

测试必须验证可观察行为，例如 CLI 退出码、JSON/Markdown、数据库记录、Filter 事件、
沙箱运行记录、指标和明文泄漏扫描。不得只断言“不抛异常”，不得削弱断言、扩大异常捕获
或用 skip 掩盖未实现功能。

聚焦诊断、修复、重测最多三轮。三轮后仍失败，目标保持 `[~]` 并报告精确阻塞。

### 4.5 验收和进度更新

只在目标任务行的每条验收标准都有本轮命令证据后：

1. 将该任务从 `[ ]` 或 `[~]` 改为 `[x]`，填写完成日期；
2. 不改写任务原有验收标准和测试方法；
3. 强制重新同步生成引用：

```powershell
.\.venv\Scripts\python.exe .github/skills/auto-coder/scripts/sync_spec.py --force
.\.venv\Scripts\python.exe .claude/skills/auto-coder/scripts/sync_spec.py --force
```

测试失败、前置缺失或仅完成部分实现时不得标记 `[x]`。

### 4.6 运行 QA Tester

产品任务通过自身验收后，按 `QA_TEST_PLAN.md` 执行已解锁的对应 QA case：

1. 一次执行和判定一个 case。
2. 只有本轮真实命令输出才能作为通过证据；阅读代码、引用旧记录或整套测试的笼统结果
   不能替代单 case 证据。
3. 除命令外，至少记录两个具体证据值，例如通过数、桶计数、状态、耗时或
   `plaintext_hits=0`。
4. 判定后立即以相同证据更新 `.github/skills/qa-tester/QA_TEST_PROGRESS.md` 和
   `.claude/skills/qa-tester/QA_TEST_PROGRESS.md` 的对应行与汇总计数，不得形成两个
   独立进度账本。
5. 每个 QA section 完成后运行：

```powershell
.\.venv\Scripts\python.exe .github/skills/qa-tester/scripts/qa_validate_notes.py --section <SECTION>
```

6. validator 未达到零问题前不得继续宣称该 section 完成。

“run QA”只授权测试执行和只读诊断，不授权修改产品代码；只有用户明确要求
“test and fix”，或重新进入 auto-coder 实施循环时，才可修复产品。QA 修复最多进行三轮。

## 5. 架构与代码规范

### 5.1 项目边界

- Python 最低版本为 3.10，不使用 3.11/3.12 才支持的语法。
- 新增 Python 文件遵循 `CONTRIBUTING.md` 的 Tencent Apache-2.0 版权头，年份使用文件
  创建年份。
- 使用 4 空格缩进，行宽不超过 120；遵循仓库 Black/YAPF/flake8 配置。
- 代码、测试、注释和文档命名保持清楚、具体；公共数据结构和边界接口应有类型标注。
- 所有新增或实质修改的 Python 函数、方法（包括测试辅助函数）必须添加函数级中文
  docstring，简要说明其作用；涉及公共接口、异常处理、数据持久化或安全边界时，还应说明
  关键输入输出、失败语义或安全约束。注释应解释意图和约束，不得只把代码逐句翻译成中文。
- `codereview/` 宿主应用层可以使用仓库已经声明且已安装在 `.venv` 中的依赖（包括
  SQLAlchemy、Pydantic）；不得把仅存在于开发者全局环境、但未被项目声明的包当作可用
  依赖。
- `skills/code-review/scripts/` 会进入 Container/Cube 隔离 workspace，不能假定宿主
  `.venv` 会被复制或挂载，因此默认优先使用 Python 标准库，但不绝对禁止第三方库。确有
  必要引入时，必须先向用户说明包名、固定版本、用途、收益、替代方案、许可证/安全风险、
  依赖声明位置及沙箱镜像/runtime 的供应方式，获得明确批准并同步修改 `DEV_SPEC.md`。
- 用户批准新增依赖后，Agent 可以自行把固定版本安装到仓库 `.venv`，并在受控的
  Container 镜像或 Cube/E2B 模板构建/预置阶段安装相同依赖；不得污染系统 Python 或
  用户级 site-packages。依赖必须通过仓库认可的文件锁定版本和完整性，并验证宿主与目标
  沙箱的包版本、解释器兼容性和环境摘要一致。
- 依赖准备与代码评审任务运行必须分离。允许在经批准的镜像/模板构建阶段获取依赖，但
  评审任务执行期间仍保持 `network_policy=deny`，禁止临时在线安装、动态下载执行或因
  沙箱缺包静默回退宿主。仅在 `.venv` 安装成功不能作为沙箱可用证据。
- 依赖 fake runtime/model 时通过公共构造函数或接口注入，不 monkeypatch 内部函数。

### 5.2 复用 SDK，不重复造框架

必须复用 tRPC-Agent SDK 的：

- `create_default_skill_repository`、`SkillToolSet` 和 skill stage/run 机制；
- container、cube、local workspace runtime 和 `WorkspaceOutputSpec`；
- `BaseFilter` / `run_filters`；
- Telemetry span/trace；
- `LlmAgent`、`Runner`、`OpenAIModel` 和 Session 服务；
- 已有 SQLAlchemy 依赖与可移植类型写法。

项目自研范围仅限确定性规则与 diff 领域逻辑、检/脱同源模块、去重分桶、报告和五张
`cr_*` 业务表。

### 5.3 单核心与单一实现

- `ReviewPipeline.run()` 是唯一检测链路。
- CLI、dry-run、测试以及 `LlmAgent + SkillToolSet` 必须调用同一 pipeline。
- 两个入口共享 manifest、Filter、sandbox、storage、finding 和 report model。
- diff 解析器、规则和 secret patterns 只放在
  `skills/code-review/scripts/lib/`；不得在 `codereview/` 复制规则逻辑。
- JSON 是 canonical report；Markdown 和数据库统计必须来自同一份已校验、已脱敏对象。
- 输出排序必须稳定，相同输入和配置应产生确定性结果。

## 6. 不可破坏的领域契约

### 6.1 输入语义

- `--diff-file` 和 `--repo-path` 是 changed-lines 增量审查。
- `--files` 是 `status=snapshot`、`review_scope=full_file` 的显式全文件扫描。
- fixture 保留其声明的 diff 或 full-file 载荷类型。
- 新增/snapshot hunk 的 old 侧固定为 `0,0`；删除 hunk 的 new 侧固定为 `0,0`。
- `old_to_new_line_map` 只记录未修改 context 行。
- 普通规则只分析新侧；仅 secrets 可报告删除旧侧，并必须使用真实旧行号和
  `line_side=old`，禁止伪造 line 0。
- `--repo-path` 使用单次 `git diff HEAD` 加
  `git ls-files --others --exclude-standard`；Git 调用使用 argv，禁止 `shell=True`。

### 6.2 Finding 与分桶

finding 至少包含：

```text
severity, category, file, line, title, evidence,
recommendation, confidence, source
```

去重键固定为 `(file, line, category)`。桶边界互不重叠：

- `0.80 <= confidence <= 1.00`：`findings`
- `0.50 <= confidence < 0.80`：`needs_human_review`
- `0.00 <= confidence < 0.50`：`suppressed`
- `warnings`：只存运行和治理问题

不得按 severity 给 confidence 保底。LLM 只可增强 recommendation、summary 和人工复核
提示，不得增删 finding 或修改 identity、rule、severity、confidence、bucket 和 dedup。

### 6.3 数据库和失败语义

保持五表最小 schema：

- `cr_review_task`
- `cr_sandbox_run`
- `cr_filter_event`
- `cr_finding`
- `cr_report`

默认 SQLite，`ReviewStore` 保留 SQL 后端替换接口，并支持按 task id 返回完整 bundle。
原始 diff 默认不落库。

Filter 拦截、沙箱超时、非零退出和输出截断都必须成为脱敏记录与 warnings。能生成报告时
状态为 `completed_with_warnings`；只有输入解析、DB 初始化/关键写入或报告生成等致命失败
才为 `failed`。严禁在沙箱失败后回退到宿主执行规则。

## 7. 安全边界

### 7.1 执行治理

- pipeline 只接受 `script_id + structured_args`。
- 命令只能从 `skills/code-review/scripts/manifest.json` 解析。
- 禁止任意 shell 字符串、`shell=True`、动态下载执行、在线安装依赖、可写宿主仓库挂载
  和静默 local fallback。
- 每次执行前必须先过真实 Filter 链。`DENY` 和 `NEEDS_HUMAN_REVIEW` 必须短路，沙箱运行
  数和副作用均为 0。
- container 是生产严格默认，且仅在可验证本次实际 `network_mode=none` 时放行。
- cube 在无法提供机器可验证的无出口/受控网关证明时默认 deny。
- local 只能由用户或 evaluate 显式选择，并写入隔离/网络无法强制证明的 warning。

锁定默认预算：

```text
max_sandbox_runs = 10
per_run_timeout_seconds = 30
sandbox_time_budget_seconds = 90
review_deadline_seconds = 110
max_output_bytes_per_run = 1 MiB
max_output_bytes_per_review = 2 MiB
network_policy = deny
```

环境变量必须按白名单重新构造，不能透传宿主环境。API Key、token、password 和其他环境
值不得进入沙箱、日志、报告、数据库或 Telemetry。

### 7.2 敏感信息

- detector 必须在受控宿主任务内存/临时目录和隔离 workspace 中检查原始输入；不得在检测
  前破坏性脱敏。
- 原始 diff、代码行、环境变量值、evidence、stdout/stderr 和 Filter reasons 不得发送给
  LLM 或 Telemetry。
- 按“沙箱输出脱敏 → 宿主字段二次脱敏 → JSON/Markdown/数据库完整出口扫描”执行三层
  防护。
- detect 与 redact 必须共享 `secret_rules.py` 的同一模式表。
- 最终扫描发现明文时阻止持久化并把任务标为 failed。
- task workspace 必须在 `finally` 清理；清理失败只记录不含敏感路径和内容的 warning。
- 测试只能使用合成凭据。进度记录只写计数和 `plaintext_hits=0`，不得粘贴密钥、diff、
  环境变量值或本机绝对路径。

## 8. 测试和质量门禁

- 所有测试、QA、evaluate、lint 和验证命令必须在仓库 `.venv` 中执行。证据记录应能看出
  使用的是 `.venv`，例如命令显式调用 `.\.venv\Scripts\python.exe`，或先执行
  `.\.venv\Scripts\Activate.ps1` 后在同一 shell 中运行。
- 禁止把系统 Python、用户级 site-packages 或全局 pytest 的结果作为通过证据。若误用，
  必须如实标记为无效证据，并在 `.venv` 中重新运行。
- 测试代码、测试辅助和测试数据统一放在 `examples/code_review_agent/tests/`，使用 pytest；
  项目顶层不得另建 `fixtures/`。
- `tests/unit/` 只验证单个确定性模块接口，不得依赖 Docker、网络或真实模型 Key。
- `tests/integration/` 验证模块或本地适配器协作；默认使用 fake runtime/model、`tmp_path`
  和临时 SQLite。
- `tests/e2e/` 从 CLI 或 evaluate 入口验证 JSON、Markdown、数据库 bundle、指标和退出码。
- `tests/fixtures/` 只保存输入与预期数据，不保存可执行测试；`tests/support/` 只保存跨两个
  以上测试层复用的 fake、builder 和断言，禁止复制产品逻辑。
- 必选 fixture 缺失必须失败，不得 skip；测试不得写入业务 `review.db` 或仓库持久化目录。
- container 和 real model 测试分别标记 `container`、`real_llm`；只有缺少对应可选前置
  条件时才允许 skip。缺少实现不是 skip。
- Cube 默认拒绝是确定性安全测试，不得跳过。
- 每个公开 fixture 都必须验证 JSON、Markdown、数据库 bundle 和预期桶/状态。
- secret fixture 必须同时证明“检测到 secret finding”和“所有出口明文命中数为 0”。
- suite 通过不能自动把其所有组成 QA case 标为通过。
- 完成一个纵向闭环后运行普通回归：

```powershell
.\.venv\Scripts\python.exe -m pytest examples/code_review_agent/tests -q -m "not container and not real_llm"
```

- 发布前还必须运行：

```powershell
.\.venv\Scripts\python.exe examples/code_review_agent/evaluate.py --sandbox local
.\.venv\Scripts\python.exe -m flake8 examples/code_review_agent
```

`evaluate.py` 默认必须真实执行仓库自带可信 Skill 脚本，强制 fake model 和显式 local
sandbox；不得用 fake workspace 冒充评测，也不得污染业务 `review.db`。

## 9. 禁止事项

- 不得未经授权修改锁定设计、验收阈值、测试样本期望或排期验收文字。
- 不得提前实现第 7 章的 SARIF、目标仓库测试、外部扫描器、LLM 语义补审/降噪、
  A2A/AG-UI、RAG、多语言规则或在线评测平台。
- 不得用 LLM 参与确定性检出或把低置信候选塞入正式 findings。
- 不得把 `WorkspaceCapabilities.network_allowed` 当作实例网络状态证明。
- 不得把 `--dry-run` 当作切换 local sandbox 的开关。
- 不得记录或持久化原始 diff、明文凭据或宿主绝对路径。
- 新增依赖必须先按 5.1 节报告并获得用户明确批准；批准后 Agent 可以自行安装到仓库
  `.venv` 和受控沙箱镜像/模板，但不得安装到系统 Python、用户级 site-packages，或在
  评审任务运行期间联网安装。启动网络服务、使用真实模型 Key、stage、commit 或 push
  仍必须分别获得用户明确授权。

## 10. 每次交付时的报告格式

开发回合结束必须报告：

- 排期任务 ID、结果和是否更新为 `[x]`；
- 修改文件；
- 实际运行的测试/QA case、退出码、pass/fail/skip 数和关键证据；
- 尚存 warnings、环境依赖测试或阻塞；
- 下一个 `[~]` 或 `[ ]` 任务。

不得声称未实际运行的测试通过，不得在仍有必选 QA case pending 时宣称完整验收通过。
