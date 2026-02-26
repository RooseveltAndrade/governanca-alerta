import os
import requests
import msal

TENANT_ID = os.getenv("M365_TENANT_ID")
CLIENT_ID = os.getenv("M365_CLIENT_ID")
CLIENT_SECRET = os.getenv("M365_CLIENT_SECRET")
SENDER_UPN = os.getenv("M365_SENDER_UPN")  # mailbox que vai enviar

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["https://graph.microsoft.com/.default"]

def _get_token() -> str:
    app = msal.ConfidentialClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )
    result = app.acquire_token_for_client(scopes=SCOPE)
    if "access_token" not in result:
        raise RuntimeError(f"Falha ao obter token: {result}")
    return result["access_token"]

def enviar_email(destinatarios: list[str], assunto: str, corpo: str) -> None:
    token = _get_token()
    url = f"https://graph.microsoft.com/v1.0/users/{SENDER_UPN}/sendMail"

    payload = {
        "message": {
            "subject": assunto,
            "body": {"contentType": "Text", "content": corpo},
            "toRecipients": [{"emailAddress": {"address": d}} for d in destinatarios],
        },
        "saveToSentItems": True,
    }

    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if r.status_code not in (202,):
        raise RuntimeError(f"Erro sendMail: {r.status_code} - {r.text}")