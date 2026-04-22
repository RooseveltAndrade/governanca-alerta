import argparse
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from services.envio_email import enviar_email


def _parse_destinatarios(valor: str) -> list[str]:
    destinatarios = []
    vistos = set()
    for item in str(valor or "").split(","):
        email = item.strip()
        if not email or "@" not in email:
            continue
        chave = email.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        destinatarios.append(email)
    return destinatarios


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--recipients-env", default="RUNNER_ALERT_EMAIL_RECIPIENTS")
    args = parser.parse_args()

    destinatarios = _parse_destinatarios(os.getenv(args.recipients_env, ""))
    if not destinatarios:
        fallback = os.getenv("CONTACT_ROOSEVELT_EMAIL", "")
        destinatarios = _parse_destinatarios(fallback)

    if not destinatarios:
        return 1

    log_path = Path(args.log_file)
    try:
        log_conteudo = log_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        log_conteudo = f"Não foi possível ler o log {log_path}: {exc}"


    # Tenta extrair o traceback ou a última exceção do log
    resumo_erro = ""
    linhas_log = log_conteudo.splitlines()
    trecho_erro = []
    in_traceback = False
    for linha in linhas_log[::-1]:  # Percorre de trás pra frente
        if 'Traceback (most recent call last):' in linha:
            in_traceback = True
        if in_traceback or linha.strip().startswith('TimeoutError') or linha.strip().startswith('Exception') or linha.strip().startswith('ERRO'):
            trecho_erro.insert(0, linha)
        if in_traceback and linha.strip() == '':
            break
    if trecho_erro:
        resumo_erro = '\n'.join(trecho_erro[-10:])  # Mostra as últimas 10 linhas do erro
    else:
        # Se não achou traceback, pega as últimas 10 linhas do log
        resumo_erro = '\n'.join(linhas_log[-10:])

    corpo = (
        f"A execução automática falhou.\n\n"
        f"Resumo do erro:\n{resumo_erro}\n\n"
        f"Mensagem recebida: {args.message}\n"
        f"EntryPoint/Log: {log_path}\n\n"
        "Conteúdo completo do log:\n"
        f"{log_conteudo}"
    )

    resumo_html = resumo_erro.replace("\t", "    ")
    log_html = log_conteudo.replace("\t", "    ")
    corpo_html = (
        "<div style='font-family:Arial, sans-serif; font-size:16px; color:#1a1a1a; line-height:1.4;'>"
        "<p><strong>A execução automática falhou.</strong></p>"
        "<p><strong>Resumo do erro:</strong></p>"
        f"<pre style='background:#f4f4f4; padding:10px; border:1px solid #ddd; white-space:pre-wrap;'>{resumo_html}</pre>"
        f"<p><strong>Mensagem recebida:</strong> {args.message}</p>"
        f"<p><strong>EntryPoint/Log:</strong> {log_path}</p>"
        "<p><strong>Conteúdo completo do log:</strong></p>"
        f"<pre style='background:#f4f4f4; padding:10px; border:1px solid #ddd; white-space:pre-wrap;'>{log_html}</pre>"
        "</div>"
    )

    ok = enviar_email(
        destinatarios,
        args.subject,
        corpo,
        corpo_html=corpo_html,
        suppress_failure_alert=True,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())