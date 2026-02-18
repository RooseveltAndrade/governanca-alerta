def identificar_destinatario(linha):
    etapa = str(linha.get("STATUS ATUAL", "")).upper()
    status_validacao = str(linha.get("STATUS VALIDAÇÃO", "")).upper()

    # Só envia se estiver pendente ou em andamento
    if status_validacao not in ["PENDENTE", "EM ANDAMENTO"]:
        return []

    if "DIRETORIA DE SISTEMAS" in etapa:
        return ["bahia@empresa.com"]

    elif "DIRETORIA DE APOIO" in etapa:
        return ["adriana@empresa.com"]

    elif "LIDER" in etapa:
        lider = linha.get("LIDER USUARIO DO ACESSO")
        if lider:
            return [f"{lider.lower().replace(' ', '.')}@empresa.com"]

    elif "GOVERNANÇA" in etapa:
        return [
            "lucas@empresa.com",
            "laisa@empresa.com",
            "kleyton@empresa.com"
        ]

    elif "ÁREA RESPONSÁVEL" in etapa:
        responsavel = linha.get("USUÁRIO RESPONSÁVEL")
        if responsavel:
            return [f"{responsavel.lower().replace(' ', '.')}@empresa.com"]

    return []
