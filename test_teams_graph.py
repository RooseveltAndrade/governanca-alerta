import os
import json
import atexit
from pathlib import Path

import requests
import msal
from dotenv import load_dotenv

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SCOPES = [
    "User.Read",
    "Chat.ReadWrite",
    "ChatMessage.Send",
]

CACHE_DIR = Path(".auth_cache")
CACHE_FILE = CACHE_DIR / "teams_token_cache.bin"


def load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()

    if CACHE_FILE.exists():
        cache.deserialize(CACHE_FILE.read_text(encoding="utf-8"))

    def save_cache() -> None:
        if cache.has_state_changed:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(cache.serialize(), encoding="utf-8")

    atexit.register(save_cache)
    return cache


def get_token_device_flow(tenant_id: str, client_id: str, expected_upn: str) -> str:
    cache = load_cache()
    authority = f"https://login.microsoftonline.com/{tenant_id}"

    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
        token_cache=cache,
    )

    accounts = app.get_accounts(username=expected_upn)
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and "access_token" in result:
            print("OK token obtido do cache.")
            return result["access_token"]

    all_accounts = app.get_accounts()
    if all_accounts:
        result = app.acquire_token_silent(SCOPES, account=all_accounts[0])
        if result and "access_token" in result:
            print("OK token obtido do cache.")
            return result["access_token"]

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"Falha ao iniciar device flow: {flow}")

    print("\n=== AUTENTICAÇÃO MICROSOFT ===")
    print(flow["message"])
    print(f"Faça login com a conta: {expected_upn}\n")

    result = app.acquire_token_by_device_flow(flow)
    token = result.get("access_token")
    if not token:
        raise RuntimeError(f"Falha ao obter token delegado: {json.dumps(result, ensure_ascii=False, indent=2)}")

    account_username = (
        result.get("id_token_claims", {}).get("preferred_username")
        or result.get("id_token_claims", {}).get("upn")
        or ""
    ).lower()

    if expected_upn and account_username and account_username != expected_upn.lower():
        raise RuntimeError(
            f"Você autenticou com '{account_username}', mas o esperado é '{expected_upn}'. "
            "Apague o cache e autentique com a conta correta."
        )

    print("OK token delegado obtido por login interativo.")
    return token


def graph_get(url: str, token: str) -> requests.Response:
    return requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )


def graph_post(url: str, token: str, payload: dict) -> requests.Response:
    return requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )


def ensure_one_on_one_chat(token: str, sender_id: str, target_id: str) -> str:
    payload = {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"{GRAPH_BASE}/users('{sender_id}')",
            },
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"{GRAPH_BASE}/users('{target_id}')",
            },
        ],
    }

    resp = graph_post(f"{GRAPH_BASE}/chats", token, payload)
    print(f"HTTP chats: {resp.status_code}")
    print(resp.text)

    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Falha ao criar/obter chat: {resp.text}")

    data = resp.json()
    chat_id = data.get("id")
    if not chat_id:
        raise RuntimeError("Chat criado/encontrado sem id.")

    return chat_id


def send_chat_message(token: str, chat_id: str, message: str) -> None:
    payload = {
        "body": {
            "contentType": "text",
            "content": message,
        }
    }

    resp = graph_post(f"{GRAPH_BASE}/chats/{chat_id}/messages", token, payload)
    print(f"HTTP messages: {resp.status_code}")
    print(resp.text)

    if resp.status_code not in (200, 201, 202):
        raise RuntimeError(f"Falha ao enviar mensagem: {resp.text}")


def main() -> int:
    load_dotenv()

    tenant_id = str(os.getenv("M365_TENANT_ID", "")).strip()
    client_id = str(os.getenv("M365_CLIENT_ID", "")).strip()
    sender_upn = str(os.getenv("M365_SENDER_UPN", "")).strip()
    test_user_email = str(os.getenv("TEAMS_TEST_TO", "")).strip()
    test_message = str(
        os.getenv(
            "TEAMS_TEST_MESSAGE",
            "[TESTE AUTOMACAO] Mensagem enviada com token delegado via Microsoft Graph.",
        )
    ).strip()

    if not all([tenant_id, client_id, sender_upn, test_user_email]):
        print("Defina no .env: M365_TENANT_ID, M365_CLIENT_ID, M365_SENDER_UPN e TEAMS_TEST_TO")
        return 1

    print("1) Obtendo token delegado...")
    token = get_token_device_flow(tenant_id, client_id, sender_upn)
    print("OK token obtido")

    print(f"2) Buscando usuário destino: {test_user_email}")
    user_resp = graph_get(
        f"{GRAPH_BASE}/users/{test_user_email}?$select=id,displayName,userPrincipalName",
        token,
    )
    print(f"HTTP users: {user_resp.status_code}")
    if user_resp.status_code != 200:
        print(user_resp.text)
        return 2

    user_data = user_resp.json()
    target_id = user_data["id"]
    print("OK destino:", user_data.get("displayName"), "|", user_data.get("userPrincipalName"))

    print(f"3) Buscando remetente: {sender_upn}")
    sender_resp = graph_get(
        f"{GRAPH_BASE}/users/{sender_upn}?$select=id,displayName,userPrincipalName",
        token,
    )
    print(f"HTTP sender: {sender_resp.status_code}")
    if sender_resp.status_code != 200:
        print(sender_resp.text)
        return 3

    sender_data = sender_resp.json()
    sender_id = sender_data["id"]
    print("OK remetente:", sender_data.get("displayName"), "|", sender_data.get("userPrincipalName"))

    print("4) Criando/obtendo chat 1:1...")
    chat_id = ensure_one_on_one_chat(token, sender_id, target_id)
    print("OK chat_id:", chat_id)

    print("5) Enviando mensagem...")
    send_chat_message(token, chat_id, test_message)
    print("OK mensagem enviada com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())