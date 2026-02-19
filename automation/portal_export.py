import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

load_dotenv()



LOGIN_URL = "https://portal.gpssa.com.br/gps/login.aspx"
EXPORT_URL = "https://portal.gpssa.com.br/RAR/ToExcel/SpreadsHeetGearExcel"

USERNAME = os.getenv("PORTAL_USER")
PASSWORD = os.getenv("PORTAL_PASS")

print("USER:", USERNAME)
print("PASS carregada:", "SIM" if PASSWORD else "NÃO")

def exportar_relatorio():
    session = requests.Session()

    # 1️⃣ Acessa página de login
    response = session.get(LOGIN_URL)
    soup = BeautifulSoup(response.text, "html.parser")

    print("---- INPUTS ENCONTRADOS ----")
    for input_tag in soup.find_all("input"):
        print(input_tag.get("name"))


    viewstate = soup.find(id="__VIEWSTATE")["value"]
    viewstate_generator = soup.find(id="__VIEWSTATEGENERATOR")["value"]

    event_validation = soup.find(id="__EVENTVALIDATION")

    print("Tem EVENTVALIDATION?", "SIM" if event_validation else "NÃO")

    # 2️⃣ Faz login
    payload = {
        "user": USERNAME,
        "pass": PASSWORD,
        "__EVENTTARGET": "Manager1",
        "__EVENTARGUMENT": "btnLogin|event|Click",
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": viewstate_generator,
    }

    login_response = session.post(LOGIN_URL, data=payload)

    if "login" in login_response.url.lower():
        print("❌ Falha no login")
        return

    print("✅ Login realizado com sucesso")

    # 3️⃣ Exporta relatório
    params = {
        "NomeArquivo": "CriacaoUsuario",
        "NomeViewModel": "RAR.ViewModels.CriacaoUsuario.CadastroChamadoResult"
    }

    export_response = session.post(EXPORT_URL, params=params)

    with open("relatorio.xlsx", "wb") as f:
        f.write(export_response.content)

    print("✅ Relatório salvo como relatorio.xlsx")


if __name__ == "__main__":
    exportar_relatorio()
