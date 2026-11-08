import json
import re
import unicodedata
from pathlib import Path

DOCUMENTS = ("terms", "privacy", "risk")
PHONE = re.compile(r"\+[1-9][0-9]{7,14}")
VERSION = re.compile(r"[A-Za-z0-9_.-]{1,64}")


def load_documents(path):
    if not path:
        return {}
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict) or set(data) != set(DOCUMENTS):
        raise ValueError("Onboarding requires terms, privacy and risk documents")
    result = {}
    for key in DOCUMENTS:
        item = data[key]
        version, body = item["version"], item["body"]
        if not isinstance(version, str) or not VERSION.fullmatch(version):
            raise ValueError(f"Invalid document version for {key}")
        if set(body) != {"ar", "en"} or any(
            not isinstance(body[lang], str) or not body[lang].strip()
            for lang in ("ar", "en")
        ):
            raise ValueError(f"Document {key} must contain Arabic and English text")
        result[key] = {"version": version, "body": body}
    return result


def validate_profile(body):
    raw_name, phone = body.get("full_name"), body.get("phone")
    if not isinstance(raw_name, str) or not isinstance(phone, str):
        raise ValueError("Name and phone must be strings")
    names = unicodedata.normalize("NFC", raw_name).split()
    name = " ".join(names)
    if len(names) < 4 or len(name) > 120 or not all(
        any(char.isalpha() for char in part) and
        all(char.isalpha() or unicodedata.category(char).startswith("M") or char in "-'’"
            for char in part)
        for part in names
    ):
        raise ValueError("Invalid full name")
    phone = phone.strip()
    if not PHONE.fullmatch(phone):
        raise ValueError("Invalid international phone number")
    return name, phone
