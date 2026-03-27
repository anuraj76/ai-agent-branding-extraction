"""
Branding extraction tool for the ADK agent.
Crawls a website and extracts branding elements from HTML and CSS.
"""

import re
import json
import logging
import cssutils
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import Counter

# Suppress cssutils noisy logging
cssutils.log.setLevel(logging.CRITICAL)

NAMED_COLORS = {
    "white": "#ffffff", "black": "#000000", "red": "#ff0000",
    "blue": "#0000ff", "green": "#008000", "gray": "#808080",
    "grey": "#808080", "silver": "#c0c0c0", "navy": "#000080",
    "orange": "#ffa500", "yellow": "#ffff00", "purple": "#800080",
    "transparent": "transparent",
}


def _is_color_value(value: str) -> bool:
    value = value.strip().lower()
    patterns = [
        r'^#[0-9a-f]{3,8}$',
        r'^rgb\(',
        r'^rgba\(',
        r'^hsl\(',
        r'^hsla\(',
    ]
    if any(re.match(p, value) for p in patterns):
        return True
    return value in NAMED_COLORS


def _normalize_color(value: str) -> str | None:
    value = value.strip().lower()
    if not value or value in ('inherit', 'initial', 'unset', 'none', 'currentcolor', 'var'):
        return None
    if value in NAMED_COLORS:
        return NAMED_COLORS[value]
    if _is_color_value(value):
        return value
    return None


def _extract_css_from_page(soup: BeautifulSoup, base_url: str) -> str:
    """Collect CSS from <style> tags and linked stylesheets."""
    all_css = ""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BrandingBot/1.0)"}

    for style_tag in soup.find_all("style"):
        all_css += style_tag.get_text() + "\n"

    for link in soup.find_all("link", rel="stylesheet"):
        href = link.get("href", "")
        if not href:
            continue
        css_url = urljoin(base_url, href)
        try:
            resp = requests.get(css_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                all_css += resp.text + "\n"
        except Exception:
            pass

    return all_css


def _parse_css_rules(css_text: str) -> list[dict]:
    """Parse CSS text into a list of {selector, property, value} dicts."""
    rules = []
    try:
        sheet = cssutils.parseString(css_text, validate=False)
        for rule in sheet:
            if hasattr(rule, "selectorText") and hasattr(rule, "style"):
                selector = rule.selectorText
                for prop in rule.style:
                    rules.append({
                        "selector": selector,
                        "property": prop.name,
                        "value": prop.value,
                    })
    except Exception:
        # Fallback: regex-based extraction
        pattern = r"([^{}]+)\{([^{}]+)\}"
        for match in re.finditer(pattern, css_text):
            selector = match.group(1).strip()
            for decl in match.group(2).split(";"):
                if ":" in decl:
                    prop, _, val = decl.partition(":")
                    rules.append({
                        "selector": selector,
                        "property": prop.strip(),
                        "value": val.strip(),
                    })
    return rules


def _extract_colors(css_rules: list[dict]) -> dict:
    """Extract and categorize colors from CSS rules."""
    color_counts = Counter()
    background_colors = {}
    text_colors = {}
    border_colors = []
    css_variables = {}

    color_in_value = re.compile(
        r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)|hsla?\([^)]+\))"
    )

    for rule in css_rules:
        selector = rule["selector"]
        prop = rule["property"]
        value = rule["value"]

        # CSS custom properties (design tokens)
        if prop.startswith("--"):
            match = color_in_value.search(value)
            if match or _is_color_value(value.strip()):
                css_variables[prop] = value.strip()
            continue

        if prop in ("background-color", "background"):
            match = color_in_value.search(value)
            color_val = match.group(1) if match else _normalize_color(value)
            if color_val and color_val != "transparent":
                background_colors[selector] = color_val
                color_counts[color_val] += 1

        elif prop == "color":
            normalized = _normalize_color(value)
            if normalized and normalized != "transparent":
                text_colors[selector] = normalized
                color_counts[normalized] += 1

        elif "border" in prop and "color" in prop:
            normalized = _normalize_color(value)
            if normalized and normalized != "transparent":
                border_colors.append({"selector": selector, "color": normalized})
                color_counts[normalized] += 1

    primary_palette = [
        c for c, _ in color_counts.most_common(10)
        if c not in ("transparent", "inherit", "none") and _is_color_value(c)
    ]

    return {
        "primary_palette": primary_palette,
        "background_colors": background_colors,
        "text_colors": text_colors,
        "border_colors": border_colors,
        "css_variables": css_variables,
    }


