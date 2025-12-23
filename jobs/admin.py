from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

# Import all models
from .models import Job, Tool, Category, Subscriber, BlockRule, UserSubmission, ActiveJob

# --- ADMIN REGISTRATIONS ---

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "slug")
    search_fields = ("name",)
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name",)}

# --- BASE ADMIN (Shared Visuals & Logic) ---
class BaseJobAdmin(admin.ModelAdmin):
    """
    Holds all the visual settings so we don't have to duplicate code.
    Both 'Inbox' and 'Active' admins will inherit from this.
    """
    list_display = (
        "logo_preview",
        "job_card_header",
        "score_badge",
        "work_arrangement", 
        "salary_range",   
        "tech_stack_preview",
        "status_badge",
        "action_buttons",
    )
    
    list_filter = ("screening_status", "work_arrangement", "role_type", "created_at")
    
    # UPGRADE 1: Search by Tool Name too (e.g., search "Marketo")
    search_fields = ("title", "company", "description", "tools__name")
    
    # UPGRADE 2: Organized "Edit" Screen
    fieldsets = (
        ("Key Info", {
            "fields": ("title", "company", "company_logo", "apply_url", "location")
        }),
        ("Job Details", {
            "fields": ("description", "role_type", "work_arrangement", "salary_range", "tools")
        }),
        ("Screening & AI", {
            "fields": ("screening_status", "screening_score", "screening_reason", "tags"),
            "classes": ("collapse",), # Click to expand
        }),
        ("Monetization", {
            "fields": ("is_pinned", "is_featured", "plan_name"),
            "classes": ("collapse",),
        }),
        ("System Data", {
            "fields": ("created_at", "updated_at", "screened_at", "screening_details"),
            "classes": ("collapse",),
        }),
    )

    # Editable fields in the list view (Quick edits)
    list_editable = ("work_arrangement", "salary_range")

    # Readonly fields
    readonly_fields = ("created_at", "updated_at", "screened_at", "screening_details")
    
    filter_horizontal = ("tools",)
    list_per_page = 25
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('tools')

    # --- VISUAL COLUMNS ---
    def logo_preview(self, obj):
        if obj.company_logo:
            return format_html(
                '<img src="{}" style="width: 40px; height: 40px; object-fit: contain; border-radius: 6px; border: 1px solid #e5e7eb; background: #fff;" />',
                obj.company_logo
            )
        return format_html(
            '<div style="width: 40px; height: 40px; border-radius: 6px; background: #f3f4f6; color: #9ca3af; display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: bold;">?</div>'
        )
    logo_preview.short_description = "Logo"

    def job_card_header(self, obj):
        return format_html(
            '<div style="line-height: 1.2;">'
            '<div style="font-weight: 700; font-size: 14px;">{}</div>'
            '<div style="font-size: 12px; opacity: 0.8;">{} • {}</div>'
            '</div>',
            obj.title,
            obj.company,
            obj.location or obj.get_work_arrangement_display()
        )
    job_card_header.short_description = "Role & Company"
    job_card_header.admin_order_field = "title"

    def score_badge(self, obj):
        try:
            val = float(obj.screening_score) if obj.screening_score is not None else 0.0
        except (ValueError, TypeError):
            val = 0.0

        if val >= 80:
            bg, text = "#d1fae5", "#065f46" # Green
        elif val >= 50:
            bg, text = "#fef3c7", "#92400e" # Amber
        else:
            bg, text = "#fee2e2", "#b91c1c" # Red
        
        score_str = "{:.0f}".format(val)

        return format_html(
            '<span style="background: {}; color: {}; padding: 4px 8px; border-radius: 99px; font-weight: 700; font-size: 11px;">{}</span>',
            bg, text, score_str
        )
    score_badge.short_description = "Score"
    score_badge.admin_order_field = "screening_score"

    def status_badge(self, obj):
        colors = {
            'approved': ('#dcfce7', '#166534'), # Green
            'rejected': ('#f3f4f6', '#374151'), # Gray
            'pending':  ('#e0e7ff', '#3730a3'), # Indigo
        }
        bg, text = colors.get(obj.screening_status, ('#f3f4f6', '#000'))
        return format_html(
            '<span style="background: {}; color: {}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase;">{}</span>',
            bg, text, obj.screening_status
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "screening_status"

    def tech_stack_preview(self, obj):
        tools = obj.tools.all()[:4]
        if not tools:
            return format_html('<span style="color: #9ca3af;">-</span>')
        
        html = '<div style="display: flex; gap: 4px; flex-wrap: wrap;">'
        for tool in tools:
            html += f'<span style="background: rgba(128,128,128,0.2); border: 1px solid rgba(128,128,128,0.3); padding: 1px 6px; border-radius: 4px; font-size: 10px; white-space: nowrap;">{tool.name}</span>'
        if obj.tools.count() > 4:
            html += '<span style="font-size: 10px; opacity: 0.7;">...</span>'
        html += '</div>'
        return format_html(html)
    tech_stack_preview.short_description = "Tech Stack"

    def action_buttons(self, obj):
        change_url = reverse('admin:jobs_job_change', args=[obj.id])
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<a href="{}" style="background: #4f46e5; color: white; padding: 4px 10px; border-radius: 6px; text-decoration: none; font-size: 11px; font-weight: 600;">Edit</a>'
            '<a href="{}" target="_blank" style="opacity: 0.7; font-size: 12px; text-decoration: none;">↗ Apply</a>'
            '</div>',
            change_url,
            obj.apply_url
        )
    action_buttons.short_description = "Actions"

    # --- BULK ACTIONS ---
    actions = ("mark_approved", "mark_rejected", "mark_pending", "activate_jobs", "deactivate_jobs")

    @admin.action(description="✅ Approve selected")
    def mark_approved(self, request, queryset):
        queryset.update(screening_status="approved", is_active=True)

    @admin.action(description="❌ Reject selected")
    def mark_rejected(self, request, queryset):
        queryset.update(screening_status="rejected", is_active=False)

    @admin.action(description="⏳ Mark as Pending")
    def mark_pending(self, request, queryset):
        queryset.update(screening_status="pending", is_active=False)

    @admin.action(description="👁️ Set Active (Visible)")
    def activate_jobs(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="🚫 Set Inactive (Hidden)")
    def deactivate_jobs(self, request, queryset):
        queryset.update(is_active=False)

