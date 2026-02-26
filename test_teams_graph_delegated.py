import json
import os
import time

import msal
import requests
from dotenv import load_dotenv


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
    client_id = str(os.getenv("M365_DELEGATED_CLIENT_ID", "")).strip() or str(os.getenv("M365_CLIENT_ID", "")).strip()
    test_user_email = str(os.getenv("TEAMS_TEST_TO", "")).strip()

    if not all([tenant_id, client_id, test_user_email]):
        print("Defina no .env: M365_TENANT_ID, M365_CLIENT_ID (ou M365_DELEGATED_CLIENT_ID) e TEAMS_TEST_TO")
        return 1

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scopes = [
        "https://graph.microsoft.com/User.Read",
        "https://graph.microsoft.com/Chat.ReadWrite",
        "https://graph.microsoft.com/ChatMessage.Send",
    ]

    print("1) Iniciando autenticação Delegated (Device Code)...")
    app = msal.PublicClientApplication(client_id=client_id, authority=authority)
    flow = app.initiate_device_flow(scopes=scopes)

    if "user_code" not in flow:
        print("Falha ao iniciar Device Code:")
        print(json.dumps(flow, indent=2, ensure_ascii=False))
        return 2

    print(flow.get("message"))
    print("Aguardando login/consentimento...")

    result = app.acquire_token_by_device_flow(flow)
    token = result.get("access_token")
    if not token:
        print("Falha ao obter token Delegated:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 3

    print("OK token Delegated obtido")
    print("Scopes concedidos:", result.get("scope", "(não informado)"))

    print(f"2) Buscando usuário destino: {test_user_email}")
    user_resp = graph_get(
        f"https://graph.microsoft.com/v1.0/users/{test_user_email}?$select=id,displayName,userPrincipalName",
        token,
    )
    print(f"HTTP users: {user_resp.status_code}")
    if user_resp.status_code != 200:
        print(user_resp.text)
        return 4

    user_data = user_resp.json()
    target_id = user_data["id"]
    print("OK destino:", user_data.get("displayName"), "|", user_data.get("userPrincipalName"))

    print("2.1) Identificando usuário logado (/me)")
    me_resp = graph_get("https://graph.microsoft.com/v1.0/me?$select=id,displayName,userPrincipalName", token)
    print(f"HTTP me: {me_resp.status_code}")
    if me_resp.status_code != 200:
        print(me_resp.text)
        return 5

    me_data = me_resp.json()
    sender_id = me_data["id"]
    sender_upn = str(me_data.get("userPrincipalName", "")).strip()
    print("OK remetente:", me_data.get("displayName"), "|", sender_upn)

    if sender_upn.lower() == test_user_email.lower():
        print("TEAMS_TEST_TO deve ser diferente do usuário logado no Device Code.")
        return 6

    print("3) Criando/obtendo chat 1:1")
    chat_payload = {
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
                "user@odata.bind": f"https://graph.microsoft.com/v1.0/users('{target_id}')",
            },
        ],
    }

    chat_resp = graph_post("https://graph.microsoft.com/v1.0/chats", token, chat_payload)
    print(f"HTTP chats: {chat_resp.status_code}")
    if chat_resp.status_code not in (200, 201):
        print(chat_resp.text)
        return 7

    chat_data = chat_resp.json()
    chat_id = chat_data.get("id")
    print("OK chat:", chat_id)

    print("4) Enviando mensagem de teste")
    now_txt = time.strftime("%d/%m/%Y %H:%M:%S")
    msg_payload = {
        "body": {
            "contentType": "text",
            "content": f"[TESTE DELEGATED] Mensagem enviada via Graph no dia {now_txt}.",
        }
    }

    msg_resp = graph_post(f"https://graph.microsoft.com/v1.0/chats/{chat_id}/messages", token, msg_payload)
    print(f"HTTP messages: {msg_resp.status_code}")

    if msg_resp.status_code in (200, 201):
        print("OK mensagem enviada no Teams com Delegated.")
        print(json.dumps(msg_resp.json(), indent=2, ensure_ascii=False))
        return 0

    print("Falha ao enviar mensagem:")
    print(msg_resp.text)
    return 8


if __name__ == "__main__":
    raise SystemExit(main())
