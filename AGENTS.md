# LiveCrime Agent Instructions

## Project overview

- LiveCrime is a rule-based Telegram news autoposter written in Python.
- It collects crime-news metadata, selects serious true-crime events, builds one post, and publishes it through the Telegram Bot API.
- RSS and HTML sources must produce the same `news_item` structure.
- The project is intentionally explainable: selection must be traceable to explicit rules, not opaque ranking.
- Core editorial principle: **Better 0 posts than an irrelevant or weak crime post.**
- Preserve the existing architecture and coding style unless a task explicitly requires a redesign.
- Use only free sources, free libraries, and the free Telegram Bot API.
- Do not add paid news APIs, paid AI APIs, mandatory cloud AI, or paid infrastructure dependencies.
- Do not weaken filtering merely to increase publication frequency.

## Repository map

- `main.py` orchestrates one complete run and owns publication/history sequencing.
- `config.py` contains source switches, topic rules, score rules, limits, and safe runtime defaults.
- `collectors/rss_collector.py` collects RSS entries.
- `collectors/html_collector.py` dispatches existing site-specific HTML adapters.
- `processing/normalizer.py` normalizes RSS dates and descriptions.
- `processing/filters.py` applies date, hard-topic, score, and ranking rules.
- `processing/deduplicator.py` handles URL, title, and cross-source event deduplication.
- `article/fetcher.py` fetches article HTML and extracts text and image URLs.
- `generation/post_generator.py` creates HTML-safe text posts, photo captions, and hashtags.
- `publishing/telegram.py` owns Bot API requests and the temporary-image fallback.
- `storage/history.py` reads, compares, updates, and writes publication history.
- `core/environment.py` configures the certificate bundle.
- `core/run_lock.py` prevents concurrent local processes.
- `tests/` contains unit and regression tests for filters, extraction, deduplication, publishing, selection, and workflow safety.
- `.github/workflows/livecrime.yml` runs the production job and commits only changed publication history.

## Current `news_item` contract

- Collector fields are `title`, `url`, `published_at`, `description`, and `source`.
- `published_at` is a timezone-aware `datetime` when known; it may be `None` when a reliable date is unavailable.
- Filtering adds `matched_topics`, `strong_topics`, `contextual_topics`, diagnostic reasons, and `score`.
- Article loading adds `article_text` and `image_url` to that same dictionary.
- Keep text, image, title, and URL attached to one `news_item`; do not create parallel lists that can drift out of sync.
- A missing article body uses `description` as the post-generator fallback.

## Actual runtime pipeline

The current `main.py` order is:

1. Configure the SSL certificate bundle.
2. Select enabled sources and collect RSS or HTML items.
3. Normalize dates/descriptions inside the collectors.
4. Filter by `NEWS_LOOKBACK_DAYS`.
5. Apply the hard serious-crime topic filter.
6. Add scores and require `MIN_PUBLICATION_SCORE`.
7. Rank candidates by score, preserving source order for ties.
8. Fetch article HTML once per ranked candidate and attach both `article_text` and `image_url`.
9. Run URL, title, and cross-source event deduplication in `remove_duplicates()`.
10. Load history; bypass its selection restriction only in `DRY_RUN`.
11. Slice `selected_news` to `MAX_NEWS_PER_RUN`.
12. Generate exactly one independent post per selected item.
13. Publish or print the post according to `DRY_RUN`.
14. Add only confirmed publications to history and save history once if it changed.

- Do not move article loading after event dedup without redesigning that algorithm: event comparison uses the beginning of `article_text`.
- Do not silently reorder filter, score, ranking, deduplication, history, selection, and publication stages.
- If a task description presents a simplified pipeline, follow the verified code order above unless the task explicitly changes it.

## Safe execution and DRY_RUN

