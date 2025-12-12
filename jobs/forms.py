from django import forms
from .models import Job

class JobSubmissionForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['title', 'company', 'company_logo', 'location', 'salary_range', 'apply_url', 'tags', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 outline-none', 'placeholder': 'e.g. Senior Marketing Ops Manager'}),
            'company': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 outline-none', 'placeholder': 'e.g. Acme Corp'}),
            'company_logo': forms.URLInput(attrs={'class': 'w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 outline-none', 'placeholder': 'https://...'}),
            'location': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 outline-none', 'placeholder': 'e.g. Remote, USA'}),
            'salary_range': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 outline-none', 'placeholder': 'e.g. $120k - $150k'}),
            'apply_url': forms.URLInput(attrs={'class': 'w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 outline-none', 'placeholder': 'Link to application page'}),
            'tags': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 outline-none', 'placeholder': 'e.g. Marketo, Salesforce, SQL'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-3 rounded-lg border border-slate-300 focus:ring-2 focus:ring-teal-500 outline-none h-40', 'placeholder': 'Paste job description here...'}),
        }
