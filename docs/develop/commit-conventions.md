# 提交信息规范（Conventional Commits 1.0.0）

本项目遵循 [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) 规范。

## 提交信息结构

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

- `type` 与 `:` 及其后空格为必须；`scope`、`!`、`body`、`footer` 均为可选。
- 除 `BREAKING CHANGE` 必须大写外，各元素大小写不敏感。

## type

- 必须以 type 前缀开头，由名词构成。
- 规范定义的类型（必须按此含义使用）：

  | type | 含义 |
  | --- | --- |
  | `feat` | 引入新功能 |
  | `fix` | 修复 bug |
  | `build` | 影响构建系统或外部依赖的变更 |
  | `chore` | 不修改源码或测试的杂项变更 |
  | `ci` | CI 配置文件与脚本的变更 |
  | `docs` | 文档变更 |
  | `style` | 不影响代码含义的格式变更 |
  | `refactor` | 既不修复 bug 也不新增功能的重构 |
  | `perf` | 提升性能的代码变更 |
  | `test` | 新增或修正测试 |

## scope

- 可选，置于 type 之后、`:` 之前，用括号包裹。
- 必须是一个描述代码库某部分的名词，如 `fix(parser):`。

## description

- 必须，紧跟冒号与空格之后。
- 是对代码变更的简短概括。

## body

- 可选，在 description 之后空一行开始。
- 自由格式，可包含任意多段（以空行分隔）。

## footer

- 可选，在 body 之后空一行开始。
- 每个 footer 由一个 token + 分隔符 + 值组成：
  - 分隔符为 `:<space>` 或 `<space>#`
  - token 中的空格用 `-` 替代，如 `Acked-by`（以此区分 footer 与多段 body）
- `BREAKING CHANGE` 是例外，可原样作为 token（保持大写）；`BREAKING-CHANGE` 与 `BREAKING CHANGE` 同义。
