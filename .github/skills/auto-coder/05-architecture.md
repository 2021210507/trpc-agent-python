<!-- Generated from DEV_SPEC.md. Do not edit directly. -->

## 5. 架构设计

### 5.1 分层

```
入口层    run_agent.py (CLI)          agent/ (LlmAgent + SkillToolSet)
              │                              │
              └──────────┬───────────────────┘
                         ▼
应用层    codereview/pipeline.py  ReviewPipeline.run()  ← 唯一检测链路
              │
              ├─ inputs.py / config.py（ChangeSet + 输入边界）
              ├─ governance.py（manifest 驱动的 Filter 治理门）
              ├─ sandbox.py（container|cube|local 工厂）
              ├─ dedup.py / redaction.py / llm_enhancer.py
              ├─ metrics.py / report.py（snapshot + ReportRenderer）
              └─ store/（SQLAlchemy 5 表 + ReviewStore ABC）
                         │
技能层    skills/code-review/scripts/lib/  ← 单一真相源（纯标准库）
          沙箱内直接执行；宿主 local 模式 importlib 加载同一份
```

### 5.2 目录树（交付清单，任务完成的文件级依据）

```
examples/skills_code_review_agent/
├── README.md
├── run_agent.py
├── agent/
│   ├── __init__.py
│   ├── agent.py
│   └── prompts.py
├── codereview/
│   ├── __init__.py
│   ├── config.py
│   ├── pipeline.py
│   ├── inputs.py
│   ├── governance.py
│   ├── sandbox.py
│   ├── redaction.py
│   ├── dedup.py
│   ├── llm_enhancer.py
│   ├── report.py
│   ├── metrics.py
│   └── store/
│       ├── __init__.py
│       ├── models.py
│       ├── review_store.py
│       └── init_db.py
├── skills/code-review/
│   ├── SKILL.md
│   ├── references/
│   │   └── security-boundaries.md
│   ├── rules/
│   │   ├── security.md
│   │   ├── async-errors.md
│   │   ├── resource-leak.md
│   │   ├── missing-tests.md
│   │   ├── secrets.md
│   │   └── db-lifecycle.md
│   └── scripts/
│       ├── manifest.json
│       ├── parse_diff.py
│       ├── run_checks.py
│       └── lib/
│           ├── __init__.py
│           ├── diff_parser.py
│           ├── rule_engine.py
│           ├── rules_security.py
│           ├── rules_async.py
│           ├── rules_resource.py
│           ├── rules_db.py
│           ├── rules_tests.py
│           └── secret_rules.py
├── evaluate.py
├── schemas/
│   └── review_report.schema.json
├── sample_output/
│   ├── review_report.json
│   └── review_report.md
└── tests/
    ├── README.md
    ├── unit/
    │   ├── test_config.py
    │   ├── test_diff_parser.py
    │   ├── test_redaction.py
    │   ├── test_rules.py
    │   ├── test_rules_ast.py
    │   ├── test_dedup.py
    │   └── test_metrics.py
    ├── integration/
    │   ├── test_inputs.py
    │   ├── test_store.py
    │   ├── test_report.py
    │   ├── test_skill_scripts.py
    │   ├── test_governance.py
    │   ├── test_sandbox_safety.py
    │   ├── test_pipeline.py
    │   ├── test_llm_enhancer.py
    │   └── test_agent_entry.py
    ├── e2e/
    │   ├── test_cli.py
    │   ├── test_fixtures_e2e.py
    │   └── test_evaluate.py
    ├── fixtures/
    │   ├── diffs/        # 8 条公开 fixture
    │   └── corpus/       # 标注评测语料
    └── support/          # 共享 fake、builder 和断言
```

### 5.3 Pipeline 八阶段

1. 建任务：`cr_review_task(status=running)`，记录输入类型、config snapshot、schema/rule-pack version 和 config digest。
2. 安全读取与解析：校验输入根、路径和体积，在受控宿主内存/任务目录读取原始内容，按输入形态提取带 `review_scope` 的 ChangeSet；`--files` 标为 snapshot/full_file，fixture 保留声明的载荷语义，新增/删除 hunk 使用固定 `0,0` 契约。此阶段不破坏性脱敏，也不记录代码原文。
3. Filter 治理门：解析 execution manifest，校验 script/摘要/参数/路径/环境/网络/runtime，并在执行前预检预算；DENY/NEEDS_HUMAN_REVIEW 短路并记录脱敏原因。
4. 沙箱执行：stage skill 与最小输入集 → 再校验 realpath/hash → 预算受控运行注册脚本。secrets 规则对原始内容检测，沙箱在输出 evidence/stdout/stderr 前首次脱敏；失败转 warnings，不回退宿主。
5. 后处理：宿主对所有输出二次脱敏 → changed-line 过滤 → 三元组稳定去重 → 无重叠阈值分桶。
6. LLM 增强（fake|real|off）：仅接收脱敏数据，只改写 recommendation/summary/复核提示，不得改变 canonical finding 集合及其 severity/confidence/bucket。
7. 冻结与持久化：生成不可变 metrics snapshot 和 canonical ReviewReport，最终泄漏扫描通过后写 findings/filter_events/sandbox_runs/report；任何明文命中阻止持久化。
8. 报告与清理：schema 校验 → JSON 原子写入 → 从 JSON 确定性渲染 MD 并原子写入 → telemetry 白名单打点 → `finally` 清理 workspace。

### 5.4 四信任域与三层脱敏

| 信任域 | 可见原始 diff | 允许输出 |
|--------|--------------|---------|
| 受控宿主输入层 | 是，仅任务内存/临时目录 | ChangeSet 元数据和送入隔离 workspace 的最小输入集；禁止日志 |
| 隔离沙箱 | 是，仅本次任务 | 已脱敏 findings、stdout/stderr 摘要 |
| LLM | 否 | 仅脱敏后的 finding 和摘要素材 |
| 持久化/报告/Telemetry | 否 | 已脱敏结构化数据、计数、枚举和摘要 |

三层脱敏：

1. 沙箱内：secrets 规则先对原始内容完成检测，产出 evidence/stdout/stderr 时首次脱敏（`lib/secret_rules.py`）。
2. 宿主：对 finding 的 evidence/recommendation、Filter reasons、异常和沙箱摘要进行二次脱敏。
3. 出口：JSON、Markdown、数据库和允许的 Telemetry 属性在写入前做完整对象扫描；发现明文则阻止写入并标记 failed。

检测规则与脱敏共享同一正则表（secret_rules.py 单一真相源），杜绝「检出未脱/脱了未检」。
