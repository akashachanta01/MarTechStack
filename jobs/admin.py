from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib import messages

# Import all models
from .models import Job, Tool, Category, Subscriber, BlockRule, UserSubmission, ActiveJob

# --- 1. GLOBAL ACTIONS (Available everywhere) ---

@admin.action(description="🤖 Auto-Tag Tech Stack (Scan Description)")
def auto_tag_tools(modeladmin, request, queryset):
    """
    Scans the description of selected jobs and adds Tool tags 
    if the tool name appears in the text.
    """
    # 1. Load all tools into memory for fast matching
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
                
            # strict check: look for tool name boundaries to avoid substrings
            # e.g. avoid matching "R" in "Re-engagement"
            tool_name = tool.name.lower()
            
            # Simple check (can be improved with regex if needed)
            if tool_name in text:
                job.tools.add(tool)
                added_count += 1
        
        if added_count > 0:
            affected_jobs += 1
            
    modeladmin.message_user(request, f"✅ Scanned {queryset.count()} jobs. Updated Tech Stack for {affected_jobs} jobs.", messages.SUCCESS)

@admin.action(description="🗑️ DELETE ALL 'Rejected' Jobs (Cleanup)")
def delete_all_rejected(modeladmin, request, queryset):
    """
    Nuclear option to clean up the database. 
    Ignores the selection and deletes ALL jobs marked as 'rejected'.
    """
    count, _ = Job.objects.filter(screening_status='rejected').delete()
    modeladmin.message_user(request, f"🧹 Wiped {count} rejected jobs from existence.", messages.WARNING)

# --- 2. MODEL ADMINS ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "tool_count")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

    def tool_count(self, obj):
        return obj.tools.count()

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "job_count")
    search_fields = ("name",)
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name",)}

    def job_count(self, obj):
        return obj.jobs.count()

# --- BASE JOB ADMIN ---
class BaseJobAdmin(admin.ModelAdmin):
    """
    Shared Logic for all Job views.
    """
    # UI CONFIG
    list_per_page = 50
    save_on_top = True
    list_display_links = ("job_card_header",) # Makes the title clickable!
    
    # SEARCH & FILTER
    search_fields = ("title", "company", "description", "tools__name")
    list_filter = (
        "screening_status", 
        "work_arrangement", 
        "role_type", 
        "created_at",
        ("tools", admin.EmptyFieldListFilter), # Filter by "Has Tools" vs "Empty"
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

    # --- VISUALS ---
    def logo_preview(self, obj):
        if obj.company_logo:
            return format_html(
                '<img src="{}" style="width: 32px; height: 32px; object-fit: contain; border-radius: 4px; border: 1px solid #eee; background: white;" />',
                obj.company_logo
            )
        return "No Logo"
    logo_preview.short_description = "Img"

    def job_card_header(self, obj):
        # Color code the score
        score = obj.screening_score or 0
        color = "green" if score > 70 else "orange" if score > 40 else "red"
        
        return format_html(
            '<div style="line-height: 1.2;">'
            '<div style="font-weight: 600; font-size: 14px; color: #1f2937;">{}</div>'
            '<div style="font-size: 12px; color: #6b7280;">{}</div>'
            '</div>',
            obj.title,
            obj.company
        )
    job_card_header.short_description = "Job Details"

    def score_display(self, obj):
        val = obj.screening_score or 0
        bg = "#d1fae5" if val >= 80 else "#fef3c7" if val >= 50 else "#fee2e2"
        text = "#065f46" if val >= 80 else "#92400e" if val >= 50 else "#b91c1c"
        return format_html(
            '<span style="background: {}; color: {}; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">{:.0f}</span>',
            bg, text, val
        )
    score_display.short_description = "AI Score"

    def tools_preview(self, obj):
        tools = list(obj.tools.all()[:3])
        count = obj.tools.count()
        if not tools:
            return format_html('<span style="color: #d1d5db;">(empty)</span>')
        
        html_str = ""
        for t in tools:
            html_str += f'<span style="border:1px solid #e5e7eb; background:#f9fafb; padding:0px 4px; border-radius:3px; font-size:10px; margin-right:2px;">{t.name}</span>'
        
        if count > 3:
            html_str += f'<span style="font-size:10px; color:#6b7280;">+{count-3}</span>'
        return format_html(html_str)
    tools_preview.short_description = "Stack"

    # --- ACTIONS ---
    actions = [
        "mark_approved", "mark_rejected", "mark_pending", 
        "activate_jobs", "deactivate_jobs", 
        "delete_all_rejected", "auto_tag_tools" # <--- NEW ACTIONS
    ]

    @admin.action(description="✅ Approve selected")
    def mark_approved(self, request, queryset):
        queryset.update(screening_status="approved", is_active=True)

    @admin.action(description="❌ Reject selected")
    def mark_rejected(self, request, queryset):
        queryset.update(screening_status="rejected", is_active=False)

    @admin.action(description="⏳ Mark Pending")
    def mark_pending(self, request, queryset):
        queryset.update(screening_status="pending", is_active=False)

    @admin.action(description="👁️ Set Visible")
    def activate_jobs(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="🚫 Set Hidden")
    def deactivate_jobs(self, request, queryset):
        queryset.update(is_active=False)

# --- 1. INBOX ADMIN (To-Do List) ---
@admin.register(Job)
class JobAdmin(BaseJobAdmin):
    # Only show inactive jobs in the main inbox
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=False)

    list_display = (
        "logo_preview", "job_card_header", "score_display", 
        "screening_status", "location", "tools_preview", "created_at"
    )
    
    # Quick edits right from the list
    list_editable = ("screening_status",) 

# --- 2. ACTIVE JOBS ADMIN (Live Dashboard) ---
@admin.register(ActiveJob)
class ActiveJobAdmin(BaseJobAdmin):
    # Only show LIVE jobs
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)
    
    list_display = (
        "logo_preview", "job_card_header", "score_display", 
        "is_pinned", "is_featured", # Easy monetization toggles
        "tools_preview", "open_link"
    )
    
    list_editable = ("is_pinned", "is_featured")

    def open_link(self, obj):
        return format_html('<a href="{}" target="_blank">↗ Apply</a>', obj.apply_url)
    open_link.short_description = "Link"

# --- 3. SUBMISSIONS ---
@admin.register(UserSubmission)
class UserSubmissionAdmin(BaseJobAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tags__icontains="User Submission")

# --- OTHER ADMINS ---
@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at")

@admin.register(BlockRule)
class BlockRuleAdmin(admin.ModelAdmin):
    list_display = ("rule_type", "value", "enabled")
