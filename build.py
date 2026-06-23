#!/usr/bin/env python3
"""
emoji-site — Static site generator
Fetches the Unicode emoji-test.txt spec and generates a complete static website.
Zero external dependencies — uses only Python stdlib.
"""

import json
import os
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EMOJI_TEST_URL = "https://www.unicode.org/Public/emoji/latest/emoji-test.txt"
CACHE_DIR = Path(".emoji-cache")
DIST_DIR = Path("dist")
STATIC_DIR = Path("static")

# Skin tone modifier codepoints
SKIN_TONE_MODIFIERS = {"1F3FB", "1F3FC", "1F3FD", "1F3FE", "1F3FF"}
SKIN_TONE_NAMES = {
    "1F3FB": "light skin tone",
    "1F3FC": "medium-light skin tone",
    "1F3FD": "medium skin tone",
    "1F3FE": "medium-dark skin tone",
    "1F3FF": "dark skin tone",
}

# Representative emojis for each group (for category pills)
GROUP_ICONS = {
    "Smileys & Emotion": "😀",
    "People & Body": "👋",
    "Animals & Nature": "🐶",
    "Food & Drink": "🍕",
    "Travel & Places": "✈️",
    "Activities": "⚽",
    "Objects": "💡",
    "Symbols": "❤️",
    "Flags": "🏳️",
    "Component": "🔧",
}


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_emoji_data():
    """Download emoji-test.txt, caching locally to avoid repeated downloads."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / "emoji-test.txt"

    if cache_file.exists():
        print(f"  Using cached {cache_file}")
        return cache_file.read_text(encoding="utf-8")

    print(f"  Downloading {EMOJI_TEST_URL} ...")
    req = urllib.request.Request(EMOJI_TEST_URL, headers={"User-Agent": "emoji-site/1.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read().decode("utf-8")

    cache_file.write_text(data, encoding="utf-8")
    print(f"  Cached to {cache_file}")
    return data


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def slugify(text):
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")


def parse_emoji_data(text):
    """Parse emoji-test.txt into structured data."""
    emojis = []
    groups = {}  # group_name -> {subgroups: {subgroup_name -> [emoji_indices]}}
    current_group = None
    current_subgroup = None

    # Regex for data lines:
    # 1F600                                      ; fully-qualified     # 😀 E1.0 grinning face
    line_re = re.compile(
        r"^(?P<codes>[A-F0-9][A-F0-9 ]+?)\s+;\s+(?P<status>\S+)\s+#\s+(?P<char>\S+)\s+E(?P<version>[\d.]+)\s+(?P<name>.+)$"
    )

    for line in text.splitlines():
        line = line.strip()

        # Group header: # group: Smileys & Emotion
        if line.startswith("# group:"):
            current_group = line.split(":", 1)[1].strip()
            if current_group not in groups:
                groups[current_group] = {"subgroups": {}}
            continue

        # Subgroup header: # subgroup: face-smiling
        if line.startswith("# subgroup:"):
            current_subgroup = line.split(":", 1)[1].strip()
            if current_group and current_subgroup not in groups[current_group]["subgroups"]:
                groups[current_group]["subgroups"][current_subgroup] = []
            continue

        # Skip comments and blank lines
        if not line or line.startswith("#"):
            continue

        m = line_re.match(line)
        if not m:
            continue

        status = m.group("status")
        if status != "fully-qualified":
            continue

        codes = m.group("codes").strip()
        code_list = codes.split()
        char = m.group("char")
        version = m.group("version")
        name = m.group("name").strip()

        # Determine if this is a skin tone variant
        has_skin_tone = any(c in SKIN_TONE_MODIFIERS for c in code_list)

        emoji_entry = {
            "codes": codes,
            "code_list": code_list,
            "char": char,
            "name": name,
            "version": version,
            "group": current_group,
            "subgroup": current_subgroup,
            "slug": slugify(name),
            "is_skin_variant": has_skin_tone,
        }

        idx = len(emojis)
        emojis.append(emoji_entry)

        if current_group and current_subgroup:
            groups[current_group]["subgroups"][current_subgroup].append(idx)

    return emojis, groups


def build_base_emoji_map(emojis):
    """
    Group skin tone variants with their base emoji.
    Returns:
        base_emojis: list of base emoji entries (with 'variants' list attached)
        slug_set: set of all used slugs (for deduplication)
    """
    base_emojis = []
    slug_counts = {}

    for emoji in emojis:
        if emoji["is_skin_variant"]:
            continue

        # Find skin tone variants for this emoji
        variants = []
        base_codes = emoji["code_list"]

        for other in emojis:
            if not other["is_skin_variant"]:
                continue
            # Check if this variant's non-modifier codes match the base
            other_base = [c for c in other["code_list"] if c not in SKIN_TONE_MODIFIERS]
            if other_base == base_codes:
                variants.append(other)

        emoji["variants"] = variants

        # Deduplicate slugs
        slug = emoji["slug"]
        if slug in slug_counts:
            slug_counts[slug] += 1
            emoji["slug"] = f"{slug}-{slug_counts[slug]}"
        else:
            slug_counts[slug] = 0

        base_emojis.append(emoji)

    return base_emojis


# ---------------------------------------------------------------------------
# HTML Templates
# ---------------------------------------------------------------------------

SVG_SEARCH = '<svg class="search__icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>'
SVG_COPY = '<svg class="copy-button__icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>'
SVG_BACK = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>'


def html_head(title, description, canonical="", extra_head=""):
    """Generate the <head> section."""
    og_image = ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <meta name="description" content="{escape(description)}">
  <meta property="og:title" content="{escape(title)}">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:type" content="website">
  {f'<link rel="canonical" href="{escape(canonical)}">' if canonical else ''}
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📖</text></svg>">
  <link rel="stylesheet" href="{get_root_prefix()}style.css">
  {extra_head}
</head>"""


