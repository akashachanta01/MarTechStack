import re

from django.core.management.base import BaseCommand

from jobs.models import BlogPost


# ---------------------------------------------------------------------------
# Normalize existing BlogPost rows so old AI-generated posts and new
# hand-authored posts are visually consistent on the blog.
#
# Idempotent: each post is only saved when a field actually changes, so a
# second run in a row reports "0 changed". Safe to run on every deploy.
# ---------------------------------------------------------------------------

CANONICAL_AUTHOR = "MarTechJobs Team"

CANONICAL_CATEGORIES = {
    "Tech Stacks",
    "Career Advice",
    "Salary Guides",
    "Industry News",
}

WORDS_PER_MINUTE = 225
EXCERPT_MAX = 160
META_DESCRIPTION_MAX = 160
META_TITLE_MAX = 60

TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(html):
    """Replace HTML tags with spaces and collapse whitespace."""
    text = TAG_RE.sub(" ", html or "")
    return " ".join(text.split())


def compute_read_time(content):
    words = len(strip_tags(content).split())
    minutes = max(1, round(words / WORDS_PER_MINUTE))
    return f"{minutes} min read"


def canonicalize_category(category, title):
    if category in CANONICAL_CATEGORIES:
        return category
    haystack = f"{category or ''} {title or ''}".lower()

    def has(*needles):
        return any(n in haystack for n in needles)

    if has("salary", "pay", "compensation"):
        return "Salary Guides"
    if has("stack", "tool", "platform", "technology", "automation", "integration"):
        return "Tech Stacks"
    if has("news", "trend", "future", "report", "industry"):
        return "Industry News"
    return "Career Advice"


def derive_excerpt(content):
    text = strip_tags(content)
    if not text:
        return ""
    if len(text) <= EXCERPT_MAX:
        return text
    snippet = text[:EXCERPT_MAX]
    # Trim back to a word boundary.
    if " " in snippet:
        snippet = snippet[: snippet.rfind(" ")]
    return f"{snippet.rstrip()}..."


class Command(BaseCommand):
    help = (
        "Normalize existing BlogPost rows (author, category, read_time, "
        "excerpt, meta fields) for visual consistency. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without saving anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write("Running normalize_blog_posts in DRY-RUN mode (no writes).")

        total = 0
        changed_posts = 0
        author_changed = 0
        read_time_changed = 0
        excerpt_filled = 0
        meta_description_filled = 0
        meta_title_filled = 0
        category_remaps = {}  # "from -> to" -> count

        for post in BlogPost.objects.all().iterator():
            total += 1
            try:
                changed = False

                # 1. Author unification.
                if post.author and "AI" in post.author and post.author != CANONICAL_AUTHOR:
                    post.author = CANONICAL_AUTHOR
                    author_changed += 1
                    changed = True

                # 2. Category canonicalization.
                new_category = canonicalize_category(post.category, post.title)
                if new_category != post.category:
                    key = f"{post.category or '(blank)'} -> {new_category}"
                    category_remaps[key] = category_remaps.get(key, 0) + 1
                    post.category = new_category
                    changed = True

                # 3. read_time normalization.
                new_read_time = compute_read_time(post.content)
                if new_read_time != post.read_time:
                    post.read_time = new_read_time
                    read_time_changed += 1
                    changed = True

                # 4. excerpt safety.
                if not (post.excerpt or "").strip():
                    derived = derive_excerpt(post.content)
                    if derived:
                        post.excerpt = derived
                        excerpt_filled += 1
                        changed = True

                # 5. meta_description safety.
                if not (post.meta_description or "").strip():
                    if (post.excerpt or "").strip():
                        post.meta_description = post.excerpt[:META_DESCRIPTION_MAX]
                        meta_description_filled += 1
                        changed = True

                # 6. meta_title safety.
                if not (post.meta_title or "").strip():
                    if (post.title or "").strip():
                        post.meta_title = post.title[:META_TITLE_MAX]
                        meta_title_filled += 1
                        changed = True

                if changed:
                    changed_posts += 1
                    if not dry_run:
                        post.save()

            except Exception as exc:  # noqa: BLE001 - one bad row must not abort the run.
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipped post id={getattr(post, 'pk', '?')} "
                        f"('{getattr(post, 'slug', '?')}') due to error: {exc}"
                    )
                )
                continue

        # ---- Summary ----------------------------------------------------
        verb = "would change" if dry_run else "changed"
        self.stdout.write("")
        self.stdout.write("Blog post normalization summary:")
        self.stdout.write(f"  Author {verb}:           {author_changed}")
        self.stdout.write(f"  Category remapped:       {sum(category_remaps.values())}")
        for key in sorted(category_remaps):
            self.stdout.write(f"      {key}: {category_remaps[key]}")
        self.stdout.write(f"  read_time {verb}:        {read_time_changed}")
        self.stdout.write(f"  Excerpt filled:          {excerpt_filled}")
        self.stdout.write(f"  meta_description filled:  {meta_description_filled}")
        self.stdout.write(f"  meta_title filled:        {meta_title_filled}")
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Normalized {changed_posts} of {total} posts.")
        )
