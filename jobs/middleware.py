from django.http import HttpResponsePermanentRedirect

class DomainRedirectMiddleware:
    """
    Redirects all traffic from martechstack.io to martechjobs.io
    while preserving the path (e.g. /post-job/).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().lower()
        
        # If the user comes from the old domain (or www version)
        if "martechstack.io" in host:
            return HttpResponsePermanentRedirect(f"https://martechjobs.io{request.path}")
            
        return self.get_response(request)
