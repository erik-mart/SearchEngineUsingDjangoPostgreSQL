# Django + PostgreSQL Blog Search Demo

This project is an educational demo of search behavior in Django with PostgreSQL, showing side-by-side timing for:

1. normal substring search (`icontains`)
2. PostgreSQL full-text search (`tsvector` + GIN)

It also includes Markdown article rendering, JSON import, duplicate protection, pagination, and an EXPLAIN debug page.

## Features

- Blog articles with Markdown content rendering
- Article list pagination (`10` per page)
- JSON article importer (`import_articles`) with recursive `.json` scanning
- Duplicate protection using a DB constraint on `title + content_hash`
- Search comparison metrics (`count` + `fetch top N`) for fair timing demos
- Indexed search sort toggle: `relevance` (default) or `newest`
- Public debug EXPLAIN page (available when `DEBUG=True`)

## Prerequisites

- Python 3.8+
- PostgreSQL 12+
- pip

## Setup

### 1) Create PostgreSQL database/user

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE searchdb;
CREATE USER test_user WITH PASSWORD 'test_user';
GRANT ALL PRIVILEGES ON DATABASE searchdb TO test_user;
\c searchdb
GRANT USAGE, CREATE ON SCHEMA public TO test_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO test_user;
\q
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Apply migrations

```bash
python manage.py migrate
```

### 4) (Optional) create admin user

```bash
python manage.py createsuperuser
```

### 5) Run server

```bash
python manage.py runserver
```

## Main Endpoints

- `http://127.0.0.1:8000/` article list (paginated)
- `http://127.0.0.1:8000/article/<id>/` article detail
- `http://127.0.0.1:8000/search/?q=term&indexed_sort=relevance` search comparison
- `http://127.0.0.1:8000/search/debug/explain/?q=term&indexed_sort=newest` EXPLAIN plans (`DEBUG=True` only)
- `http://127.0.0.1:8000/admin/` Django admin

## Search Demo Behavior

`/search/` shows both strategies for the same query:

- Normal query (`icontains`)
  - `count <N> in <X> ms`
  - `fetch 20 in <Y> ms`
- Indexed query (`tsvector` + GIN)
  - `count <N> in <X> ms`
  - `fetch 20 in <Y> ms`

Indexed sort toggle:

- `indexed_sort=relevance` (default): sorts by rank, then newest
- `indexed_sort=newest`: sorts by newest only (rank not used for ordering)

See `SEARCH_COMPARISON.md` for detailed interpretation and benchmarking notes.

## JSON Import Command

Import all matching objects from a directory tree:

```bash
python manage.py import_articles /path/to/json-directory
```

Preview import only:

```bash
python manage.py import_articles /path/to/json-directory --dry-run
```

Importer rules:

- Reads all `*.json` files recursively
- Imports objects containing string `title` and `content`
- Skips blank fields and invalid JSON files
- Skips duplicates (same `title` + same `content`)

## Exported Articles Fixture

Current database articles have been exported to:

- `blog/fixtures/articles_export.json`

Import this fixture into your database:

```bash
python manage.py loaddata blog/fixtures/articles_export.json
```

If you want to regenerate the fixture from your current database state:

```bash
python manage.py dumpdata blog.Article --indent 2 --output blog/fixtures/articles_export.json
```

Notes:

- `loaddata` imports full model rows (including `created_at` and `content_hash` values from the fixture)
- importing into a DB that already has overlapping rows may fail because of the unique constraint on `title + content_hash`

## Duplicate Protection

`Article` includes:

- `content_hash` (MD5 of content)
- unique constraint on `('title', 'content_hash')`

This avoids PostgreSQL large-text index-size limits while preventing duplicate imports reliably.

## PostgreSQL Indexes Used for Search

Current migration set includes:

- `blog/migrations/0002_add_tsvector_gin_index.py` (unweighted full-text GIN)
- `blog/migrations/0004_add_weighted_tsvector_gin_index.py` (weighted full-text GIN that matches current query expression)

Weighted index expression:

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

## Tests

Use SQLite test settings:

```bash
python manage.py test blog --settings=django_postgresql.test_settings
```


