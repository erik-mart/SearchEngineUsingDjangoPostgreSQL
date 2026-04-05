import hashlib

from django.db import migrations, models
from django.db.models import Count, Min


def populate_hash_and_deduplicate_articles(apps, schema_editor):
    Article = apps.get_model('blog', 'Article')

    for article in Article.objects.all().only('id', 'content').iterator():
        content = article.content or ''
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        Article.objects.filter(id=article.id).update(content_hash=content_hash)

    duplicates = (
        Article.objects.values('title', 'content_hash')
        .annotate(min_id=Min('id'), total=Count('id'))
        .filter(total__gt=1)
    )

    for item in duplicates.iterator():
        (
            Article.objects.filter(title=item['title'], content_hash=item['content_hash'])
            .exclude(id=item['min_id'])
            .delete()
        )


def noop_reverse(apps, schema_editor):
    # Deleted duplicates cannot be restored automatically.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0002_add_tsvector_gin_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='article',
            name='content_hash',
            field=models.CharField(db_index=True, default='', editable=False, max_length=32),
            preserve_default=False,
        ),
        migrations.RunPython(populate_hash_and_deduplicate_articles, noop_reverse),
        migrations.AddConstraint(
            model_name='article',
            constraint=models.UniqueConstraint(
                fields=('title', 'content_hash'),
                name='unique_article_title_content_hash',
            ),
        ),
    ]

