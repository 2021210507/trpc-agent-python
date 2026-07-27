<!-- Generated from DEV_SPEC.md. Do not edit directly. -->

## 6. 项目排期

> **排期原则**
> - 只按本文档设计落地：以 5.2 目录树为交付清单，每个任务都在文件系统产生可见变化
> - 每个任务 ≈1h 一个可验收增量，给出验收标准 + 测试方法，尽量 TDD
> - 先打通离线闭环（解析 → 规则 → 落库 → 报告 → dry-run），再上安全边界（Filter + 沙箱），最后 Agent 入口与评测
> - 外部依赖（Docker、真实模型）在单元测试一律 fake 注入；container/real 实测放专门任务

### 阶段总览

1. **阶段 A：工程骨架与离线内核** — 目录、配置、diff 解析、规则引擎、脱敏（纯标准库可测）
2. **阶段 B：落库闭环** — SQLAlchemy 5 表、去重分桶、报告、CLI、dry-run 全链路
3. **阶段 C：安全边界** — Filter 治理链、沙箱三后端、安全测试、container 实测
4. **阶段 D：Agent 入口与评测** — LlmAgent+SkillToolSet、LLM 增强、8 fixtures、evaluate.py
5. **阶段 E：收尾** — 指标核对、README、设计说明、sample_output、全绿

### 📊 进度跟踪表 (Progress Tracking)

> **状态说明**：`[ ]` 未开始 | `[~]` 进行中 | `[x]` 已完成

#### 阶段 A：工程骨架与离线内核

| 任务编号 | 任务名称 | 状态 | 完成日期 | 验收标准 | 测试方法 |
|---------|---------|------|---------|---------|---------|
| A1 | 目录骨架 + ReviewConfig + schema + 分层 pytest 基座 | [x] | 2026-07-24 | 5.2 目录树全部空模块就位；tests/unit、integration、e2e、fixtures、support 分层存在且 fixture 不在项目顶层；ReviewConfig 含 2.1 输入上限、2.6 预算默认值和版本字段；review_report schema 可加载；pytest 可发现并跑通冒烟测试 | tests/unit/test_config.py：测试分层目录、默认值/环境覆盖/config_digest 稳定性断言；schema 语法校验 |
| A2 | diff 解析器与 ChangeSet（scripts/lib/diff_parser.py） | [x] | 2026-07-25 | 按 2.1 字段契约解析 unified diff；覆盖 rename/binary/CRLF/no-newline/删除/新增/snapshot、review_scope、old/new changed lines；新增/snapshot old=`0,0`、删除 new=`0,0`，字段非空；old_to_new 只映射 context；完整新增文件可重建 full_text | tests/unit/test_diff_parser.py：逐边界断言 status/scope、规范路径、`0,0`、context-only 映射、analysis_mode 和 input_sha256 |
| A3 | 检/脱同源密钥模块（scripts/lib/secret_rules.py + codereview/redaction.py） | [x] | 2026-07-25 | ≥12 种密钥模式 + Shannon 熵；detect 与 redact 共用同一正则表；检测读取原始值，任何输出使用 `[REDACTED:<类型>]`；新侧与删除旧侧均扫描，旧侧定位带 line_side=old；recommendation/reasons/error/stdout/stderr 均可统一扫描 | tests/unit/test_redaction.py：≥48 条真实格式语料检出率 ≥95%、≥10 条良性语料；字符串/配置/删除侧密钥、注释占位符和所有旁路字段无明文 |
| A4 | 规则引擎框架 + 安全类规则（rule_engine.py + rules_security.py） | [x] | 2026-07-27 | Rule 协议（rule_id/category/severity/confidence/match）；SQLi f-string、shell=True、eval/exec 可检出；仅结构类规则忽略注释/docstring/普通字符串，secrets 不走该通用过滤 | tests/unit/test_rules.py：正样本命中；危险 API 仅出现在注释/字符串时 0 FP；字符串真实密钥仍命中 |
| A5 | 异步 + 资源泄漏规则（rules_async.py + rules_resource.py） | [x] | 2026-07-26 | async 内 time.sleep、未 await、open/ClientSession 未 with/close 可检出（含 hunk 跨行） | tests/unit/test_rules.py 扩展：各规则正/负样本 |
| A6 | DB 生命周期 + 测试缺失规则（rules_db.py + rules_tests.py） | [x] | 2026-07-26 | 连接未关/事务未 commit 可检出；missing-tests 为变更集级启发式，置信度锁 0.5–0.8 | tests/unit/test_rules.py 扩展：missing-tests 断言 confidence<0.8 恒成立 |
| A7 | AST 增强层（requires_full_file + review_scope 约束） | [x] | 2026-07-26 | changed_lines scope 只报 AST 节点与新变更行相交的问题；full_file scope 明确扫描全文；deleted_lines 不跑普通 AST；纯残缺 diff 不 ast.parse；失败降级 + warning | tests/unit/test_rules_ast.py：增量模式历史问题不报、snapshot 模式同一问题可报、变更行命中、新增文件 AST、删除/残缺/语法错误稳定处理 |
| A8 | 输入层与安全 staging（codereview/inputs.py） | [x] | 2026-07-26 | 四种输入互斥并统一产出 ChangeSet；`--files` 固定 snapshot/full_file，fixture 保留 diff/full-file 载荷类型，repo untracked 为 added/full_file；Git argv 禁 shell；realpath、symlink/junction 和输入总量在 staging 前检查；原始内容仅留受控任务域 | tests/integration/test_inputs.py：四输入与 scope/status；fixture diff hunk 不被改写；.env 检出、忽略目录/二进制；路径/超限拒绝；日志无原始密钥 |
| A9 | CR Skill、执行 manifest 与沙箱入口 | [x] | 2026-07-26 | SKILL.md frontmatter 合规；6 篇规则文档声明能力/盲区；security-boundaries.md 完整；manifest 声明 script_id/entrypoint/hash/参数/预算/网络；run_checks.py 读输入输出已脱敏 findings.json | tests/integration/test_skill_scripts.py：manifest schema/摘要校验；subprocess 直跑注册脚本；findings 9 字段且输出无明文 |

