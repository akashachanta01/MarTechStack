from django.contrib import admin
from django.utils.html import format_html
from .models import Job, Tool, Category, Subscriber, BlockRule

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
        "tech_stack_preview",
        "status_badge",
        "action_buttons",
    )
    list_filter = ("screening_status", "is_active", "remote", "role_type", "created_at")
    search_fields = ("title", "company", "description")
    readonly_fields = ("created_at", "screened_at", "screening_details")
    filter_horizontal = ("tools",)
    list_per_page = 25
    
    # ⚡️ Performance Optimization: Prefetch tools to avoid N+1 queries
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('tools')

    # --- 1. VISUAL COLUMNS ---

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
            '<div style="font-weight: 700; font-size: 14px; color: #111827;">{}</div>'
            '<div style="font-size: 12px; color: #6b7280;">{} • {}</div>'
            '</div>',
            obj.title,
            obj.company,
            obj.location or "Remote"
        )
    job_card_header.short_description = "Role & Company"

    def score_badge(self, obj):
        score = obj.screening_score or 0
        if score >= 80:
            bg, text = "#d1fae5", "#065f46" # Green
        elif score >= 50:
            bg, text = "#fef3c7", "#92400e" # Amber
        else:
            bg, text = "#fee2e2", "#b91c1c" # Red
        
        return format_html(
            '<span style="background: {}; color: {}; padding: 4px 8px; border-radius: 99px; font-weight: 700; font-size: 11px;">{:.0f}</span>',
            bg, text, score
        )
    score_badge.short_description = "Score"

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

    def tech_stack_preview(self, obj):
        tools = obj.tools.all()[:4]
        if not tools:
            return format_html('<span style="color: #d1d5db;">-</span>')
        
        html = '<div style="display: flex; gap: 4px; flex-wrap: wrap;">'
        for tool in tools:
            html += f'<span style="background: #f3f4f6; border: 1px solid #e5e7eb; color: #374151; padding: 1px 6px; border-radius: 4px; font-size: 10px; white-space: nowrap;">{tool.name}</span>'
        if obj.tools.count() > 4:
            html += '<span style="font-size: 10px; color: #6b7280;">...</span>'
        html += '</div>'
        return format_html(html)
    tech_stack_preview.short_description = "Tech Stack"

    def action_buttons(self, obj):
        return format_html(
            '<div style="display: flex; align-items: center; gap: 8px;">'
            '<a href="/staff/review/?q={}" target="_blank" style="background: #4f46e5; color: white; padding: 4px 10px; border-radius: 6px; text-decoration: none; font-size: 11px; font-weight: 600;">Review</a>'
            '<a href="{}" target="_blank" style="color: #6b7280; font-size: 12px; text-decoration: none;">↗ Apply</a>'
            '</div>',
            obj.title, # Searches the review queue by title
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
