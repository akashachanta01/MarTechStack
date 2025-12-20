from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

# Import all models, including the new 'ActiveJob' proxy model
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

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
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
    
    list_filter = ("screening_status", "is_active", "work_arrangement", "role_type", "created_at")
    search_fields = ("title", "company", "description")
    
    # Editable fields in the list view
    list_editable = ("work_arrangement", "salary_range")

    # Readonly fields (prevent accidental changes to system-managed data)
    readonly_fields = ("created_at", "screened_at", "screening_details")
    
    filter_horizontal = ("tools",)
    list_per_page = 25
    
    # Default sorting: Newest first
    ordering = ("-created_at",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('tools')

    # --- 1. VISUAL COLUMNS (Sortable/Style) ---

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
            '<a href="{}" style="background: #4f46e5; color: white; padding: 4px 10px; border-radius: 6px; text-decoration: none; font-size: 11px; font-weight: 600;">Edit Details</a>'
            '<a href="{}" target="_blank" style="opacity: 0.7; font-size: 12px; text-decoration: none;">↗ Apply</a>'
            '</div>',
            change_url,
            obj.apply_url
        )
    action_buttons.short_description = "Actions"

    # --- 2. BULK ACTIONS ---
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


@admin.register(UserSubmission)
class UserSubmissionAdmin(JobAdmin):
    # Only show jobs tagged "User Submission"
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tags__icontains="User Submission")

# --- NEW: ACTIVE JOBS (LIVE ON SITE) ---
@admin.register(ActiveJob)
class ActiveJobAdmin(JobAdmin):
    """
    A read-focused view for jobs that are currently live on the site.
    """
    list_display = (
        "logo_preview",
        "job_card_header",
        "score_badge",
        "work_arrangement",
        "salary_range",
        "tech_stack_preview",
        "action_buttons",
    )
    
    # FILTER: Only show jobs that are live
    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_active=True)

    # Disable "Add" to prevent accidental creation here
    def has_add_permission(self, request):
        return False
    
    # Disable "Delete" to ensure deletions happen in the main view
    def has_delete_permission(self, request, obj=None):
        return False

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
