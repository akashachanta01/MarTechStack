"""Server-side PostHog tracking.

The browser snippet misses visitors who block analytics scripts (common with
Marketing Ops / developer audiences) or never run JavaScript. This sends the
same key facts straight from the server: one `server_pageview` per real HTML
page view plus a few conversion events. Events go through a small background
queue, so a slow or unreachable PostHog never slows a page down.
"""
import hashlib
import logging
import queue
import re
import sys
import threading
from datetime import datetime, timezone

from django.conf import settings

log = logging.getLogger(__name__)

BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|archiver|facebookexternalhit|embedly|preview|monitor|"
    r"curl|wget|python|httpx|go-http|java/|okhttp|headless|lighthouse|pagespeed|uptime|scrapy|axios|node-fetch",
    re.I,
)
SKIP_PREFIXES = ("/admin", "/static", "/media", "/staff", "/tools/api", "/api/", "/accounts/api",
                 "/favicon", "/robots.txt", "/sitemap", "/llms.txt", "/health")
UTM_KEYS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content")

_q = queue.Queue(maxsize=2000)
_worker = None
_lock = threading.Lock()


def enabled():
    if not getattr(settings, "POSTHOG_KEY", ""):
        return False
    if getattr(settings, "SERVER_ANALYTICS_DISABLED", False):
        return False
    return "test" not in sys.argv


def client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")) or ""


def is_bot(request):
    ua = request.META.get("HTTP_USER_AGENT", "")
    return not ua or bool(BOT_RE.search(ua))


# Order matters: first match wins. (name shown on dashboards, pattern)
AI_ASSISTANTS = [  # an AI fetching the page right now because a person asked it something
    ("ChatGPT", r"ChatGPT-User"), ("Claude", r"Claude-User"), ("Perplexity", r"Perplexity-User"),
    ("Mistral", r"MistralAI-User"), ("DuckDuckGo AI", r"DuckAssistBot"), ("Gemini", r"Google-Agent|Gemini"),
    ("Meta AI", r"meta-externalfetcher"),
]
AI_CRAWLERS = [  # AI companies collecting pages to train models or power AI search
    ("OpenAI (GPTBot)", r"GPTBot"), ("OpenAI search", r"OAI-SearchBot"),
    ("Anthropic (ClaudeBot)", r"ClaudeBot|Claude-SearchBot|anthropic-ai"),
    ("Perplexity", r"PerplexityBot"), ("Google AI (Gemini)", r"Google-Extended|GoogleOther"),
    ("ByteDance", r"Bytespider"), ("Common Crawl", r"CCBot"), ("Amazon", r"Amazonbot"),
    ("Meta AI", r"meta-externalagent|FacebookBot"), ("Cohere", r"cohere-ai"), ("You.com", r"YouBot"),
    ("Diffbot", r"Diffbot"), ("Timpi", r"Timpibot"), ("ImageSift", r"ImagesiftBot"),
]
SEARCH_ENGINES = [
    ("Google", r"Googlebot|Google-InspectionTool|Storebot-Google|AdsBot-Google"), ("Bing", r"bingbot|BingPreview"),
    ("Apple", r"Applebot"), ("DuckDuckGo", r"DuckDuckBot"), ("Yandex", r"YandexBot"), ("Baidu", r"Baiduspider"),
    ("Yahoo", r"Slurp"), ("Seznam", r"SeznamBot"), ("Naver", r"Yeti"),
]
_COMPILED_GROUPS = [(kind, [(name, re.compile(rx, re.I)) for name, rx in group]) for kind, group in (
    ("ai_assistant", AI_ASSISTANTS), ("ai_crawler", AI_CRAWLERS), ("search_engine", SEARCH_ENGINES))]
_MODERN_BROWSER = re.compile(r"Chrome/|Firefox/|Safari/|Edg/", re.I)


def classify(request):
    """(visitor_type, agent) for a page request. visitor_type is one of:
    person, ai_assistant, ai_crawler, search_engine, other_bot, suspected_bot.
    Self-identified agents are matched by name; 'suspected_bot' is a client that
    claims to be a modern browser but omits headers every modern browser sends
    (Sec-Fetch-Mode, Accept-Language) — typical of scrapers faking a browser."""
    ua = request.META.get("HTTP_USER_AGENT", "")
    for kind, group in _COMPILED_GROUPS:
        for name, rx in group:
            if rx.search(ua):
                return kind, name
    if not ua or BOT_RE.search(ua):
        return "other_bot", (ua.split("/")[0][:40] or "No user agent")
    # Chrome/Edge/Firefox always send Sec-Fetch-Mode (older Safari doesn't), and
    # every real browser sends Accept-Language.
    needs_sec_fetch = bool(re.search(r"Chrome/|Firefox/", ua))
    if _MODERN_BROWSER.search(ua) and (not request.META.get("HTTP_ACCEPT_LANGUAGE")
                                       or (needs_sec_fetch and not request.META.get("HTTP_SEC_FETCH_MODE"))):
        return "suspected_bot", "Fake browser (missing browser headers)"
    return "person", ""


