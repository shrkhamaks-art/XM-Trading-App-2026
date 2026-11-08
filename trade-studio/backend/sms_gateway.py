"""Adapter for an operator-configured HTTPS SMS gateway."""

import json
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def create_sender(url, token):
    if not url and not token:
        return None
    endpoint = urlsplit(url or "")
    if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username is not None
            or endpoint.password is not None or endpoint.query or endpoint.fragment
            or not token or "\r" in token or "\n" in token):
        raise ValueError("Configure an HTTPS SMS gateway URL and bearer token")

    def send(phone, code):
        request = Request(url, data=json.dumps({"to": phone, "code": code}).encode(), headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {token}",
        })
        with build_opener(NoRedirect()).open(request, timeout=7) as response:
            if not 200 <= response.status < 300:
                raise OSError("SMS gateway rejected delivery")

    return send
