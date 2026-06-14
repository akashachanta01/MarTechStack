from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import UserProfile, ProWaitlistEntry


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    verbose_name_plural = "Profile"
    filter_horizontal = ('preferred_stack', 'saved_jobs')
    readonly_fields = ('created_at', 'updated_at', 'pro_waitlist_at')


class ProWaitlistFilter(admin.SimpleListFilter):
    title = 'Go Pro waitlist'
    parameter_name = 'pro_waitlist'

    def lookups(self, request, model_admin):
        return (('yes', 'On waitlist'),)

    def queryset(self, request, qs):
        if self.value() == 'yes':
            return qs.filter(userprofile__pro_waitlist=True)
        return qs


class CustomUserAdmin(UserAdmin):
    """Re-register User so account signups are easy to find: newest first,
    with name/email/join-date up front and the MarTech profile inline."""
    inlines = (UserProfileInline,)
    list_display = ('email', 'first_name', 'last_name', 'date_joined', 'last_login', 'on_waitlist', 'is_active')
    list_filter = ('is_active', 'is_staff', 'date_joined', ProWaitlistFilter)
    ordering = ('-date_joined',)
    search_fields = ('email', 'first_name', 'last_name', 'username')

    @admin.display(boolean=True, description='Pro waitlist')
    def on_waitlist(self, obj):
        return bool(getattr(obj, 'userprofile', None) and obj.userprofile.pro_waitlist)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


@admin.register(ProWaitlistEntry)
class ProWaitlistAdmin(admin.ModelAdmin):
    """Dedicated 'Pro Waitlist' list: everyone who clicked Join the waitlist,
    newest first, with email + join date. Read-only, searchable, exportable."""
    list_display = ('email', 'full_name', 'pro_waitlist_at')
    ordering = ('-pro_waitlist_at',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    list_select_related = ('user',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pro_waitlist=True)

    @admin.display(description='Email', ordering='user__email')
    def email(self, obj):
        return obj.user.email

    @admin.display(description='Name')
    def full_name(self, obj):
        return obj.user.get_full_name() or '—'

    def has_add_permission(self, request):
        return False
