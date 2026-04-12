import os
import json
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from openai import OpenAI
from jobs.models import BlogPost

class Command(BaseCommand):
    help = 'Generates an SEO-optimized blog post using AI. Runs maximum once per week.'

    def handle(self, *args, **options):
        self.stdout.write("🤖 Booting up AI Content Engine...")

        # 1. 7-DAY RULE: Check if we need to post
        latest_post = BlogPost.objects.filter(author="MarTechJobs AI").order_by('-published_at').first()
        
        if latest_post and latest_post.published_at >= (timezone.now() - timedelta(days=6)).date():
            self.stdout.write(self.style.SUCCESS("   ✅ A recent AI blog post already exists (less than 7 days old). Skipping generation."))
            return

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self.stdout.write(self.style.ERROR("   ❌ Missing OPENAI_API_KEY in environment variables."))
            return

        client = OpenAI(api_key=api_key)

        # 2. Strategic SEO Topic Matrix
        topics = [
            # Top-of-funnel ("What is" content)
            {"topic": "What is Martech? A Beginner's Guide", "category": "Career Advice"},
            {"topic": "What is a Martech Stack? (And How to Build One)", "category": "Tech Stacks"},
            {"topic": "What is Marketing Operations?", "category": "Career Advice"},
            {"topic": "What Does a Marketing Operations Manager Do?", "category": "Career Advice"},
            
            # Career guides (Job seeker intent)
            {"topic": "How to Break Into Martech: A Career Guide", "category": "Career Advice"},
            {"topic": "Top Martech Skills Employers Are Hiring For in 2026", "category": "Career Advice"},
            {"topic": "How to Become a HubSpot Consultant", "category": "Career Advice"},
            {"topic": "Salesforce Admin vs Salesforce Developer — Which Career Path is Right for You?", "category": "Career Advice"},
            {"topic": "What is a Marketing Technologist? (And How to Become One)", "category": "Career Advice"},
            
            # Salary content (High intent, highly linkable)
            {"topic": "Martech Salary Guide 2026: Benchmarks and Trends", "category": "Salary Guides"},
            {"topic": "Marketing Operations Manager Salary: What to Expect in 2026", "category": "Salary Guides"},
            {"topic": "Salesforce Administrator Salary Guide", "category": "Salary Guides"},
            
            # Tool/trend content (Attracts employers and senior professionals)
            {"topic": "Top Martech Companies to Work For in 2026", "category": "Industry News"},
            {"topic": "The Best Martech Stack Examples from Leading Companies", "category": "Tech Stacks"},
            {"topic": "Top Martech Tools Every Marketing Ops Professional Should Know", "category": "Tech Stacks"}
        ]
        
        selected = random.choice(topics)
        self.stdout.write(f"   ✍️ Drafting article: '{selected['topic']}'...")

        # 3. The AI Prompt
        prompt = f"""
        You are the lead content writer for MarTechJobs.io, a niche job board for Marketing Operations, Analytics, and Technology professionals.
        Write a highly technical, engaging, and SEO-optimized blog post about: "{selected['topic']}".
        
        Strict Requirements:
        - Tone: Professional but conversational. Sound like a seasoned Marketing Operations veteran. Use industry terms accurately.
        - Formatting: Output the content in clean HTML. Use <p>, <h2>, <h3>, <ul>, <li>, and <strong> tags. 
        - DO NOT wrap the HTML in Markdown ticks (like ```html). Provide ONLY the raw HTML string for the content.
        - Internal Linking: End the article with a brief, natural call to action telling the reader to either "search for open roles on MarTechJobs" or "try our free suite of MarTech tools at martechjobs.io/tools/".
        
        Output a strict JSON object with these exact keys:
        {{
            "title": "Catchy SEO Title (under 60 chars)",
            "excerpt": "A compelling 2-sentence summary for the blog feed.",
            "content": "<p>Your full HTML content goes here...</p>",
            "meta_description": "A 150-character SEO description.",
            "read_time": "X min read"
        }}
        """

        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert technical SEO writer. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7 # Slight creativity for engaging writing
            )
            
            data = json.loads(completion.choices[0].message.content)
            
            # 4. Handle Unique Slugs & Save to Database
            slug = slugify(data['title'])
            if BlogPost.objects.filter(slug=slug).exists():
                slug = f"{slug}-{random.randint(100, 9999)}"

            post = BlogPost.objects.create(
                title=data['title'],
                slug=slug,
                excerpt=data['excerpt'],
                content=data['content'],
                meta_title=data['title'][:60],
                meta_description=data['meta_description'],
                author="MarTechJobs AI",
                category=selected['category'],
                read_time=data['read_time'],
                is_published=True,
                published_at=timezone.now().date()
            )

            self.stdout.write(self.style.SUCCESS(f"✨ Success! Automated post published: {post.title}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ AI Generation Failed: {e}"))
