import os
import zipfile
from pathlib import Path

import pytest

CHECK_ENV_VAR = "CHECK_BUILT_WHEEL_ASSETS"

REQUIRED_WHEEL_FILES: tuple[str, ...] = (
    "competitive_verifier_resources/jekyll/assets/js/mathjax-config.js",
    "competitive_verifier_resources/jekyll/assets/vendor/VERSIONS.txt",
    "competitive_verifier_resources/jekyll/assets/vendor/THIRD_PARTY_LICENSES.txt",
    "competitive_verifier_resources/jekyll/assets/vendor/mathjax/LICENSE.txt",
    "competitive_verifier_resources/jekyll/assets/vendor/mathjax/es5/tex-mml-chtml.js",
    "competitive_verifier_resources/jekyll/assets/vendor/mathjax/es5/a11y/sre.js",
    "competitive_verifier_resources/jekyll/assets/vendor/mathjax/es5/sre/mathmaps/base.json",
    "competitive_verifier_resources/jekyll/assets/vendor/mathjax/es5/sre/mathmaps/en.json",
    "competitive_verifier_resources/jekyll/assets/vendor/highlight/LICENSE.txt",
    "competitive_verifier_resources/jekyll/assets/vendor/highlight/highlight.min.js",
    "competitive_verifier_resources/jekyll/assets/vendor/highlight/styles/default.min.css",
    "competitive_verifier_resources/jekyll/assets/vendor/hint/LICENSE.txt",
    "competitive_verifier_resources/jekyll/assets/vendor/hint/hint.min.css",
    "competitive_verifier_resources/jekyll_theme_overrides/jekyll-theme-minimal/_layouts/default.html",
)


pytestmark = pytest.mark.package


def test_built_wheel_contains_self_hosted_doc_assets() -> None:
    if os.environ.get(CHECK_ENV_VAR) != "1":
        pytest.skip(
            f"Set {CHECK_ENV_VAR}=1 after `poetry build --format wheel --clean` "
            "to run this package artifact test.",
        )

    wheels = sorted(Path("dist").glob("competitive_verifier-*.whl"))

    assert len(wheels) == 1, (
        "Expected exactly one wheel under dist/. "
        "Run `poetry build --format wheel --clean` before this test.\n"
        f"Found: {', '.join(path.as_posix() for path in wheels) or '<none>'}"
    )

    wheel = wheels[0]

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())

    missing_files = [path for path in REQUIRED_WHEEL_FILES if path not in names]

    assert not missing_files, (
        f"{wheel} does not contain required documentation assets:\n"
        + "\n".join(missing_files)
    )