#### 阶段 B：落库闭环

| 任务编号 | 任务名称 | 状态 | 完成日期 | 验收标准 | 测试方法 |
|---------|---------|------|---------|---------|---------|
| B1 | SQLAlchemy 5 表 + ReviewStore ABC + init_db | [x] | 2026-07-26 | 2.8 的 5 表模型和索引；report 保存 schema/rule-pack/config/input 版本摘要；SqlReviewStore 支持 SQLite 默认和 URL 切换；get_task_bundle 聚合返回；init-db 幂等 | tests/integration/test_store.py：CRUD、索引/版本字段、bundle 完整性、重复 init-db、脱敏 JSON 字段 |
| B2 | 稳定去重与四桶路由（codereview/dedup.py） | [x] | 2026-07-26 | 三元组去重；按 severity/confidence/evidence 具体度选主项；also_matched 稳定合并；边界无重叠；warnings 只收运行告警 | tests/unit/test_dedup.py：候选乱序输入仍生成相同 JSON；0.50/0.80/1.00 边界和同行同类合并断言 |
| B3 | MetricsCollector + telemetry span（codereview/metrics.py） | [x] | 2026-07-27 | 2.9 的 immutable snapshot 字段完整；span 属性仅走白名单；无 OTel 环境零副作用 | tests/unit/test_metrics.py：三桶/suppressed/Filter 两类计数；snapshot 冻结；敏感文本和绝对路径无法进入 span |
| B4 | Canonical JSON + Markdown renderer（codereview/report.py） | [x] | 2026-07-27 | JSON schema 校验、稳定排序、最终泄漏扫描、原子写入；input_summary 显示 source/scope；MD 仅从 JSON 渲染并区分 old/new 行号；八段完整；ReportRenderer 可扩展 | tests/integration/test_report.py：scope 与 line_side 渲染、JSON/MD/DB 统计一致、重复渲染字节一致、空 findings、原子写入和明文阻止 |
| B5 | ReviewPipeline 八阶段编排（codereview/pipeline.py，fake runtime + model off 先行） | [x] | 2026-07-27 | 5.3 八阶段串通；原始输入仅存在于受控宿主/沙箱；沙箱先检测再脱敏，宿主二次脱敏，出口扫描；异常按 2.8.1 收敛；finally 清理 workspace | tests/integration/test_pipeline.py：真实格式密钥能检出但 task/findings/report/log 无明文；清理成功/失败语义；DB 无原始 diff 全文 |
| B6 | CLI 四子命令 + dry-run 链路（run_agent.py） | [x] | 2026-07-27 | review/show/list/init-db 可用；四输入互斥；支持 `--db-url`；`--dry-run --sandbox local` 零 Key/无 Docker 跑通；仅 dry-run 不换 sandbox；退出码 0/1/2；本期拒绝 command/run-tests/llm-denoise 参数 | tests/e2e/test_cli.py：review→show→list；临时 DB URL；零 Key local <120s；无 Docker strict container exit=2；fail-on-severity 边界 |

#### 阶段 C：安全边界

