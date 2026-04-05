import hashlib

from django.db import models


class Article(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    content_hash = models.CharField(max_length=32, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.content_hash = hashlib.md5(self.content.encode('utf-8')).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'content_hash'],
                name='unique_article_title_content_hash',
            )
        ]
