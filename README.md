# context-harness

`context-harness` 是一个 local-first 的个人 AI 上下文闭环框架。

V1 聚焦两个本地 Code Agent 数据源：

- Codex
- Claude Code

项目采用“机制层”和“用户数据层”分离的设计。仓库只维护 CLI、skills、hook installers、templates、docs 和 tests；conversations、memory、logs、sync state 等用户数据放在可配置的数据目录中，例如 `~/.context-harness`。

当前设计文档：

- [docs/superpowers/specs/2026-06-16-context-harness-design.md](docs/superpowers/specs/2026-06-16-context-harness-design.md)
