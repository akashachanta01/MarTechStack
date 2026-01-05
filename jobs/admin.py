from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib import messages

# Import all models
from .models import Job, Tool, Category, Subscriber, BlockRule, UserSubmission, ActiveJob, BlogPost
from .emails import send_job_alert, send_digest_alert 

# --- 1. GLOBAL ACTIONS ---

@admin.action(description="🤖 Auto-Tag Tech Stack")
def auto_tag_tools(modeladmin, request, queryset):
    all_tools = list(Tool.objects.all())
    affected_jobs = 0
    for job in queryset:
        text = (job.description + " " + job.title).lower()
        added_count = 0
        for tool in all_tools:
            if tool in job.tools.all(): continue
            if tool.name.lower() in text:
                job.tools.add(tool)
                added_count += 1
        if added_count > 0: affected_jobs += 1
    modeladmin.message_user(request, f"✅ Scanned {queryset.count()} jobs. Updated Tech Stack for {affected_jobs} jobs.", messages.SUCCESS)

@admin.action(description="🗑️ DELETE ALL 'Rejected' Jobs")
def delete_all_rejected(modeladmin, request, queryset):
    count, _ = Job.objects.filter(screening_status='rejected').delete()
    modeladmin.message_user(request, f"🧹 Wiped {count} rejected jobs.", messages.WARNING)

# --- 2. HELPERS ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name",)}

# --- 3. BLOG POST ADMIN (NEW) ---
@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "published_at", "is_published")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "content")
    list_filter = ("is_published", "category")

# --- 4. JOB ADMINS ---

