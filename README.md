# Sri Lanka This Week — Machine-Readable Feeds

Machine-readable RSS + JSON feeds for the weekly 🇱🇰 **Sri Lanka This Week** digest published at  
[github.com/nuuuwan/lk_news_digest](https://github.com/nuuuwan/lk_news_digest).

This repository does **not** generate original news content. It:

- consumes the AI-generated weekly digest curated and maintained by **[Nuwan Senaratna](https://github.com/nuuuwan)** in `nuuuwan/lk_news_digest`, and  
- exposes a clean, standards-compliant RSS 2.0 and JSON Feed 1.1 output for use in feed readers and integrations.

---

## Feeds

Hosted via GitHub Pages at:

- **RSS 2.0:** `https://nandulak.github.io/lk-news-weekly-feed/news.xml`  
- **JSON Feed 1.1:** `https://nandulak.github.io/lk-news-weekly-feed/news.json`

Both feeds:

- Track the **latest weekly editions only** (rolling window, capped).
- Ensure **one canonical item per edition date**, even if multiple historical README variants exist.
- Include only editions from **2025-10-17 onwards** (configurable in `build_feeds.py`).
- Provide:
  - `title` with edition date and (when available) source count
  - stable `guid` / `id`
  - `pubDate` / `date_published` in UTC
  - a short **human-readable summary**
  - full HTML content for rich readers

Specs referenced:

- RSS 2.0 Specification (Harvard / UserLand).   
- JSON Feed Version 1.1 specification (jsonfeed.org).   

---

## How it Works

The core logic lives in [`build_feeds.py`](build_feeds.py):

1. **Fetch latest edition**
   - Downloads `README.md` from `nuuuwan/lk_news_digest`.
2. **Fetch historical editions**
   - Lists `data/history/` via GitHub API.
   - Considers all `*.md` files, regardless of naming convention (e.g. `README.20251011.082145.md`).
3. **Parse editions**
   - Extracts:
     - edition date from the prompt range or heading
     - source count from the “English News Articles” line
   - Renders Markdown ➝ HTML with GitHub-friendly semantics.
   - Normalises timestamps:
     - Treats the edition date as **06:00 LKT** (UTC+5:30) and converts to UTC.
4. **Deduplicate by edition date**
   - Keeps only the **latest/best version per date** using a simple, explicit heuristic:
     - Later filenames override earlier.
     - Longer `content_html` can override shorter when dates match.
5. **Filter + order**
   - Includes only editions `>= CUTOFF_DATE` (currently `2025-10-17`).
   - Sorts newest-first.
   - Truncates to a rolling window (`MAX_ITEMS`).
6. **Emit feeds**
   - **RSS:** RSS 2.0 with:
     - `<content:encoded>` for full HTML
     - `<atom:link rel="self">` for self-discovery
     - Standards-compliant metadata and encoding.
   - **JSON Feed:** valid JSON Feed 1.1 with parallel structure.

A scheduled GitHub Actions workflow runs `build_feeds.py`, commits any changes, and GitHub Pages serves the updated feeds.

---

## Attribution & Credits

### Original Digest & News Sources

- The **Sri Lanka This Week** digest is created and maintained by **[Nuwan Senaratna](https://github.com/nuuuwan)** in  
  [`nuuuwan/lk_news_digest`](https://github.com/nuuuwan/lk_news_digest).  
- Nuwan’s project:
  - Aggregates **vetted English-language Sri Lankan news sources**.
  - Uses AI to generate an editorial-style weekly summary, as documented in that repository.
- This repository:
  - Only republishes that digest in machine-readable formats (RSS/JSON).
  - Does **not** modify the editorial substance of Nuwan’s work.
  - Does **not** claim ownership of:
    - Nuwan’s prompts, methodology, or prose.
    - Any third-party articles cited in the digest.

All rights to the underlying news content remain with the respective publishers and authors.  
Please consult `nuuuwan/lk_news_digest` for upstream licensing and usage terms.

### This Repository

- Feed wrapper design & implementation: **[@nandulak](https://github.com/nandulak)**.
- Upstream editorial content: **[@nuuuwan](https://github.com/nuuuwan)** and referenced news sources.

If you use these feeds publicly, good practice is to **credit both**:

> “Sri Lanka This Week — based on the AI-generated weekly digest by Nuwan Senaratna (`nuuuwan/lk_news_digest`), feed wrapper by `lk-news-weekly-feed`.”

---

### AI Attribution Statement

This project is co-created by a human maintainer and an AI assistant, following the emerging **AI Attribution Toolkit** conventions from IBM Research. 

**Attribution (feeds/tooling in this repo)**

> **AIA HAb Ce Nc Hin R GPT-5 Thinking v1.0**  
> This means:
> - **Human-AI Blend (HAb)**: The feed generation code, documentation, and design were created through a balanced collaboration between human contributors and an AI assistant.
> - **Content Edits (Ce)**: AI was used to refine text, improve clarity, and align with web, RSS, and JSON Feed best practices.
> - **New Content (Nc)**: AI proposed initial drafts for parts of the code, README, and HTML, which were subsequently modified and validated by a human maintainer.
> - **Human-Initiated (Hin)**: All AI contributions were produced in response to explicit human prompts and guidance.
> - **Reviewed (R)**: All AI-generated or AI-assisted outputs (including this statement) were reviewed, corrected, or accepted by the human maintainer before publication.
> - **Model**: GPT-5 Thinking (via ChatGPT), version information as available at time of collaboration.
 

---

## Usage

Typical usage patterns:

- Subscribe in your feed reader:
  - Add `https://nandulak.github.io/lk-news-weekly-feed/news.xml` (RSS), or
  - Add `https://nandulak.github.io/lk-news-weekly-feed/news.json` (JSON Feed).
- Integrate into applications or dashboards:
  - Poll on a **weekly** cadence.
  - Respect HTTP caching and ETag/Last-Modified semantics where applicable.
- Always display attribution to:
  - **Sri Lanka This Week** (Nuwan’s digest).
  - Original publishers cited in each edition.

---

## Development

Key files:

- `build_feeds.py` — fetches upstream content and builds feeds.
- `.github/workflows/build-feed.yml` — scheduled build + commit.
- `index.html` — human-facing landing page for the feeds.

Contributions are welcome via pull requests or issues that:

- Improve standards compliance, performance, or robustness.
- Enhance transparency, accessibility, and ethical attribution.

---

## License

- **Code** in this repository is licensed under the MIT License (see `LICENSE`).
- **Digest content** and **linked articles** remain under their respective original licenses and terms.
- Users of this repository are responsible for complying with those upstream licenses and terms when redistributing or embedding content.

---
