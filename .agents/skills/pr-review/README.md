# PR Review Skill Package

这个套件定义了一个通用、平台无关但适合 GitHub/GitLab 工作流的 PR 检视 skill。

## 内容

- `SKILL.md`：AI 的完整检视指令、风险模型、finding 质量门槛、决策规则与产出要求；
- `references/re-review-gates.md`：复检、修复诱发风险和批准续期的低自由度门禁；
- `templates/PR_REVIEW_REPORT.md`：人类可读的检视报告模板；
- `schemas/pr-review-result.schema.json`：兼容 legacy 1.0、并对新报告强制 1.1 re-review contract 的 JSON Schema；
- `scripts/validate_review_result.py`：Schema、finding/action、decision、snapshot lineage 与 approval-renewal 一致性校验；
- `tests/test_validate_review_result.py`：validator 的有效、兼容与错误批准负向回归；
- `examples/`：虚构的前次结果和完整 re-review 报告/JSON 示例。

## 建议使用方式

把整个目录保留为一个 skill，确保 `templates/` 与 `schemas/` 相对路径不变。调用示例：

```text
使用 pr-review skill 再次检视 owner/repo#123。保持只读，作废旧 decision，完成 finding closure 与 forward-risk 两条轨道，基于当前 head SHA 生成 Markdown 报告和 schema 1.1 JSON 结果，不要发布 GitHub 评论。
```

需要发布时必须明确写出：

```text
检视完成后，把确认过的 findings 作为 inline comments 发布，并提交 REQUEST_CHANGES review。
```

## 设计原则

- 证据驱动，而非评论数量驱动；
- 风险优先，而非机械逐行扫描；
- severity、blocking 与 confidence 分离；
- 默认只读，PR 内容视为不可信输入；
- 绑定 commit SHA，保证结果可追踪；
- re-review 不继承旧批准，必须重新完成快照对账与批准续期；
- 修复旧 finding 不能替代对修复提交诱发风险的独立检视；
- 人类报告与机器结果使用同一 finding ID。