_root_prefix_stack = [""]

def get_root_prefix():
    return _root_prefix_stack[-1]


def emoji_card_html(emoji):
    """Generate HTML for a single emoji grid card."""
    slug = emoji["slug"]
    name = escape(emoji["name"])
    char = emoji["char"]
    return f"""<div class="emoji-card" data-slug="{slug}" data-name="{name}" data-char="{char}" title="{name}">
  <span class="emoji-card__char">{char}</span>
  <span class="emoji-card__name">{name}</span>
  <div class="emoji-card__copied"><span class="emoji-card__copied-text">Copied!</span></div>
</div>"""


def emoji_card_link_html(emoji):
    """Generate HTML for an emoji card that links to its detail page."""
    slug = emoji["slug"]
    name = escape(emoji["name"])
    char = emoji["char"]
    prefix = get_root_prefix()
    return f"""<a href="{prefix}emoji/{slug}/" class="emoji-card" data-slug="{slug}" data-name="{name}" data-char="{char}" title="{name}">
  <span class="emoji-card__char">{char}</span>
  <span class="emoji-card__name">{name}</span>
  <div class="emoji-card__copied"><span class="emoji-card__copied-text">Copied!</span></div>
</a>"""


# ---------------------------------------------------------------------------
# Page generators
# ---------------------------------------------------------------------------

