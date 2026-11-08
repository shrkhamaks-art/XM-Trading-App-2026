"""Send transactional sign-in codes through Brevo's HTTPS endpoint."""

import json
from urllib.request import Request, build_opener

if __package__:
    from .sms_gateway import NoRedirect
else:
    from sms_gateway import NoRedirect


def brevo_sender(api_key, from_address):
    if (not api_key or not from_address or
            any(char in api_key or char in from_address for char in ("\r", "\n"))):
        raise ValueError("Set BREVO_API_KEY and BREVO_FROM_EMAIL together")

    def send(address, code):
        payload = {
            "sender": {"name": "Trade Studio", "email": from_address},
            "to": [{"email": address}],
            "subject": "Trade Studio | رمز الدخول",
            "textContent": f"رمز الدخول: {code}\nالرمز صالح لمدة خمس دقائق.",
        }
        request = Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json", "api-key": api_key},
            method="POST",
        )
        with build_opener(NoRedirect()).open(request, timeout=10) as response:
            if response.status != 201:
                raise OSError("Email provider did not accept the message")

    return send