def distinct_id_for(request):
    """Same id as the browser when possible, so server and browser events join up:
    signed-in user id, else the PostHog cookie's id, else a daily anonymous hash."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return str(user.id), True
    key = getattr(settings, "POSTHOG_KEY", "")
    raw = request.COOKIES.get("ph_%s_posthog" % key, "")
    if raw:
        try:
            import json
            from urllib.parse import unquote
            did = json.loads(unquote(raw)).get("distinct_id")
            if did:
                return str(did), False
        except Exception:
            pass
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = "%s|%s|%s" % (client_ip(request), request.META.get("HTTP_USER_AGENT", ""), day)
    return "srv_" + hashlib.sha256(seed.encode()).hexdigest()[:24], False


def base_props(request):
    props = {
        "$current_url": request.build_absolute_uri(),
        "$pathname": request.path,
        "$host": request.get_host(),
        "$referrer": request.META.get("HTTP_REFERER", ""),
        "$ip": client_ip(request),
        "$raw_user_agent": request.META.get("HTTP_USER_AGENT", "")[:400],
        "$lib": "martechjobs-server",
        "source": "server",
    }
    match = getattr(request, "resolver_match", None)
    if match and match.url_name:
        props["page_type"] = match.url_name
    for k in UTM_KEYS:
        if request.GET.get(k):
            props[k] = request.GET[k][:200]
    return props


def capture(event, request=None, properties=None, distinct_id=None):
    """Queue one event. Never raises; drops events if disabled or the queue is full."""
    try:
        if not enabled():
            return
        props = {}
        identified = False
        if request is not None:
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated and user.is_staff:
                return  # founder/staff traffic stays out of the numbers (same as the browser snippet)
            props.update(base_props(request))
            did, identified = distinct_id_for(request)
            distinct_id = distinct_id or did
        props.update(properties or {})
        if not identified:
            props["$process_person_profile"] = False
        _q.put_nowait({
            "event": event,
            "distinct_id": distinct_id or "server",
            "properties": props,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        _ensure_worker()
    except queue.Full:
        pass
    except Exception:
        log.debug("server analytics capture failed", exc_info=True)


def _ensure_worker():
    global _worker
    if _worker is not None and _worker.is_alive():
        return
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_run, name="posthog-server", daemon=True)
            _worker.start()


def _run():
    while True:
        item = _q.get()
        batch = [item]
        while len(batch) < 50:
            try:
                batch.append(_q.get_nowait())
            except queue.Empty:
                break
        _send(batch)


def _send(batch):
    import requests
    host = getattr(settings, "POSTHOG_SERVER_HOST", "") or "https://us.i.posthog.com"
    try:
        requests.post(host.rstrip("/") + "/batch/",
                      json={"api_key": settings.POSTHOG_KEY, "batch": batch}, timeout=5)
    except Exception:
        log.debug("server analytics send failed", exc_info=True)


class ServerPageviewMiddleware:
    """One `server_pageview` per HTML page served (not assets, APIs or staff), labelled
    with visitor_type so people, AI assistants, AI crawlers, search engines and
    scrapers can be counted separately instead of being thrown away."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if (request.method == "GET" and response.status_code == 200
                    and "text/html" in response.get("Content-Type", "")
                    and not request.path.startswith(SKIP_PREFIXES)):
                kind, agent = classify(request)
                if kind == "person":
                    capture("server_pageview", request, {"visitor_type": kind})
                else:
                    # One shared id per agent; never creates person profiles.
                    capture("server_pageview", request, {"visitor_type": kind, "agent": agent},
                            distinct_id="agent:%s:%s" % (kind, agent))
            elif (request.method == "POST" and response.status_code == 200
                    and request.path.rstrip("/") == "/tools/api/ats-match"):
                capture("server_resume_check", request)
        except Exception:
            log.debug("server pageview failed", exc_info=True)
        return response
