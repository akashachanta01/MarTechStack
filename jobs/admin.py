from django.contrib import admin
from .models import Job, Tool, Category, Subscriber, BlockRule # Corrected ToolCategory to Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name",)
    list_filter = ("category",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "location",
        "remote",
        "role_type",
        "screening_status",
        "screening_score",
        "is_active",
        "created_at",
    )
    list_filter = ("remote", "role_type", "screening_status", "is_active", "created_at")
    search_fields = ("title", "company", "location", "description")
    readonly_fields = ("created_at", "screened_at")
    filter_horizontal = ("tools",)
    ordering = ("-created_at",)

    actions = ("mark_approved", "mark_rejected", "mark_pending", "activate_jobs", "deactivate_jobs")

    @admin.action(description="Mark selected jobs as Approved")
    def mark_approved(self, request, queryset):
        queryset.update(screening_status="approved")

    @admin.action(description="Mark selected jobs as Rejected")
    def mark_rejected(self, request, queryset):
        queryset.update(screening_status="rejected")

    @admin.action(description="Mark selected jobs as Pending")
    def mark_pending(self, request, queryset):
        queryset.update(screening_status="pending")

    @admin.action(description="Activate selected jobs (visible)")
    def activate_jobs(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected jobs (hidden)")
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
    list_filter = ("rule_type", "enabled", "created_at")
    search_fields = ("value", "notes")
    ordering = ("-created_at",)
