<!-- Generated from DEV_SPEC.md. Do not edit directly. -->

## 4. 测试约定

### 4.1 目录与框架

- pytest；所有测试代码、测试辅助和测试数据统一放在 `examples/skills_code_review_agent/tests/`
- `tests/unit/`：单个确定性模块接口测试；不依赖 Docker、API Key 或网络，外部依赖使用 fake 或临时本地替代
- `tests/integration/`：多个模块或本地适配器的协作测试，包括 SQLite、Filter 链、Skill 脚本、沙箱和 pipeline
- `tests/e2e/`：从 CLI / evaluate 输入到 JSON、Markdown、数据库 bundle、指标和退出码的完整闭环
- `tests/fixtures/`：只存测试输入与预期数据，不存可执行测试；公开样本放 `diffs/`，评测语料放 `corpus/`
- `tests/support/`：只存被两个以上测试层复用的 fake、builder 和公共断言，不复制产品逻辑
- 命名：`test_<module>.py`；8 条公开样本的系统测试用 `tests/e2e/test_fixtures_e2e.py`
- container 实测用 `@pytest.mark.container` 标记（无 Docker 环境 skip）
- real 模型实测用 `@pytest.mark.real_llm` 标记（无 Key 环境 skip）
- 必选 fixture 缺失必须失败，不得 skip；所有写入使用 `tmp_path`、临时 SQLite 或任务 workspace，不污染业务目录

### 4.2 Fake 注入约定

- 沙箱：测试经构造函数注入 fake workspace runtime（预置 stdout/exit_code/超时行为），不 monkeypatch 内部函数
- 模型：fake model 走与 real 完全相同的调用路径，返回固定模板
- 数据库：单测用 `sqlite:///:memory:` 或 tmp_path 下临时文件

### 4.3 公开 fixture（8 条，AC1 硬性交付）

数据位于 `tests/fixtures/diffs/`，由 `tests/e2e/test_fixtures_e2e.py` 通过公开入口执行：

| fixture | 内容 | 预期 |
|---------|------|------|
| 01_clean | 无问题 diff | 0 findings，报告正常生成 |
| 02_security | SQL 注入 f-string + subprocess shell=True | ≥2 条 security findings（high/critical） |
| 03_async_leak | async 内 time.sleep + ClientSession 未关 | async-errors + resource-leak 各 ≥1 |
| 04_db_lifecycle | 连接未 close、事务未 commit | ≥1 条 db-lifecycle |
| 05_missing_tests | 改源码不改测试 | needs_human_review 含 missing-tests 项，findings 桶为空该类 |
| 06_duplicate_finding | 同文件同行同类多规则命中 | 去重后 1 条，extra.also_matched 非空 |
| 07_sandbox_failure | 注入沙箱失败（--inject-sandbox-failure 或 fake runtime） | 0 findings + warnings 记录 + status=completed_with_warnings，报告照常渲染 |
| 08_secret_redaction | 字符串/配置中含 AWS Key、GitHub PAT、password，并含注释占位符对照 | 真实格式产生 secrets finding；占位符降噪；报告、DB、日志和沙箱摘要字节级无明文 |

### 4.4 评测语料与 CI 硬门禁（AC2 代理）

`evaluate.py` 是本地/CI 的离线评测硬门禁，**不拒绝**；但必须澄清口径，避免把公开语料门禁误写成「官方隐藏样本 AC2」。

**语料规模（定死，禁止「若干」这种模糊表述）**：

- 正样本 ≥20（6 类覆盖，不含 2.3 声明盲区场景）
- 干净负样本 ≥10（高置信 FP 期望为 0）
- 密钥语料 ≥48 条 + 良性列表（0 FP）
- 另含边界样本：纯 diff changed-lines vs `--files` full-file 两种审查口径、fixture 载荷类型保持、残缺 hunk、binary/rename、新增/删除 `0,0` 退化值、context-only 行映射和删除侧 secret 定位
- 匹配键：`(file, line, category)`，与去重三元组一致；只匹配 findings 桶（needs_human_review / suppressed / warnings 不计入 P/R）
- 另建 blind-spot stress corpus，覆盖拆分密钥、动态拼接、跨函数资源传递、非标准测试目录等已声明盲区；只输出观测结果，不混入硬门禁分母，也不得从评测产物中静默消失

**硬门禁阈值（任一不达标 → 非零退出码）**：

| 指标 | 阈值 | 对应验收 |
|------|------|---------|
| 8 条公开 fixture 全部成功产出 JSON + MD + DB 记录 | 8/8 | AC1 |
| 高危问题 Recall（critical/high，代理语料） | ≥ 0.80 | AC2 代理 |
| findings 桶 finding-level 误报占比 `FP/(TP+FP)` | ≤ 0.15 | AC2 代理 |
| 脱敏检出率 | ≥ 0.95 | AC5 |
| fake model 完整评测流程墙钟时间 | ≤ 120 s | AC6 |
| Precision / Recall / F1 | 输出到摘要；F1 **不设单独硬阈值**（由上两项 Recall/FP 约束即可，避免三重冲突） | 观测指标 |

**明确不是硬门禁的**：

