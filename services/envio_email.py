import os
import ssl
import base64
import smtplib
import logging
import requests
import msal
from email.message import EmailMessage

from config import email_config


def _as_bool(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "y", "sim")


def _limpar_destinatarios(destinatarios: list[str]) -> list[str]:
    # remove vazios, "não encontrado", espaços, duplicados
    limpos = []
    vistos = set()

    for d in destinatarios or []:
        if not d:
            continue
        d = str(d).strip()
        if not d:
            continue
        if d.lower() in ("não encontrado", "nao encontrado", "none", "null"):
            continue
        if "@" not in d:
            continue

        key = d.lower()
        if key in vistos:
            continue

        vistos.add(key)
        limpos.append(d)

    return limpos


def _enviar_email_outlook(
    destinatarios: list[str],
    assunto: str,
    corpo: str,
    corpo_html: str | None = None,
    inline_attachments: list[dict] | None = None,
) -> bool:
    """
    Envio local via Outlook Desktop (Windows).
    Requer Outlook instalado e conta logada no perfil do usuário.
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        logging.error(
            "Pacote 'pywin32' não encontrado para envio via Outlook local. "
            "Instale com: pip install pywin32"
        )
        return False

    try:
        pythoncom.CoInitialize()

        try:
            outlook = win32com.client.gencache.EnsureDispatch("Outlook.Application")
        except Exception:
            outlook = win32com.client.Dispatch("Outlook.Application")

        mail = outlook.CreateItem(0)
        mail.To = "; ".join(destinatarios)
        mail.Subject = assunto
        # Adiciona Reply-To para o grupo
        mail.ReplyRecipients.Add("infraregional@gpssa.com.br")
        if corpo_html:
            html_final = corpo_html
            for item in inline_attachments or []:
                cid = str(item.get("cid", "")).strip()
                content_type = str(item.get("content_type", "application/octet-stream"))
                data = item.get("data", b"")
                if not cid or not data:
                    continue
                data_b64 = base64.b64encode(data).decode("ascii")
                html_final = html_final.replace(
                    f"cid:{cid}",
                    f"data:{content_type};base64,{data_b64}",
                )
            mail.HTMLBody = html_final
        else:
            mail.Body = corpo
        mail.Send()
        logging.info(f"Email enviado via Outlook local -> {destinatarios}")
        return True

    except Exception as e:
        logging.error(
            "Erro no envio via Outlook local. "
            "Valide se é o Outlook Desktop clássico (não o Novo Outlook), "
            "se a conta está logada e se a sessão do usuário está ativa."
        )
        logging.error(f"Detalhe: {e}")
        return False

    finally:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass


def _enviar_email_graph(
    destinatarios: list[str],
    assunto: str,
    corpo: str,
    corpo_html: str | None = None,
    inline_attachments: list[dict] | None = None,
) -> bool:
    tenant_id = str(os.getenv("M365_TENANT_ID", "")).strip()
    client_id = str(os.getenv("M365_CLIENT_ID", "")).strip()
    client_secret = str(os.getenv("M365_CLIENT_SECRET", "")).strip()

    sender_upn = str(os.getenv("M365_SENDER_UPN", "")).strip()
    if not sender_upn:
        sender_upn = str(os.getenv("DEFAULT_FROM_EMAIL", email_config.DEFAULT_FROM_EMAIL)).strip()

    if not all([tenant_id, client_id, client_secret, sender_upn]):
        logging.error(
            "Configuração Graph incompleta. Defina M365_TENANT_ID, M365_CLIENT_ID, "
            "M365_CLIENT_SECRET e M365_SENDER_UPN (ou DEFAULT_FROM_EMAIL)."
        )
        return False

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scopes = ["https://graph.microsoft.com/.default"]

    try:
        app = msal.ConfidentialClientApplication(
            client_id=client_id,
            authority=authority,
            client_credential=client_secret,
        )
        token_result = app.acquire_token_for_client(scopes=scopes)
        access_token = token_result.get("access_token")
        if not access_token:
            logging.error(f"Falha ao obter token Graph: {token_result}")
            return False

        url = f"https://graph.microsoft.com/v1.0/users/{sender_upn}/sendMail"
        payload = {
            "message": {
                "subject": assunto,
                "body": {
                    "contentType": "HTML" if corpo_html else "Text",
                    "content": corpo_html if corpo_html else corpo,
                },
                "toRecipients": [
                    {"emailAddress": {"address": d}} for d in destinatarios
                ],
                "replyTo": [
                    {"emailAddress": {"address": "infraregional@gpssa.com.br"}}
                ],
            },
            "saveToSentItems": True,
        }

        if inline_attachments:
            payload["message"]["attachments"] = []
            for item in inline_attachments:
                cid = str(item.get("cid", "")).strip()
                name = str(item.get("name", "inline.bin")).strip() or "inline.bin"
                content_type = str(item.get("content_type", "application/octet-stream"))
                data = item.get("data", b"")
                if not cid or not data:
                    continue
                payload["message"]["attachments"].append(
                    {
                        "@odata.type": "#microsoft.graph.fileAttachment",
                        "name": name,
                        "contentType": content_type,
                        "contentBytes": base64.b64encode(data).decode("ascii"),
                        "isInline": True,
                        "contentId": cid,
                    }
                )

        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        if response.status_code == 202:
            # logging.info(f"Email enviado via Graph -> {destinatarios}")
            return True

        logging.error(
            f"Erro Graph sendMail: HTTP {response.status_code} | {response.text}"
        )
        return False

    except Exception as e:
        logging.exception(f"Erro inesperado no envio via Graph: {e}")
        return False


def enviar_email(
    destinatarios: list[str],
    assunto: str,
    corpo: str,
    corpo_html: str | None = None,
    inline_attachments: list[dict] | None = None,
) -> bool:
    """
    Envia email via SMTP.
    Retorna True se enviou, False se não enviou.
    Levanta exceção apenas em erro inesperado.
    """

    destinatarios = _limpar_destinatarios(destinatarios)

    safe_test_to = str(os.getenv("SAFE_TEST_TO", "")).strip()
    if safe_test_to:
        destinatarios = [safe_test_to]
        logging.info("SAFE_TEST_TO ativo: redirecionando envio para destinatário de teste.")

    if not destinatarios:
        logging.warning("enviar_email: lista de destinatários vazia (após limpeza).")
        return False

    provider = str(os.getenv("EMAIL_PROVIDER", "smtp")).strip().lower()

    smtp_server = os.getenv("SMTP_SERVER", email_config.SMTP_SERVER)
    smtp_port = int(os.getenv("SMTP_PORT", str(email_config.SMTP_PORT)))

    use_tls = _as_bool(os.getenv("SMTP_USE_TLS", str(email_config.SMTP_USE_TLS)), True)
    use_ssl = _as_bool(os.getenv("SMTP_USE_SSL", str(email_config.SMTP_USE_SSL)), False)

    username = os.getenv("SMTP_USERNAME", email_config.SMTP_USERNAME)
    password = os.getenv("SMTP_PASSWORD", email_config.SMTP_PASSWORD)

    from_email = os.getenv("DEFAULT_FROM_EMAIL", email_config.DEFAULT_FROM_EMAIL)

    dry_run = _as_bool(os.getenv("DRY_RUN", "False"), False)
    if dry_run:
        logging.info(
            f"[DRY_RUN] Não enviou email. To={destinatarios} | Subject={assunto}"
        )
        return True

    if provider == "graph":
        return _enviar_email_graph(
            destinatarios,
            assunto,
            corpo,
            corpo_html=corpo_html,
            inline_attachments=inline_attachments,
        )

    if provider == "outlook":
        return _enviar_email_outlook(
            destinatarios,
            assunto,
            corpo,
            corpo_html=corpo_html,
            inline_attachments=inline_attachments,
        )

    if not username or not password:
        logging.error("SMTP_USERNAME/SMTP_PASSWORD não configurados no .env")
        return False

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = from_email
    msg["To"] = ", ".join(destinatarios)
    msg.set_content(corpo)
    if corpo_html:
        msg.add_alternative(corpo_html, subtype="html")
        if inline_attachments:
            html_part = msg.get_payload()[-1]
            for item in inline_attachments:
                cid = str(item.get("cid", "")).strip()
                content_type = str(item.get("content_type", "application/octet-stream"))
                data = item.get("data", b"")
                if not cid or not data:
                    continue
                try:
                    maintype, subtype = content_type.split("/", 1)
                except ValueError:
                    maintype, subtype = "application", "octet-stream"
                html_part.add_related(
                    data,
                    maintype=maintype,
                    subtype=subtype,
                    cid=f"<{cid}>",
                )

    try:
        # SSL (465) OU TLS (587)
        if use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=60) as server:
                server.login(username, password)
                server.send_message(msg)

        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=60) as server:
                server.ehlo()
                if use_tls:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                server.login(username, password)
                server.send_message(msg)

        logging.info(f"Email enviado com sucesso -> {destinatarios}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logging.error(
            "Falha de autenticação SMTP. "
            "Possíveis causas: senha errada, SMTP AUTH bloqueado, MFA exigindo App Password.",
        )
        logging.error(f"Detalhe: {e}")
        return False

    except smtplib.SMTPException as e:
        logging.error(f"Erro SMTP ao enviar email: {e}")
        return False

    except Exception as e:
        logging.exception(f"Erro inesperado ao enviar email: {e}")
        return False