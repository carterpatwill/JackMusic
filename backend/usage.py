"""Guards that protect the live site's free API allowances.

The live site (Render) and any local copy use the SAME Spotify / YouTube /
Instagram keys, so every call made while working locally comes out of the
live site's allowance. Overuse has already gotten Spotify blocked for about
a day. So:

- Live API calls happen only on the host (Render sets RENDER), or locally
  when you opt in with LIVE_APIS=1. Otherwise everything is served from the
  saved copies in the database's api_cache table, and fetches raise
  OfflineError instead of calling out.
- When a service rate-limits us, the "blocked until" time is saved in the
  database (not just in memory), so a restart or a second server waits it
  out instead of retrying and making the block longer.
"""

import os
import time


class OfflineError(RuntimeError):
    """Raised instead of making a live API call when live calls are off."""


def on_host():
    return bool(os.environ.get("RENDER"))


def live_apis():
    return on_host() or os.environ.get("LIVE_APIS", "").strip() == "1"


def require_live(service):
    if not live_apis():
        raise OfflineError(
            f"Live {service} calls are off on this machine (saved data only). "
            "Set LIVE_APIS=1 to allow them."
        )


def blocked_until(service):
    """Epoch seconds until which the service asked us to stop (0 if not)."""
    from . import db

    row = db.cache_get(f"blocked:{service}")
    return float(row.get("until", 0)) if row else 0.0


def is_blocked(service):
    return time.time() < blocked_until(service)


def block(service, seconds):
    from . import db

    db.cache_put(f"blocked:{service}", {"until": time.time() + seconds})
