<!-- Generated from DEV_SPEC.md. Do not edit directly. -->

## 2. 功能规格

### 2.1 输入解析（R3）

支持四种输入，统一解析为 `ChangeSet`：

- `--diff-file <path>`：unified diff / PR patch 文件
- `--repo-path <dir>`：git 工作区变更（staged + unstaged，同时可读全文件内容）
- `--files <a.py> <b.py>`：无 baseline 的文件快照列表，执行**全文件扫描**；每个文件记为 `status=snapshot`、`review_scope=full_file`，整份内容都属于候选行
- `--fixture <name>`：内置测试样例；fixture 必须声明其载荷类型，diff fixture 保留真实 old/new hunk，full-file fixture 才按 `--files` 的 snapshot 语义处理

**四种输入互斥**：同一次调用只允许指定一种，CLI 层校验，同时给出多个直接报错退出，避免多输入源结果冲突的模糊状态。

**输入形态不等价**：`--repo-path` 的 tracked 变更和 `--diff-file` 是增量审查，changed-line 过滤能隔离历史遗留问题；`--files` 没有旧版本可比较，是显式全量扫描，AST 可报告文件任意行上的既有问题。调用方若需要增量语义必须提供 repo 或 diff，不能期待 `--files` 自动推断实际改动。报告 input summary 必须显示 `review_scope`，评测不得把 full-file 与 changed-lines 结果当作同一口径直接比较。

**领域模型契约**（实现、报告与测试共用；路径统一为 `/` 分隔的仓库相对路径）：

| 模型 | 必须字段 |
|------|---------|
| `ChangeSet` | `source_kind(diff_file\|repo_path\|files\|fixture)`、`input_sha256`、`files`、`file_count`、`hunk_count`、`additions`、`deletions`、`parse_warnings` |
| `FileChange` | `old_path`、`new_path`、`normalized_path`、`status(added\|modified\|deleted\|renamed\|snapshot)`、`review_scope(changed_lines\|full_file\|deleted_lines\|skipped)`、`is_binary`、`hunks`、`old_changed_lines`、`new_changed_lines`、`full_text(str\|None)`、`analysis_mode(ast_validated\|diff_heuristic\|skipped)` |
| `Hunk` | `old_start`、`old_count`、`new_start`、`new_count`、`context_lines`、`added_lines`、`deleted_lines`、`old_to_new_line_map` |

`Hunk` 字段不可缺失或取 `None`，退化状态固定采用 unified diff 的 `0,0` 语义：

| 场景 | old 侧 | new 侧 | changed lines | `old_to_new_line_map` |
|------|--------|--------|---------------|-----------------------|
| 新增文件 / snapshot（N 行） | `old_start=0, old_count=0` | `new_start=1, new_count=N` | old=`[]`，new=`1..N` | `{}` |
| 删除文件（N 行） | `old_start=1, old_count=N` | `new_start=0, new_count=0` | old=`1..N`，new=`[]` | `{}` |
| 普通 hunk | 取 diff header 的整数 | 取 diff header 的整数 | 分别记录 `-/+` 行 | 只映射未修改 context 行 |

空文件新增/删除若 diff 只有元数据而没有内容 hunk，则 `hunks=[]`，不构造虚假的零长度 hunk。替换行没有可靠的一一语义关系，不得写入 `old_to_new_line_map`。

finding 的 `file` 使用 `normalized_path`：新增/修改/rename/snapshot 取新路径，删除取旧路径。`line` 默认表示新侧行号，扩展字段 `line_side` 默认为 `new`；仅 secrets 规则可对删除侧原始凭据生成 `line_side=old`、`line=<旧行号>` 的 finding，提示密钥可能仍存在于补丁/历史中并建议轮换。普通代码规则不报告已经删除的代码。不得用 `line=0` 或临近新行伪造删除侧位置。

**--repo-path 的 git 变更获取方式**（定死，避免 staged/unstaged 合并陷阱）：

