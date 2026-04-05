import bleach
import markdown as markdown_lib

from django import template
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.text import Truncator

register = template.Library()

ALLOWED_TAGS = set(bleach.sanitizer.ALLOWED_TAGS).union(
	{
		"p",
		"br",
		"hr",
		"h1",
		"h2",
		"h3",
		"h4",
		"h5",
		"h6",
		"pre",
		"code",
		"blockquote",
		"ul",
		"ol",
		"li",
		"strong",
		"em",
		"a",
		"table",
		"thead",
		"tbody",
		"tr",
		"th",
		"td",
	}
)

ALLOWED_ATTRIBUTES = {
	**bleach.sanitizer.ALLOWED_ATTRIBUTES,
	"a": ["href", "title", "rel"],
}


def render_markdown(value):
	source = value or ""
	rendered = markdown_lib.markdown(
		source,
		extensions=["extra", "sane_lists", "nl2br"],
	)
	cleaned = bleach.clean(
		rendered,
		tags=ALLOWED_TAGS,
		attributes=ALLOWED_ATTRIBUTES,
		strip=True,
	)
	return bleach.linkify(cleaned)


@register.filter(name="markdownify")
def markdownify(value):
	return mark_safe(render_markdown(value))


@register.filter(name="markdown_preview")
def markdown_preview(value, word_count=50):
	try:
		word_count = int(word_count)
	except (TypeError, ValueError):
		word_count = 50

	text = strip_tags(render_markdown(value))
	normalized_text = " ".join(text.split())
	return Truncator(normalized_text).words(word_count, truncate=" …")

