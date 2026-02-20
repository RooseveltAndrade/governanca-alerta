import pandas as pd
import unicodedata

def _norm_col(s: str) -> str:
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.upper()
    s = " ".join(s.split())
    return s

def carregar_planilha(caminho_arquivo: str) -> pd.DataFrame:
    df = pd.read_excel(caminho_arquivo)
    df.columns = [_norm_col(c) for c in df.columns]
    return df
