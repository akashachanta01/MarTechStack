"""Display-time cleanup for employer job descriptions.

Descriptions arrive from each ATS with their own formatting habits. Measured on
live jobs (Oct 2026): 75% fake section headings with a bold paragraph, 78% pad
with empty spacer paragraphs, 18% show LinkedIn tracking tags ("#LI-EMEA") and
a few are plain text with no HTML at all. This normalises them for reading on
the job page only: the stored text, the JobPosting JSON-LD and the resume
matcher all keep using the original description.

Every description heading becomes an <h2 class="jd-h">, the level right under
the page's <h1> (the job title). Pure regex, no parsing: runs in well under a
millisecond on the longest live description (24k chars).
"""
import html
import re

# A heading-like label: short, no tags inside, not a sentence.
_LABEL = r"[^<>]{2,90}?"

_LI_TAG_RE = re.compile(r"#LI-[A-Za-z0-9]+\b")
# <p></p>, <p>&nbsp;</p>, <p><br></p>, <p><span> </span></p> ...
_EMPTY_P_RE = re.compile(
    r"<p[^>]*>(?:\s|&nbsp;|&#160;| |<br\s*/?>|<span[^>]*>(?:\s|&nbsp;| )*</span>)*</p>",
    re.I,
)
# <p><strong>About the role</strong></p>  (optionally with a stray <br> or colon)
_BOLD_P_RE = re.compile(
    r"<p[^>]*>\s*<(strong|b)>\s*(" + _LABEL + r")\s*(?:<br\s*/?>)?\s*</\1>\s*(?:<br\s*/?>\s*)*</p>",
    re.I,
)
# <p><b>Position Summary</b><br>text...</p>: heading, then the rest stays a paragraph.
_BOLD_BR_P_RE = re.compile(
    r"<p([^>]*)>\s*<(strong|b)>\s*(" + _LABEL + r")\s*</\2>\s*<br\s*/?>", re.I
)
# Inside lists etc.: "...<br><br><b>Required Qualifications</b><br>...". The breaks
# before the label are trimmed in code: a regex "(<br>)+" prefix rescans every run
# of breaks from each position (17s on a 20k-<br> feed in testing).
_BOLD_BR_INLINE_RE = re.compile(
    r"<(strong|b)>\s*(" + _LABEL + r")\s*</\1>\s*<br\s*/?>", re.I
)
_TRAILING_BR_RE = re.compile(r"(?:<br\s*/?>\s*)+$", re.I)
# Existing headings of any level (often wrapping a <strong>). The body is capped at
# 400 chars and can't cross another heading tag, so an unclosed <h2> can't make it
# rescan the rest of the text (12s on a 20k-<h2> feed before the cap).
_HEADING_RE = re.compile(r"<h([1-6])[^>]*>((?:(?!</?h[1-6]).){0,400}?)</h\1>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")


def _label_ok(text):
    t = text.strip()
    # Sentences ("We value diversity.") stay bold text, not headings.
    return 2 <= len(t) <= 90 and not t.endswith((".", ",", ";"))


def _plain_to_html(text):
    """Plain text with blank lines and "- " bullets -> paragraphs, lists, headings."""
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        # A short first line followed by more lines is a section label ("What you will do").
        if len(lines) > 1 and _label_ok(lines[0]) and len(lines[0]) <= 60 and not lines[0][:1] in "-•*":
            out.append('<h2 class="jd-h">%s</h2>' % html.escape(lines[0]))
            lines = lines[1:]
        items, para = [], []
        for l in lines:
            m = re.match(r"^[-•*·]\s+(.*)", l)
            if m:
                if para:
                    out.append("<p>%s</p>" % "<br>".join(para))
                    para = []
                items.append("<li>%s</li>" % html.escape(m.group(1)))
            else:
                if items:
                    out.append("<ul>%s</ul>" % "".join(items))
                    items = []
                para.append(html.escape(l))
        if items:
            out.append("<ul>%s</ul>" % "".join(items))
        if para:
            out.append("<p>%s</p>" % "<br>".join(para))
    return "\n".join(out)


def tidy_description(text):
    if not text:
        return text
    if not re.search(r"<[a-zA-Z/!]", text):
        return _plain_to_html(text)

    def heading(m):
        inner = _TAG_RE.sub("", m.group(2)).strip()
        if not inner:
            return ""
        return '<h2 class="jd-h">%s</h2>' % inner

    def bold_p(m):
        label = m.group(2)
        if not _label_ok(label):
            return m.group(0)
        return '<h2 class="jd-h">%s</h2>' % label.strip()

    def bold_br_p(m):
        label = m.group(3)
        if not _label_ok(label):
            return m.group(0)
        return '<h2 class="jd-h">%s</h2><p%s>' % (label.strip(), m.group(1))

    def inline_labels(t):
        # Can't put a real heading inside a list item: a block-level label instead,
        # only where the label sits on its own line (a <br> before and after).
        out, pos = [], 0
        for m in _BOLD_BR_INLINE_RE.finditer(t):
            before = t[pos:m.start()]
            tail = before[-200:]
            trimmed = _TRAILING_BR_RE.sub("", tail.rstrip())
            if trimmed == tail.rstrip() or not _label_ok(m.group(2)):
                out.append(before + m.group(0))
            else:
                out.append(before[:len(before) - len(tail)] + trimmed)
                out.append('<strong class="jd-h jd-h-inline">%s</strong>' % m.group(2).strip())
            pos = m.end()
        out.append(t[pos:])
        return "".join(out)

    t = _LI_TAG_RE.sub("", text)
    t = _HEADING_RE.sub(heading, t)
    t = _BOLD_P_RE.sub(bold_p, t)
    t = _BOLD_BR_P_RE.sub(bold_br_p, t)
    t = inline_labels(t)
    t = _EMPTY_P_RE.sub("", t)
    return t
