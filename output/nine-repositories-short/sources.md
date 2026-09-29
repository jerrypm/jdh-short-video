# Sources, checks and unresolved claims

All checks below were run on **28 September 2026** from this machine. Nothing in this folder was
published.

## 1. The article

| Field | Value |
| --- | --- |
| Title | 9 Cool Repositories I Found on the Internet This Week |
| Author | Jerry PM (Medium handle `21zerixpm`) |
| Publication | Stackademic |
| Published | 6 September 2026 (article PDF page 1) |
| Supplied file | `/Users/jeripurnamamaulid/Downloads/9 Cool Repositories I Found on the Internet This Week _ by Jerry PM _ Sep, 2026 _ Stackademic.pdf` |
| Pages | 20 total; **pages 1–15 are the article**. Pages 16–20 are the clap/follow footer, responses, "More from" cards and Medium recommendations and were ignored. |
| Extracted with | `pdfinfo`, `pdftotext -layout`, `pdftotext -bbox-layout`, `pdftoppm -r 300 -png` (Poppler, `/opt/homebrew/bin`) |

Pages 16–20 were excluded on purpose, so no Medium navigation, avatars, notification counters,
comment threads or unrelated recommended articles are shown anywhere in the video. The nine
repositories, in the article's own saved order, with the page range each one occupies:

| # | Display name | Repository | Article pages | Point used in the video |
| --- | --- | --- | --- | --- |
| 1 | ECC | https://github.com/affaan-m/ECC | 2–3 | Packages skills, agents and hooks; choose selectively |
| 2 | CLI-Anything | https://github.com/HKUDS/CLI-Anything | 3–5 | Generates command-line interfaces for desktop tools |
| 3 | screenshot-to-code | https://github.com/abi/screenshot-to-code | 5–6 | Converts reference screenshots into web layouts |
| 4 | ScrapeGraphAI | https://github.com/ScrapeGraphAI/Scrapegraph-ai | 6–8 | Prompt-driven extraction of web data |
| 5 | Google Skills | https://github.com/google/skills | 8–9 | Agent skills for cloud and developer workflows |
| 6 | DeepSeek Harness | https://github.com/deepseek-ai/deepseek-harness | 9–11 | Plugin-based agent framework; the article calls it a developer preview |
| 7 | Humanizer | https://github.com/blader/humanizer | 11 | Edits AI-style prose while preserving code and data |
| 8 | Stop Slop | https://github.com/hardikpandya/stop-slop | 12–13 | Writing rules and a rubric for reviewing prose |
| 9 | OmniRoute | https://github.com/diegosouzapw/OmniRoute | 13 | Routing infrastructure across model providers |

Every crop used in the video is taken from those pages only. Crops are defined by word bounding
boxes (`source/extract_source.py`, output `source/crops.json`) and each crop is asserted to contain
none of the article's changing numbers: `stars`, `~NNNk`, `%`, `tokens`, `providers`, `commits`,
`followers`. Because the star count sits on the same line as each repository slug, slug crops are
cut horizontally at the end of the slug, before the separator.

## 2. Article URL

`article_url` for the upload metadata:

```
https://blog.stackademic.com/9-cool-repositories-i-found-on-the-internet-this-week-4966841b1a22
```

How it was verified, and what could not be verified:

- The supplied PDF's own link annotations carry the story id **`4966841b1a22`** in every
  Medium cross-link on pages 1–15 (for example `source=post_page---author_recirc--4966841b1a22`).
  Extracted with `pdftohtml` and read from the generated HTML.
- A public web search for the exact title returned that URL as the first result, with a matching
  title, the author Jerry PM, the publication Stackademic and a snippet of the article's own
  section headings ("1. ECC ➞ the maximalist · 2. CLI-Anything …"). The slug and the story id in
  that URL match the id embedded in the PDF.
- Direct fetches of `medium.com/stackademic/<slug>`, `blog.stackademic.com/<slug>` and
  `medium.com/p/4966841b1a22` all returned **HTTP 403 from Cloudflare** on 28 September 2026, and the
  author's public RSS feed (`medium.com/feed/@21zerixpm`) only carries the ten most recent posts, so
  the Sep 6 story is not in it. The URL is therefore verified by story id plus a public index, not by
  fetching the page itself.
