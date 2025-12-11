from django.contrib import admin
from .models import Job, Tool, Category

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'location', 'salary_range', 'created_at', 'is_active')
    search_fields = ('title', 'company', 'tools__name')
    list_filter = ('is_active', 'created_at')
    filter_horizontal = ('tools',) # Makes selecting multiple tools easier

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
