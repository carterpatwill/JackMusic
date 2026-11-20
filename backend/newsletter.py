"""Newsletter signups via Kit (kit.com), which holds the mailing list.

Env:
    KIT_API_KEY  - Kit v4 API key (Settings -> Developer). Required.
    KIT_FORM_ID  - optional Kit form id; signups are added to that form so
                   they show its name as the source and get its emails.

Kit is the source of truth for the list. The local `subscribers` table is
only a backup, since Render's free-tier disk resets on every redeploy.
"""

import os

import requests

API = "https://api.kit.com/v4"


class NewsletterError(Exception):
    pass


def configured():
    return bool(os.environ.get("KIT_API_KEY"))


def subscribe(email):
    headers = {"X-Kit-Api-Key": os.environ["KIT_API_KEY"]}
    form_id = os.environ.get("KIT_FORM_ID", "").strip()
    try:
        # Create (or find) the subscriber...
        r = requests.post(f"{API}/subscribers", headers=headers,
                          json={"email_address": email}, timeout=15)
        if r.status_code >= 400:
            raise NewsletterError(f"create {r.status_code}: {r.text[:200]}")
        # ...then attach them to the site's form, if one is set.
        if form_id:
            r = requests.post(f"{API}/forms/{form_id}/subscribers", headers=headers,
                              json={"email_address": email}, timeout=15)
            if r.status_code >= 400:
                raise NewsletterError(f"form {r.status_code}: {r.text[:200]}")
    except requests.RequestException as e:
        raise NewsletterError(type(e).__name__)
