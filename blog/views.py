from django.shortcuts import render
from django.db.models import F, Q
from django.db import connection
from django.core.paginator import Paginator
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.conf import settings
from django.http import Http404
from time import perf_counter
from .models import Article


SEARCH_PREVIEW_SIZE = 20
ARTICLE_LIST_PAGE_SIZE = 10


def _time_call(func):
    start = perf_counter()
    result = func()
    elapsed_ms = (perf_counter() - start) * 1000
    return result, elapsed_ms


def _normal_search_queryset(query):
    return Article.objects.filter(
        Q(title__icontains=query) | Q(content__icontains=query)
    ).order_by('-created_at')


def _indexed_search_queryset(query, indexed_sort='relevance'):
    search_query = SearchQuery(query, config='english', search_type='plain')
    base_indexed_qs = Article.objects.annotate(
        search_vector=(
            SearchVector('title', weight='A', config='english')
            + SearchVector('content', weight='B', config='english')
        ),
    ).filter(
        search_vector=search_query
    )

    if indexed_sort == 'newest':
        return base_indexed_qs.order_by('-created_at')

    return base_indexed_qs.annotate(
        rank=SearchRank(F('search_vector'), search_query)
    ).order_by('-rank', '-created_at')


def article_list(request):
    """Display all articles"""
    articles_qs = Article.objects.all()
    paginator = Paginator(articles_qs, ARTICLE_LIST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'blog/article_list.html', {
        'articles': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
    })


def article_detail(request, pk):
    """Display a single article"""
    article = Article.objects.get(pk=pk)
    return render(request, 'blog/article_detail.html', {'article': article})


def article_search(request):
    """Search articles by title or content"""
    query = request.GET.get('q', '')
    indexed_sort = request.GET.get('indexed_sort', 'relevance')
    if indexed_sort not in {'relevance', 'newest'}:
        indexed_sort = 'relevance'

    articles = []
    normal_count_ms = None
    normal_fetch_ms = None
    indexed_count_ms = None
    indexed_fetch_ms = None
    normal_count = 0
    indexed_count = None
    active_method = 'normal'
    indexed_sorted_by = None

    if query:
        normal_qs = _normal_search_queryset(query)

        normal_count, normal_count_ms = _time_call(normal_qs.count)
        normal_results, normal_fetch_ms = _time_call(
            lambda: list(normal_qs[:SEARCH_PREVIEW_SIZE])
        )
        articles = normal_results

        if connection.vendor == 'postgresql':
            indexed_qs = _indexed_search_queryset(query, indexed_sort=indexed_sort)

            indexed_count, indexed_count_ms = _time_call(indexed_qs.count)
            indexed_results, indexed_fetch_ms = _time_call(
                lambda: list(indexed_qs[:SEARCH_PREVIEW_SIZE])
            )
            articles = indexed_results
            active_method = 'indexed'
            indexed_sorted_by = indexed_sort

    return render(request, 'blog/article_search.html', {
        'articles': articles,
        'query': query,
        'normal_count_ms': normal_count_ms,
        'normal_fetch_ms': normal_fetch_ms,
        'indexed_count_ms': indexed_count_ms,
        'indexed_fetch_ms': indexed_fetch_ms,
        'normal_count': normal_count,
        'indexed_count': indexed_count,
        'active_method': active_method,
        'indexed_sorted_by': indexed_sorted_by,
        'indexed_sort': indexed_sort,
        'preview_size': SEARCH_PREVIEW_SIZE,
    })


def search_explain_debug(request):
    if not settings.DEBUG:
        raise Http404("Debug endpoint is disabled.")

    query = request.GET.get('q', '').strip()
    indexed_sort = request.GET.get('indexed_sort', 'relevance')
    if indexed_sort not in {'relevance', 'newest'}:
        indexed_sort = 'relevance'

    normal_plan = None
    indexed_plan = None

    if query:
        normal_plan = _normal_search_queryset(query).explain()
        if connection.vendor == 'postgresql':
            indexed_plan = _indexed_search_queryset(
                query,
                indexed_sort=indexed_sort,
            ).explain()

    return render(request, 'blog/search_explain_debug.html', {
        'query': query,
        'indexed_sort': indexed_sort,
        'normal_plan': normal_plan,
        'indexed_plan': indexed_plan,
        'is_postgresql': connection.vendor == 'postgresql',
    })

