from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from dotenv import load_dotenv
import os
import re
import shutil
import time

from selenium.common.exceptions import ElementNotInteractableException


class PortalGPS:

    LOGIN_URL = "https://portal.gpssa.com.br/gps/login.aspx"

    def __init__(self, fast_mode=True):
        load_dotenv()

        self.username = os.getenv("PORTAL_USER")
        self.password = os.getenv("PORTAL_PASS")

        self.fast_mode = fast_mode
        self.driver = None
        self.wait = None
        self.planilhas_dir = os.path.abspath(os.path.join(os.getcwd(), "planilhas"))
        os.makedirs(self.planilhas_dir, exist_ok=True)
        self._normalizar_estrutura_planilhas()
        self.download_dir = self._garantir_diretorio_download()

    # =====================================================
    # 🔹 INICIALIZAÇÃO
    # =====================================================

    def iniciar_driver(self):
        options = Options()
        options.add_argument("--start-maximized")
        print(f"Download dir: {self.download_dir}")

        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
        }
        options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        self.wait = WebDriverWait(
            self.driver,
            12 if self.fast_mode else 20
        )

    def encerrar(self):
        if self.driver:
            self.driver.quit()

    # =====================================================
    # 🔹 UTILIDADES
    # =====================================================

    def js_click(self, element):
        self.driver.execute_script("arguments[0].click();", element)

    def wait_visible_enabled_element(self, by, value, timeout=20):
        def _resolver(driver):
            for elemento in driver.find_elements(by, value):
                try:
                    if elemento.is_displayed() and elemento.is_enabled():
                        return elemento
                except Exception:
                    continue
            return False

        return WebDriverWait(self.driver, timeout).until(_resolver)

    def preencher_input(self, element, value):
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});",
            element,
        )

        try:
            element.click()
        except Exception:
            pass

        try:
            element.clear()
            element.send_keys(value)
            return
        except ElementNotInteractableException:
            pass

        self.driver.execute_script(
            "arguments[0].focus();"
            "arguments[0].value = '';"
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
            "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
            element,
            value,
        )

    def wait_loading_mask(self, timeout=20):
        try:
            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class,'x-mask-msg')]")
                )
            )
        except Exception:
            pass

    def save_debug_screenshot(self, name):
        if self.fast_mode:
            return
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(self.download_dir, f"debug_{name}_{ts}.png")
        self.driver.save_screenshot(path)
        print(f"Screenshot salvo: {path}")

    # =====================================================
    # 🔹 LOGIN
    # =====================================================

    def login(self):
        print("Acessando página de login...")
        self.driver.get(self.LOGIN_URL)

        self.wait.until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )

        self.wait_loading_mask(timeout=10)

        user_input = self.wait_visible_enabled_element(
            By.ID,
            "txtUsername-inputEl",
            timeout=20,
        )

        pass_input = self.wait_visible_enabled_element(
            By.ID,
            "txtPassword-inputEl",
            timeout=20,
        )

        print("Preenchendo credenciais...")
        self.preencher_input(user_input, self.username)

        self.preencher_input(pass_input, self.password)
        pass_input.send_keys(Keys.RETURN)

        print("Aguardando redirecionamento...")
        self.wait.until(EC.url_contains("Portal.aspx"))

        print("✅ Login realizado com sucesso!")

    # =====================================================
    # 🔹 IFRAME HANDLER
    # =====================================================

    def switch_to_frame_with_xpath(self, xpath, timeout=5):
        self.driver.switch_to.default_content()

        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            return True
        except Exception:
            pass

        frames = self.driver.find_elements(By.TAG_NAME, "iframe")

        for idx, frame in enumerate(frames):
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame(frame)
            try:
                WebDriverWait(self.driver, 2).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                print(f"Elemento encontrado no iframe #{idx}")
                return True
            except Exception:
                continue

        self.driver.switch_to.default_content()
        return False

    # =====================================================
    # 🔹 MENU EXTJS
    # =====================================================

    def click_tree_item(self, text, expand_only=False):

        safe_text = text.replace("'", "\"")

        node_xpath = (
            "//span[contains(@class,'x-tree-node-text') and "
            f"contains(normalize-space(), '{safe_text}')]"
        )

        node = self.wait.until(
            EC.presence_of_element_located((By.XPATH, node_xpath))
        )

        self.driver.execute_script("arguments[0].scrollIntoView(true);", node)
        time.sleep(0.2 if self.fast_mode else 0.5)

        try:
            row = node.find_element(By.XPATH, "./ancestor::tr[1]")
            expander = row.find_element(
                By.XPATH, ".//img[contains(@class,'x-tree-ec-icon')]"
            )
            self.js_click(expander)
        except Exception:
            pass

        if not expand_only:
            self.js_click(node)

    def click_tree_child(self, parent_text, child_text):
        safe_parent = parent_text.replace("'", "\"")
        safe_child = child_text.replace("'", "\"")

        parent_xpath = (
            "//span[contains(@class,'x-tree-node-text') and "
            f"contains(normalize-space(), '{safe_parent}')]/ancestor::tr[1]"
        )
        parent_row = self.wait.until(
            EC.presence_of_element_located((By.XPATH, parent_xpath))
        )
        self.driver.execute_script("arguments[0].scrollIntoView(true);", parent_row)
        time.sleep(0.2 if self.fast_mode else 0.5)

        child_xpath = (
            "//span[contains(@class,'x-tree-node-text') and "
            f"contains(normalize-space(), '{safe_child}')]"
        )

        for _ in range(3 if self.fast_mode else 5):
            try:
                WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.XPATH, child_xpath))
                )
                break
            except Exception:
                pass

            try:
                expander = parent_row.find_element(
                    By.XPATH, ".//img[contains(@class,'x-tree-ec-icon')]"
                )
                ActionChains(self.driver).move_to_element(expander).click().perform()
                time.sleep(0.3 if self.fast_mode else 0.8)
                continue
            except Exception:
                pass

            try:
                parent_text_el = parent_row.find_element(
                    By.XPATH, ".//span[contains(@class,'x-tree-node-text')]"
                )
                ActionChains(self.driver).move_to_element(
                    parent_text_el
                ).double_click().perform()
                time.sleep(0.3 if self.fast_mode else 0.8)
            except Exception:
                pass

        child = self.wait.until(EC.presence_of_element_located((By.XPATH, child_xpath)))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", child)
        time.sleep(0.2 if self.fast_mode else 0.5)
        self.js_click(child)

    # =====================================================
    # 🔹 EXPORTAÇÃO
    # =====================================================

    def click_pendentes(self):
        def try_click():
            return self.driver.execute_script(
                """
                const labels = Array.from(document.querySelectorAll('label'));
                const label = labels.find(l => l.textContent.trim().toUpperCase() === 'PENDENTES');
                if (!label) return false;
                const input = label.control || label.previousElementSibling || label.nextElementSibling;
                if (input && input.tagName === 'INPUT') {
                    input.click();
                } else {
                    label.click();
                }
                return true;
                """
            )

        self.driver.switch_to.default_content()
        try:
            if try_click():
                return True
        except Exception:
            pass

        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        for idx, frame in enumerate(frames):
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame(frame)
            try:
                if try_click():
                    print(f"Clique rápido PENDENTES no iframe #{idx}")
                    self.driver.switch_to.default_content()
                    return True
            except Exception:
                pass

        self.driver.switch_to.default_content()
        return False

    def click_excel(self):
        def try_click():
            return self.driver.execute_script(
                """
                const spans = Array.from(document.querySelectorAll('span'));
                const span = spans.find(s => s.textContent.trim() === 'Excel');
                if (!span) return false;
                let btn = span.closest('a,button,div');
                if (btn) btn.click();
                else span.click();
                return true;
                """
            )

        self.driver.switch_to.default_content()
        try:
            if try_click():
                return True
        except Exception:
            pass

        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        for idx, frame in enumerate(frames):
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame(frame)
            try:
                if try_click():
                    print(f"Clique rápido Excel no iframe #{idx}")
                    self.driver.switch_to.default_content()
                    return True
            except Exception:
                pass

        self.driver.switch_to.default_content()
        return False

    def wait_download_complete(self, timeout=60):
        seconds = 0
        exts = (".xlsx", ".xls", ".csv")
        while seconds < timeout:
            files = os.listdir(self.download_dir)
            has_file = any(f.lower().endswith(exts) for f in files)
            has_partial = any(f.endswith(".crdownload") for f in files)
            if has_file and not has_partial:
                newest = max(
                    (f for f in files if f.lower().endswith(exts)),
                    key=lambda f: os.path.getmtime(os.path.join(self.download_dir, f)),
                    default=None,
                )
                print(f"Download concluído: {newest}")
                return newest
            time.sleep(1)
            seconds += 1
        print("Arquivos na pasta após timeout:", os.listdir(self.download_dir))
        raise TimeoutError("Download não finalizou no tempo esperado.")

    def _mes_pt(self, dt):
        meses = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
        return meses[dt.tm_mon - 1]

    def _garantir_diretorio_download(self, data_ref=None):
        data_ref = data_ref or time.localtime()
        ano = time.strftime("%Y", data_ref)
        mes = self._mes_pt(data_ref)
        dia = time.strftime("%d-%m-%Y", data_ref)
        destino_dir = os.path.join(self.planilhas_dir, ano, mes, dia)
        os.makedirs(destino_dir, exist_ok=True)
        return destino_dir

    def _extrair_data_do_nome_arquivo(self, filename):
        match = re.search(r"(\d{2})-(\d{2})-(\d{4})", filename)
        if not match:
            return None

        dia, mes, ano = match.groups()
        try:
            return time.strptime(f"{dia}-{mes}-{ano}", "%d-%m-%Y")
        except ValueError:
            return None

    def _resolver_conflito_destino(self, destino):
        if not os.path.exists(destino):
            return destino

        base, ext = os.path.splitext(destino)
        contador = 1
        while True:
            candidato = f"{base}_{contador}{ext}"
            if not os.path.exists(candidato):
                return candidato
            contador += 1

    def _mesclar_diretorio(self, origem, destino):
        os.makedirs(destino, exist_ok=True)
        for item in os.listdir(origem):
            origem_item = os.path.join(origem, item)
            destino_item = os.path.join(destino, item)

            if os.path.isdir(origem_item):
                self._mesclar_diretorio(origem_item, destino_item)
                if os.path.isdir(origem_item) and not os.listdir(origem_item):
                    os.rmdir(origem_item)
                continue

            destino_item = self._resolver_conflito_destino(destino_item)
            shutil.move(origem_item, destino_item)

        if os.path.isdir(origem) and not os.listdir(origem):
            os.rmdir(origem)

    def _normalizar_estrutura_planilhas(self):
        ano_atual = time.strftime("%Y")
        ano_dir = os.path.join(self.planilhas_dir, ano_atual)
        os.makedirs(ano_dir, exist_ok=True)
        meses = {"jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"}
        extensoes = (".xlsx", ".xls", ".csv")

        for item in os.listdir(self.planilhas_dir):
            origem = os.path.join(self.planilhas_dir, item)

            if item == ano_atual:
                continue

            if os.path.isdir(origem) and item.lower() in meses:
                destino_mes = os.path.join(ano_dir, item.lower())
                self._mesclar_diretorio(origem, destino_mes)
                continue

            if os.path.isfile(origem) and item.lower().startswith("criacaousuario") and item.lower().endswith(extensoes):
                data_arquivo = self._extrair_data_do_nome_arquivo(item)
                if not data_arquivo:
                    data_arquivo = time.localtime(os.path.getmtime(origem))
                destino_dir = self._garantir_diretorio_download(data_arquivo)
                destino = os.path.join(destino_dir, item)

                if os.path.exists(destino):
                    if os.path.getsize(origem) == os.path.getsize(destino):
                        os.remove(origem)
                        continue
                    destino = self._resolver_conflito_destino(destino)

                shutil.move(origem, destino)

    def _organizar_download(self, filename):
        if not filename:
            return None

        origem = os.path.join(self.download_dir, filename)
        data_arquivo = self._extrair_data_do_nome_arquivo(filename) or time.localtime()
        destino_dir = self._garantir_diretorio_download(data_arquivo)
        destino = os.path.join(destino_dir, filename)

        if os.path.abspath(origem) == os.path.abspath(destino):
            return destino

        try:
            destino = self._resolver_conflito_destino(destino)
            shutil.move(origem, destino)
            print(f"Arquivo movido para: {destino}")
            return destino  # ✅ caminho final completo
        except Exception as e:
            print(f"Erro ao mover arquivo: {e}")
            return None

    # =====================================================
    # 🔹 FLUXO COMPLETO
    # =====================================================

    def exportar_relatorio_pendentes(self):

        print("Abrindo menu Controle de Acesso...")

        menu_xpath = (
            "//span[contains(@class,'x-tree-node-text') and "
            "contains(normalize-space(),'Controle de Acesso')]"
        )

        if not self.switch_to_frame_with_xpath(menu_xpath):
            raise Exception("Menu não encontrado")

        self.click_tree_item("Controle de Acesso", expand_only=True)

        time.sleep(1)

        print("Clicando em Concessão de acesso...")
        try:
            self.click_tree_child(
                "Controle de Acesso",
                "Concessão de acesso Genérico e Privilegiado",
            )
        except Exception:
            self.click_tree_child("Controle de Acesso", "Concessão de acesso")

        time.sleep(2)

        print("Clicando em PENDENTES...")
        self.click_pendentes()
        self.wait_loading_mask()

        time.sleep(2)

        print("Clicando em Excel...")
        self.click_excel()

        print("✅ Exportação acionada!")

        arquivos_antes = set(os.listdir(self.download_dir))

        # remove arquivos antigos do mesmo relatório para garantir download novo
        for f in list(arquivos_antes):
            if f.lower().startswith("criacaousuario") and f.lower().endswith((".xls", ".xlsx")):
                try:
                    os.remove(os.path.join(self.download_dir, f))
                except Exception:
                    pass

        filename = self.wait_download_complete(timeout=90)
        caminho_final = self._organizar_download(filename)

        if not caminho_final:
            raise Exception("Não foi possível organizar o arquivo baixado.")

        return caminho_final  # ✅ retorna caminho final

    # =====================================================
    # 🔹 EXECUÇÃO
    # =====================================================

    def executar(self):
        try:
            self.iniciar_driver()
            self.login()
            caminho_final = self.exportar_relatorio_pendentes()
            return caminho_final  # ✅ retorna para ser usado depois (ler planilha / enviar emails)
        finally:
            self.encerrar()


if __name__ == "__main__":
    portal = PortalGPS(fast_mode=True)
    caminho = portal.executar()
    print("✅ Caminho final do arquivo:", caminho)
