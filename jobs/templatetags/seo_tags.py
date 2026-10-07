import re

from django import template

register = template.Library()
SUFFIX = " | MarTechJobs"


def _cut(text, limit):
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit - 1].rsplit(" ", 1)[0]
    prev = None
    while prev != cut:  # never leave half an &entity; or trailing punctuation
        prev = cut
        cut = re.sub(r"&[#\w]*;?$", "", cut).rstrip(" ,;:—-–|·")
    return cut + "…"


@register.filter(is_safe=True)
def seo_title(value, limit=65):
    """Google shows ~60-65 characters: drop the brand suffix first, then cut at a word."""
    text = re.sub(r"\s+", " ", str(value)).strip()
    if len(text) > limit and text.endswith(SUFFIX):
        text = text[: -len(SUFFIX)]
    return _cut(text, limit)


@register.filter(is_safe=True)
def seo_desc(value, limit=158):
    """Meta descriptions are cut by Google after ~155-160 characters; end on a whole word."""
    return _cut(str(value), limit)


def _visible_len(text):
    return len(re.sub(r"&[#\w]+;", "x", text))
