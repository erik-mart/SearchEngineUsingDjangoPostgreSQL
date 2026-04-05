from django.db import migrations


def create_tsvector_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute(
        """
        CREATE INDEX IF NOT EXISTS blog_article_search_vector_gin_idx
        ON blog_article
        USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')))
        """
    )


def drop_tsvector_gin_index(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    schema_editor.execute(
        "DROP INDEX IF EXISTS blog_article_search_vector_gin_idx"
    )


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_tsvector_gin_index, drop_tsvector_gin_index),
    ]