- `DRY_RUN` reads `LIVECRIME_DRY_RUN` and defaults to `True` when the variable is missing or invalid.
- Local runs are therefore safe by default.
- In `DRY_RUN=True`, collect, filter, rank, extract, deduplicate, generate, and print normally.
- In `DRY_RUN=True`, history does not restrict the test selection, so the same candidates can be examined repeatedly.
- In `DRY_RUN=True`, never call Telegram and never write `storage/published.json`.
- Tests and diagnostics should use `DRY_RUN=True` unless a test replaces all network and storage effects with controlled doubles.
- `MAX_NEWS_PER_RUN = 1`; do not change it casually or bypass it elsewhere.
- `POST_MODE = "single"`; one selected item corresponds to one Telegram message.
- **Never perform a real Telegram send unless the task explicitly requires it.**
- A request to test code, run the suite, or inspect output is not authorization for a live send.
- Before any safe end-to-end run, confirm the effective value of `DRY_RUN` and preserve a hash of `storage/published.json`.

## Hard true-crime filtering

- The hard filter is an editorial safety boundary, not a recall-maximization feature.
- Standalone strong topics currently cover homicide forms, sexual violence, shootings resulting in death, and suicide forms.
- `STRONG_TOPICS` may admit a story independently, subject to exclusions.
- `CONDITIONAL_SERIOUS_TOPICS` currently include attempted attacks, attacks, shootings, beatings, and related forms.
- A conditional topic admits a story only together with a configured severe-outcome expression.
- `CONTEXTUAL_TOPICS` explain or score context but cannot independently open the hard filter.
- Procedural terms such as accusation, investigation, arrest, court, search, fraud, theft, and drugs are not sufficient by themselves.
- Topic matching is anchored at the beginning of a word; do not replace it with unrestricted substring matching.
- The special `убит` guard must not turn the infinitive `убить` into a completed homicide.
- `matched_topics`, `strong_topics`, `contextual_topics`, `admission_reason`, and `rejection_reason` are diagnostic contracts; preserve them.
- Score cannot compensate for failure of the hard filter.
- `MIN_PUBLICATION_SCORE = 4`.
- Contextual score bonus is capped at 3.
- Do not change strong topics, conditional topics, severe outcomes, exclusions, scoring, or threshold in an unrelated task.
- Add regression tests for every known false positive and every nearby valid true-crime case when changing topic logic.

## Deduplication

- `remove_duplicates()` is one ordered operation with three layers: exact URL, similar title, then cross-source event comparison.
- Normalized-title similarity uses `SequenceMatcher` with threshold `0.75`.
- Explicit conflicting locations protect similar titles from being merged.
- Event dedup compares different sources only.
- Both items must have reliable publication dates.
- The maximum event time distance is 36 hours.
- Fingerprints use the title plus the first 1,600 characters of article text or description.
- Event topic families currently distinguish homicide, sexual violence, and suicide.
- The comparison requires at least 5 shared meaningful tokens.
- Minimum shared-token overlap against the smaller token set is `0.45`.
- A shared location is sufficient after those base checks.
- Without a shared location, require at least 7 shared tokens and Jaccard similarity of at least `0.20`.
- Noise words, procedural terms, topic markers, and lightweight Russian inflections are removed locally without a morphology service.
- Do not loosen these thresholds to merge more stories without paired positive and negative tests.
- When event duplicates compete, prefer higher score, then article text, then image, then longer article text, then stable first occurrence.
- Keep DRY_RUN event-dedup diagnostics free of secrets and useful for explaining the decision.

## History and cross-run deduplication

- `storage/published.json` records only confirmed successful publications.
- Never clear, bulk-edit, or manually prune history unless the task explicitly names the entries and authorizes it.
- Add history only after the corresponding Telegram result is confirmed successful.
- Do not add history for failed, skipped, dry-run, or uncertain publications.
- Save history once after processing the selected items, and only when it actually changed.
- New history entries store `title`, `url`, `published_at`, `source`, and a compact `event_fingerprint`.
- The compact fingerprint stores event topics, meaningful tokens, and locations, not full article text.
- Legacy entries without `event_fingerprint` remain valid and are compared by URL.
- Never require a migration that would invalidate old history unless a dedicated migration task explicitly authorizes it.
- GitHub Actions must stage only `storage/published.json`; never replace that with `git add .`.

## Article extraction and cleanup

