import logging
import os

from dotenv import load_dotenv

from main import _montar_corpo_agregado
from services.envio_email import enviar_email


def main() -> int:
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    safe_test_to = str(os.getenv("SAFE_TEST_TO", "")).strip()
    test_to = str(os.getenv("TEST_TO", "")).strip()
    destinatario = safe_test_to or test_to

    if not destinatario:
        logging.error("Defina SAFE_TEST_TO ou TEST_TO no .env.")
        return 1 

    assunto = "[TESTE] Envio de email"
    itens_teste = [
        {
            "id": "0000",
            "status": "PENDENTE LIDER",
            "tipo_usuario": "GENÉRICO",
            "usuario_acesso": "USUARIO TESTE",
            "acesso": "PORTAL",
            "sistema": "GPS",
        }
    ]
    corpo, corpo_html, inline_attachments = _montar_corpo_agregado(itens_teste)

    ok = enviar_email(
        [destinatario],
        assunto,
        corpo,
        corpo_html=corpo_html,
        inline_attachments=inline_attachments,
    )
    logging.info("Resultado do envio: %s", ok)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())