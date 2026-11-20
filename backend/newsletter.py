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


# ---- "New subscriber" email to the site owner -----------------------------
# Sent through Resend's HTTPS API, because Render's free tier blocks SMTP
# (so Gmail SMTP can't work there).
#   RESEND_API_KEY - Resend API key (resend.com -> API Keys).
#   NOTIFY_EMAIL   - where to send it. With Resend's default sender
#                    (onboarding@resend.dev) this must be the email your
#                    Resend account was created with.
#   NOTIFY_FROM    - optional sender, once a domain is verified in Resend.

def notify_configured():
    return bool(os.environ.get("RESEND_API_KEY") and os.environ.get("NOTIFY_EMAIL"))


def all_subscribers(limit=2000):
    """Active subscriber emails from Kit, oldest first. None if Kit fails."""
    if not configured():
        return None
    headers = {"X-Kit-Api-Key": os.environ["KIT_API_KEY"]}
    emails, after = [], None
    try:
        while len(emails) < limit:
            params = {"per_page": 500, "sort_field": "id", "sort_order": "asc"}
            if after:
                params["after"] = after
            r = requests.get(f"{API}/subscribers", headers=headers, params=params, timeout=15)
            if r.status_code >= 400:
                return None
            data = r.json()
            emails += [s["email_address"] for s in data.get("subscribers", [])]
            page = data.get("pagination") or {}
            if not page.get("has_next_page"):
                break
            after = page.get("end_cursor")
    except (requests.RequestException, ValueError):
        return None
    return emails


def notify_new_subscriber(email):
    """Best effort: a failed notification never breaks the signup."""
    sender = os.environ.get("NOTIFY_FROM") or "Quigley Discovery <onboarding@resend.dev>"
    emails = all_subscribers()
    if emails is None:
        listing = "(Couldn't load the full list from Kit this time.)\n"
    else:
        if email.lower() not in (e.lower() for e in emails):
            emails.append(email)  # Kit can lag a moment behind the signup
        listing = (f"Everyone on the list ({len(emails)}):\n"
                   + "".join(f"{i}. {e}\n" for i, e in enumerate(emails, 1)))
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
            json={
                "from": sender,
                "to": [os.environ["NOTIFY_EMAIL"]],
                "subject": f"New newsletter signup: {email}",
                "text": (
                    f"{email} just signed up on quigleydiscovery.com.\n\n"
                    f"{listing}\n"
                    "Manage the list in Kit: https://app.kit.com/subscribers\n"
                ),
            },
            timeout=15,
        )
        if r.status_code >= 400:
            print(f"Signup notification failed: {r.status_code} {r.text[:200]}")
    except requests.RequestException as e:
        print(f"Signup notification failed: {type(e).__name__}")
