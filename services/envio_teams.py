import atexit
import json
import logging
import os
from pathlib import Path

import msal
import requests


GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = [
    "User.Read",
    "Chat.ReadWrite",
    "ChatMessage.Send",
]

CACHE_DIR = Path(".auth_cache")
CACHE_FILE = CACHE_DIR / "teams_token_cache.bin"

_TOKEN_CACHE = None
_SENDER_CACHE = None
_USER_CACHE: dict[str, dict] = {}


def _as_bool(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "sim")


def _limpar_destinatarios(destinatarios: list[str]) -> list[str]:
    limpos = []
    vistos = set()

    for destinatario in destinatarios or []:
        if not destinatario:
            continue

        destinatario = str(destinatario).strip()
        if not destinatario or "@" not in destinatario:
            continue

        chave = destinatario.lower()
        if chave in vistos:
            continue

        vistos.add(chave)
        limpos.append(destinatario)

    return limpos


def _parse_destinatarios_env(valor: str) -> list[str]:
    return _limpar_destinatarios([item.strip() for item in str(valor or "").split(",")])


def teams_habilitado() -> bool:
    return _as_bool(os.getenv("ENABLE_TEAMS_ALERTS", "False"), False)


def _load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()

    if CACHE_FILE.exists():
        cache.deserialize(CACHE_FILE.read_text(encoding="utf-8"))

    def save_cache() -> None:
        if cache.has_state_changed:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(cache.serialize(), encoding="utf-8")

    atexit.register(save_cache)
    return cache


def _get_token_delegado() -> str | None:
    global _TOKEN_CACHE

    if _TOKEN_CACHE:
        return _TOKEN_CACHE

    tenant_id = str(os.getenv("M365_TENANT_ID", "")).strip()
    client_id = str(os.getenv("M365_CLIENT_ID", "")).strip()
    expected_upn = str(os.getenv("M365_SENDER_UPN", "")).strip()

    if not all([tenant_id, client_id, expected_upn]):
        logging.error(
            "Teams: configuração incompleta. Defina M365_TENANT_ID, M365_CLIENT_ID e M365_SENDER_UPN."
        )
        return None

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
        token_cache=_load_cache(),
    )

    contas = app.get_accounts(username=expected_upn)
    if contas:
        result = app.acquire_token_silent(SCOPES, account=contas[0])
        if result and "access_token" in result:
            _TOKEN_CACHE = result["access_token"]
            return _TOKEN_CACHE

    todas_contas = app.get_accounts()
    if todas_contas:
        result = app.acquire_token_silent(SCOPES, account=todas_contas[0])
        if result and "access_token" in result:
            _TOKEN_CACHE = result["access_token"]
            return _TOKEN_CACHE

    permitir_interativo = _as_bool(os.getenv("TEAMS_ALLOW_INTERACTIVE_LOGIN", "False"), False)
    if not permitir_interativo:
        logging.error(
            "Teams: token delegado indisponível no cache. Rode test_teams_graph.py ou ative TEAMS_ALLOW_INTERACTIVE_LOGIN=True para autenticar manualmente."
        )
        return None

    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        logging.error(f"Teams: falha ao iniciar device flow: {flow}")
        return None

    logging.info(flow.get("message", "Teams: autenticação device flow iniciada."))
    result = app.acquire_token_by_device_flow(flow)
    token = result.get("access_token")
    if not token:
        logging.error(f"Teams: falha ao obter token delegado: {json.dumps(result, ensure_ascii=False)}")
        return None

    _TOKEN_CACHE = token
    return token


def _graph_get(url: str, token: str) -> requests.Response:
    return requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )


def _graph_post(url: str, token: str, payload: dict) -> requests.Response:
    return requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )


def _resolver_usuario(token: str, email: str) -> dict | None:
    chave = email.lower()
    if chave in _USER_CACHE:
        return _USER_CACHE[chave]

    resposta = _graph_get(
        f"{GRAPH_BASE}/users/{email}?$select=id,displayName,userPrincipalName",
        token,
    )
    if resposta.status_code != 200:
        logging.error(f"Teams: falha ao resolver usuário {email}: HTTP {resposta.status_code} | {resposta.text}")
        return None

    dados = resposta.json()
    _USER_CACHE[chave] = dados
    return dados


def _resolver_remetente(token: str) -> dict | None:
    global _SENDER_CACHE

    if _SENDER_CACHE:
        return _SENDER_CACHE

    sender_upn = str(os.getenv("M365_SENDER_UPN", "")).strip()
    if not sender_upn:
        logging.error("Teams: M365_SENDER_UPN não configurado.")
        return None

    _SENDER_CACHE = _resolver_usuario(token, sender_upn)
    return _SENDER_CACHE


def _obter_chat_1x1(token: str, sender_id: str, target_id: str) -> str | None:
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

    resposta = _graph_post(f"{GRAPH_BASE}/chats", token, payload)
    if resposta.status_code not in (200, 201, 202):
        logging.error(f"Teams: falha ao criar/obter chat 1:1: HTTP {resposta.status_code} | {resposta.text}")
        return None

    chat_id = resposta.json().get("id")
    if not chat_id:
        logging.error("Teams: chat 1:1 retornado sem id.")
        return None

    return chat_id


def enviar_mensagem_teams(destinatarios: list[str], mensagem: str, content_type: str = "text") -> bool:
    if not teams_habilitado():
        return True

    destinatarios = _limpar_destinatarios(destinatarios)

    safe_test_to = _parse_destinatarios_env(os.getenv("TEAMS_SAFE_TEST_TO", ""))
    if safe_test_to:
        destinatarios = safe_test_to
        logging.info("TEAMS_SAFE_TEST_TO ativo: redirecionando mensagem para destinatário de teste.")

    if not destinatarios:
        logging.warning("Teams: lista de destinatários vazia.")
        return False

    if _as_bool(os.getenv("DRY_RUN", "False"), False):
        logging.info(f"[DRY_RUN] Não enviou Teams. To={destinatarios}")
        return True

    token = _get_token_delegado()
    if not token:
        return False

    remetente = _resolver_remetente(token)
    if not remetente:
        return False

    sender_id = remetente.get("id")
    if not sender_id:
        logging.error("Teams: remetente sem id retornado pelo Graph.")
        return False

    sucesso = True
    for destinatario in destinatarios:
        usuario = _resolver_usuario(token, destinatario)
        if not usuario:
            sucesso = False
            continue

        target_id = usuario.get("id")
        if not target_id:
            logging.error(f"Teams: destinatário {destinatario} sem id retornado pelo Graph.")
            sucesso = False
            continue

        chat_id = _obter_chat_1x1(token, sender_id, target_id)
        if not chat_id:
            sucesso = False
            continue

        payload = {
            "body": {
                "contentType": content_type,
                "content": mensagem,
            }
        }
        resposta = _graph_post(f"{GRAPH_BASE}/chats/{chat_id}/messages", token, payload)
        if resposta.status_code not in (200, 201, 202):
            logging.error(
                f"Teams: falha ao enviar mensagem para {destinatario}: HTTP {resposta.status_code} | {resposta.text}"
            )
            sucesso = False
            continue

        logging.info(f"Teams enviado para {destinatario}")

    return sucesso