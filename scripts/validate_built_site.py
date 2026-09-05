#!/usr/bin/env python3
"""Validate the generated static site without fetching external URLs.

The validator is deliberately deterministic: it checks only files in the build
directory and same-origin URLs. Upstream publishers are not contacted during a
release, so an unavailable third-party site cannot make an otherwise identical
FINER build pass or fail.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree


SITE_ORIGINS = {"projectfiner.com", "www.projectfiner.com"}
SKIPPED_SCHEMES = {"data", "javascript", "mailto", "tel"}
REQUIRED_SITEMAP_ROUTES = {
    "/",
    "/about/",
    "/changelog/",
    "/corrections/",
    "/data-dictionary/",
    "/data-rights/",
    "/downloads/",
    "/districts/",
    "/methodology/",
    "/privacy/",
    "/releases/meghalaya-standardized-preview-v1/",
}
LEGACY_HTML_PREFIXES = ("/charts/", "/digital-payments/")
REQUIRED_CSP_DIRECTIVES = {
    "default-src": {"'self'"},
    "object-src": {"'none'"},
    "base-uri": {"'self'"},
    "form-action": {"'self'"},
    "frame-src": {"'none'"},
    "upgrade-insecure-requests": set(),
}


@dataclass
class Control:
    tag: str
    attrs: dict[str, str]
    wrapped_by_label: bool = False


@dataclass
class Page:
    file: Path
    route: str
    links: list[tuple[str, str, str]] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    labels_for: set[str] = field(default_factory=set)
    controls: list[Control] = field(default_factory=list)
    missing_alt: int = 0
    unnamed_buttons: int = 0
    html_lang: str | None = None
    title: str = ""
    descriptions: list[str] = field(default_factory=list)
    canonicals: list[str] = field(default_factory=list)
    json_ld: list[str] = field(default_factory=list)
    content_security_policies: list[str] = field(default_factory=list)
    referrer_policies: list[str] = field(default_factory=list)
    refresh: bool = False


class PageParser(HTMLParser):
    def __init__(self, page: Page):
        super().__init__(convert_charrefs=True)
        self.page = page
        self._title_depth = 0
        self._label_depth = 0
        self._button_stack: list[dict[str, object]] = []
        self._json_ld_depth = 0
        self._json_ld_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs_list: list[tuple[str, str | None]]):
        attrs = {name: value or "" for name, value in attrs_list}

        if tag == "html":
            self.page.html_lang = attrs.get("lang")
        if tag == "title":
            self._title_depth += 1
        if tag == "label":
            self._label_depth += 1
            if attrs.get("for"):
                self.page.labels_for.add(attrs["for"])
        if tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self._json_ld_depth += 1
            self._json_ld_buffer = []

        element_id = attrs.get("id")
        if element_id:
            self.page.ids.append(element_id)

        if tag == "meta":
            if attrs.get("name", "").lower() == "description":
                self.page.descriptions.append(attrs.get("content", "").strip())
            if attrs.get("name", "").lower() == "referrer":
                self.page.referrer_policies.append(attrs.get("content", "").strip())
            if attrs.get("http-equiv", "").lower() == "content-security-policy":
                self.page.content_security_policies.append(attrs.get("content", "").strip())
            if attrs.get("http-equiv", "").lower() == "refresh":
                self.page.refresh = True

        if tag == "link" and "canonical" in attrs.get("rel", "").lower().split():
            self.page.canonicals.append(attrs.get("href", ""))

        for attribute in ("href", "src"):
            value = attrs.get(attribute)
            if value:
                self.page.links.append((tag, attribute, html.unescape(value.strip())))

        if tag == "img" and "alt" not in attrs:
            self.page.missing_alt += 1

        if tag in {"input", "select", "textarea"}:
            if tag != "input" or attrs.get("type", "text").lower() != "hidden":
                self.page.controls.append(Control(tag, attrs, self._label_depth > 0))

        if tag == "button":
            named_by_attribute = any(
                attrs.get(name, "").strip()
                for name in ("aria-label", "aria-labelledby", "title")
            )
            self._button_stack.append({"named": named_by_attribute, "text": []})

    def handle_startendtag(self, tag: str, attrs_list: list[tuple[str, str | None]]):
        self.handle_starttag(tag, attrs_list)
        if tag in {"title", "label", "script", "button"}:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str):
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
        if tag == "label" and self._label_depth:
            self._label_depth -= 1
        if tag == "script" and self._json_ld_depth:
            self.page.json_ld.append("".join(self._json_ld_buffer).strip())
            self._json_ld_buffer = []
            self._json_ld_depth -= 1
        if tag == "button" and self._button_stack:
            button = self._button_stack.pop()
            has_text = bool("".join(button["text"]).strip())
            if not button["named"] and not has_text:
                self.page.unnamed_buttons += 1

    def handle_data(self, data: str):
        if self._title_depth:
            self.page.title += data
        if self._json_ld_depth:
            self._json_ld_buffer.append(data)
        for button in self._button_stack:
            button["text"].append(data)


def route_for_file(root: Path, file: Path) -> str:
    relative = file.relative_to(root)
    if relative.name == "index.html":
        parent = relative.parent.as_posix()
        return "/" if parent == "." else f"/{parent}/"
    return f"/{relative.as_posix()}"


def parse_pages(root: Path) -> dict[str, Page]:
    pages: dict[str, Page] = {}
    for file in sorted(root.rglob("*.html")):
        route = route_for_file(root, file)
        page = Page(file=file, route=route)
        parser = PageParser(page)
        parser.feed(file.read_text(encoding="utf-8"))
        parser.close()
        pages[route] = page
    return pages


def candidate_paths(root: Path, path: str) -> list[Path]:
    target = root / unquote(path).lstrip("/")
    candidates = [target]
    if path.endswith("/"):
        candidates.append(target / "index.html")
    elif target.suffix == "":
        candidates.extend((target.with_suffix(".html"), target / "index.html"))
    return candidates


def resolve_internal_url(page_route: str, raw_url: str) -> tuple[str, str] | None:
    parsed = urlsplit(raw_url)
    if parsed.scheme.lower() in SKIPPED_SCHEMES:
        return None
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return None
    if parsed.netloc and parsed.hostname not in SITE_ORIGINS:
        return None
    if raw_url.startswith("//") and parsed.hostname not in SITE_ORIGINS:
        return None

    if parsed.netloc:
        path = parsed.path or "/"
    else:
        path = urlsplit(urljoin(f"https://projectfiner.com{page_route}", raw_url)).path
    return path or page_route, unquote(parsed.fragment)


def find_existing_target(root: Path, path: str) -> Path | None:
    for candidate in candidate_paths(root, path):
        if candidate.is_file():
            return candidate
    return None


def accessible_control_name(control: Control, page: Page) -> bool:
    attrs = control.attrs
    if control.wrapped_by_label:
        return True
    if any(attrs.get(name, "").strip() for name in ("aria-label", "aria-labelledby", "title")):
        return True
    element_id = attrs.get("id")
    return bool(element_id and element_id in page.labels_for)


def parse_csp(policy: str) -> dict[str, set[str]]:
    directives: dict[str, set[str]] = {}
    for raw_directive in policy.split(";"):
        parts = raw_directive.strip().split()
        if parts:
            directives[parts[0].lower()] = set(parts[1:])
    return directives


def validate_pages(root: Path, pages: dict[str, Page]) -> tuple[list[str], int, int]:
    errors: list[str] = []
    links_checked = 0
    json_ld_checked = 0
    ids_by_file = {page.file: set(page.ids) for page in pages.values()}

    for page in pages.values():
        location = page.route
        uses_site_template = not page.refresh and not location.startswith(LEGACY_HTML_PREFIXES)
        if not page.refresh:
            if len(page.content_security_policies) != 1:
                errors.append(
                    f"{location}: expected one Content Security Policy, "
                    f"found {len(page.content_security_policies)}"
                )
            else:
                directives = parse_csp(page.content_security_policies[0])
                for directive, required_values in REQUIRED_CSP_DIRECTIVES.items():
                    if directive not in directives:
                        errors.append(f"{location}: CSP is missing {directive}")
                    elif not required_values.issubset(directives[directive]):
                        errors.append(
                            f"{location}: CSP {directive} is missing "
                            f"{', '.join(sorted(required_values))}"
                        )
            if page.referrer_policies != ["strict-origin-when-cross-origin"]:
                errors.append(
                    f"{location}: expected referrer policy "
                    "'strict-origin-when-cross-origin'"
                )
        if uses_site_template:
            if not page.html_lang:
                errors.append(f"{location}: <html> has no language")
            if not page.title.strip():
                errors.append(f"{location}: page title is empty")
            if not page.descriptions or any(not item for item in page.descriptions):
                errors.append(f"{location}: meta description is missing or empty")
            if page.missing_alt:
                errors.append(f"{location}: {page.missing_alt} image(s) have no alt attribute")
            if page.unnamed_buttons:
                errors.append(f"{location}: {page.unnamed_buttons} button(s) have no accessible name")

            duplicate_ids = sorted({item for item in page.ids if page.ids.count(item) > 1})
            if duplicate_ids:
                errors.append(f"{location}: duplicate id(s): {', '.join(duplicate_ids[:10])}")

            for control in page.controls:
                if not accessible_control_name(control, page):
                    descriptor = control.attrs.get("id") or control.attrs.get("name") or "unnamed"
                    errors.append(f"{location}: <{control.tag}> {descriptor!r} has no accessible label")

            for payload in page.json_ld:
                json_ld_checked += 1
                if not payload:
                    errors.append(f"{location}: empty JSON-LD block")
                    continue
                try:
                    json.loads(payload)
                except json.JSONDecodeError as exc:
                    errors.append(f"{location}: invalid JSON-LD ({exc.msg} at character {exc.pos})")

        if uses_site_template and location != "/404.html":
            if len(page.canonicals) != 1:
                errors.append(f"{location}: expected one canonical URL, found {len(page.canonicals)}")
            elif resolve_internal_url(location, page.canonicals[0]) is None:
                errors.append(f"{location}: canonical URL is not on projectfiner.com")

        for tag, attribute, raw_url in page.links:
            resolved = resolve_internal_url(location, raw_url)
            if resolved is None:
                continue
            path, fragment = resolved
            links_checked += 1
            target = find_existing_target(root, path)
            if target is None:
                errors.append(f"{location}: <{tag}> {attribute} points to missing {raw_url!r}")
                continue
            if fragment and target.suffix == ".html" and fragment not in ids_by_file.get(target, set()):
                errors.append(f"{location}: fragment #{fragment} does not exist in {path}")

    return errors, links_checked, json_ld_checked


def validate_sitemap(root: Path, pages: dict[str, Page]) -> tuple[list[str], int]:
    errors: list[str] = []
    sitemap = root / "sitemap.xml"
    if not sitemap.is_file():
        return ["/sitemap.xml: file is missing"], 0

    try:
        document = ElementTree.parse(sitemap)
    except ElementTree.ParseError as exc:
        return [f"/sitemap.xml: invalid XML ({exc})"], 0

    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = [
        (node.text or "").strip()
        for node in document.findall("sm:url/sm:loc", namespace)
    ]
    duplicates = sorted({location for location in locations if locations.count(location) > 1})
    if duplicates:
        errors.append(f"/sitemap.xml: duplicate URL(s): {', '.join(duplicates[:10])}")

    routes: set[str] = set()
    for location in locations:
        parsed = urlsplit(location)
        if parsed.scheme != "https" or parsed.hostname != "projectfiner.com":
            errors.append(f"/sitemap.xml: non-canonical origin {location!r}")
            continue
        if parsed.query or parsed.fragment:
            errors.append(f"/sitemap.xml: URL contains query or fragment {location!r}")
        route = parsed.path or "/"
        routes.add(route)
        target = find_existing_target(root, route)
        if target is None:
            errors.append(f"/sitemap.xml: URL has no built page {location!r}")
            continue
        target_route = route_for_file(root, target)
        page = pages.get(target_route)
        if page and page.refresh:
            errors.append(f"/sitemap.xml: redirect page must not be indexed {location!r}")
        if page and page.canonicals != [location]:
            errors.append(f"/sitemap.xml: canonical mismatch for {location!r}")

    missing_required = sorted(REQUIRED_SITEMAP_ROUTES - routes)
    if missing_required:
        errors.append(f"/sitemap.xml: missing required route(s): {', '.join(missing_required)}")

    return errors, len(locations)


def validate_site(root: Path) -> tuple[list[str], dict[str, int]]:
    root = root.resolve()
    if not root.is_dir():
        return [f"build directory does not exist: {root}"], {}
    pages = parse_pages(root)
    if not pages:
        return [f"no HTML pages found under {root}"], {}

    page_errors, links_checked, json_ld_checked = validate_pages(root, pages)
    sitemap_errors, sitemap_urls = validate_sitemap(root, pages)
    return page_errors + sitemap_errors, {
        "pages": len(pages),
        "internal_links": links_checked,
        "json_ld_blocks": json_ld_checked,
        "sitemap_urls": sitemap_urls,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a built Project FINER site")
    parser.add_argument("build_directory", nargs="?", default="dist", type=Path)
    args = parser.parse_args()

    errors, stats = validate_site(args.build_directory)
    if errors:
        print(f"Built-site validation failed with {len(errors)} issue(s):", file=sys.stderr)
        for error in errors[:100]:
            print(f"  - {error}", file=sys.stderr)
        if len(errors) > 100:
            print(f"  ...and {len(errors) - 100} more", file=sys.stderr)
        return 1

    print(
        "Built-site validation passed: "
        f"{stats['pages']} pages, {stats['internal_links']} internal links, "
        f"{stats['json_ld_blocks']} JSON-LD blocks, "
        f"{stats['sitemap_urls']} sitemap URLs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