- Fetch each article page once whenever possible.
- Use the same HTML response to extract both `article_text` and `image_url`.
- If both keys are already present, do not repeat the HTTP request.
- Network, HTTP, parser, or empty-text failure for one article must not stop other candidates.
- Keep extraction in `article/fetcher.py`; collectors gather cards and metadata only.
- Prefer a reliable article-body DOM container over page-wide paragraph scraping.
- Use source-specific extraction or stop markers for site-specific chrome and footers.
- Current dedicated extractors exist for `АГН Москва: происшествия`, `VN.ru: происшествия`, and `KrasnoyarskMedia: происшествия`.
- Current source-specific stop-marker cleanup also covers PeterburgMedia and VN.ru.
- Do not turn a source-specific defect into a global aggressive blacklist.
- Do not remove useful paragraphs merely because they are short.
- When adding cleanup, reproduce a real page, identify the responsible DOM, and add a focused regression fixture.
- Verify the beginning and end of several articles from the affected source.
- Confirm that representative articles from unrelated sources remain unchanged.

## Image URL and photo publishing

- Image extraction checks `og:image`, then `twitter:image`, and resolves relative URLs against the article URL.
- Images are not stored in the repository.
- Production photo flow is: remote image URL -> Telegram `sendPhoto` -> temporary-file fallback only for a confirmed Telegram remote-fetch error -> multipart `sendPhoto` -> text fallback after confirmed failure.
- Remote-fetch fallback markers are deliberately narrow; do not download every image after an arbitrary Bot API error.
- Temporary images live in the operating-system temp directory and are removed in `finally`.
- Downloaded content must have `Content-Type: image/*`, must not be empty, and must stay within 10 MiB.
- File suffixes derive from MIME type, not an untrusted URL extension.
- A successful remote `sendPhoto` must not trigger multipart upload or `sendMessage`.
- A successful multipart `sendPhoto` must not trigger `sendMessage`.
- A confirmed photo failure may use one text fallback so the news can still be published.
- One `news_item` may create at most one Telegram message.
- Connect timeout is 10 seconds; read timeout is 30 seconds.
- Telegram attempts are capped at 2 with a 2-second delay, but only `ConnectTimeout` is automatically retried.
- `ReadTimeout` and general `ConnectionError` are uncertain outcomes: Telegram may already have accepted the message.
- On an uncertain outcome, do not retry, do not fall back to another method, and do not update history.
- Logs may include safe error descriptions and image URLs, but never Bot API URLs containing tokens.
- Do not add placeholder/logo filtering as an undocumented assumption; first verify current source behavior and add explicit tests if implementing it.

## Telegram secrets and environment

- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are read from environment variables.
- Local `.env` loading is supported by `python-dotenv`; `.env` is ignored by Git.
- `LIVECRIME_DRY_RUN` is the only switch that may disable the safe default.
- GitHub Actions supplies the two Telegram secrets and sets `LIVECRIME_DRY_RUN` to `"false"`.
- Never print, commit, paste into fixtures, or interpolate secrets into logged URLs.
- Do not add real credentials to `.env.example`, tests, documentation, or commit messages.
- SSL setup may set `SSL_CERT_FILE` to the bundled `certifi` CA path when it is not already configured.

## Concurrency and scheduling

- `core/run_lock.py` uses a non-blocking exclusive `fcntl` lock at the system-temp path `livecrime-autoposter.lock`.
- A second local process exits before it can publish the same selection.
- GitHub Actions uses concurrency group `livecrime-autoposter`.
- Keep `cancel-in-progress: false`; a later run must wait rather than cancel an active publisher.
- The repository workflow exposes `workflow_dispatch` and intentionally has no built-in `schedule` block.
- Current scheduling model: `cron-job.org -> GitHub API workflow_dispatch -> GitHub Actions -> LiveCrime`.
- Do not add a second scheduler or restore GitHub cron in an unrelated task.
- The workflow runs `main.py` before the history commit step, so a failed run must not commit history.

## Source maintenance

