# 2.0.0

Release 2.0.0

Update pagination handling, validation, and documentation.

Changes since 1.8.3:

```text
README.md           | 14 ++++++++++
 porntrex_api/api.py | 75 ++++++++++++++++++++++++++++++++++++++++++++---------
 pyproject.toml      |  4 +--
 3 files changed, 79 insertions(+), 14 deletions(-)
```

# Changelog

## 1.8.3 — 2026-10-27

- Start search pagination at the first page and encode search terms correctly in paths and query strings.
- Recognize MP4 download links with signed query strings or fragments without changing their tokens.
- Remove the fixed, outdated search cache-buster.
- Close CLI sessions and report failed downloads accurately.
- Use the published `eaf-base-api>=4.2.5` dependency.