- The search result showed the date as "Sep 5, 2026" while the article page itself shows
  "Sep 6, 2026"; the video says neither, and the card header uses the article's own **SEP 6, 2026**.
- The article's later "In Stackademic" recirculation link
  `medium.com/stackademic/your-ai-agent-skills-should-not-belong-to-one-coding-tool-93a9105a881f`
  is a *different* story and is not used.

## 3. Official repository checks (GitHub REST API, 28 September 2026)

Method: `GET https://api.github.com/repos/<owner>/<repo>` and
`GET https://api.github.com/repos/<owner>/<repo>/readme` (raw). README copies are saved in
`source/readmes/`. No repository was cloned, installed, built or executed, and no installation
command from the article was run.

| Repository | License | Last push seen | README facts that back the video's one point |
| --- | --- | --- | --- |
| affaan-m/ECC | MIT | 2026-09-28 | Indexes "hooks" and "lifecycle hook", SKILL.md and install instructions; describes itself as an agent harness system for several coding agents |
| HKUDS/CLI-Anything | Apache-2.0 | 2026-09-22 | "Making ALL Software Agent-Native", references a CLI-Hub registry, GUI programs and generated SKILL.md files |
| abi/screenshot-to-code | MIT | 2026-09-09 | "Convert screenshots, mockups, Figma designs, and screen recordings into clean, functional code using AI"; lists HTML/Tailwind, React, Vue, Bootstrap, Ionic stacks |
| ScrapeGraphAI/Scrapegraph-ai | MIT | 2026-09-25 | "Python scraper based on AI"; documents `SmartScraper` graph pipelines driven by a prompt |
| google/skills | Apache-2.0 | 2026-09-25 | Agent Skills for Google products, including Google Cloud; installs the skills with `npx skills add google/skills` |
| deepseek-ai/deepseek-harness | MIT | 2026-09-28 | "everything-is-a-plugin architecture"; README has a **"Developer preview"** section stating there will be compatibility-breaking changes — the article's preview wording is accurate |
| blader/humanizer | MIT | 2026-09-28 | "makes AI-written text sound like a person wrote it"; built on Wikipedia's *Signs of AI writing*; works in Claude Code and Codex |
| hardikpandya/stop-slop | MIT | 2026-03-17 | "A skill for removing AI tells from prose"; SKILL.md plus reference files |
| diegosouzapw/OmniRoute | MIT | 2026-09-28 | AI gateway: one endpoint in front of many providers, with routing strategies, fallback and circuit breakers |

All nine URLs returned HTTP 200 on that date, so none of them is broken or renamed.

### Numbers that were read but deliberately omitted

Star counts, provider counts, token-saving percentages, skill/agent/hook counts, commit counts,
install size and free-token estimates all appear in the article and in some READMEs. They change
constantly, so **none of them appears in the video, the title, the description or the captions**. The
only counts that survive are structural and stable: "nine repositories" and the article's own
"six of nine" split.

### Claims that remain unresolved

- **OmniRoute compression savings** (a wide percentage range in the article) and its provider
  inventory were not measured on any traffic. The video says only that it routes across providers.
- **ScrapeGraphAI's maintenance advantage** ("survives a redesign") is the article's argument; the
  video repeats the prompt-driven idea, not the comparative claim.
- **CLI-Anything's coverage of specific desktop programs** was not tested; the video says it turns
  desktop software into command-line tools.
- **Developer preview status** of DeepSeek Harness was verified in its README on 28 September 2026.
  It is presented as a preview and not as production-ready.
- Whether any of the nine repositories is safe or appropriate for a particular machine was not
  evaluated; the video's closing line tells the viewer to read the README first.

## 4. What this production did not do

- No repository was installed, cloned or executed.
- No command shown inside an article crop was run.
- No live demonstration, screenshot of a running tool, or performance result is presented or implied.
- No cloud service was used for speech, images or rendering, and no voice cloning was used.
- Gemini Nano was not used, and no claim is made about what any model can run offline.
