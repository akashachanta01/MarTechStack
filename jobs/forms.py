from django import forms
from .models import Job, Tool


class HoneypotMixin(forms.Form):
    # Spam trap: invisible to humans, but bots auto-fill it. Submissions
    # with this field filled are rejected.
    website = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(attrs={
            'style': 'position:absolute;left:-9999px;top:-9999px;',
            'tabindex': '-1',
            'autocomplete': 'off',
            'aria-hidden': 'true',
        })
    )

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError("Submission rejected.")
        return ''


class JobPostForm(HoneypotMixin, forms.ModelForm):
    # Strategy: Simple 2-Tier Structure
    PLAN_CHOICES = [
        ('free', 'Standard Listing - Free'),
        ('featured', 'Featured Listing - $99'),
    ]
    
    plan = forms.ChoiceField(
        choices=PLAN_CHOICES, 
        widget=forms.HiddenInput(), 
        initial='free'
    )

    # Improved Tech Stack Selection
    tools = forms.ModelMultipleChoiceField(
        queryset=Tool.objects.all().order_by('name'),
        widget=forms.CheckboxSelectMultiple(),
        required=False,
        label="Select Existing Tools"
    )

    # New Field for Custom Tools
    new_tools = forms.CharField(
        required=False,
        label="Add New Tools",
        widget=forms.TextInput(attrs={
            'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 
            'placeholder': 'e.g. CustomCRM, Internal Tool (comma separated)'
        })
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
            'title': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500 font-bold', 'placeholder': 'e.g. Senior Marketing Operations Manager'}),
            'company': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500 font-bold', 'placeholder': 'e.g. Acme Corp'}),
            'location': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'e.g. New York, NY or Remote'}),
            'salary_range': forms.TextInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'e.g. $120k - $150k'}),
            'apply_url': forms.URLInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'https://...'}),
            'role_type': forms.Select(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500 bg-white'}),
            'description': forms.Textarea(attrs={
                'class': 'w-full rounded-xl border-slate-300 focus:ring-4 focus:ring-indigo-100 focus:border-indigo-500 transition-all duration-200', 
                'rows': 8,
                'placeholder': 'Describe the role, responsibilities, and what makes your team great...'
            }),
            'company_logo': forms.URLInput(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500', 'placeholder': 'Link to logo image URL'}),
        }


class ContactForm(HoneypotMixin, forms.Form):
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={
            'placeholder': 'you@example.com (optional — only if you want a reply)'
        })
    )
    subject = forms.CharField(
        label="Topic",
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': "What's this about? Bug, idea, listing issue…"
        })
    )
    message = forms.CharField(
        label="Feedback",
        widget=forms.Textarea(attrs={
            'rows': 6,
            'placeholder': "What's working, what's broken, what you wish existed…"
        })
    )
