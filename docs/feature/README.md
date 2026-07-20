# Feature Designs

This directory contains draft designs for upcoming features that are not yet
part of the stable public API.

Use one subdirectory per new feature. The directory is the documentation carrier
for the feature's requirements, technical design, architect review,
implementation plan, verification notes, migration notes, and release readiness.
Prefer this layout:

```text
docs/feature/<feature-slug>/
  requirements.md
  design.md
  technical-review-YYYY-MM-DD.md
  implementation-plan.md
  verification.md
```

Once a feature is implemented and stabilized, update the stable docs such as
`docs/api.md`, package READMEs, or architecture docs, and keep the feature
directory as historical context or mark it superseded.

Current drafts, including older single-file designs:

- [Codex Feature Lifecycle Plugin](./codex-feature-lifecycle-plugin/requirements.md)
- [Accessibility Selector Engine Technical Design](./accessibility-selector-engine/design.md)
- [WeChat Agent Skill Technical Design](./wechat-agent-skill/design.md)
- [WeChat Tool Internal Modularization](./wechat-tool-modularization/design.md)
- [WeChat Accessibility Action API Design](./wechat-accessibility-action-api-design.md)
