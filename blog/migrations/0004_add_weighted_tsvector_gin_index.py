from django.db import migrations


def create_weighted_tsvector_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute(
        """
        CREATE INDEX IF NOT EXISTS blog_article_weighted_search_vector_gin_idx
        ON blog_article
        USING GIN (
            (
                setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(content, '')), 'B')
            )
        )
        """
    )


def drop_weighted_tsvector_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute(
        "DROP INDEX IF EXISTS blog_article_weighted_search_vector_gin_idx"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0003_article_unique_title_content'),
    ]

    operations = [
        migrations.RunPython(
            create_weighted_tsvector_gin_index,
            drop_weighted_tsvector_gin_index,
        ),
    ]

