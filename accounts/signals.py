# Signal handlers are defined in models.py via @receiver decorators.
# This file exists so apps.py can import it to register those handlers.
from accounts.models import ensure_user_profile  # noqa: F401
