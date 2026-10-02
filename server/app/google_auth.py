"""Google sign-in for the super-admin page: verify the ID token the browser got from Google.

Only /super uses this, never a room device, so it is not on the event-day critical path
(invariant 6). It makes one HTTPS call to Google (their public keys, cached by google-auth).
Kept in its own module so tests can replace `verify`.
"""

from google.auth.transport import requests as g_requests
from google.oauth2 import id_token


def verify(credential: str, client_id: str) -> dict:
    """Return Google's claims for a valid token for our client id. Raises ValueError if not."""
    return id_token.verify_oauth2_token(credential, g_requests.Request(), client_id)