| 任务编号 | 任务名称 | 状态 | 完成日期 | 验收标准 | 测试方法 |
|---------|---------|------|---------|---------|---------|
| C1 | Manifest 驱动 Filter 治理链（codereview/governance.py） | [x] | 2026-07-27 | 基于真实 BaseFilter/run_filters；按 2.7 顺序校验 script/hash/参数/路径/环境/网络/预算/runtime；网络决策读取最终生效配置/可验证证明而非仅凭 capability；FilterAction 与 FindingBucket 分型；非 ALLOW 短路且原因脱敏落库 | tests/integration/test_governance.py：未注册脚本、hash 不符、参数/shell/path/预算逃逸均被拒且副作用为 0；container capability 为 true 但实际 network_mode=none 可放行；cube 无证明默认拒绝、仅用户确认仍拒绝 |
| C2 | 沙箱工厂、staging 与预算（codereview/sandbox.py） | [x] | 2026-07-27 | container 严格默认且实际 `network_mode=none` 可验证；宿主 repo 不可写挂载；staging 后复验 realpath/hash；per-run 与累计预算预检；WorkspaceOutputSpec 限额；环境构造而非透传 | tests/integration/test_sandbox_safety.py：只读/最小 staging、网络配置默认值与覆盖拒绝、超时、输出截断、累计预算、金丝雀环境变量 |
| C3 | 沙箱失败即数据 + container 实测 | [x] | 2026-07-27 | blocked/timeout/nonzero/truncated/cleanup_error 均形成脱敏 run/warning；任务可出报告则 completed_with_warnings；Docker 下 02/08 fixture 真容器跑通且 network_mode=none 未覆盖 | tests/integration/test_sandbox_safety.py 扩展 + @pytest.mark.container；捕获输出全量明文扫描 |

#### 阶段 D：Agent 入口与评测

| 任务编号 | 任务名称 | 状态 | 完成日期 | 验收标准 | 测试方法 |
|---------|---------|------|---------|---------|---------|
| D1 | LLM 增强层（codereview/llm_enhancer.py，fake|real|off） | [x] | 2026-07-27 | fake 与 real 走相同 LlmAgent+Runner 路径；仅改写 recommendation/summary/复核提示；输入全量脱敏；不得改变 finding identity/rule/severity/confidence/bucket/dedup；有 Key 也不自动 real | tests/integration/test_llm_enhancer.py：canonical finding 对象前后逐字段一致；仅允许文本增强字段变化；LLM 输入无明文 |
| D2 | Agent 入口（agent/agent.py + prompts.py，LlmAgent+SkillToolSet） | [x] | 2026-07-27 | 经 SkillRepository 加载 code-review skill；Agent 与 CLI 共享同一 manifest、Filter、sandbox、storage 和 ReviewPipeline；输出 canonical finding 集合一致 | tests/integration/test_agent_entry.py：双入口一致性断言；两入口对未注册脚本同样拒绝 |
| D3 | 8 条公开 fixture + e2e（tests/fixtures/diffs/ + tests/e2e/test_fixtures_e2e.py） | [x] | 2026-07-27 | 4.3 表 8 条全交付；逐条断言 findings/桶/状态/JSON+MD+DB；08 号验证“真实密钥能检出且所有出口无明文”及注释占位符降噪 | pytest tests/e2e/test_fixtures_e2e.py 参数化 8/8 通过 + 日志/文件/DB 字节级扫描 |
| D4 | 评测语料 + evaluate.py CI 硬门禁 | [x] | 2026-07-27 | 4.4 语料规模与 blind-spot 观测集达标；匹配键 (file,line,category)；硬门禁：8 fixture、高危 Recall≥0.8、finding-level FP 占比≤0.15、脱敏≥0.95、≤120s；强制 fake+local；摘要含版本/配置/环境；默认不写 DB；README 明示 AC2 为代理 | python examples/code_review_agent/evaluate.py --sandbox local（期望 exit=0）+ tests/e2e/test_evaluate.py：禁止 real/LLM 降噪参数，门禁失败 exit 非零 |

#### 阶段 E：收尾

| 任务编号 | 任务名称 | 状态 | 完成日期 | 验收标准 | 测试方法 |
|---------|---------|------|---------|---------|---------|
| E1 | real 模型实测 + sample_output | [x] | 2026-07-27 | real 模式仅显式开启并用真实 Key 跑通 02_security fixture；sample_output JSON 通过 schema，MD 由该 JSON 渲染，样例不含环境特定绝对路径或敏感值 | @pytest.mark.real_llm 用例 + schema/稳定渲染/明文扫描 |
| E2 | README + 300–500 字设计说明 + 验收总检 | [x] | 2026-07-27 | README 含用法/AC 代理口径/安全信任域/manifest/沙箱 local 指引/输出限制；设计说明覆盖题目全部主题；风险表完整；AC1–AC8 逐条核对 | 全量 pytest + flake8 + schema 校验 + AC 对照表逐项打勾 |
| E3 | 8 条 realistic fixture + 成对 E2E | [x] | 2026-07-27 | 原 8 条 smoke fixture 全部保留；每类新增 1 条 60–150 行新增代码、至少双文件且包含正常实现/风险/干扰项的 realistic diff；16 条均验证 JSON+MD+DB，realistic 逐条保持类别、分桶、去重和脱敏契约；evaluate 仍使用原 8 条门禁 | tests/e2e/test_fixtures_e2e.py：8 条 realistic 逐条聚焦通过 + 原 8 条 smoke 回归 + 普通全量回归 |
