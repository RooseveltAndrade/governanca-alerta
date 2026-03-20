from __future__ import annotations

from pathlib import Path
import unicodedata

import pandas as pd


def _norm_col(s: str) -> str:
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.upper()
    s = " ".join(s.split())
    return s


def _encontrar_coluna(df: pd.DataFrame, *candidatas: str) -> str | None:
    mapa = {_norm_col(col): col for col in df.columns}
    for candidata in candidatas:
        col_real = mapa.get(_norm_col(candidata))
        if col_real:
            return col_real
    return None


def carregar_planilha_desligamentos(caminho_arquivo: str | Path) -> pd.DataFrame:
    caminho = Path(caminho_arquivo)
    df = pd.read_excel(caminho)
    df.columns = [_norm_col(c) for c in df.columns]
    return df


def validar_colunas_desligamentos(df: pd.DataFrame) -> dict[str, str]:
    colunas = {
        "status_atual": _encontrar_coluna(df, "STATUS ATUAL"),
        "status_folha": _encontrar_coluna(df, "STATUS FOLHA"),
        "contrato": _encontrar_coluna(df, "CONTRATO"),
        "tipo_usuario": _encontrar_coluna(df, "TIPO USUARIO", "TIPO USUÁRIO"),
        "lider_usuario": _encontrar_coluna(df, "LIDER USUARIO DO ACESSO", "LIDER USUÁRIO DO ACESSO"),
        "usuario_acesso": _encontrar_coluna(df, "USUARIO DO ACESSO", "USUÁRIO DO ACESSO"),
        "acesso": _encontrar_coluna(df, "ACESSO"),
        "sistema": _encontrar_coluna(df, "SISTEMA"),
        "id": _encontrar_coluna(df, "ID"),
    }

    faltantes = [nome for nome, coluna in colunas.items() if coluna is None and nome in {"status_atual", "status_folha", "contrato", "tipo_usuario", "lider_usuario", "id"}]
    if faltantes:
        raise ValueError(
            "Planilha de desligamentos sem colunas obrigatórias: "
            f"{', '.join(faltantes)}. Colunas atuais: {', '.join(str(c) for c in df.columns)}"
        )

    return {k: v for k, v in colunas.items() if v is not None}


def classificar_motivo_atuacao(df: pd.DataFrame) -> pd.Series:
    colunas = validar_colunas_desligamentos(df)

    status_atual = df[colunas["status_atual"]].fillna("").astype(str).str.strip().str.upper()
    status_folha = df[colunas["status_folha"]].fillna("").astype(str).str.strip().str.upper()
    tipo_usuario = df[colunas["tipo_usuario"]].fillna("").astype(str).str.strip().str.upper()
    contrato = df[colunas["contrato"]].fillna("").astype(str).str.strip().str.upper()

    motivo = pd.Series("", index=df.index, dtype="object")
    motivo.loc[(status_atual == "ATIVO") & (status_folha == "DESLIGADO")] = "status_folha_desligado"
    motivo.loc[(status_atual == "ATIVO") & (tipo_usuario == "TERCEIRO") & (contrato == "CANCELADO")] = "contrato_cancelado_terceiro"
    return motivo


def filtrar_desligados_ativos(df: pd.DataFrame) -> pd.DataFrame:
    motivo = classificar_motivo_atuacao(df)
    df_filtrado = df.loc[motivo != ""].copy()
    df_filtrado["MOTIVO_ATUACAO"] = motivo.loc[df_filtrado.index]
    return df_filtrado


def resumir_desligados(df_filtrado: pd.DataFrame) -> dict[str, object]:
    if df_filtrado.empty:
        return {"total": 0, "tipos_usuario": {}}

    coluna_tipo = _encontrar_coluna(df_filtrado, "TIPO USUARIO", "TIPO USUÁRIO")
    tipos = (
        df_filtrado[coluna_tipo]
        .fillna("")
        .astype(str)
        .str.strip()
        .value_counts()
        .to_dict()
        if coluna_tipo
        else {}
    )

    return {
        "total": int(len(df_filtrado)),
        "tipos_usuario": tipos,
    }