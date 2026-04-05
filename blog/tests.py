import json
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.db import IntegrityError
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse

from blog.models import Article


class ImportArticlesCommandTests(TestCase):
	def test_imports_articles_from_nested_json_files(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			temp_path = Path(temp_dir)
			nested_dir = temp_path / "nested"
			nested_dir.mkdir()

			(temp_path / "single.json").write_text(
				json.dumps({"title": "First Article", "content": "First body."}),
				encoding="utf-8",
			)
			(nested_dir / "many.json").write_text(
				json.dumps(
					{
						"items": [
							{"title": "Second Article", "content": "Second body."},
							{
								"meta": {
									"title": "Third Article",
									"content": "Third body.",
								}
							},
						]
					}
				),
				encoding="utf-8",
			)

			stdout = StringIO()
			call_command("import_articles", str(temp_path), stdout=stdout)

		self.assertEqual(Article.objects.count(), 3)
		self.assertQuerySetEqual(
			Article.objects.order_by("title").values_list("title", flat=True),
			["First Article", "Second Article", "Third Article"],
			transform=lambda value: value,
		)
		output = stdout.getvalue()
		self.assertIn("Files scanned: 2", output)
		self.assertIn("Articles imported: 3", output)
		self.assertIn("Files with errors: 0", output)

	def test_dry_run_reports_articles_without_creating_records(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			temp_path = Path(temp_dir)
			(temp_path / "article.json").write_text(
				json.dumps({"title": "Preview Only", "content": "Not saved."}),
				encoding="utf-8",
			)

			stdout = StringIO()
			call_command("import_articles", str(temp_path), "--dry-run", stdout=stdout)

		self.assertEqual(Article.objects.count(), 0)
		output = stdout.getvalue()
		self.assertIn("[dry-run] Would import article 'Preview Only'", output)
		self.assertIn("Articles imported: 1", output)

	def test_skips_blank_objects_and_reports_invalid_json(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			temp_path = Path(temp_dir)
			(temp_path / "blank.json").write_text(
				json.dumps({"title": "   ", "content": "Valid but blank title check."}),
				encoding="utf-8",
			)
			(temp_path / "invalid.json").write_text("{not valid json", encoding="utf-8")
			(temp_path / "no_article.json").write_text(
				json.dumps({"name": "Missing expected keys"}),
				encoding="utf-8",
			)

			stdout = StringIO()
			call_command("import_articles", str(temp_path), stdout=stdout)

		self.assertEqual(Article.objects.count(), 0)
		output = stdout.getvalue()
		self.assertIn("Skipped object with blank title/content", output)
		self.assertIn("Invalid JSON in", output)
		self.assertIn("No importable article objects found", output)
		self.assertIn("Objects skipped: 1", output)
		self.assertIn("Duplicates skipped: 0", output)
		self.assertIn("Files with errors: 1", output)

	def test_skips_duplicate_articles_on_reimport(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			temp_path = Path(temp_dir)
			(temp_path / "article.json").write_text(
				json.dumps({"title": "Unique Article", "content": "Same content."}),
				encoding="utf-8",
			)

			first_stdout = StringIO()
			second_stdout = StringIO()
			call_command("import_articles", str(temp_path), stdout=first_stdout)
			call_command("import_articles", str(temp_path), stdout=second_stdout)

		self.assertEqual(Article.objects.count(), 1)
		self.assertIn("Articles imported: 1", first_stdout.getvalue())
		self.assertIn("Duplicates skipped: 0", first_stdout.getvalue())
		self.assertIn("Articles imported: 0", second_stdout.getvalue())
		self.assertIn("Duplicates skipped: 1", second_stdout.getvalue())


class MarkdownRenderingTests(TestCase):
	def test_article_detail_renders_markdown_as_html(self):
		article = Article.objects.create(
			title="Markdown Detail",
			content="# Heading\n\nThis is **bold** and [a link](https://example.com).\n\n<script>alert('xss')</script>",
		)

		response = self.client.get(reverse("blog:article_detail", args=[article.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "<h1>Heading</h1>", html=True)
		self.assertContains(response, "<strong>bold</strong>", html=True)
		self.assertContains(response, '<a href="https://example.com" rel="nofollow">a link</a>', html=True)
		self.assertNotContains(response, "<script>", html=True)
		self.assertNotContains(response, "**bold**")

	def test_article_list_preview_strips_markdown_syntax(self):
		Article.objects.create(
			title="Markdown Preview",
			content="# Intro\n\nThis preview has **bold** text and [a link](https://example.com).",
		)

		response = self.client.get(reverse("blog:article_list"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Intro This preview has bold text and a link.")
		self.assertNotContains(response, "**bold**")
		self.assertNotContains(response, "[a link](https://example.com)")

	def test_article_search_preview_uses_markdown_aware_text(self):
		Article.objects.create(
			title="Markdown Search",
			content="Paragraph with `inline code` and *emphasis* for searching.",
		)

		response = self.client.get(reverse("blog:article_search"), {"q": "searching"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Paragraph with inline code and emphasis for searching.")
		self.assertNotContains(response, "`inline code`")
		self.assertNotContains(response, "*emphasis*")


class ArticleListPaginationTests(TestCase):
	def setUp(self):
		for i in range(25):
			Article.objects.create(
				title=f"Article {i}",
				content=f"Content for article {i}.",
			)

	def test_article_list_first_page_is_paginated(self):
		response = self.client.get(reverse("blog:article_list"))

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.context["is_paginated"])
		self.assertEqual(response.context["page_obj"].number, 1)
		self.assertEqual(len(response.context["articles"]), 10)
		self.assertContains(response, "Page 1 of 3")

	def test_article_list_second_page_has_remaining_items(self):
		response = self.client.get(reverse("blog:article_list"), {"page": 2})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["page_obj"].number, 2)
		self.assertEqual(len(response.context["articles"]), 10)
		self.assertContains(response, "Page 2 of 3")

	def test_invalid_page_falls_back_to_first_page(self):
		response = self.client.get(reverse("blog:article_list"), {"page": "invalid"})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["page_obj"].number, 1)

	def test_out_of_range_page_returns_last_page(self):
		response = self.client.get(reverse("blog:article_list"), {"page": 99})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["page_obj"].number, 3)
		self.assertEqual(len(response.context["articles"]), 5)


class ArticleConstraintTests(TestCase):
	def test_article_title_content_is_unique(self):
		Article.objects.create(title="Duplicate", content="Same content")

		with self.assertRaises(IntegrityError):
			Article.objects.create(title="Duplicate", content="Same content")


class SearchTimingTests(TestCase):
	def test_article_search_shows_result_count_and_duration(self):
		Article.objects.create(
			title="Athletics Notes",
			content="Training and athletics schedule.",
		)

		response = self.client.get(reverse("blog:article_search"), {"q": "athletics"})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Results for:</strong> "athletics"', html=False)
		self.assertContains(response, "Normal query")
		self.assertContains(response, "icontains")
		self.assertContains(response, "fetch")
		self.assertContains(response, "ms")
		self.assertIsNotNone(response.context["normal_count_ms"])
		self.assertGreaterEqual(response.context["normal_count_ms"], 0)
		self.assertIsNotNone(response.context["normal_fetch_ms"])
		self.assertGreaterEqual(response.context["normal_fetch_ms"], 0)
		self.assertEqual(response.context["normal_count"], 1)
		self.assertEqual(response.context["preview_size"], 20)
		self.assertContains(response, "View EXPLAIN plans for this search")

	def test_postgres_indexed_results_are_sorted_by_relevance(self):
		if connection.vendor != "postgresql":
			self.skipTest("Relevance ranking applies to PostgreSQL full-text search only.")

		high_relevance = Article.objects.create(
			title="Athletics Performance Guide",
			content="General training notes.",
		)
		Article.objects.create(
			title="General Sports Update",
			content="This article briefly mentions athletics once.",
		)

		response = self.client.get(reverse("blog:article_search"), {"q": "athletics"})

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["active_method"], "indexed")
		self.assertEqual(response.context["indexed_sorted_by"], "relevance")
		self.assertGreater(response.context["indexed_count"], 0)
		self.assertEqual(response.context["articles"][0].id, high_relevance.id)

	def test_postgres_indexed_results_can_be_sorted_by_newest(self):
		if connection.vendor != "postgresql":
			self.skipTest("Indexed sorting modes apply to PostgreSQL full-text search only.")

		relevance_top = Article.objects.create(
			title="Athletics Master Guide",
			content="Deep athletics athletics athletics analysis.",
		)
		newest = Article.objects.create(
			title="Recent sports note",
			content="Contains athletics once.",
		)

		response = self.client.get(
			reverse("blog:article_search"),
			{"q": "athletics", "indexed_sort": "newest"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["active_method"], "indexed")
		self.assertEqual(response.context["indexed_sorted_by"], "newest")
		self.assertEqual(response.context["indexed_sort"], "newest")
		self.assertGreater(response.context["indexed_count"], 0)
		self.assertEqual(response.context["articles"][0].id, newest.id)
		self.assertNotEqual(response.context["articles"][0].id, relevance_top.id)

	def test_invalid_indexed_sort_falls_back_to_relevance(self):
		Article.objects.create(
			title="Athletics Notes",
			content="Contains athletics term.",
		)

		response = self.client.get(
			reverse("blog:article_search"),
			{"q": "athletics", "indexed_sort": "invalid"},
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context["indexed_sort"], "relevance")


class SearchExplainDebugTests(TestCase):
	def test_public_can_view_explain_page_in_debug(self):
		with override_settings(DEBUG=True):
			response = self.client.get(
				reverse("blog:search_explain_debug"),
				{"q": "athletics", "indexed_sort": "newest"},
			)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Search EXPLAIN Debug")
		self.assertContains(response, "Normal Query Plan")
		self.assertIsNotNone(response.context["normal_plan"])

	def test_explain_page_returns_404_when_debug_is_false(self):
		with override_settings(DEBUG=False):
			response = self.client.get(
				reverse("blog:search_explain_debug"),
				{"q": "athletics"},
			)

		self.assertEqual(response.status_code, 404)


