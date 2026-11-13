from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication subclass that exempts CSRF checks on JSON API endpoints.
    Allows stateless API clients, Next.js rewrites on any port (3000, 3001, 3002...),
    and mobile browsers accessing via local Wi-Fi to communicate without CSRF blocks.
    """
    def enforce_csrf(self, request):
        # Do not enforce CSRF for API requests
        return
