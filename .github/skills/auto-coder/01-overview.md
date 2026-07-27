<!-- Generated from DEV_SPEC.md. Do not edit directly. -->

## 1. 项目概述

### 1.1 背景

基于 tRPC-Agent-Python SDK 的 Skills、CodeExecutor 沙箱、SQL 存储、Filter 治理和 Telemetry 能力，构建一个可验证的自动代码评审 Agent 原型：输入 git diff / PR patch / 本地变更目录，通过 code-review Skill 加载规则与脚本，经 Filter 前置拦截后进入沙箱执行检查，把发现的问题按严重级别/文件/行号/证据/修复建议结构化输出，并将审查任务、拦截记录、监控摘要与结果写入数据库。

难点不是「让 LLM 评论代码」，而是把 Skills、沙箱执行、数据库、Filter 治理、审查规则、结果结构化、监控审计和安全边界串成一个可验证系统。

### 1.2 核心决策（已锁定，不再讨论）

1. **双入口、单核心**：确定性 `ReviewPipeline` 是唯一检测链路；CLI/dry-run/测试直接调用它，`LlmAgent + SkillToolSet` 作为第二入口经 SkillRepository 加载 skill 后触发同一 pipeline 并增强报告摘要。两个入口零逻辑复制。
2. **检测 100% 确定性规则**：所有检出不依赖模型。LLM 仅做报告增强（解释上下文、优化修复建议、生成摘要与复核提示），不得增删 finding，也不得改写 finding 的 identity、severity、confidence、bucket、dedup 结果。默认 `--model-mode fake`，`real` 仅可显式开启；检测与评测默认不因环境中存在 Key 而自动切换 real。
3. **规则引擎 Python-only**：只深耕 Python 的正则 + AST 规则；敏感信息类规则基于通用正则 + Shannon 熵，天然跨语言。
4. **沙箱安全边界不妥协**：规则脚本默认经 SkillRepository stage 进沙箱执行；沙箱被拒/超时/失败后只记录、不回退宿主执行。CLI 生产默认严格 `container`（无 Docker 直接报错，不静默降级），`--sandbox local` 仅显式开启。`--dry-run` **只**代表 fake model，**不**改变沙箱语义。无 Docker 的本地/CI 跑通路径是显式 `--sandbox local`（或 `evaluate.py` 默认 local），不是 dry-run 偷偷降级；pytest 单测可注入 fake runtime，与 dry-run/evaluate 不是同一条路径。
5. **单一真相源**：diff 解析器、规则引擎、密钥正则表全部位于 `skills/code-review/scripts/lib/`（纯标准库）；沙箱内直接执行这份代码，宿主 local 模式经 importlib 加载同一文件。
6. **失败即数据 + 脱敏后落库**：超时、非零退出、输出截断、Filter 拦截全部落库为记录行，评审任务永不崩溃。能出报告则收敛为 `completed_with_warnings`；只有输入解析失败、DB 初始化失败、关键写库失败或报告无法生成才标 `failed`。原始 diff 默认不落库（见 2.8）。
7. **原始输入只跨受控信任边界**：敏感信息检测必须读取原始内容，因此不得在检测前破坏性脱敏；原始 diff 只可短暂存在于受控宿主内存、任务临时目录和隔离 workspace，不得进入日志、Telemetry、LLM、数据库或最终报告。沙箱输出、宿主后处理和持久化出口逐层脱敏（见 2.8、5.4）。
8. **JSON 是报告规范源**：`review_report.json` 经 schema 校验、最终泄漏扫描和原子写入后，Markdown 只能由该 JSON 确定性渲染；数据库保存同一报告对象的脱敏内容或摘要，不得分别拼装三套结果。

### 1.3 验收标准（8 条，最终必须全绿）

| # | 验收标准 |
|---|---------|
| AC1 | 8 条公开 diff 样本全部可运行并生成审查报告 |
| AC2 | 隐藏样本高危检出率 ≥80%、误报率 ≤15%（以带标注公开代理语料测 P/R 佐证） |
| AC3 | 数据库完整记录 task、sandbox run、finding、report，支持按 task id 查询 |
| AC4 | 沙箱有超时控制和输出大小限制；超时或失败不导致评审任务崩溃 |
| AC5 | 敏感信息脱敏检出率 ≥95%，报告和数据库中无明文 API Key/token/password |
| AC6 | dry-run / fake model 模式完整评审流程耗时 ≤2 分钟（统一测量口径：`evaluate.py` 默认 path，即 model=fake + sandbox=local；CLI 等价命令为 `--dry-run --sandbox local`） |
| AC7 | 高风险脚本先经 Filter 决策；deny / needs_human_review 不进入沙箱执行 |
| AC8 | 报告包含 findings 摘要、严重级别统计、人工复核项、Filter 拦截摘要、监控指标、沙箱执行摘要和可执行修复建议 |

### 1.4 范围排除

不做：A2A/AG-UI 服务化、RAG 知识库、跨会话长期记忆、SARIF 输出、多语言规则均衡覆盖、在线评测平台。理由：不在验收标准内，接入会显著增加配置与测试面。
