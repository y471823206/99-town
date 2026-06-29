# 99-town 开发流程

本项目使用 GitHub Issue → Branch → PR 工作流，由 AI Agent (北北/Hermes) 强制执行。

## 规则

1. 所有改动必须先建 GitHub Issue
2. 从 main 拉分支 `fix/N` 或 `feat/N`
3. commit 引用 issue 号
4. 提交 PR，review 后合并

## 仓库

- GitHub: https://github.com/y471823206/99-town
- 推送用 SSH: git@github.com:y471823206/99-town.git

## 禁止

- 直接改 main
- 无 issue 的改动
- 未测试的合并