1. 用一条 `git diff HEAD` 获取「工作区当前状态 vs 上一次 commit」的完整 diff——天然合并 staged + unstaged，禁止分别跑 `git diff` 和 `git diff --cached` 再手动合并（同一文件两份 diff 的 hunk 会重叠冲突）。
2. `git diff HEAD` 不含 untracked 新文件，须额外跑 `git ls-files --others --exclude-standard` 获取 untracked 列表，将其按真实 `status=added`、`review_scope=full_file` 处理；内容读取与 synthetic hunk 构造可复用 `--files`，但不得把 untracked 的 status 写成 snapshot。
3. 所有 Git 调用必须使用 argv 数组并固定工作目录，禁止 `shell=True`；路径在读取与 staging 前必须 `resolve` 并验证仍位于 repo 根目录内，拒绝指向仓库外的 symlink、junction 或其他重解析点。

**--repo-path 默认忽略规则**（可经 ReviewConfig 配置，默认值如下）：

- `.gitignore` 内文件：自动忽略——`--exclude-standard` 已实现该语义，无需额外过滤。
- 二进制文件：忽略。diff 内 binary 变更按边界跳过；untracked 文件做二进制嗅探（内容含 NUL 字节即跳过）。
- 虚拟环境与构建目录**显式兜底清单**（不依赖用户是否配好 .gitignore）：`.git/`、`.venv/`、`venv/`、`node_modules/`、`build/`、`dist/`、`__pycache__/`、`*.egg-info/`、`.tox/`、`.mypy_cache/`、`.pytest_cache/`。
- untracked 文件的规则适用范围**按类别区分，不得只收 .py**：Python 类规则（security/async/resource/db/missing-tests）仅作用于 `.py` 文件；secrets 规则作用于**所有文本文件**（含 `.env`、`.yaml`、`.json`、`.ini`、`.toml`、`.txt` 等）——明文密钥最常出现在未跟踪的配置文件里，只扫 Python 会直接威胁 AC5。
- 输入限额集中在 `ReviewConfig`：`max_input_file_bytes=1 MiB`、`max_input_files=500`、`max_input_bytes=10 MiB`、`max_diff_lines=50,000`。单文件超限跳过并记 warnings；文件数、总字节数或总行数超限在 staging 前由 Filter 标 `needs_human_review`，不得先复制或执行后再依赖超时收拾。
- 宿主仓库不得可写挂载进沙箱；只复制审查所需的最小输入集到任务 workspace。`--files` 仅接受显式命名、位于当前输入根目录内的普通文件，同样执行 realpath 与限额检查。

diff 解析必须覆盖边界：rename、binary、CRLF、`\ No newline at end of file`、删除文件、新增文件。新增文件的 unified diff 若包含从第 1 行开始且无缺口的全部新增内容，可重建 `full_text` 并启用 AST；否则 `full_text=None`，按 diff heuristic 分析。

**原始输入边界**：解析器和沙箱内 secrets 规则允许在受控内存/任务 workspace 中读取原始内容，以完成真实密钥检测；解析期间不得记录代码行、环境变量或密钥值。进入 LLM、日志、Telemetry、数据库、finding evidence、sandbox 摘要和报告前必须脱敏。任务 workspace 在 `finally` 中清理，清理失败只记录不含敏感路径/内容的 warning。

### 2.2 CR Skill（R1）

`examples/skills_code_review_agent/skills/code-review/`（自包容，随示例目录整体拷贝可用）：

- `SKILL.md`：YAML frontmatter（name=code-review）+ 用法说明 + 工作流描述
- `rules/`：6 类规则文档（security / async-errors / resource-leak / missing-tests / secrets / db-lifecycle），每篇含规则清单、rule_id、severity、置信度、`requires_full_file` 标记、示例
- `references/security-boundaries.md`：原始输入信任域、禁止路径、网络、环境变量、预算、脱敏和失败语义的自检说明
- `scripts/manifest.json`：机器可读执行清单，是脚本 allowlist、参数模板和执行预算的唯一判定源
- `scripts/parse_diff.py`：沙箱内 diff 解析入口（读 `work/inputs/diff.json`，输出解析结果到 `out/`）
- `scripts/run_checks.py`：沙箱内规则检查入口（输出 findings JSON 到 `out/findings.json`）
- `scripts/lib/`：纯标准库实现——`diff_parser.py`、`rule_engine.py`、`rules_security.py`、`rules_async.py`、`rules_resource.py`、`rules_db.py`、`rules_tests.py`、`secret_rules.py`（检/脱同源正则表 + 熵检测）