- 官方「隐藏样本」AC2 本身——CI 拿不到隐藏集；门禁只能证明**公开代理语料**达标，README 验收表须写明「AC2 以代理语料佐证」。
- LLM 降噪/补审相关指标——本期默认 off，不进门禁。
- container / real LLM 实测——用 pytest mark，无环境时 skip，不阻塞普通 CI。

**输出与回归历史**：评测强制 `model_mode=fake`，不接受 real 或本期不存在的 LLM 降噪参数。摘要写 `eval_summary.json`（必选），记录 schema/rule-pack/config digest、Python、平台、runtime 和墙钟时间；可选 `--write-db` 写入独立 SQLite 形成回归历史（默认关闭，且不得污染业务 review.db）。

**evaluate.py 的 sandbox 口径（与 CLI 生产默认解耦）**：

| 路径 | sandbox | model | 用途 |
|------|---------|-------|------|
| `evaluate.py`（普通 CI / 本地门禁，默认） | **显式 `local`** | fake | ≤120s 硬门禁统一测量口径；摘要记录 runtime/OS/是否有 Docker |
| `evaluate.py --sandbox container` | container | fake | 额外结果；Docker 可用时跑，**不与 local 基准耗时直接比较** |
| `run_agent.py review`（生产默认） | **严格 container** | fake\|real\|off | 无 Docker 直接报错；不受 evaluate 默认影响 |
| pytest 单元 / pipeline 单测 | 注入 fake workspace | fake/off | 测编排与落库，不冒充「脚本真执行」 |
| `@pytest.mark.container` / cube 集成 | container / cube | fake | Docker 可用时跑，不可用 skip，**不阻塞普通 CI** |

硬约束：

1. **evaluate 默认 local 必须是显式选择**（代码与文档都写成 `--sandbox local`），不是 `--dry-run` 偷偷换沙箱——CLI 的 dry-run 仍只代表 fake model，沙箱语义不变。
2. **evaluate 默认路径禁止用 fake workspace**：必须真跑仓库自带的可信 Skill 脚本 + 固定 fixture，否则无法证明脚本执行过；仅允许执行本仓库 `skills/code-review/scripts/` 与 fixtures，禁止用户自定义命令混入门禁路径。
3. local 模式下 Filter 仍运行，并把「隔离与网络策略不可强制证明」降级告警写入 warnings；cube 默认拒绝的原因是当前 SDK 无法提供具体实例无出口/受控网关的可验证证明，而不是 `network_allowed=True` 字段本身。container 集成测试必须验证实际生效的 `network_mode=none`。

**与 pytest 的分工**：pytest 负责 unit、integration 与 fixture 驱动的 e2e；`evaluate.py` 负责跨 fixture 的聚合指标门禁。CI 建议顺序：`pytest examples/skills_code_review_agent/tests/ -q`（跳过 container/real_llm）→ `python examples/skills_code_review_agent/evaluate.py --sandbox local`（model=fake + sandbox=local）。

### 4.5 关键安全测试

- 超时击杀：注入 sleep 超过 per_run_timeout 的脚本，断言 timed_out=True 且任务不崩
- 输出截断：产出超限输出，断言截断标志 + warnings
- 金丝雀环境变量：宿主设 `TRPC_AGENT_API_KEY=canary-xyz`，断言沙箱子进程环境与所有落库内容不含该值
- 治理哨兵：未注册脚本、摘要不匹配、未知/重复/超长参数、shell 元字符和预算超限请求均被 deny，副作用哨兵未触发、沙箱运行数为 0
- 路径边界：覆盖 `../`、绝对宿主路径、指向 repo 外的 symlink/junction、超大输入，断言 staging 前拒绝且未读取目标内容
- 检测后脱敏：真实格式密钥在原始 fixture 中能生成 secrets finding，但 evidence、recommendation、Filter reasons、异常、stdout/stderr、Telemetry、JSON/MD/DB 均无明文
- 字符串/注释作用域：结构类 API 仅出现在注释/字符串时不报；字符串中的真实密钥必须检出；明显占位符不进入高置信 findings
- changed-line AST：完整文件中的历史遗留问题不在 changed lines 时不报；新增文件可重建全文时启用 AST；残缺 hunk 自动降级且不崩
- full-file scope：同一文件通过 `--files` 输入时允许报告任意行，ChangeSet/JSON/MD 明确显示 `status=snapshot` 与 `review_scope=full_file`；不得把它的结果冒充增量审查
- hunk 退化状态：新增/snapshot 断言 old=`0,0`，删除断言 new=`0,0`，字段非空；映射只含 context 行；删除侧 secret 使用真实 old line 和 `line_side=old`
- 报告一致性：JSON 通过 schema，MD 与 DB 统计均来自同一报告对象；模拟中断后不存在半写文件
- 明文扫描：e2e 后对 review_report.json/.md、sqlite 文件和捕获日志做字节级扫描，断言无明文密钥

### 4.6 测试哲学

只测外部行为（CLI 出入参、报告内容、DB 行、返回结构），不测内部实现细节；每条 AC 至少有一个专门测试；断言用具体值，不用「不抛异常」当通过标准。
