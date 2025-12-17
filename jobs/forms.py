from django import forms
from .models import Job, Tool

class JobPostForm(forms.ModelForm):
    PLAN_CHOICES = [
        ('standard', 'Standard Listing - $99'),
        ('featured', 'Featured Listing - $149'),
        ('premium', 'Premium Bundle - $199'),
    ]
    
    plan = forms.ChoiceField(
        choices=PLAN_CHOICES, 
        widget=forms.HiddenInput(), 
        initial='standard'
    )

    tools = forms.ModelMultipleChoiceField(
        queryset=Tool.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'grid grid-cols-2 gap-2'}),
        required=False,
        label="Tech Stack"
    )
    
    work_arrangement = forms.ChoiceField(
        choices=Job.WORK_ARRANGEMENT_CHOICES,
        widget=forms.RadioSelect(),
        initial='onsite',
    )

    class Meta:
        model = Job
        fields = [
            'title', 'company', 'company_logo', 'location', 'work_arrangement', 
            'role_type', 'salary_range', 'apply_url', 'description', 'tools'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'e.g. Senior Marketing Operations Manager'}),
            'company': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'e.g. Acme Corp'}),
            'location': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'e.g. New York, NY or Remote'}),
            'salary_range': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'e.g. $120k - $150k'}),
            'apply_url': forms.URLInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'https://...'}),
            'role_type': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500'}),
            'description': forms.Textarea(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'rows': 6}),
            'company_logo': forms.URLInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'Link to logo image URL'}),
        }
