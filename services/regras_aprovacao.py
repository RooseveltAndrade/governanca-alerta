def identificar_destinatario(linha):
    status = str(linha.get("STATUS ATUAL", "")).upper()

    if status == "PENDENTE GOVERNANÇA":
        return [
            "lucas@email.com",
            "laisa@email.com",
            "kleyton@email.com"
        ]

    elif status == "PENDENTE LIDER":
        lider = linha.get("LIDER USUARIO DO ACESSO")
        if lider:
            return [f"{lider.lower().replace(' ', '.')}@empresa.com"]

    elif status == "PENDENTE DIRETORIA":
        return [
            "bahia@empresa.com",
            "adriana@empresa.com"
        ]

    elif status == "APROVAÇÃO ÁREA RESPONSÁVEL":
        responsavel = linha.get("USUÁRIO RESPONSÁVEL")
        if responsavel:
            return [f"{responsavel.lower().replace(' ', '.')}@empresa.com"]

    return []
