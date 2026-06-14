from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        # Capture name fields passed from our custom signup template
        data = form.cleaned_data
        user.first_name = request.POST.get('first_name', '').strip()[:30]
        user.last_name = request.POST.get('last_name', '').strip()[:150]
        if commit:
            user.save()
        return user
