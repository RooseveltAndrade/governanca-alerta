import pandas as pd
import unicodedata


def _norm_text(v: str) -> str:
    """
    Normaliza texto para bater chaves:
    - remove acentos
    - trim
    - colapsa espaços
    - upper
    """
    s = str(v or "").strip()
    if not s:
        return ""

    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = " ".join(s.split())
    return s.upper()


def _norm_email(v: str) -> str:
    s = str(v or "").strip().lower()
    return s if ("@" in s and "." in s) else ""


class DiretorioAcessos:
    """
    Lê 1 arquivo Excel com 2 abas:
    - ACESSO: colunas esperadas -> ACESSO / E-mail Equipe / E-mail Líder
      - LIDERES: colunas esperadas -> Líder / E-mail Líder

    Uso:
      dir = DiretorioAcessos("data/Equipe Solucionadora.xlsx")
      email = dir.email_por_acesso("OFFICE365 GRSA")
      email = dir.email_por_lider("Wesley dos Santos Pereira")
    """

    def __init__(self, caminho_xlsx: str):
        self.caminho_xlsx = caminho_xlsx

        self._map_acesso_email: dict[str, str] = {}
        self._map_acesso_origem: dict[str, str] = {}
        self._map_acesso_lider_email: dict[str, str] = {}
        self._map_lider_email: dict[str, str] = {}

        self._carregar()

    def _carregar(self):
        xls = pd.ExcelFile(self.caminho_xlsx)

        # =========================
        # ABA: ACESSO
        # =========================
        if "ACESSO" not in xls.sheet_names:
            raise ValueError("Aba 'ACESSO' não encontrada no arquivo.")

        df_acesso = pd.read_excel(xls, sheet_name="ACESSO")
        df_acesso.columns = [str(c).strip() for c in df_acesso.columns]

        col_acesso = "ACESSO"
        col_email_equipe = "E-mail Equipe"
        col_email_lider = "E-mail Líder"

        if col_acesso not in df_acesso.columns:
            raise ValueError(
                "Aba 'ACESSO' precisa ter a coluna 'ACESSO'."
            )

        if col_email_equipe not in df_acesso.columns and col_email_lider not in df_acesso.columns:
            raise ValueError(
                "Aba 'ACESSO' precisa ter ao menos uma das colunas: 'E-mail Equipe' ou 'E-mail Líder'."
            )

        for _, row in df_acesso.iterrows():
            acesso = _norm_text(row.get(col_acesso))
            email_equipe = _norm_email(row.get(col_email_equipe)) if col_email_equipe in df_acesso.columns else ""
            email_lider = _norm_email(row.get(col_email_lider)) if col_email_lider in df_acesso.columns else ""
            email = email_equipe or email_lider
            if acesso and email:
                self._map_acesso_email[acesso] = email
                self._map_acesso_origem[acesso] = "equipe" if email_equipe else "lider"
            if acesso and email_lider:
                self._map_acesso_lider_email[acesso] = email_lider

        # =========================
        # ABA: LIDERES
        # =========================
        if "LIDERES" not in xls.sheet_names:
            raise ValueError("Aba 'LIDERES' não encontrada no arquivo.")

        df_lideres = pd.read_excel(xls, sheet_name="LIDERES")
        df_lideres.columns = [str(c).strip() for c in df_lideres.columns]

        col_lider = "Líder"
        col_email_lider = "E-mail Líder"

        if col_lider not in df_lideres.columns or col_email_lider not in df_lideres.columns:
            raise ValueError(
                "Aba 'LIDERES' precisa ter as colunas: 'Líder' e 'E-mail Líder'."
            )

        for _, row in df_lideres.iterrows():
            lider = _norm_text(row.get(col_lider))
            email = _norm_email(row.get(col_email_lider))
            if lider and email:
                self._map_lider_email[lider] = email

    # =========================
    # Consultas
    # =========================
    def email_por_acesso(self, acesso: str) -> str:
        return self._map_acesso_email.get(_norm_text(acesso), "")

    def origem_email_por_acesso(self, acesso: str) -> str:
        return self._map_acesso_origem.get(_norm_text(acesso), "")

    def email_lider_por_acesso(self, acesso: str) -> str:
        return self._map_acesso_lider_email.get(_norm_text(acesso), "")

    def email_por_lider(self, lider: str) -> str:
        return self._map_lider_email.get(_norm_text(lider), "")

    def debug_stats(self) -> dict:
        return {
            "qtd_acessos": len(self._map_acesso_email),
            "qtd_lideres": len(self._map_lider_email),
        }