- Configure sources in `SOURCES`; do not hard-code source lists in `main.py`.
- Preserve the common collector output contract.
- Keep HTML site differences inside the existing adapter dispatch.
- Use direct article URLs and timezone-aware dates; use `None` rather than inventing a date.
- Limit HTML collection to the configured first-page scope.
- A timeout, 403, malformed feed, parser change, or empty source must log a warning and allow other sources to continue.
- Do not bypass CAPTCHA or anti-bot protection.
- Do not add Selenium or Playwright for source collection.
- Expand coverage only from a verified direct RSS or maintainable HTML category page.
- Enable sources incrementally and inspect title, URL, date, source name, pipeline counts, and article extraction.
- Never weaken the hard filter to compensate for an empty or unreliable source.

## Rules for Codex

### Before changing files

- Read this file completely, then inspect the files named by the task.
- Read `00_Стартовые_требования_LiveCrime_Autoposter.md` and `ROADMAP.md` when changing architecture or pipeline behavior.
- Check `git status --short --branch` before editing.
- Treat every pre-existing change as user-owned; do not overwrite or clean it up.
- Record the hash or diff state of `storage/published.json` for tasks that run the application or touch publication logic.
- Confirm whether the task authorizes external network access, live Telegram publication, history mutation, scheduler changes, or source enabling.
- Prefer a narrow change over a broad refactor.

### While changing files

- Preserve function boundaries, dictionary contracts, ordering, and comments unless the task requires a change.
- Add short comments around non-obvious safety decisions; do not narrate every obvious line.
- Catch specific exceptions; never use a bare `except:`.
- Keep failures isolated to one source, article, image, or post where possible.
- Do not download or commit binary images.
- Do not create a second HTTP request when data can be extracted from an HTML response already held in memory.
- Do not mix title, URL, text, image, caption, or history data from different `news_item` objects.
- Do not change enabled sources, `MAX_NEWS_PER_RUN`, filtering, history, Telegram, workflow, or scheduling outside the task scope.
- Add or update focused regression tests whenever behavior changes.

### Verification after changes

- Run the smallest focused tests while iterating, then run the full test suite before handoff.
- For end-to-end diagnostics, use effective `DRY_RUN=True` and verify no Telegram request occurred.
- Compare the before/after hash or diff of `storage/published.json` after safe runs.
- Inspect `git diff --check` for whitespace errors.
- Inspect the complete final diff, including staged and unstaged changes.
- Confirm no secret, `.env`, temporary image, cache, or unrelated file entered the diff.
- Confirm the requested behavior and its important negative cases.
- If network conditions prevent a live-source diagnostic, report that limitation instead of inventing results.

## Testing requirements

- Use the repository virtual environment when available: `.venv/bin/python -m unittest discover -s tests -v`.
- Tests must not call the real Telegram API.
- Mock Telegram request functions, image downloads, time delays, and filesystem effects as narrowly as possible.
- Preserve coverage for successful photo sends, confirmed photo fallback, uncertain delivery, and one-time history updates.
- Preserve regression coverage for strict-filter false positives and valid serious-crime cases.
- Preserve cross-source dedup tests for same-event pairs and close but distinct events.
- Preserve extractor tests for useful body text, removed site chrome, and unaffected other sources.
- Workflow tests must keep `workflow_dispatch`, no `schedule`, concurrency safety, production `LIVECRIME_DRY_RUN=false`, and history-only staging.

## Git rules

- Do not amend, reset, rebase, force-push, or discard user work unless explicitly requested.
- Do not use destructive checkout/reset commands to clean the tree.
- Stage only files that belong to the task.
- Review the staged diff before committing.
- Use the exact commit subject requested by the task.
- Do not create an empty commit.
- Do not push unless the user explicitly requests a push.
- After committing, report the commit hash and whether the branch is ahead of its upstream.

## Final report format

Keep the handoff short but evidence-based. Include:

1. Files changed and the behavior implemented.
2. Actual configuration values or thresholds relevant to the task.
3. Focused and full test commands with pass counts.
4. Safe-run results, including source/candidate counts when requested.
5. Whether Telegram was contacted or a real message was sent.
6. Whether `storage/published.json` changed.
7. Any network, HTTP, parser, or source limitations observed.
8. Commit subject and short hash.
9. Final working-tree state and relationship to `origin/main`.

- Never claim a live verification that was not performed.
- Distinguish confirmed facts from inferences and unavailable external state.
- Mention any verified mismatch between a task assumption and the current code.
