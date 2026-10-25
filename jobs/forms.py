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

    # Job function so user-posted roles land on the right category page
    # (Engineering / Operations / Data) instead of defaulting to 'other' and
    # never appearing in category listings.
    function = forms.ChoiceField(
        choices=[('engineering', 'Engineering'), ('operations', 'Operations'), ('data', 'Data & Analytics')],
        widget=forms.Select(attrs={'class': 'w-full rounded-xl border-slate-300 focus:ring-indigo-500 bg-white'}),
        label="Job Function",
        help_text="Which category does this role belong to?",
    )

    class Meta:
        model = Job
        fields = [
            'title', 'company', 'company_logo', 'location', 'work_arrangement', 'function',
            'role_type', 'salary_range', 'apply_url', 'description', 'tools',
            'poster_name', 'poster_email', 'poster_role',
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
            'poster_name': forms.TextInput(attrs={'placeholder': 'e.g. Priya Sharma', 'autocomplete': 'name'}),
            'poster_email': forms.EmailInput(attrs={'placeholder': 'you@company.com', 'autocomplete': 'email'}),
            'poster_role': forms.Select(attrs={'class': 'bg-white'}),
        }
        labels = {'poster_name': 'Your name', 'poster_email': 'Work email', 'poster_role': 'You are'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Who posted the job: required so every submission can be verified and
        # followed up; kept private (admin + founder alert only).
        self.fields['poster_name'].required = True
        self.fields['poster_email'].required = True
        self.fields['poster_role'].required = False
        self.fields['poster_role'].choices = [('', 'Select (optional)')] + list(Job.POSTER_ROLE_CHOICES)

    def clean_poster_email(self):
        return (self.cleaned_data.get('poster_email') or '').strip().lower()


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


class SponsorInquiryForm(HoneypotMixin, forms.Form):
    company = forms.CharField(max_length=200)
    name = forms.CharField(label="Your name", max_length=200)
    email = forms.EmailField(label="Work email")
    option = forms.ChoiceField(label="Interested in", choices=[
        ("newsletter", "Weekly email sponsor"), ("tool_page", "Tool page sponsor"),
        ("featured", "Featured company roles"), ("other", "Not sure yet / other")])
    message = forms.CharField(label="Anything we should know? (optional)", required=False, max_length=2000,
                              widget=forms.Textarea(attrs={"rows": 4}))


class CourseInterestForm(HoneypotMixin, forms.Form):
    name = forms.CharField(label="Your name (optional)", max_length=200, required=False)
    email = forms.EmailField(label="Your email")
    phone = forms.CharField(label="Phone / WhatsApp (optional)", max_length=30, required=False)
    program = forms.ChoiceField(choices=[("course", "This course"), ("cheaper", "A single tool at a lower price"),
                                         ("other", "A course on another platform")],
                                initial="course", required=False, widget=forms.RadioSelect,
                                label="What are you interested in? (optional)")

    def clean_program(self):
        return self.cleaned_data.get("program") or "course"

    def clean_name(self):
        # Email-only requests: use the part before @ so admin rows stay readable.
        return (self.cleaned_data.get("name") or "").strip()
    tool_note = forms.CharField(label="Which tool or platform? (optional)", max_length=200, required=False)
