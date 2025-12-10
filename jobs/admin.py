# Register your models here.
from django.contrib import admin
from .models import Job, Tool, Category

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'created_at', 'is_active')
    filter_horizontal = ('tools',) # Makes selecting multiple tools easier

admin.site.register(Tool)
admin.site.register(Category)