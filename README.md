# competitive-verifier

[![Actions Status](https://github.com/NotLeonian/competitive-verifier/actions/workflows/verify.yml/badge.svg?branch=main)](https://github.com/NotLeonian/competitive-verifier/actions/workflows/verify.yml?query=branch%3Amain) [![GitHub Pages](https://img.shields.io/static/v1?label=GitHub+Pages&message=competitive-verifier+&color=brightgreen&logo=github)](https://notleonian.github.io/competitive-verifier)

Upstream PyPI package: [![PyPI](https://img.shields.io/pypi/v/competitive-verifier)](https://pypi.org/project/competitive-verifier/)

This is [Not_Leonian](https://github.com/NotLeonian)'s fork of [competitive-verifier/competitive-verifier](https://github.com/competitive-verifier/competitive-verifier).

- [Getting Started](https://notleonian.github.io/competitive-verifier/installer.html) / [日本語](https://notleonian.github.io/competitive-verifier/installer.ja.html)
- [Reference](https://notleonian.github.io/competitive-verifier/document.html) / [日本語](https://notleonian.github.io/competitive-verifier/document.ja.html)
- [DESIGN(日本語)](https://notleonian.github.io/competitive-verifier/DESIGN)


## Get started

### Use in GitHub Actions

See [GitHub Pages](https://notleonian.github.io/competitive-verifier/installer.html).
[日本語](https://notleonian.github.io/competitive-verifier/installer.ja.html)

To use this fork with the generated workflow, specify the fork's package in every `competitive-verifier/actions/setup@v2` step:

```yaml
- name: Set up competitive-verifier
  uses: competitive-verifier/actions/setup@v2
  with:
    cache-pip: true
    package: git+https://github.com/NotLeonian/competitive-verifier.git@main
```

### Use in local

#### Install(local)

Needs Python 3.10 or greater.

`pip install competitive-verifier` installs the upstream package. To install this fork, use:

```sh
pip install git+https://github.com/NotLeonian/competitive-verifier.git@main
```

To pin the installed version, replace `main` at the end of the URL with the SHA of the latest commit on the `main` branch.

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
poetry run poe test

# type check
poetry run poe mypy

# lint and type check
poetry run poe lint

# format
poetry run poe format

# run local source
poetry run competitive-verifier $args
```
