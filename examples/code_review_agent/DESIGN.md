# 自动代码评审 Agent 方案设计

## 方案设计说明

本 Agent 把 `code-review` Skill 作为规则与脚本的可复用边界：SKILL.md 说明输入、输出和安全边界，manifest 固定允许执行的脚本及其哈希，规则只对 diff 的新增侧或显式 snapshot 生效。Pipeline 是唯一检测链路，CLI、fixture、评测和 Agent 入口共享同一份解析、治理、沙箱、存储和报告对象，因此不会出现“测试走假实现、生产走另一套逻辑”的分叉。

沙箱默认使用 Container，并要求本次运行可验证 `network_mode=none`；Cube 缺少可证明的受控网络时拒绝；local 只是用户显式调试 fallback，必定留下隔离不可验证告警。Filter 在 stage 前校验 manifest、路径、结构化参数、网络策略和预算，DENY 与 NEEDS_HUMAN_REVIEW 不创建 sandbox。环境只按白名单重建，模型 Key、token 和 password 不会传给脚本。

数据库采用可替换的 SQL 接口，默认 SQLite 的五张 `cr_*` 表分别保存任务、sandbox run、Filter 事件、finding 与最终报告；不持久化原始 diff。finding 以文件、行号、类别去重，并依置信度分为 findings、needs_human_review、suppressed，运行故障只进入 warnings。报告 JSON 是 canonical 来源，Markdown、数据库摘要和 severity 统计均由它派生，确保可回放且排序稳定。

安全链路先在受控内存检测，再对 sandbox 输出、宿主字段和全部出口三次脱敏；发现明文会阻止写入。监控记录总耗时、沙箱与 LLM 耗时、调用次数、拦截次数、严重级别和异常分布。LLM 只可增强建议、摘要和人工复核提示，real 模式必须显式开启并从 `.env` 白名单读取，不能参与确定性检出或改变 finding 身份。

## 风险表

| 风险 | 控制措施 | 审计证据 |
|---|---|---|
| 任意命令执行 | manifest 加哈希、结构化参数和 Filter 前置拦截 | Filter 事件、零 sandbox run |
| 网络或宿主逃逸 | Container `network_mode=none`，Cube 默认拒绝，local 明示告警 | runtime 类型、网络策略摘要 |
| 密钥泄漏 | 同源 detect/redact、全出口扫描、模型环境白名单 | `plaintext_hits=0`、失败阻断 |
| 资源耗尽 | 次数、超时、单次/总输出和 deadline 预算 | sandbox run、warning、metrics |
| LLM 越权 | 仅合并文本字段，冻结 finding identity 与分桶 | fake/real identity 对照测试 |
| 误报与遗漏 | 确定性规则、公开语料、人工复核桶 | evaluation 指标、needs_human_review |
| 数据回放泄密 | 仅保存摘要和 canonical 脱敏报告，不保存原始 diff | SQLite bundle 查询 |

## AC1–AC8 核对

| 项目 | 核对结果 | 证据 |
|---|---|---|
| AC1 | ✓ | 8 条 simple fixture 与 8 条 complex 配对样例均产生报告与 bundle。 |
| AC2 | ✓（公开代理） | `evaluate.py` 输出 Recall/FP；不代表隐藏集。 |
| AC3 | ✓ | 五表初始化、CRUD 与 task bundle 测试。 |
| AC4 | ✓ | timeout、nonzero、截断与 Filter 短路测试。 |
| AC5 | ✓ | secret fixture 和全出口明文扫描。 |
| AC6 | ✓ | fake/local 评测时长门禁。 |
| AC7 | ✓ | deny/human review 无 sandbox 副作用。 |
| AC8 | ✓ | canonical JSON 与 Markdown/metrics/摘要一致性测试。 |