# --- 1. INBOX (INACTIVE JOBS ONLY) ---
@admin.register(Job)
class JobAdmin(BaseJobAdmin):
    """
    Shows ONLY inactive jobs (Pending, Rejected, or manually hidden).
    This is your 'To-Do' list.
    """
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=False)

# --- 2. ACTIVE JOBS (LIVE ON SITE ONLY) ---
@admin.register(ActiveJob)
class ActiveJobAdmin(BaseJobAdmin):
    """
    Shows ONLY live jobs.
    This is your 'Dashboard'.
    """
    # UPGRADE 3: Add 'is_pinned' to list_editable so you can pin jobs instantly from the list!
    list_editable = ("work_arrangement", "salary_range", "is_pinned", "is_featured") 
    
    list_display = (
        "logo_preview",
        "job_card_header",
        "score_badge",
        "is_pinned",  # Add checkbox column
        "is_featured", # Add checkbox column
        "work_arrangement",
        "salary_range",
        "tech_stack_preview",
        "action_buttons",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)

    # Disable "Add" here (create new jobs in the main inbox or via script)
    def has_add_permission(self, request):
        return False
    
    # Disable "Delete" here to prevent accidents
    def has_delete_permission(self, request, obj=None):
        return False

# --- 3. USER SUBMISSIONS (ALL) ---
@admin.register(UserSubmission)
class UserSubmissionAdmin(BaseJobAdmin):
    """
    Shows all user submissions, regardless of status.
    """
    def get_queryset(self, request):
        # We inherit from BaseJobAdmin directly so we don't get the 'False' filter from JobAdmin
        qs = super(BaseJobAdmin, self).get_queryset(request) # Call grandparent queryset
        return qs.prefetch_related('tools').filter(tags__icontains="User Submission")

# --- OTHER ADMINS ---

@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at")
    search_fields = ("email",)
    ordering = ("-created_at",)

@admin.register(BlockRule)
class BlockRuleAdmin(admin.ModelAdmin):
    list_display = ("rule_type", "value", "enabled", "created_at")
    list_filter = ("rule_type", "enabled")
    search_fields = ("value", "notes")
    ordering = ("-created_at",)