`manifest.json` 每个条目至少包含 `script_id`、`entrypoint`、`sha256`、允许参数的名称/类型/枚举/长度、`timeout_seconds`、`max_output_bytes`、`requires_network`。Agent/pipeline 只能请求 `script_id + structured_args`，Filter 根据 manifest 生成 argv；禁止提交任意 shell 字符串。Skill staging 后必须校验 entrypoint realpath 位于 Skill 根目录内且摘要一致。`SKILL.md` 只解释工作流并引用 manifest，不承担机器授权。

### 2.3 规则引擎（6 类，Python-only）

| 类别 | category 值 | 检测手段 | 置信度 |
|------|------------|---------|--------|
| 安全（SQL 注入 f-string 拼接、命令注入 os.system/subprocess shell=True、eval/exec） | security | 正则 + 全文件可得时 AST 确认 | AST 确认 ≥0.9；纯 diff 正则 0.7–0.85 |
| 敏感信息（AWS AKIA、GitHub PAT ghp_/github_pat_、Slack、OpenAI sk-、JWT、PEM 私钥、DB 连接串、赋值型 password/token/secret） | secrets | 检/脱同源正则表 + Shannon 熵 | ≥0.9 |
| 异步错误（async def 内 time.sleep、协程未 await、事件循环内阻塞 IO） | async-errors | 正则 + AST | 0.6–0.9 |
| 资源泄漏（open/aiohttp ClientSession/socket 未 with 或未 close） | resource-leak | 正则 + hunk 跨行 + AST | 0.6–0.9 |
| DB 生命周期（连接未关、事务未 commit/rollback、游标泄漏） | db-lifecycle | 同上 | 0.6–0.9 |
| 测试缺失（新增/修改非测试源码但变更集内无对应 test 文件变化） | missing-tests | 变更集形状启发式 | 锁 0.5–0.8，永进 needs_human_review |

候选侧别：security/async-errors/resource-leak/db-lifecycle/missing-tests 只分析新侧内容；secrets 同时扫描新增/上下文输出中的新侧内容和被删除的旧侧内容。旧侧命中表示凭据可能已经进入补丁或 Git 历史，finding 必须明确 `line_side=old`，修复建议以轮换/吊销为主，不能描述为“当前文件仍硬编码该值”。

**规则覆盖边界与盲区策略**（实现和评测口径都以此为准）：

| 类别 | 规则覆盖能力 | 已声明的盲区（不检出，不算漏报缺陷） |
|------|------------|-----------------------------------|
| secrets | 强：正则 + 熵检测，跨语言；公开代理语料脱敏检出率目标 ≥95% | 拆分/编码/运行时拼接、自定义短 token、私有格式可能漏检 |
| missing-tests | 文件级结构比对，不涉及代码语义；仅作为人工复核提示 | 非标准测试目录、动态生成测试、集成测试映射、已有覆盖关系可能误判 |
| resource-leak | 较强：AST 可识别 open/connect 后无 close/with 的经典模式 | 跨函数传递的句柄、仅异常路径泄漏（需控制流分析） |
| db-lifecycle | 较强：识别已知 DB 库 API（connect/commit/rollback）调用模式 | 连接池误用、嵌套事务（需调用上下文理解） |
| async-errors | 中等：AST 可查协程创建后未 await/未传 gather/create_task 的直接模式 | 变量先赋值、之后才 await（需数据流分析） |
| security | 中等：已知危险 API（直接/限定名 eval/exec、os.system/popen、subprocess shell helper、SQL f-string/拼接/format/%）模式 | 运行时函数别名、变量传播得到的 shell 参数、动态属性名和业务逻辑漏洞（权限绕过、认证逻辑错误） |

