# Changelog

## 1.8.3 — 2026-10-27

- Start search pagination at the first page and encode search terms correctly in paths and query strings.
- Recognize MP4 download links with signed query strings or fragments without changing their tokens.
- Remove the fixed, outdated search cache-buster.
- Close CLI sessions and report failed downloads accurately.
- Use the published `eaf-base-api>=4.2.5` dependency.

