import pandas as pd
import unicodedata


def normalizar_nome(nome: str) -> str:
    nome = str(nome or "").strip()
    nome = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    nome = " ".join(nome.split()).upper()
    return nome


class DiretorioEmails:
    def __init__(self, caminho_planilha_emails: str, col_nome="NOME", col_email="EMAIL"):
        df = pd.read_excel(caminho_planilha_emails)
        df.columns = [c.strip().upper() for c in df.columns]

        col_nome = col_nome.upper()
        col_email = col_email.upper()

        if col_nome not in df.columns or col_email not in df.columns:
            raise ValueError(f"Planilha de emails precisa ter colunas {col_nome} e {col_email}. Colunas atuais: {list(df.columns)}")

        df[col_nome] = df[col_nome].apply(normalizar_nome)
        df[col_email] = df[col_email].astype(str).str.strip().str.lower()

        # dicionário nome_normalizado -> email
        self._map = dict(zip(df[col_nome], df[col_email]))

    def obter_email(self, nome: str) -> str | None:
        chave = normalizar_nome(nome)
        return self._map.get(chave)