**盲区处理原则**：规则覆盖不到的场景保持为声明盲区，本期不用 LLM 顶上。理由：一旦 LLM 参与检出判断，检出率/误报率（AC2）无法稳定复现。盲区清单写入各规则文档和 README；CI 硬门禁语料只覆盖明确声明支持的模式，另设 blind-spot stress corpus 作为观测项，记录漏检但不冒充正式门禁通过。P/R/F1 只统计 findings 桶。

**按规则类别降误报**：security/async-errors/resource-leak/db-lifecycle 等代码结构规则可忽略仅出现在注释、docstring 或普通字符串中的 API 名称；secrets 规则必须扫描字符串字面量、配置文件和注释，注释中的疑似示例密钥只能根据占位符特征降置信或进入人工复核，不得统一跳过。diff 上下文行（非 `+/-` 行）不作为 finding 主定位行。

**AST 退化策略（经 `requires_full_file` 规则元信息实现）**：每条规则在元信息中声明 `requires_full_file: true|false`。unified diff 只含 hunk 片段，对残缺代码跑 `ast.parse()` 大概率语法错误，因此：

- 全文件内容可得（--repo-path / --files，或可完整重建的新增文件 diff）：`requires_full_file=true` 的 AST 规则正常启用。对 `review_scope=changed_lines`，AST 节点范围必须与 `new_changed_lines` 相交才可产出当前审查 finding；上下文可以引用未修改行，但主定位必须锚定变更行。对 `review_scope=full_file`（--files、untracked、真实新增文件），`new_changed_lines` 覆盖全文，交集约束按设计退化为全量扫描，允许报告任意行，报告必须明确标注该 scope。`review_scope=deleted_lines` 不运行普通 AST 代码规则。
- 纯 diff 输入（--diff-file 且无原始文件可读）：`requires_full_file=true` 的规则**自动跳过 AST 路径**（禁止尝试解析残缺片段导致异常），仅保留正则 + 行级启发部分，置信度整体下调一档（0.7–0.85）；无正则等价物的纯 AST 规则直接不产出，或产出低置信项进 needs_human_review。
- 全文件 AST 解析失败：记录 parse warning，将该文件的 `analysis_mode` 降为 `diff_heuristic`，继续运行其他规则，不得终止整次 review。

### 2.4 结构化 finding（R4）

必须字段：`severity`（critical/high/medium/low/info）、`category`、`file`、`line`、`title`、`evidence`（已脱敏）、`recommendation`、`confidence`（0–1）、`source`（rule-engine/ast/heuristic）。扩展字段：`line_side`（new/old，默认 new）、`rule_id`、`bucket`、`dedup_key`、`extra`（JSON，含 also_matched）。删除侧仅允许 secrets 使用 `line_side=old`；评测匹配仍使用 `(file,line,category)`，需要区分侧别的边界测试额外断言 `line_side`。

### 2.5 去重与降噪（R6）

- 去重键：三元组 `(file, line, category)`。重复候选依次按 severity、confidence、evidence 具体程度选主项，其余 rule_id 去重后按稳定字典序合入 `extra.also_matched`。最终输出固定按 severity、file、line、category、rule_id 排序，保证相同输入重复运行得到相同 JSON。
- 四桶路由（边界不得重叠）：`0.80 ≤ confidence ≤ 1.00` → `findings`；`0.50 ≤ confidence < 0.80` → `needs_human_review`；`0.00 ≤ confidence < 0.50` → `suppressed`（仅保存脱敏审计计数和原因摘要，不进报告主体）。
- `warnings` 桶与代码问题分离，专放运行告警：沙箱失败、输出截断、Filter 拦截、规则执行异常、local 沙箱降级提示。
- confidence 必须来自可复现的证据强度；不得为满足 Recall 指标按 severity 设置置信度保底。明确危险 API、完整 AST 结构或强格式密钥可以自然得到高置信，模糊正则与上下文不足的候选必须进入人工复核或 suppressed。

### 2.6 沙箱执行与安全边界（R2 + R7）

