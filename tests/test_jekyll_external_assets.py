from html.parser import HTMLParser

from competitive_verifier_resources.resources import jekyll_files

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


def _is_external_url(url: str) -> bool:
    stripped_url = url.strip().lower()
    return stripped_url.startswith(("http://", "https://", "//"))


class ExternalAssetHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.inline_script_count = 0
        self.external_script_srcs: list[str] = []
        self.external_stylesheet_hrefs: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self._handle_tag(tag, attrs)

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self._handle_tag(tag, attrs)

    def _handle_tag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        tag_name = tag.lower()
        attrs_by_name = {name.lower(): value for name, value in attrs}

        if tag_name == "script":
            src = attrs_by_name.get("src")

            if src is None:
                self.inline_script_count += 1
            elif _is_external_url(src):
                self.external_script_srcs.append(src)

            return

        if tag_name != "link":
            return

        rel = attrs_by_name.get("rel")
        href = attrs_by_name.get("href")

        if rel is None or href is None:
            return

        rel_values = set(rel.lower().split())

        if "stylesheet" in rel_values and _is_external_url(href):
            self.external_stylesheet_hrefs.append(href)


def _is_vendored_mathjax_bundle(path: str) -> bool:
    return path.startswith("assets/vendor/mathjax/es5/")


def _is_vendored_asset(path: str) -> bool:
    return path.startswith("assets/vendor/")


def _find_external_asset_issues(path: str, content: bytes) -> list[str]:
    parser = ExternalAssetHTMLParser()
    parser.feed(content.decode("utf-8", errors="ignore"))

    issues: list[str] = []

    if parser.inline_script_count > 0:
        issues.append(f"{path}: inline <script>")

    issues.extend(
        f"{path}: external <script src>: {src}" for src in parser.external_script_srcs
    )

    issues.extend(
        f"{path}: external stylesheet: {href}"
        for href in parser.external_stylesheet_hrefs
    )

    return issues


def test_jekyll_resources_do_not_reference_external_js_or_css() -> None:
    files = jekyll_files()
    offenders: list[str] = []

    for path, content in files.items():
        if not _is_vendored_asset(path):
            offenders.extend(_find_external_asset_issues(path, content))

        offenders.extend(
            f"{path}: contains {domain_name}"
            for domain_bytes, domain_name in BLOCKED_DOMAINS_EVERYWHERE
            if domain_bytes in content
        )

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
