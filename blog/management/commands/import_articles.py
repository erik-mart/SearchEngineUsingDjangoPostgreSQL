import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from blog.models import Article


class Command(BaseCommand):
    help = "Import Article records from JSON files in a directory."

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            type=str,
            help="Directory to scan recursively for .json files.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview imports without creating Article records.",
        )

    def handle(self, *args, **options):
        directory = Path(options["directory"]).expanduser().resolve()
        dry_run = options["dry_run"]

        if not directory.is_dir():
            raise CommandError(f"Directory does not exist or is not a directory: {directory}")

        json_files = sorted(path for path in directory.rglob("*.json") if path.is_file())

        if not json_files:
            self.stdout.write(self.style.WARNING(f"No JSON files found in {directory}"))
            return

        files_scanned = 0
        imported_count = 0
        skipped_count = 0
        duplicate_count = 0
        error_count = 0

        for json_file in json_files:
            files_scanned += 1
            try:
                with json_file.open("r", encoding="utf-8") as file_handle:
                    payload = json.load(file_handle)
            except json.JSONDecodeError as exc:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Invalid JSON in {json_file}: {exc}")
                )
                continue
            except OSError as exc:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(f"Could not read {json_file}: {exc}")
                )
                continue

            matches = list(self._find_article_objects(payload))
            if not matches:
                self.stdout.write(
                    self.style.WARNING(f"No importable article objects found in {json_file}")
                )
                continue

            for article_data in matches:
                title = article_data["title"].strip()
                content = article_data["content"].strip()

                if not title or not content:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipped object with blank title/content in {json_file}"
                        )
                    )
                    continue

                if dry_run:
                    if Article.objects.filter(title=title, content=content).exists():
                        duplicate_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"[dry-run] Would skip duplicate article '{title}' from {json_file}"
                            )
                        )
                    else:
                        imported_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[dry-run] Would import article '{title}' from {json_file}"
                            )
                        )
                    continue

                _, created = Article.objects.get_or_create(title=title, content=content)
                if created:
                    imported_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Imported article '{title}' from {json_file}"
                        )
                    )
                else:
                    duplicate_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skipped duplicate article '{title}' from {json_file}"
                        )
                    )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Import complete."))
        self.stdout.write(f"Files scanned: {files_scanned}")
        self.stdout.write(f"Articles imported: {imported_count}")
        self.stdout.write(f"Objects skipped: {skipped_count}")
        self.stdout.write(f"Duplicates skipped: {duplicate_count}")
        self.stdout.write(f"Files with errors: {error_count}")

    def _find_article_objects(self, value):
        if isinstance(value, dict):
            title = value.get("title")
            content = value.get("content")
            if isinstance(title, str) and isinstance(content, str):
                yield {"title": title, "content": content}

            for nested_value in value.values():
                yield from self._find_article_objects(nested_value)

        elif isinstance(value, list):
            for item in value:
                yield from self._find_article_objects(item)

