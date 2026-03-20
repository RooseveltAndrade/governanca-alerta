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

    corpo = (
        f"A execução automática falhou.\n\n"
        f"Mensagem: {args.message}\n"
        f"EntryPoint/Log: {log_path}\n\n"
        "Conteúdo do log:\n"
        f"{log_conteudo}"
    )

    ok = enviar_email(
        destinatarios,
        args.subject,
        corpo,
        suppress_failure_alert=True,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())