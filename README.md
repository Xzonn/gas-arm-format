# gas-arm-format

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://github.com/Xzonn/gas-arm-format/blob/main/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/Xzonn/gas-arm-format/blob/main/LICENSE)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/Xzonn/gas-arm-format/blob/main/.pre-commit-hooks.yaml)

A formatter and pre-commit hook for GNU ARM/Thumb assembly.

Formats `.s` and preprocessed `.S` files.

```diff
-entry:mov   r0,#1
-push {r4,lr}
+entry: mov r0, #1
+  push {r4, lr}
```

## Installation

Requires Python 3.10 or later.

```console
pip install gas-arm-format
```

## Usage

Format one or more files in place:

```console
gas-arm-format source.S other.s
```

Check formatting without writing changes:

```console
gas-arm-format --check source.S
```

`--check` prints the names of files that need formatting and exits with status 1
if any are found.

Instructions use two-space indentation by default; directives start at column
zero. To change the indentation:

```console
gas-arm-format --indent 4 --directive-indent 0 source.S
```

Run `gas-arm-format --help` for all options.

## As a pre-commit hook

Add the following to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Xzonn/gas-arm-format
    rev: v0.1.0
    hooks:
      - id: gas-arm-format
```

The hook formats `.s` and `.S` files. Pass command-line options through `args`:

```yaml
      - id: gas-arm-format
        args: [--indent, "4"]
```

## License

MIT. See [LICENSE](https://github.com/Xzonn/gas-arm-format/blob/main/LICENSE).