class BaseJobAdmin(admin.ModelAdmin):
    list_per_page = 50
    save_on_top = True
    list_display_links = ("job_card_header",) 
    search_fields = ("title", "company", "description", "tools__name")
    list_filter = ("screening_status", "work_arrangement", "created_at", ("tools", admin.EmptyFieldListFilter))
    fieldsets = (
        ("Key Info", {"fields": ("title", "company", "company_logo", "apply_url", "location")}),
        ("Job Details", {"fields": ("description", "role_type", "work_arrangement", "salary_range", "tools")}),
        ("Screening & AI", {"fields": ("screening_status", "screening_score", "screening_reason", "tags"), "classes": ("collapse",)}),
        ("Monetization", {"fields": ("is_pinned", "is_featured", "plan_name"), "classes": ("collapse",)}),
        ("System Data", {"fields": ("slug", "created_at", "updated_at", "screened_at", "screening_details"), "classes": ("collapse",)}),
    )
    readonly_fields = ("created_at", "updated_at", "screened_at", "screening_details")
    filter_horizontal = ("tools",)
    ordering = ("-created_at",)
    actions = [auto_tag_tools, delete_all_rejected, "send_digest", "mark_approved", "mark_rejected", "mark_pending", "activate_jobs", "deactivate_jobs"]

    def logo_preview(self, obj):
        if obj.company_logo: return format_html('<img src="{}" style="width:32px; height:32px; object-fit:contain; border-radius:4px; border:1px solid #ccc; background:white;" />', obj.company_logo)
        return "No Logo"
    logo_preview.short_description = "Img"

    def job_card_header(self, obj):
        return format_html('<div style="line-height:1.2;"><div style="font-weight:600; font-size:14px;">{}</div><div style="font-size:12px; opacity:0.7;">{}</div></div>', obj.title, obj.company)
    job_card_header.short_description = "Job Details"
    job_card_header.admin_order_field = "title" 

    def score_display(self, obj):
        val = float(obj.screening_score or 0.0)
        bg = "#d1fae5" if val >= 80 else "#fef3c7" if val >= 50 else "#fee2e2"
        text = "#065f46" if val >= 80 else "#92400e" if val >= 50 else "#b91c1c"
        return format_html('<span style="background:{}; color:{}; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:11px;">{}</span>', bg, text, "{:.0f}".format(val))
    score_display.short_description = "Score"
    score_display.admin_order_field = "screening_score"

    def tools_preview(self, obj):
        tools = obj.tools.all()
        if not tools: return format_html('<span style="opacity:0.5;">-</span>')
        return format_html("".join([f'<span style="display:inline-block; border:1px solid #ccc; background:rgba(128,128,128,0.1); padding:0 4px; border-radius:3px; font-size:10px; margin-right:2px; margin-bottom:2px;">{t.name}</span>' for t in tools]))
    tools_preview.short_description = "Stack"

    def source_link(self, obj):
        if obj.apply_url: return format_html('<a href="{}" target="_blank" style="color:#4f46e5; font-weight:bold; text-decoration:none;">Link ↗</a>', obj.apply_url)
        return "-"
    source_link.short_description = "Apply"

    def source_tag(self, obj):
        if not obj.tags: return "-"
        return obj.tags.replace("User Submission", "User").replace("AI Scraper", "AI")
    source_tag.short_description = "Source"

    def posted_date(self, obj): return obj.created_at.strftime("%b %d")
    posted_date.short_description = "Posted"
    posted_date.admin_order_field = "created_at"

    @admin.action(description="📨 Send DIGEST Email")
    def send_digest(self, request, qs):
        jobs = list(qs.order_by('-created_at'))
        if not jobs: return
        qs.update(screening_status="approved", is_active=True)
        send_digest_alert(jobs)
        self.message_user(request, f"✅ Sent DIGEST with {len(jobs)} jobs.", messages.SUCCESS)

    @admin.action(description="✅ Approve & Alert")
    def mark_approved(self, request, qs):
        if qs.count() > 3: self.message_user(request, f"⚠️ Too many jobs for single alerts.", messages.ERROR); return
        for job in qs:
            if job.screening_status != 'approved':
                job.screening_status = "approved"; job.is_active = True; job.save(); send_job_alert(job)
        self.message_user(request, f"✅ Approved {qs.count()} jobs.", messages.SUCCESS)

    @admin.action(description="❌ Reject")
    def mark_rejected(self, request, qs): qs.update(screening_status="rejected", is_active=False)
    @admin.action(description="⏳ Pending")
    def mark_pending(self, request, qs): qs.update(screening_status="pending", is_active=False)
    @admin.action(description="👁️ Visible")
    def activate_jobs(self, request, qs): qs.update(is_active=True)
    @admin.action(description="🚫 Hidden")
    def deactivate_jobs(self, request, qs): qs.update(is_active=False)

@admin.register(Job)
class JobAdmin(BaseJobAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=False).exclude(screening_status='rejected').exclude(screening_score__lte=0).prefetch_related('tools')
    list_display = ("logo_preview", "job_card_header", "location", "score_display", "source_tag", "tools_preview", "source_link", "posted_date", "screening_status")
    list_editable = ("screening_status",)

@admin.register(ActiveJob)
class ActiveJobAdmin(BaseJobAdmin):
    def get_queryset(self, request): return super().get_queryset(request).filter(is_active=True).prefetch_related('tools')
    list_display = ("logo_preview", "job_card_header", "location", "score_display", "is_pinned", "is_featured", "tools_preview", "posted_date", "view_live")
    list_editable = ("is_pinned", "is_featured")
    def view_live(self, obj):
        if obj.slug: return format_html('<a href="{}" target="_blank" style="color:#4f46e5; font-weight:bold;">View ↗</a>', f"/job/{obj.id}/{obj.slug}/")
        return "-"
    view_live.short_description = "Live Page"

@admin.register(UserSubmission)
class UserSubmissionAdmin(BaseJobAdmin):
    def get_queryset(self, request): return super().get_queryset(request).filter(tags__icontains="User Submission").prefetch_related('tools')
    list_display = ("logo_preview", "job_card_header", "location", "score_display", "screening_status", "posted_date")

@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin): list_display = ("email", "created_at")

@admin.register(BlockRule)
class BlockRuleAdmin(admin.ModelAdmin): list_display = ("rule_type", "value", "enabled")
