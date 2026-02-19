import pandas as pd


def carregar_planilha(caminho_arquivo):
	df = pd.read_excel(caminho_arquivo)
	df.columns = df.columns.str.strip()
	return df