def generate_index_page(base_emojis, groups):
    """Generate the main index.html with search and categorized grid."""
    print("  Generating index.html ...")

    total_count = len(base_emojis)
    group_count = len([g for g in groups if g != "Component"])
    version_info = "Unicode Emoji"

    # Category pills
    pills_html = f'<button class="category-pill active" data-group="all"><span class="category-pill__icon">🌐</span> All</button>\n'
    for group_name in groups:
        if group_name == "Component":
            continue
        icon = GROUP_ICONS.get(group_name, "📁")
        pills_html += f'<button class="category-pill" data-group="{slugify(group_name)}"><span class="category-pill__icon">{icon}</span> {escape(group_name)}</button>\n'

    # Emoji grid sections by group
    sections_html = ""
    for group_name, group_data in groups.items():
        if group_name == "Component":
            continue
        group_slug = slugify(group_name)
        group_emojis = []
        for subgroup_name, indices in group_data["subgroups"].items():
            for idx in indices:
                # Find the base emoji that corresponds (skip skin variants)
                original = emojis_global[idx] if idx < len(emojis_global) else None
                if original and not original["is_skin_variant"]:
                    # Find in base_emojis
                    for be in base_emojis:
                        if be["codes"] == original["codes"]:
                            group_emojis.append(be)
                            break

        if not group_emojis:
            continue

        cards = "\n".join(emoji_card_link_html(e) for e in group_emojis)
        sections_html += f"""<div class="group-section fade-in" data-group="{group_slug}" id="group-{group_slug}">
  <h2 class="group-section__title">{GROUP_ICONS.get(group_name, '')} {escape(group_name)}</h2>
  <p class="group-section__subtitle">{len(group_emojis)} emojis</p>
  <div class="emoji-grid">
    {cards}
  </div>
</div>
"""

    _root_prefix_stack.append("")

    page = f"""{html_head("emoji-site — Every Emoji, One Click Away", "Browse, search, and copy every Unicode emoji. A free, open-source emoji reference.")}
<body>
  <main class="container">
    <header class="hero">
      <h1 class="hero__logo">emoji-site</h1>
      <p class="hero__tagline">Every emoji at your fingertips. Search, click, copy.</p>
      <div class="hero__stats">
        <div class="hero__stat">
          <span class="hero__stat-value">{total_count:,}</span>
          <span class="hero__stat-label">Emojis</span>
        </div>
        <div class="hero__stat">
          <span class="hero__stat-value">{group_count}</span>
          <span class="hero__stat-label">Categories</span>
        </div>
        <div class="hero__stat">
          <span class="hero__stat-value">{version_info}</span>
          <span class="hero__stat-label">Specification</span>
        </div>
      </div>
      <div class="search">
        {SVG_SEARCH}
        <input type="search" class="search__input" id="search-input" placeholder="Search emojis..." autocomplete="off" aria-label="Search emojis">
        <span class="search__count" id="search-count"></span>
        <div class="search__hint"><kbd class="kbd">/</kbd></div>
      </div>
    </header>

    <nav class="categories" aria-label="Emoji categories">
      {pills_html}
    </nav>

    <div id="emoji-grid">
      {sections_html}
    </div>

    <div class="no-results" id="no-results">
      <div class="no-results__emoji">🔍</div>
      <p class="no-results__text">No emojis found</p>
      <p class="no-results__hint">Try a different search term</p>
    </div>
  </main>

  <footer class="footer">
    <p class="footer__text">
      Built with data from the <a href="https://unicode.org/emoji/" class="footer__link" target="_blank" rel="noopener">Unicode Emoji Specification</a><br>
      Generated on {datetime.now(timezone.utc).strftime("%B %d, %Y")} · <a href="https://github.com/nova-art/emoji-site" class="footer__link">Source on GitHub</a>
    </p>
  </footer>

  <div class="toast" id="toast"></div>
  <script src="app.js"></script>
</body>
</html>"""

    _root_prefix_stack.pop()

    (DIST_DIR / "index.html").write_text(page, encoding="utf-8")


