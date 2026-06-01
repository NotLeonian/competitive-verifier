import re

from competitive_verifier_resources.resources import jekyll_files

EXTERNAL_SCRIPT_RE = re.compile(
    rb"""<script[^>]+src=["']https?://""",
    re.IGNORECASE,
)

EXTERNAL_STYLESHEET_RE = re.compile(
    rb"""<link[^>]+rel=["']stylesheet["'][^>]+href=["']https?://""",
    re.IGNORECASE,
)

BLOCKED_DOMAINS_EVERYWHERE: tuple[tuple[bytes, str], ...] = (
    (b"polyfill.io", "polyfill.io"),
    (b"bootcdn.net", "bootcdn.net"),
    (b"bootcss.com", "bootcss.com"),
    (b"staticfile.net", "staticfile.net"),
    (b"staticfile.org", "staticfile.org"),
    (b"unionadjs.com", "unionadjs.com"),
    (b"googie-anaiytics", "googie-anaiytics"),
)

CDN_DOMAINS_ALLOWED_ONLY_IN_VENDORED_MATHJAX: tuple[tuple[bytes, str], ...] = (
    (b"cdn.jsdelivr.net", "cdn.jsdelivr.net"),
    (b"cdnjs.cloudflare.com", "cdnjs.cloudflare.com"),
)


def _is_vendored_mathjax_bundle(path: str) -> bool:
    return path.startswith("assets/vendor/mathjax/es5/")


def _is_vendored_asset(path: str) -> bool:
    return path.startswith("assets/vendor/")


def test_jekyll_resources_do_not_reference_external_js_or_css() -> None:
    files = jekyll_files()
    offenders: list[str] = []

    for path, content in files.items():
        # Real external <script src=...> / stylesheet references should only be
        # checked in our templates and first-party resources. Vendored bundles
        # can contain documentation strings or internal fallback strings.
        if not _is_vendored_asset(path):
            if EXTERNAL_SCRIPT_RE.search(content):
                offenders.append(f"{path}: external <script src>")
            if EXTERNAL_STYLESHEET_RE.search(content):
                offenders.append(f"{path}: external stylesheet")

        # Known dangerous domains are forbidden everywhere, including vendored
        # assets.
        offenders.extend(
            f"{path}: contains {domain_name}"
            for domain_bytes, domain_name in BLOCKED_DOMAINS_EVERYWHERE
            if domain_bytes in content
        )

        # jsDelivr/cdnjs strings are expected inside upstream MathJax bundles,
        # but should not appear in our own templates or other resources.
        if not _is_vendored_mathjax_bundle(path):
            offenders.extend(
                f"{path}: contains {domain_name}"
                for (
                    domain_bytes,
                    domain_name,
                ) in CDN_DOMAINS_ALLOWED_ONLY_IN_VENDORED_MATHJAX
                if domain_bytes in content
            )

    assert not offenders, "\n".join(offenders)


def test_required_vendor_assets_are_available_from_jekyll_files() -> None:
    files = jekyll_files()

    required_files = (
        "assets/js/mathjax-config.js",
        "assets/vendor/VERSIONS.txt",
        "assets/vendor/THIRD_PARTY_LICENSES.txt",
        "assets/vendor/mathjax/LICENSE.txt",
        "assets/vendor/mathjax/es5/tex-mml-chtml.js",
        "assets/vendor/mathjax/es5/a11y/sre.js",
        "assets/vendor/mathjax/es5/sre/mathmaps/base.json",
        "assets/vendor/mathjax/es5/sre/mathmaps/en.json",
        "assets/vendor/highlight/LICENSE.txt",
        "assets/vendor/highlight/highlight.min.js",
        "assets/vendor/highlight/styles/default.min.css",
        "assets/vendor/hint/LICENSE.txt",
        "assets/vendor/hint/hint.min.css",
    )

    missing_files = [path for path in required_files if path not in files]

    assert not missing_files, "\n".join(missing_files)