def _extract_typography(css_rules: list[dict]) -> dict:
    """Extract font families, sizes, weights, and line heights."""
    fonts = {}
    font_sizes = {}
    font_weights = {}
    line_heights = {}

    headings = {"h1", "h2", "h3", "h4", "h5", "h6"}

    for rule in css_rules:
        selector = rule["selector"].lower().strip()
        prop = rule["property"]
        value = rule["value"]

        is_heading = any(h in selector for h in headings)
        is_body = selector in ("body", "html", "p")

        if prop == "font-family":
            if is_heading and "heading" not in fonts:
                fonts["heading"] = value
            elif is_body and "body" not in fonts:
                fonts["body"] = value
            elif selector not in fonts:
                fonts[selector] = value

        elif prop == "font-size":
            for h in headings:
                if h in selector and h not in font_sizes:
                    font_sizes[h] = value
            if is_body and "body" not in font_sizes:
                font_sizes["body"] = value

        elif prop == "font-weight":
            if is_heading and "heading" not in font_weights:
                font_weights["heading"] = value
            elif is_body and "body" not in font_weights:
                font_weights["body"] = value

        elif prop == "line-height":
            if is_body and "body" not in line_heights:
                line_heights["body"] = value

    return {
        "fonts": fonts,
        "font_sizes": font_sizes,
        "font_weights": font_weights,
        "line_heights": line_heights,
    }


def _extract_buttons(css_rules: list[dict]) -> dict:
    """Extract primary, secondary, and general button styles."""
    primary = {}
    secondary = {}
    general = {}

    primary_patterns = ["btn-primary", "button-primary", "btn--primary", "cta-btn"]
    secondary_patterns = ["btn-secondary", "button-secondary", "btn--secondary"]
    general_patterns = ["button", ".btn", '[type="button"]', '[type="submit"]', ".button"]

    target_props = {
        "background-color", "background", "color", "border",
        "border-radius", "padding", "font-size", "font-weight",
        "border-color", "box-shadow", "text-transform", "cursor",
    }

    for rule in css_rules:
        selector = rule["selector"].lower()
        prop = rule["property"]
        value = rule["value"]

        if prop not in target_props:
            continue

        if any(p in selector for p in primary_patterns):
            primary[prop] = value
        elif any(p in selector for p in secondary_patterns):
            secondary[prop] = value
        elif any(p in selector for p in general_patterns):
            general[prop] = value

    return {"primary": primary, "secondary": secondary, "general": general}


def _extract_logos(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Find logo images and SVGs in the page."""
    logos = []
    logo_keywords = ("logo", "brand", "wordmark", "logotype")

    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "").lower()
        classes = " ".join(img.get("class", [])).lower()
        id_attr = img.get("id", "").lower()

        if any(kw in x for kw in logo_keywords for x in (alt, classes, id_attr, src.lower())):
            logos.append({
                "type": "image",
                "src": urljoin(base_url, src) if src else None,
                "alt": img.get("alt", ""),
                "width": img.get("width"),
                "height": img.get("height"),
            })

    for container in soup.find_all(class_=re.compile(r"logo|brand", re.I)):
        if container.find("svg"):
            logos.append({
                "type": "svg",
                "container_class": " ".join(container.get("class", [])),
            })

    return logos[:5]


def _extract_backgrounds(css_rules: list[dict]) -> dict:
    """Extract background colors for key layout sections."""
    backgrounds = {}
    targets = {
        "body", "html", "header", "nav", "footer",
        "main", ".header", "#header", ".footer",
        "#footer", ".navbar", ".nav", ".hero",
    }
    color_in_value = re.compile(
        r"(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)|hsla?\([^)]+\))"
    )

    for rule in css_rules:
        selector = rule["selector"].lower().strip()
        prop = rule["property"]
        value = rule["value"]

        if selector not in targets:
            continue

        if prop in ("background-color", "background"):
            match = color_in_value.search(value)
            if match:
                backgrounds[selector] = match.group(1)
            elif _is_color_value(value.strip()):
                backgrounds[selector] = value.strip()

    return backgrounds


def crawl_and_extract_branding(url: str) -> str:
    """
    Crawls a website and extracts all branding elements including colors,
    typography, button styles, logos, and background colors.

    Args:
        url: The full website URL to crawl (e.g. https://stripe.com)

    Returns:
        A JSON string containing structured branding data with sections for
        colors, typography, buttons, logos, backgrounds, and CSS variables.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        title_tag = soup.find("title")
        meta_desc = soup.find("meta", attrs={"name": "description"})

        all_css = _extract_css_from_page(soup, url)
        css_rules = _parse_css_rules(all_css)

        branding = {
            "url": url,
            "site_name": title_tag.get_text(strip=True) if title_tag else None,
            "meta_description": meta_desc.get("content") if meta_desc else None,
            "colors": _extract_colors(css_rules),
            "typography": _extract_typography(css_rules),
            "buttons": _extract_buttons(css_rules),
            "logos": _extract_logos(soup, url),
            "backgrounds": _extract_backgrounds(css_rules),
            "css_stats": {
                "total_rules_parsed": len(css_rules),
                "stylesheets_linked": len(soup.find_all("link", rel="stylesheet")),
                "inline_style_blocks": len(soup.find_all("style")),
            },
        }

        return json.dumps(branding, indent=2, ensure_ascii=False)

    except requests.exceptions.RequestException as e:
        return json.dumps({"error": f"Failed to fetch URL: {str(e)}", "url": url})
    except Exception as e:
        return json.dumps({"error": f"Extraction failed: {str(e)}", "url": url})