def generate_emoji_page(emoji, base_emojis, groups):
    """Generate an individual emoji detail page."""
    slug = emoji["slug"]
    name = emoji["name"]
    char = emoji["char"]
    codes = emoji["codes"]
    version = emoji["version"]
    group = emoji["group"]
    subgroup = emoji["subgroup"]
    variants = emoji.get("variants", [])

    page_dir = DIST_DIR / "emoji" / slug
    page_dir.mkdir(parents=True, exist_ok=True)

    # Codepoint display
    codepoint_display = " ".join(f"U+{c}" for c in emoji["code_list"])

    # Skin tone picker
    skin_html = ""
    if variants:
        skin_html = '<div class="skin-tones">\n'
        skin_html += f'  <button class="skin-tone-btn active" data-emoji="{char}" title="Default">{char}</button>\n'
        for v in variants:
            tone_codes = [c for c in v["code_list"] if c in SKIN_TONE_MODIFIERS]
            tone_name = SKIN_TONE_NAMES.get(tone_codes[0], "") if tone_codes else ""
            skin_html += f'  <button class="skin-tone-btn" data-emoji="{v["char"]}" title="{escape(tone_name)}">{v["char"]}</button>\n'
        skin_html += '</div>\n'

    _root_prefix_stack.append("../../")

    # Related emojis (same subgroup, excluding self)
    related_html = ""
    related_emojis = [e for e in base_emojis if e["subgroup"] == subgroup and e["slug"] != slug][:20]
    if related_emojis:
        related_cards = "\n".join(emoji_card_link_html(e) for e in related_emojis)
        related_html = f"""<section class="related">
  <h2 class="related__title">Related Emojis</h2>
  <div class="emoji-grid">
    {related_cards}
  </div>
</section>"""

    title = f"{char} {name.title()} — emoji-site"
    description = f"Copy {char} {name} emoji. Unicode {codepoint_display}, added in Emoji {version}."

    group_slug = slugify(group) if group else ""
    breadcrumb_html = f"""<div class="breadcrumbs">
  <a href="../../">Home</a>
  <span class="breadcrumbs__sep">›</span>
  <a href="../../group/{group_slug}/">{escape(group or '')}</a>
  <span class="breadcrumbs__sep">›</span>
  <span>{escape(subgroup or '')}</span>
</div>"""

    page = f"""{html_head(title, description, extra_head="")}
<body>
  <main class="container container--narrow">
    <div class="emoji-detail">
      <a href="../../" class="emoji-detail__back">{SVG_BACK} All Emojis</a>

      <div class="emoji-detail__hero">
        {breadcrumb_html}
        <div class="emoji-detail__char" id="emoji-display">{char}</div>
        <h1 class="emoji-detail__name">{escape(name.title())}</h1>
        <p class="emoji-detail__version">Emoji {escape(version)}</p>
        <button class="copy-button" id="copy-button" data-emoji="{char}">
          {SVG_COPY}
          <span class="copy-button__text">Copy Emoji</span>
        </button>
      </div>

      {skin_html}

      <div class="emoji-info">
        <div class="info-card">
          <div class="info-card__label">Codepoint</div>
          <div class="info-card__value"><code>{escape(codepoint_display)}</code></div>
        </div>
        <div class="info-card">
          <div class="info-card__label">Category</div>
          <div class="info-card__value">{escape(group or 'Unknown')}</div>
        </div>
        <div class="info-card">
          <div class="info-card__label">Subcategory</div>
          <div class="info-card__value">{escape(subgroup or 'Unknown')}</div>
        </div>
        <div class="info-card">
          <div class="info-card__label">Added in</div>
          <div class="info-card__value">Emoji {escape(version)}</div>
        </div>
        <div class="info-card">
          <div class="info-card__label">Shortcode</div>
          <div class="info-card__value"><code>:{slugify(name).replace('-', '_')}:</code></div>
        </div>
        {f'''<div class="info-card">
          <div class="info-card__label">Skin Tones</div>
          <div class="info-card__value">{len(variants)} variants</div>
        </div>''' if variants else ''}
      </div>

      {related_html}
    </div>
  </main>

  <footer class="footer">
    <p class="footer__text">
      <a href="../../" class="footer__link">← Back to emoji-site</a> ·
      Built from the <a href="https://unicode.org/emoji/" class="footer__link" target="_blank" rel="noopener">Unicode Emoji Spec</a>
    </p>
  </footer>

  <div class="toast" id="toast"></div>
  <script src="../../app.js"></script>
</body>
</html>"""

    _root_prefix_stack.pop()

    (page_dir / "index.html").write_text(page, encoding="utf-8")


def generate_group_page(group_name, group_data, base_emojis):
    """Generate a group/category page."""
    group_slug = slugify(group_name)
    page_dir = DIST_DIR / "group" / group_slug
    page_dir.mkdir(parents=True, exist_ok=True)

    icon = GROUP_ICONS.get(group_name, "📁")

    # Collect emojis for this group from base_emojis
    group_emojis = [e for e in base_emojis if e["group"] == group_name]

    # Build subgroup sections
    subgroup_html = ""
    for subgroup_name in group_data["subgroups"]:
        sub_emojis = [e for e in group_emojis if e["subgroup"] == subgroup_name]
        if not sub_emojis:
            continue

        display_name = subgroup_name.replace("-", " ").title()
        cards = "\n".join(emoji_card_link_html(e) for e in sub_emojis)
        subgroup_html += f"""<div class="subgroup-section fade-in">
  <h3 class="subgroup-section__title">{escape(display_name)}</h3>
  <div class="emoji-grid">
    {cards}
  </div>
</div>
"""

    title = f"{icon} {group_name} Emojis — emoji-site"
    description = f"Browse all {len(group_emojis)} {group_name.lower()} emojis. Click to copy."

    _root_prefix_stack.append("../../")

    page = f"""{html_head(title, description)}
<body>
  <main class="container">
    <div class="group-header">
      <a href="../../" class="emoji-detail__back">{SVG_BACK} All Emojis</a>
      <div class="group-header__icon">{icon}</div>
      <h1 class="group-header__title">{escape(group_name)}</h1>
      <p class="group-header__count">{len(group_emojis)} emojis</p>
    </div>

    {subgroup_html}
  </main>

  <footer class="footer">
    <p class="footer__text">
      <a href="../../" class="footer__link">← Back to emoji-site</a> ·
      Built from the <a href="https://unicode.org/emoji/" class="footer__link" target="_blank" rel="noopener">Unicode Emoji Spec</a>
    </p>
  </footer>

  <div class="toast" id="toast"></div>
  <script src="../../app.js"></script>
</body>
</html>"""

    _root_prefix_stack.pop()

    (page_dir / "index.html").write_text(page, encoding="utf-8")


