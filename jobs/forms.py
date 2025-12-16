from django import forms
from .models import Job, Tool

class JobPostForm(forms.ModelForm):
    # Customizing the tools widget to be a multi-select checkbox or select list
    tools = forms.ModelMultipleChoiceField(
        queryset=Tool.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'grid grid-cols-2 gap-2'}),
        required=False,
        label="Tech Stack (Select all that apply)"
    )

    class Meta:
        model = Job
        fields = [
            'title', 'company', 'company_logo', 'location', 'remote', 
            'role_type', 'salary_range', 'apply_url', 'description', 'tools'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border-gray-300 focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'e.g. Senior Marketing Operations Manager'
            }),
            'company': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border-gray-300 focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'e.g. Acme Corp'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border-gray-300 focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'e.g. New York, NY or Remote'
            }),
            'salary_range': forms.TextInput(attrs={
                'class': 'w-full rounded-xl border-gray-300 focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'e.g. $120k - $150k'
            }),
            'apply_url': forms.URLInput(attrs={
                'class': 'w-full rounded-xl border-gray-300 focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'https://boards.greenhouse.io/...'
            }),
            'role_type': forms.Select(attrs={
                'class': 'w-full rounded-xl border-gray-300 focus:border-indigo-500 focus:ring-indigo-500'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded-xl border-gray-300 focus:border-indigo-500 focus:ring-indigo-500',
                'rows': 6,
                'placeholder': 'Describe the role, responsibilities, and requirements...'
            }),
            'company_logo': forms.FileInput(attrs={
                'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'
            }),
        }
