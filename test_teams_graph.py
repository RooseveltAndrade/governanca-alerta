import os
import json
import requests
import msal
from dotenv import load_dotenv


def get_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.ConfidentialClientApplication(
        client_id=client_id,
        authority=authority,
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    token = result.get("access_token")
    if not token:
        raise RuntimeError(f"Falha ao obter token: {result}")
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


def main() -> int:
    load_dotenv()

    tenant_id = str(os.getenv("M365_TENANT_ID", "")).strip()
    client_id = str(os.getenv("M365_CLIENT_ID", "")).strip()
    client_secret = str(os.getenv("M365_CLIENT_SECRET", "")).strip()
    sender_upn = str(os.getenv("M365_SENDER_UPN", "")).strip()
    test_user_email = str(os.getenv("TEAMS_TEST_TO", "")).strip() or str(os.getenv("SAFE_TEST_TO", "")).strip()
    test_message = str(
        os.getenv(
            "TEAMS_TEST_MESSAGE",
            "[TESTE AUTOMACAO] Olá! Esta é uma mensagem de teste enviada via Microsoft Graph para validar chat direto no Teams.",
        )
    ).strip()

    if not all([tenant_id, client_id, client_secret, sender_upn, test_user_email]):
        print(
            "Defina no .env: M365_TENANT_ID, M365_CLIENT_ID, M365_CLIENT_SECRET, "
            "M365_SENDER_UPN e TEAMS_TEST_TO (ou SAFE_TEST_TO)"
        )
        return 1

    if sender_upn.lower() == test_user_email.lower():
        print("Para chat 1:1 de teste, TEAMS_TEST_TO deve ser diferente de M365_SENDER_UPN.")
        return 1

    print("1) Obtendo token...")
    token = get_token(tenant_id, client_id, client_secret)
    print("OK token obtido")

    print(f"2) Buscando usuário por email: {test_user_email}")
    user_resp = graph_get(
        f"https://graph.microsoft.com/v1.0/users/{test_user_email}?$select=id,displayName,userPrincipalName",
        token,
    )
    print(f"HTTP users: {user_resp.status_code}")
    if user_resp.status_code != 200:
        print(user_resp.text)
        return 2

    user_data = user_resp.json()
    user_id = user_data["id"]
    print("OK usuário encontrado:", user_data.get("displayName"), "|", user_data.get("userPrincipalName"))

    print(f"2.1) Buscando usuário remetente: {sender_upn}")
    sender_resp = graph_get(
        f"https://graph.microsoft.com/v1.0/users/{sender_upn}?$select=id,displayName,userPrincipalName",
        token,
    )
    print(f"HTTP sender: {sender_resp.status_code}")
    if sender_resp.status_code != 200:
        print(sender_resp.text)
        return 2

    sender_data = sender_resp.json()
    sender_id = sender_data["id"]
    print("OK remetente encontrado:", sender_data.get("displayName"), "|", sender_data.get("userPrincipalName"))

    print("3) Tentando criar chat 1:1 (teste de permissão Teams)")
    payload = {
        "chatType": "oneOnOne",
        "members": [
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{sender_id}')",
            },
            {
                "@odata.type": "#microsoft.graph.aadUserConversationMember",
                "roles": ["owner"],
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{user_id}')",
            }
        ],
    }

    chat_resp = graph_post("https://graph.microsoft.com/v1.0/chats", token, payload)
    print(f"HTTP chats: {chat_resp.status_code}")

    if chat_resp.status_code in (200, 201, 202):
        chat_data = chat_resp.json()
        chat_id = chat_data.get("id")

        print("OK: chat 1:1 criado/encontrado.")
        print(json.dumps(chat_data, indent=2, ensure_ascii=False))

        if not chat_id:
            print("Falha: chat criado sem ID retornado.")
            return 4

        print("4) Enviando mensagem de teste no chat...")
        message_payload = {
            "body": {
                "contentType": "text",
                "content": test_message,
            }
        }
        msg_resp = graph_post(
            f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages",
            token,
            message_payload,
        )
        print(f"HTTP messages: {msg_resp.status_code}")

        if msg_resp.status_code in (200, 201, 202):
            print("OK: mensagem enviada com sucesso no Teams.")
            print(json.dumps(msg_resp.json(), indent=2, ensure_ascii=False))
            return 0

        print("Falha ao enviar mensagem no Teams:")
        print(msg_resp.text)
        return 5

    print("Falha no teste Teams (esperado se faltarem permissões):")
    print(chat_resp.text)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
