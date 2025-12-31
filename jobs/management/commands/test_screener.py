from django.core.management.base import BaseCommand
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'Simulates the AI Screener on test cases to verify the "Strict Trap" logic.'

    def handle(self, *args, **options):
        self.stdout.write("🧠 Loading Screener Brain...")
        screener = MarTechScreener()
        
        # --- TEST CASES ---
        tests = [
            {
                "name": "THE TRAP (Generic Title + Tool)",
                "title": "Product Manager", 
                "company": "Generic Corp",
                "desc": "We are looking for a PM to lead our roadmap. You will work closely with the marketing team who uses Marketo and Salesforce. We need someone organized."
            },
            {
                "name": "THE PERFECT MATCH (Specific Title)",
                "title": "Marketing Operations Manager", 
                "company": "Tech Inc",
                "desc": "We need a MOPs expert to manage our Marketo instance, build scoring models, and integrate with Salesforce. Python is a plus."
            },
            {
                "name": "THE GENERIC MARKETER",
                "title": "Digital Marketing Manager", 
                "company": "Agency XYZ",
                "desc": "Looking for a digital marketer to run Facebook Ads and manage our Google Analytics. You will report to the VP of Marketing."
            }
        ]

        self.stdout.write("\n🔎 RUNNING DIAGNOSTICS...\n")

        for t in tests:
            self.stdout.write(f"--- TESTING: {t['name']} ---")
            self.stdout.write(f"Title: {t['title']}")
            
            # Run the screen
            result = screener.screen(t['title'], t['company'], "Remote", t['desc'], "https://example.com")
            
            # Print Verdict
            score = result.get('score')
            status = result.get('status')
            reason = result.get('reason')
            
            color = self.style.SUCCESS if status == 'approved' else self.style.ERROR
            self.stdout.write(color(f"VERDICT: {status.upper()} (Score: {score})"))
            self.stdout.write(f"Reason: {reason}\n")
