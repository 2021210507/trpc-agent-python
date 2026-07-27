<!-- Generated from DEV_SPEC.md. Do not edit directly. -->

## 7. 未来规划

以下明确不在本期交付，留作后续迭代：

- **SARIF v2.1.0 输出**：基于本期 `ReportRenderer` 和 canonical ReviewReport 接 GitHub Code Scanning，不另建报告数据模型
- **沙箱内运行目标仓库单元测试**（执行边界已定，实施时照此）：仅 `--repo-path` 模式可用（--diff-file 无仓库可跑）；整体默认 off，显式 `--run-tests targeted` 开启。启用后默认只运行 diff 中新增/修改的测试文件及路径映射可定位的相关测试；无网络容器内 `pytest -q`，单次 ≤30s，不允许在线安装依赖；找不到相关测试**不自动跑全量**；全量测试或用户自定义测试命令必须显式请求、注册为受控参数模板并再次经过 Filter。结果分类固定为：测试断言失败 → sandbox 摘要 + needs_human_review；缺依赖/插件失败/ImportError/环境不兼容 → warnings；超时/容器错误 → warnings + sandbox error；未收集或无法映射测试 → needs_human_review。以上均**不进 findings 桶**、不参与 AC2，也不导致 review 崩溃
- **外部扫描器（bandit、semgrep）进沙箱**：R2 的可选执行目标，当前以规则脚本 + diff 解析满足要求
- **LLM 语义补审（盲区折中方案）**：对规则未检出但可疑的代码（2.3 声明盲区：跨函数资源传递、异常路径泄漏、数据流类异步错误、业务逻辑漏洞）做 LLM 二次审阅。硬约束：结果**只能标 needs_human_review，永远不进正式 findings、不参与检出率/误报率统计**——补语义盲区但不破坏规则层的确定性保证。需预录制 fixture 体系支撑 fake 模式
- **LLM 降噪二分类**：只能给 canonical finding 添加脱敏的“疑似误报、建议人工复核”辅助说明，不得直接删除 finding 或改写 severity/confidence/bucket/dedup；若未来要允许改变正式结果，必须另起 schema/rule-pack 版本和独立评测合同
- **A2A / AG-UI 服务化**：多轮对话与流式事件
- **RAG 编码规范知识库 + 跨会话长期记忆**：历史评审经验沉淀
- **多语言规则**：JS/Go 等语言的安全与资源规则
- **在线评测平台**：隐藏样本集持续回归与指标看板

### 7.1 风险登记表

| 风险 | 触发信号 | 本期缓解 |
|------|---------|---------|
| 正则规则误报 | 干净样本 finding-level FP 占比上升 | AST 确认、注释/字符串作用域过滤、降低置信度、稳定例外规则 |
| AST 报告历史问题 | finding 主定位不在 new_changed_lines | AST 节点范围强制与 changed lines 相交 |
| manifest 与脚本漂移 | staged 文件 SHA-256 不一致 | Filter 在运行前 deny 并记录脱敏事件 |
| 恶意路径或大输入耗尽资源 | realpath 越界、文件/字节/行数超限 | staging 前拒绝或标人工复核，不读取越界目标 |
| 敏感信息经旁路泄漏 | 最终输出扫描命中明文 | 阻止报告/DB 持久化，任务 failed，保留无明文错误码 |
| container 不可用 | runtime 初始化失败 | 生产默认明确报错；local 仅显式开发 fallback 并写 warning |
| 外部依赖导致测试噪声 | ImportError、插件/环境错误 | 本期不运行目标仓库测试；未来按上方失败类型分桶 |
