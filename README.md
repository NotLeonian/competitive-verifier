# competitive-verifier

[![Actions Status](https://github.com/NotLeonian/competitive-verifier/actions/workflows/verify.yml/badge.svg)](https://github.com/NotLeonian/competitive-verifier/actions) [![GitHub Pages](https://img.shields.io/static/v1?label=GitHub+Pages&message=+&color=brightgreen&logo=github)](https://notleonian.github.io/competitive-verifier)

upstream の PyPI: [![PyPI](https://img.shields.io/pypi/v/competitive-verifier)](https://pypi.org/project/competitive-verifier/)

This is [Not_Leonian](https://github.com/NotLeonian)'s fork of [competitive-verifier/competitive-verifier](https://github.com/competitive-verifier/competitive-verifier).

- [Getting Started](https://notleonian.github.io/competitive-verifier/installer.html) / [日本語](https://notleonian.github.io/competitive-verifier/installer.ja.html)
- [Reference](https://notleonian.github.io/competitive-verifier/document.html) / [日本語](https://notleonian.github.io/competitive-verifier/document.ja.html)
- [DESIGN(日本語)](https://notleonian.github.io/competitive-verifier/DESIGN)


## Get started

### Use in GitHub Actions

See [GitHub Pages](https://notleonian.github.io/competitive-verifier/installer.html).
[日本語](https://notleonian.github.io/competitive-verifier/installer.ja.html)

### Use in local

#### Install(local)

Needs Python 3.9 or greater.

```sh
pip install competitive-verifier
```

Or

```sh
pip install git+https://github.com/NotLeonian/competitive-verifier.git@main
```

末尾の `main` の代わりに、main ブランチの最新のコミットの SHA を指定するとより堅実である。

**Migrate from verification-helper**

Run this script.

```sh
competitive-verifier migrate
```

## Development for contributors

```sh
pip install -U poetry
poetry install

# test
poetry run pytest

# format
poetry run poe format

# run local source
poetry run competitive-verifier $args
```