- 三后端：`create_sandbox_runtime("container"|"cube"|"local")`，默认 `container`。SDK `WorkspaceCapabilities.network_allowed` 仅作为运行时可能具备网络能力的粗粒度描述，不得当作当前实例网络已开启或已断开的证明；Filter 必须检查最终生效且可验证的网络配置。`container` 仅在确认实际 `network_mode=none` 时放行；当前 SDK 未提供可验证 Cube 出口策略的接口，因此 `cube` 在本期默认 deny，只有配置受信任模板且系统能验证其无出口网络策略或受控网关约束时方可放行，用户口头或布尔确认不构成证明；`local` 仅用于显式选择的 dev 降级，并在 warnings 记录隔离与网络策略不可强制证明的告警。
- 预算（ReviewConfig 默认值，全部可配置）：

| 配置项 | 默认值 |
|--------|--------|
| max_sandbox_runs | 10 |
| per_run_timeout_seconds | 30（覆盖 SDK skill_run 的 300s 默认） |
| sandbox_time_budget_seconds | 90 |
| review_deadline_seconds | 110 |
| max_output_bytes_per_run | 1 MiB |
| max_output_bytes_per_review | 2 MiB |
| network_policy | deny |

- `network_policy=deny` 是本项目本期的 fail-closed 安全决策，不是 SDK 对 Cube 的使用限制。题目允许对白名单网络做受控放行，但本期所有预注册脚本均为 `requires_network=false`，不实现仅凭用户确认或未验证配置开放网络的旁路。
- Filter 必须在每次执行前做“先拒后跑”的预算预检：预估本次运行加入后是否超过次数、单次超时、单次输出或总时间预算；不满足时返回 deny/needs_human_review，不得先执行再只依赖 timeout 截止。`sandbox_time_budget_seconds=90` 为沙箱累计预算，给解析、落库和报告预留时间以满足 120 秒总门禁。
- 环境变量「构造而非透传」：仅 LANG/LC_ALL/PYTHONUNBUFFERED 等无敏感值变量允许传入；PATH/PYTHONPATH 由应用在沙箱内构造；WORKSPACE_DIR/SKILLS_DIR/WORK_DIR/OUTPUT_DIR/RUN_DIR 由 runtime 注入；API Key、token 及其余宿主环境变量一律不传。
- 失败记录：超时、非零退出、输出截断、OSError 全部落 `cr_sandbox_run` 行（status/exit_code/timed_out/error_type/脱敏摘录）。

### 2.7 Filter 治理（R8）

`SandboxGovernanceFilter` 基于 SDK `BaseFilter` / `run_filters` 链，按固定顺序执行前置检查：

1. 接收 `script_id + structured_args`，拒绝任意命令字符串、shell 元字符和未知脚本。
2. 从 `scripts/manifest.json` 解析 entrypoint 与参数模板；校验参数类型、枚举、长度、重复参数和未知参数。
3. 校验 staged entrypoint realpath 位于 Skill 根目录内，文件 SHA-256 与 manifest 一致；不一致直接 deny。
4. 校验所有输入/输出路径均位于任务 workspace 内，禁止绝对宿主路径、`..`、symlink/junction 逃逸。
5. 校验 `requires_network=false` 与 runtime 网络能力；本期 manifest 中所有脚本均不得请求网络。
6. 校验环境变量仅来自 2.6 的构造白名单，值不得包含密钥模式。
7. 预检运行次数、单次超时、单次/总输出和剩余时间预算。
8. 高风险内容模式扫描作为纵深防御（如脚本内容出现 `rm -rf`、`curl|sh` 或动态拉取执行，即使脚本已注册也 deny）。
9. runtime 有效网络状态校验（不得只读取 `WorkspaceCapabilities.network_allowed` 作决定）：
   - `cube`：当前 SDK 只能说明运行时可能允许网络，不能证明具体实例无出口；本期 **默认 deny**。仅当受信任模板或受控网关已配置，且治理层能取得机器可验证的无出口/目的地约束证明时方可 allow；仅有用户确认时仍不得执行。
   - `local`：宿主进程无法提供与沙箱等价的网络隔离证明；仅在用户已**显式**传 `--sandbox local`（或 evaluate 显式选择 local）时治理门 **allow**，同时必须把「隔离与网络策略不可强制证明」降级告警写入 warnings（不得静默当成生产等价）。
   - `container`：创建参数默认 `network_mode=none`，但该值可被 `host_config` 覆盖；Filter/工厂必须验证本次实际生效配置仍为 `none` 后才 allow，被覆盖或无法验证时 deny。

