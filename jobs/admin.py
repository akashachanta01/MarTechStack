from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib import messages

# Import all models
from .models import Job, Tool, Category, Subscriber, BlockRule, UserSubmission, ActiveJob

# --- 1. GLOBAL ACTIONS ---

@admin.action(description="🤖 Auto-Tag Tech Stack")
def auto_tag_tools(modeladmin, request, queryset):
    """
    Scans the description of selected jobs and adds Tool tags 
    if the tool name appears in the text.
    """
    all_tools = list(Tool.objects.all())
    affected_jobs = 0
    
    for job in queryset:
        # Normalize text for matching
        text = (job.description + " " + job.title).lower()
        added_count = 0
        
        for tool in all_tools:
            # Check if tool is already added to avoid DB hits
            if tool in job.tools.all():
                continue
            
            # Simple check (match tool name in text)
            if tool.name.lower() in text:
                job.tools.add(tool)
                added_count += 1
        
        if added_count > 0:
            affected_jobs += 1
            
    modeladmin.message_user(request, f"✅ Scanned {queryset.count()} jobs. Updated Tech Stack for {affected_jobs} jobs.", messages.SUCCESS)

@admin.action(description="🗑️ DELETE ALL 'Rejected' Jobs")
def delete_all_rejected(modeladmin, request, queryset):
    """
    Nuclear option to clean up the database. 
    Ignores the selection and deletes ALL jobs marked as 'rejected'.
    """
    count, _ = Job.objects.filter(screening_status='rejected').delete()
    modeladmin.message_user(request, f"🧹 Wiped {count} rejected jobs.", messages.WARNING)

# --- 2. MODEL ADMINS ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name",)}

# --- 3. JOB ADMINS ---

class BaseJobAdmin(admin.ModelAdmin):
    # UI CONFIG
    list_per_page = 50
    save_on_top = True
    list_display_links = ("job_card_header",) # Click title to edit
    
    # SEARCH & FILTER
    search_fields = ("title", "company", "description", "tools__name")
    list_filter = (
        "screening_status", 
        "work_arrangement", 
        "created_at",
        ("tools", admin.EmptyFieldListFilter),
    )

    # LAYOUT
    fieldsets = (
        ("Key Info", {
            "fields": ("title", "company", "company_logo", "apply_url", "location")
        }),
        ("Job Details", {
            "fields": ("description", "role_type", "work_arrangement", "salary_range", "tools")
        }),
        ("Screening & AI", {
            "fields": ("screening_status", "screening_score", "screening_reason", "tags"),
            "classes": ("collapse",), 
        }),
        ("Monetization", {
            "fields": ("is_pinned", "is_featured", "plan_name"),
            "classes": ("collapse",),
        }),
        ("System Data", {
            "fields": ("slug", "created_at", "updated_at", "screened_at", "screening_details"),
            "classes": ("collapse",),
        }),
    )

    readonly_fields = ("created_at", "updated_at", "screened_at", "screening_details")
    filter_horizontal = ("tools",)
    ordering = ("-created_at",)
    
    actions = [auto_tag_tools, delete_all_rejected, "mark_approved", "mark_rejected", "mark_pending", "activate_jobs", "deactivate_jobs"]

    # --- VISUALS ---
    def logo_preview(self, obj):
        if obj.company_logo:
            return format_html('<img src="{}" style="width:32px; height:32px; object-fit:contain; border-radius:4px; border:1px solid #eee; background:white;" />', obj.company_logo)
        return "No Logo"
    logo_preview.short_description = "Img"

    def job_card_header(self, obj):
        return format_html(
            '<div style="line-height:1.2;"><div style="font-weight:600; color:#1f2937;">{}</div><div style="font-size:12px; color:#6b7280;">{}</div></div>',
            obj.title, obj.company
        )
    job_card_header.short_description = "Job Details"

    def score_display(self, obj):
        # FIX: Robust Float Conversion
        try:
            val = float(obj.screening_score) if obj.screening_score is not None else 0.0
        except (ValueError, TypeError):
            val = 0.0

        bg = "#d1fae5" if val >= 80 else "#fef3c7" if val >= 50 else "#fee2e2"
        text = "#065f46" if val >= 80 else "#92400e" if val >= 50 else "#b91c1c"
        
        # FIX: Pre-format to string to prevent "SafeString" formatting crash
        score_str = "{:.0f}".format(val)
        
        return format_html(
            '<span style="background:{}; color:{}; padding:2px 6px; border-radius:4px; font-weight:bold; font-size:11px;">{}</span>',
            bg, text, score_str
        )
    score_display.short_description = "AI Score"

    def tools_preview(self, obj):
        count = obj.tools.count()
        if count == 0:
            return format_html('<span style="color:#d1d5db;">(empty)</span>')
        return f"{count} Tools"
    tools_preview.short_description = "Stack"

    # --- ACTIONS ---
    @admin.action(description="✅ Approve")
    def mark_approved(self, request, qs): qs.update(screening_status="approved", is_active=True)

    @admin.action(description="❌ Reject")
    def mark_rejected(self, request, qs): qs.update(screening_status="rejected", is_active=False)

    @admin.action(description="⏳ Pending")
    def mark_pending(self, request, qs): qs.update(screening_status="pending", is_active=False)

    @admin.action(description="👁️ Visible")
    def activate_jobs(self, request, qs): qs.update(is_active=True)

    @admin.action(description="🚫 Hidden")
    def deactivate_jobs(self, request, qs): qs.update(is_active=False)


# A. INBOX (Pending/Rejected)
@admin.register(Job)
class JobAdmin(BaseJobAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=False)

    list_display = ("logo_preview", "job_card_header", "score_display", "screening_status", "tools_preview", "created_at")
    list_editable = ("screening_status",)

# B. ACTIVE JOBS (Live)
@admin.register(ActiveJob)
class ActiveJobAdmin(BaseJobAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)

    # Added 'view_live' button
    list_display = ("logo_preview", "job_card_header", "score_display", "is_pinned", "is_featured", "tools_preview", "view_live")
    list_editable = ("is_pinned", "is_featured")

    def view_live(self, obj):
        if obj.slug:
            url = f"/job/{obj.id}/{obj.slug}/"
            return format_html('<a href="{}" target="_blank" style="color:#4f46e5; font-weight:bold;">View ↗</a>', url)
        return "-"
    view_live.short_description = "Live Page"

# C. USER SUBMISSIONS (All)
@admin.register(UserSubmission)
class UserSubmissionAdmin(BaseJobAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tags__icontains="User Submission")

    list_display = ("logo_preview", "job_card_header", "score_display", "screening_status", "created_at")

# --- OTHER ---
@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at")

@admin.register(BlockRule)
class BlockRuleAdmin(admin.ModelAdmin):
    list_display = ("rule_type", "value", "enabled")
