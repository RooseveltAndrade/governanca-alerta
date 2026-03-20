from __future__ import annotations

from pathlib import Path
import argparse

from services.diretorio_acessos import DiretorioAcessos
from services.leitura_desligamentos import (
    carregar_planilha_desligamentos,
    filtrar_desligados_ativos,
    resumir_desligados,
    validar_colunas_desligamentos,
)
from services.regras_desligamentos import (
    identificar_destinatarios_desligamento,
    obter_destinatarios_sem_casos_desligamentos,
    obter_destinatarios_sumario_desligamentos,
)


def _encontrar_ultima_planilha() -> Path | None:
    base = Path("planilhas")
    arquivos = sorted(base.glob("**/IntegracaoDesligamentos-*.xls*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return arquivos[0] if arquivos else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arquivo", default="")
    parser.add_argument("--limite", type=int, default=10)
    args = parser.parse_args()

    caminho = Path(args.arquivo) if args.arquivo else _encontrar_ultima_planilha()
    if not caminho or not caminho.exists():
        print("Nenhuma planilha IntegracaoDesligamentos encontrada.")
        return 1

    print(f"Arquivo analisado: {caminho}")
    df = carregar_planilha_desligamentos(caminho)
    colunas = validar_colunas_desligamentos(df)
    print("Colunas validadas:")
    for chave, coluna in colunas.items():
        print(f"- {chave}: {coluna}")

    df_filtrado = filtrar_desligados_ativos(df)
    resumo = resumir_desligados(df_filtrado)

    print(f"Total de linhas na planilha: {len(df)}")
    print(
        "Total elegível "
        "(STATUS ATUAL = ATIVO e STATUS FOLHA = DESLIGADO "
        "ou STATUS ATUAL = ATIVO, TIPO = TERCEIRO e CONTRATO = CANCELADO): "
        f"{resumo['total']}"
    )
    if resumo["tipos_usuario"]:
        print("Totais por tipo de usuário:")
        for tipo, qtd in resumo["tipos_usuario"].items():
            print(f"- {tipo}: {qtd}")

    if not df_filtrado.empty:
        diretorio_acessos = DiretorioAcessos("data/Equipe Solucionadora.xlsx")
        print("Prévia dos registros elegíveis com destinatários resolvidos por canal:")
        preview = df_filtrado.head(args.limite).copy()
        preview["REGRA_DESTINO"] = preview.apply(
            lambda linha: identificar_destinatarios_desligamento(linha, diretorio_acessos)["regra"],
            axis=1,
        )
        preview["EMAIL_DESTINATARIOS"] = preview.apply(
            lambda linha: ", ".join(identificar_destinatarios_desligamento(linha, diretorio_acessos)["destinatarios_email"]),
            axis=1,
        )
        preview["TEAMS_DESTINATARIOS"] = preview.apply(
            lambda linha: ", ".join(identificar_destinatarios_desligamento(linha, diretorio_acessos)["destinatarios_teams"]),
            axis=1,
        )
        colunas_preview = [
            colunas.get("id"),
            colunas.get("tipo_usuario"),
            colunas.get("usuario_acesso"),
            colunas.get("lider_usuario"),
            colunas.get("contrato"),
            colunas.get("acesso"),
            colunas.get("sistema"),
            colunas.get("status_atual"),
            colunas.get("status_folha"),
            "MOTIVO_ATUACAO",
            "REGRA_DESTINO",
            "EMAIL_DESTINATARIOS",
            "TEAMS_DESTINATARIOS",
        ]
        colunas_preview = [c for c in colunas_preview if c]
        print(preview[colunas_preview].to_string(index=False))
    else:
        destinatarios_sem_casos = obter_destinatarios_sem_casos_desligamentos()
        print("Sem casos elegíveis para atuação. Destinatários previstos para o aviso de ausência de casos:")
        print(f"- Email: {', '.join(destinatarios_sem_casos['email'])}")
        print(f"- Teams: {', '.join(destinatarios_sem_casos['teams'])}")

    destinatarios_sumario = obter_destinatarios_sumario_desligamentos()
    print("Destinatários previstos para o sumário de desligamentos:")
    print(f"- Email: {', '.join(destinatarios_sumario['email'])}")
    print(f"- Teams: {', '.join(destinatarios_sumario['teams'])}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())