`FilterAction ∈ {ALLOW, DENY, NEEDS_HUMAN_REVIEW}`；DENY / NEEDS_HUMAN_REVIEW 短路，不进沙箱、不回退执行，拦截原因先脱敏再写入报告和 `cr_filter_event`。该枚举与 finding 的 `FindingBucket.NEEDS_HUMAN_REVIEW` 是不同领域概念，字段和统计必须分开。

### 2.8 数据库存储（R5）

SQLAlchemy ORM + 可移植列类型；SQLite 默认（`out/review.db`），换 MySQL/PG 只改 URL。5 表：

| 表 | 关键字段 |
|----|---------|
| cr_review_task | id、status（running/completed/completed_with_warnings/failed）、input_type/ref、diff_summary(JSON，仅元数据+脱敏摘要，见下）、config(JSON)、error_* |
| cr_sandbox_run | task_id、status(ok/failed/timeout/blocked/error)、exit_code、timed_out、filter_action、脱敏后 stdout/stderr 摘录、error_type、duration_ms |
| cr_filter_event | task_id、stage、target、action、rule、reasons(JSON) |
| cr_finding | 9 必须字段 + rule_id + bucket + dedup_key + extra(JSON)；evidence 必须已脱敏 |
| cr_report | task_id(unique)、schema_version、rule_pack_version、config_digest、input_sha256、summary、severity_stats(JSON)、filter_summary(JSON)、sandbox_summary(JSON)、metrics(JSON)、report(完整 JSON，已脱敏) |

**原始 diff 落库策略（先脱敏，后落库）**：

- **默认禁止**在数据库中保存原始 unified diff / patch 全文。原始内容由宿主安全读取，只可短暂存在于受控内存、任务临时目录和隔离 workspace，任务结束在 `finally` 中清理；不得记录到普通日志或异常文本。
- `diff_summary` 只存元数据：SHA-256、字节数、文件数、hunk 数、增删行统计、`review_scope` 分布、脱敏后的文件路径摘要；禁止含未脱敏代码行。
- finding evidence、recommendation、Filter reasons、sandbox stdout/stderr 摘录、error 信息、Telemetry 属性、最终 report **一律脱敏后再写入**。
- 若确需回放完整变更，仅允许存**脱敏副本**，且须显式配置开关开启（默认关闭）；该副本仍不得含明文密钥。

`ReviewStore` ABC + `get_task_bundle(task_id)` 一次返回 task+runs+events+findings+report；`init-db` 幂等（create_all）。五表 MVP 不再拆表，但 JSON 字段必须带 schema version；至少为 task status、run task_id、event task_id/action、finding task_id/severity/category 和 report task_id 建索引。数据库 URL 可由 CLI `--db-url` 或配置提供，默认仍为 `sqlite:///out/review.db`。

### 2.8.1 失败语义（部分失败、整体继续）

Filter 拦截或沙箱执行失败时：

1. 被标为 `deny` / `needs_human_review` 的脚本**严禁进入沙箱**（AC7）。
2. 其余已放行的检查继续执行（例如多次 `skill_run` / 多个检查命令中，一项失败不阻断其余项）。本期默认链路是单次 `run_checks.py`：若该次被拦或失败，则无沙箱侧 findings，但仍继续后处理 → 落库 → 出报告，**不回退宿主执行规则**。
3. 超时、非零退出、输出超限全部记入 `cr_sandbox_run`（含 error_type 与失败摘要），并进入 warnings 桶。
4. 任务状态：
   - `completed`：全流程成功，无 Filter 拦截、无沙箱失败、无运行告警。
   - `completed_with_warnings`：仍能生成最终报告，但存在 Filter 拦截、沙箱失败/超时/截断或其他运行告警。
   - `failed`：仅用于无法继续形成有效交付的关键失败——输入解析失败、DB 初始化失败、关键写库失败、报告无法生成。

永不因单次检查失败让整个评审任务崩溃（AC4）。

### 2.9 监控审计（R9）

`MetricsCollector` 在报告冻结时生成不可变 snapshot，落 `cr_report.metrics`（验收主路径），同时在关键阶段打 SDK telemetry span（code_review.total/.parse/.sandbox/.postprocess/.llm）。

snapshot 至少包含：`total_duration_ms`、`sandbox_duration_ms`、`llm_duration_ms`、`tool_call_count`、`sandbox_run_count`、`filter_block_count`、`filter_review_count`、`finding_count`、`warning_count`、`needs_human_review_count`、`suppressed_count`、`severity_distribution`、`category_distribution`、`error_type_distribution`、`runtime_type`、`python_version`、`platform`。

Telemetry span 属性采用白名单：只允许脱敏 task id、状态、阶段耗时、计数、枚举型 error code 和 runtime 类型；严禁写入 diff/evidence/recommendation/stdout/stderr 原文、环境变量值和本地绝对路径。无 OTel 环境时 span 自动成为零副作用。

### 2.10 报告（八段式，JSON + Markdown 双格式）

`review_report.json` + `review_report.md`，固定八段：

1. Findings 摘要（按 severity 排序）
2. 严重级别统计
3. 人工复核项（needs_human_review 桶）
4. 运行告警（warnings 桶）
5. Filter 拦截摘要
6. 沙箱执行摘要
7. 监控指标
8. 结论与可执行修复建议（编号、按严重级别排序）

`review_report.json` 是规范源，顶层至少包含 `schema_version`、`rule_pack_version`、`config_digest`、`input_sha256`、`task_id`、`input_summary`（含 source_kind 与各文件 review_scope）、四桶结果、Filter 摘要、sandbox 摘要、metrics snapshot 和 final conclusion。Markdown 的位置展示在 `line_side=old` 时必须明确标为旧侧行号，不能让读者误认为当前文件仍存在该行。生成流程固定为：

1. 构建报告对象并通过 `schemas/review_report.schema.json` 校验。
2. 对完整对象执行最终敏感信息扫描；命中明文时阻止持久化并将任务标为 failed。
3. 用同目录临时文件 + 原子替换写入 JSON。
4. Markdown 通过 `ReportRenderer` 仅从已校验 JSON 确定性渲染，写入前再次扫描并原子替换。
5. 数据库保存同一报告对象的脱敏内容或摘要，不重新计算另一份统计。

`ReportRenderer` 为扩展协议；本期实现 JSON 与 Markdown renderer，SARIF renderer 留在第 7 章。

### 2.11 CLI 与运行模式

`run_agent.py` 五个子命令：

- `review --diff-file|--repo-path|--files|--fixture [--dry-run] [--sandbox container|cube|local] [--model-mode fake|real|off] [--trace] [--log-level DEBUG|INFO|WARNING] [--fail-on-severity high|critical] [--db-url URL] [--output-dir DIR]`：直接调用唯一 `ReviewPipeline`，用于 CI 和确定性自动化。
- `user-query "<natural-language review intent>" --diff-file|--repo-path|--files|--fixture [--dry-run] [--sandbox container|cube|local] [--model-mode fake|real|off] [--trace] [--log-level DEBUG|INFO|WARNING] [--fail-on-severity high|critical] [--db-url URL] [--output-dir DIR]`：始终经 SDK `LlmAgent + SkillToolSet` 触发受控 Skill 链；自然语言仅表达意图，四种输入必须由结构化参数显式指定。
- `show <task_id>`：输出全链路 bundle
- `list`：列出历史任务
- `init-db`：幂等初始化

`--dry-run` = fake model（固定模板走与 real 完全相同的 LlmAgent+Runner 链路），**不**切换 sandbox。无 Docker 时必须同时显式传 `--sandbox local`，否则严格 container 默认会直接报错。零 Key + 无 Docker 的推荐命令：`python run_agent.py review --fixture 01_clean_simple --dry-run --sandbox local`。pytest 单测注入 fake runtime 是第三条路径，不冒充 CLI dry-run。

四种输入由互斥参数组强制只能选择一个。本期不提供 `--command`、`--run-tests` 或 `--llm-denoise`；任意命令和目标仓库测试不得通过隐藏参数进入当前实现。

`review` 直接调用唯一 `ReviewPipeline`；`user-query` 是唯一公开的 Agent 入口，SDK
`LlmAgent + SkillToolSet` 必须产生可观察的 `skill_load("code-review") → skill_run(...)`
工具调用，再由受控 `skill_run` 适配器委托同一 pipeline，不能产生第二套检测或持久化逻辑。
宿主在创建 Agent 前验证四选一结构化输入、路径、大小、编码和 diff 格式；不得让模型从自由文本推测
任意文件路径、命令、环境变量或未登记脚本。无效输入以退出码 2 拒绝，且不调用模型、Filter 或沙箱。
`skill_run` 对模型只暴露一次性 review request id；固定 Skill、script_id、argv、输入/输出路径、
环境、超时和输出限额必须由宿主结合 manifest 构造，原始 diff、宿主路径和命令字符串不得进入
模型上下文。未先成功 `skill_load`、Filter 非 ALLOW 或 request id 无效时，`skill_run` 必须零
沙箱副作用。成功的 CLI JSON 必须包含 `task_id`、状态、实际 sandbox、入口类型以及
`report_files.json` / `report_files.markdown` 的完整输出位置，方便人工和 CI 直接定位产物；路径
只输出到当前终端，绝不写入 report、数据库、Telemetry 或日志。维护者的完整 PowerShell 命令、
Docker 前置检查、16 个 fixture、模型模式和故障排查统一见
`examples/skills_code_review_agent/OPERATIONS.md`；真实模型的三项白名单变量由该目录 `.env` 读取，
runtime 类型、网络策略和输出目录必须显式通过 CLI 参数设置，不得藏在 `.env`。

`--trace` 是显式终端诊断模式：以 stderr JSON Lines 流式显示受控 query 解析、SDK
`skill_load` / `skill_run`、Filter、sandbox、Pipeline 和持久化状态；stdout 仍只输出最终 CLI JSON。
trace 字段只能包含固定事件名、安全枚举、计数、状态和布尔值，禁止输出模型私有推理、原始 query/diff、
代码/evidence、request id、命令、环境变量值和宿主路径；trace 不写入报告、数据库或 Telemetry。默认 `INFO`
日志也仅写 stderr，显示阶段、计数、固定状态码、耗时、实际 container ID 与终端可见的报告位置；`DEBUG`
可额外显示仓库相对文件路径、script_id 和已脱敏输出摘要。所有日志级别均禁止原始 diff、代码、evidence、
工具完整参数、workspace/request ID、环境变量和凭据。SDK 原始 INFO 固定降为 WARNING，避免暴露源码绝对路径和 workspace 标识。

**CLI 退出码约定**（`review` 子命令；`show`/`list`/`init-db` 成功 0、致命错误 2）：

| 退出码 | 含义 |
|--------|------|
| 0 | 审查完成且成功生成报告，含 `completed` 与 `completed_with_warnings` |
| 1 | 审查完成且报告已生成，但 findings 桶中存在达到 `--fail-on-severity` 阈值的正式 finding |
| 2 | 致命执行错误：输入无法解析、DB 关键写入失败、报告无法生成等（对应任务状态 `failed`） |

补充规则：

- Filter 拦截、沙箱脚本失败、`needs_human_review` / `suppressed` / `warnings` **默认不改变退出码**，只体现在任务状态与报告中（与 2.8.1 失败语义一致）。
- `--fail-on-severity` 默认关闭（等价于永不因 finding 返回 1）；CI 可显式设为 `high` 或 `critical`（判定为 severity ≥ 该阈值的 findings 桶条目）。只看 findings 桶，不看人工复核与运行告警。
- `evaluate.py` **独立**用非零退出码表示评测门禁失败（4.4 硬阈值任一不达标），**不复用** review CLI 的 finding 退出语义（evaluate 失败 ≠ 「有 high finding」）。
