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


class SuspiciousSignupFilter(admin.SimpleListFilter):
    """Accounts that look like bots: never verified, not Google, no resume or
    stack, and a name that doesn't appear in the email (Oct 2026 audit found ~43,
    e.g. 'Ava Martin' on four unrelated addresses)."""
    title = 'Looks fake'
    parameter_name = 'suspicious'

    def lookups(self, request, model_admin):
        return (('yes', 'Looks fake'),)

    def queryset(self, request, qs):
        if self.value() != 'yes':
            return qs
        ids = [u.pk for u in qs.filter(is_staff=False).select_related('userprofile')
               .prefetch_related('socialaccount_set', 'emailaddress_set', 'userprofile__preferred_stack')
               if looks_fake(u)]
        return qs.filter(pk__in=ids)


def looks_fake(user):
    local = (user.email or '').split('@')[0].lower()
    names = [n for n in (user.first_name, user.last_name) if n]
    name_in_email = any(len(n) >= 3 and n.split()[0].lower() in local for n in names)
    if user.socialaccount_set.all() or any(e.verified for e in user.emailaddress_set.all()):
        return False
    profile = getattr(user, 'userprofile', None)
    if profile and profile.preferred_stack.all():
        return False
    from .models import UserResume
    if UserResume.objects.filter(user=user).exists():
        return False
    return not name_in_email


@admin.action(description="Deactivate selected accounts (stops all emails; reversible)")
def deactivate_accounts(modeladmin, request, queryset):
    from jobs.models import Subscriber
    targets = queryset.filter(is_staff=False, is_superuser=False).exclude(pk=request.user.pk)
    emails = [e.lower() for e in targets.values_list('email', flat=True) if e]
    n = targets.update(is_active=False)
    subs = Subscriber.objects.filter(email__in=emails, is_active=True).update(is_active=False)
    modeladmin.message_user(request, f"Deactivated {n} account(s); {subs} matching newsletter subscription(s) stopped. "
                                     "Staff accounts are never deactivated.")


@admin.action(description="Reactivate selected accounts")
def reactivate_accounts(modeladmin, request, queryset):
    n = queryset.update(is_active=True)
    modeladmin.message_user(request, f"Reactivated {n} account(s). Their newsletter stays off until they subscribe again.")


class CustomUserAdmin(UserAdmin):
    """Re-register User so account signups are easy to find: newest first,
    with name/email/join-date up front and the MarTech profile inline."""
    inlines = (UserProfileInline,)
    list_display = ('email', 'first_name', 'last_name', 'date_joined', 'last_login', 'on_waitlist', 'is_active')
    list_filter = ('is_active', SuspiciousSignupFilter, 'is_staff', 'date_joined', ProWaitlistFilter)
    actions = [deactivate_accounts, reactivate_accounts]
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
