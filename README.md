# 🔤 emoji-site

A statically-generated emoji reference site. Browse, search, and copy every emoji — all from a zero-cost GitHub Pages deployment.

## How It Works

1. **`build.py`** fetches the official [Unicode emoji-test.txt](https://www.unicode.org/Public/emoji/latest/emoji-test.txt) spec
2. Parses every fully-qualified emoji with its name, group, subgroup, and version
3. Generates a static HTML page for each emoji, plus index and group pages
4. Outputs everything to `dist/` — ready for GitHub Pages

## Local Development

```bash
# Build the site
python3 build.py

# Preview (Python's built-in server)
python3 -m http.server 8000 -d dist
```

Then open [http://localhost:8000](http://localhost:8000).

## Deployment

The site auto-deploys to GitHub Pages via GitHub Actions on every push to `main`. It also rebuilds weekly (Monday 6am UTC) to catch new Unicode emoji releases.

To trigger a manual rebuild, go to **Actions → Build & Deploy emoji-site → Run workflow**.

## Project Structure

```
emojidex/
├── build.py                    # Static site generator
├── static/
│   ├── style.css               # Design system & styles
│   └── app.js                  # Client-side search & interactions
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions deployment
└── dist/                       # Generated output (gitignored)
    ├── index.html
    ├── search-index.json
    ├── emoji/{slug}/index.html
    └── group/{slug}/index.html
```

## Data Source

All emoji data comes from the [Unicode Consortium's emoji-test.txt](https://www.unicode.org/Public/emoji/latest/emoji-test.txt), the authoritative source for emoji sequences and metadata. No data is hardcoded.

## License

MIT
