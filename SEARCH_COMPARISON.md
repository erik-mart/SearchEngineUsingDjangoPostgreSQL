# Search Comparison Guide: `icontains` vs `tsvector` + GIN

This document explains the current search-comparison implementation in this project.

## 1) Search Strategies in the Current Version

### A) Normal search (`icontains`)

- Query behavior: `title__icontains=query OR content__icontains=query`
- Type: case-insensitive substring matching
- Typical result shape: exact text fragment matches

### B) Indexed full-text search (`tsvector` + GIN)

- Query behavior: weighted full-text vector
  - title weight `A`
  - content weight `B`
- Query uses PostgreSQL `SearchQuery(..., search_type='plain', config='english')`
- Type: tokenized/linguistic matching (can include stems and related forms)

## 2) Fair Timing Methodology

`/search/` compares equivalent work for each strategy:

- `count` timing (`count <N> in <X> ms`)
- fixed-page fetch timing (`fetch 20 in <Y> ms`)

`SEARCH_PREVIEW_SIZE` is currently `20` in `blog/views.py`.

This avoids the bias of timing `list(full_queryset)` for very different result sizes.

## 3) Indexed Sort Modes

The indexed query supports:

- `indexed_sort=relevance` (default)
  - ordered by `-rank`, then `-created_at`
- `indexed_sort=newest`
  - ordered by `-created_at`
  - no rank annotation for ordering path

This lets you demo ranking and recency with the same query.

## 4) Why Counts Differ (`icontains` vs Full-Text)

Counts often differ. This is expected because semantics differ:

- `icontains`: exact substring logic
- full-text: token/stem logic under English configuration

So treat this as a speed-and-behavior comparison, not a strict identical-match comparison.

## 5) Current Indexes Used in the Project

Migrations:

- `blog/migrations/0002_add_tsvector_gin_index.py`
- `blog/migrations/0004_add_weighted_tsvector_gin_index.py`

Weighted index (matches current weighted query expression):

```sql
CREATE INDEX IF NOT EXISTS blog_article_weighted_search_vector_gin_idx
ON blog_article
USING GIN (
    (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(content, '')), 'B')
    )
);
```

## 6) EXPLAIN Page for Live Demo

Use:

`/search/debug/explain/?q=<term>&indexed_sort=relevance`

Notes:

- endpoint is public in app routing
- endpoint is active only when `DEBUG=True`
- shows `EXPLAIN` plans for normal and indexed queries side by side

## 7) Reproducible Demo Steps

1. Ensure PostgreSQL is configured in `settings.py`.
2. Apply migrations:

```bash
python manage.py migrate
```

3. Load a larger dataset (admin or `import_articles`).
4. Run server:

```bash
python manage.py runserver
```

5. Run several queries on `/search/` in both indexed sort modes.
6. Record:
   - normal `count` ms
   - normal `fetch` ms
   - indexed `count` ms
   - indexed `fetch` ms
7. Repeat and compare medians.

## 8) Interpreting Results

- faster indexed timings are more likely on larger datasets
- warm/cold cache can shift numbers between runs
- relevance mode may add ranking overhead compared to newest mode
- count and fetch should be discussed separately

## 9) Optional Next Steps

- add repeated benchmark mode (N runs + median/p95)
- add optional `EXPLAIN ANALYZE` mode in debug page
- compare `SearchQuery` types (`plain`, `phrase`, `websearch`)
- compare rank formula variants for teaching relevance tuning