def generate_search_index(base_emojis):
    """Generate the search-index.json file."""
    print("  Generating search-index.json ...")

    index = []
    for emoji in base_emojis:
        # Build keywords from name parts, group, and subgroup
        keywords = set()
        for word in emoji["name"].lower().split():
            keywords.add(word)
        if emoji["subgroup"]:
            for word in emoji["subgroup"].replace("-", " ").split():
                keywords.add(word)
        if emoji["group"]:
            for word in emoji["group"].lower().split():
                keywords.add(word)

        index.append({
            "char": emoji["char"],
            "name": emoji["name"],
            "slug": emoji["slug"],
            "group": emoji["group"],
            "keywords": list(keywords),
        })

    index_path = DIST_DIR / "search-index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"  Search index: {len(index)} entries, {index_path.stat().st_size / 1024:.0f} KB")


def copy_static_assets():
    """Copy static CSS and JS to dist."""
    print("  Copying static assets ...")
    for f in STATIC_DIR.iterdir():
        if f.is_file():
            shutil.copy2(f, DIST_DIR / f.name)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Global reference for index generation (avoids passing everywhere)
emojis_global = []


def main():
    global emojis_global

    print("\n🔤 emoji-site — Static Site Generator\n")
    print("=" * 50)

    # 1. Fetch data
    print("\n📥 Fetching emoji data ...")
    raw_data = fetch_emoji_data()

    # 2. Parse
    print("\n🔍 Parsing emoji data ...")
    all_emojis, groups = parse_emoji_data(raw_data)
    emojis_global = all_emojis
    print(f"  Found {len(all_emojis)} fully-qualified emojis")

    # 3. Build base emoji map (group skin variants)
    print("\n🏗️  Building emoji index ...")
    base_emojis = build_base_emoji_map(all_emojis)
    variant_count = sum(len(e.get("variants", [])) for e in base_emojis)
    print(f"  {len(base_emojis)} base emojis + {variant_count} skin tone variants")

    # 4. Clean and prepare dist
    print("\n🧹 Preparing output directory ...")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    # 5. Copy static assets
    copy_static_assets()

    # 6. Generate pages
    print("\n📄 Generating pages ...")

    # Index page
    generate_index_page(base_emojis, groups)

    # Individual emoji pages
    emoji_count = 0
    for emoji in base_emojis:
        generate_emoji_page(emoji, base_emojis, groups)
        emoji_count += 1
        if emoji_count % 500 == 0:
            print(f"  ... {emoji_count}/{len(base_emojis)} emoji pages")
    print(f"  Generated {emoji_count} emoji pages")

    # Group pages
    group_count = 0
    for group_name, group_data in groups.items():
        if group_name == "Component":
            continue
        generate_group_page(group_name, group_data, base_emojis)
        group_count += 1
    print(f"  Generated {group_count} group pages")

    # 7. Search index
    generate_search_index(base_emojis)

    # 8. Summary
    print("\n" + "=" * 50)
    total_files = sum(1 for _ in DIST_DIR.rglob("*.html")) + 1  # +1 for JSON
    total_size = sum(f.stat().st_size for f in DIST_DIR.rglob("*") if f.is_file())
    print(f"\n✅ Build complete!")
    print(f"   📁 Output: {DIST_DIR}/")
    print(f"   📄 Files:  {total_files}")
    print(f"   💾 Size:   {total_size / (1024 * 1024):.1f} MB")
    print(f"\n   Preview: python3 -m http.server 8000 -d {DIST_DIR}\n")


if __name__ == "__main__":
    main()
