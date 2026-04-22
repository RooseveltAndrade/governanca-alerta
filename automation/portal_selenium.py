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
import unicodedata

from selenium.common.exceptions import ElementNotInteractableException


class PortalGPS:

    LOGIN_URL = "https://portal.gpssa.com.br/gps/login.aspx"

    def __init__(self, fast_mode=True, filtro_exportacao="PENDENTES", prefixo_arquivo="CriacaoUsuario", download_timeout=90):
        load_dotenv()

        self.username = os.getenv("PORTAL_USER")
        self.password = os.getenv("PORTAL_PASS")

        self.fast_mode = fast_mode
        self.filtro_exportacao = str(filtro_exportacao or "PENDENTES").strip().upper()
        self.prefixo_arquivo = str(prefixo_arquivo or "CriacaoUsuario").strip()
        self.download_timeout = int(download_timeout or 90)
        self._prefixos_conhecidos = {"CriacaoUsuario", "IntegracaoDesligamentos", self.prefixo_arquivo}
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

    def _input_has_value(self, element) -> bool:
        try:
            value = self.driver.execute_script("return arguments[0].value;", element)
        except Exception:
            value = None
        return bool(str(value or "").strip())

    def _click_login_button(self) -> bool:
        try:
            btn = self.driver.find_element(By.XPATH, "//button[normalize-space()='Entrar']")
            if btn.is_displayed() and btn.is_enabled():
                self.js_click(btn)
                return True
        except Exception:
            pass
        return False

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
        if not self._input_has_value(pass_input):
            self.driver.execute_script(
                "arguments[0].value = arguments[1];"
                "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
                "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
                pass_input,
                self.password,
            )

        if not self._click_login_button():
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

    def _build_tab_click_script(self):
        return r"""
                const candidatos = Array.isArray(arguments[0]) ? arguments[0] : [arguments[0]];
                const normalize = (value) => String(value || '')
                    .normalize('NFD')
                    .replace(/\p{Diacritic}/gu, '')
                    .trim()
                    .toUpperCase();
                const candidatosNorm = candidatos.map(normalize).filter(Boolean);
                const spans = Array.from(document.querySelectorAll('span'));
                const alvo = spans.find(el => {
                    const texto = normalize(el.textContent);
                    return candidatosNorm.some(c => texto === c || texto.includes(c));
                });
                if (!alvo) return false;
                let btn = alvo.closest('a,li,div');
                if (btn) btn.click();
                else alvo.click();
                return true;
                """

    def click_tab(self, nomes: list[str]) -> bool:
        def try_click():
            return self.driver.execute_script(self._build_tab_click_script(), nomes)

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
                    print(f"Aba ativa no iframe #{idx}")
                    self.driver.switch_to.default_content()
                    return True
            except Exception:
                pass

        self.driver.switch_to.default_content()
        return False

    def _build_filter_click_script(self):
        return r"""
                const labels = Array.from(document.querySelectorAll('label'));
                const filtros = Array.isArray(arguments[0]) ? arguments[0] : [arguments[0]];
                const normalize = (value) => String(value || '')
                    .normalize('NFD')
                    .replace(/\p{Diacritic}/gu, '')
                    .trim()
                    .toUpperCase();
                const filtrosNorm = filtros.map(normalize).filter(Boolean);
                let label = labels.find(l => {
                    const texto = normalize(l.textContent);
                    return filtrosNorm.some(f => texto === f);
                });
                if (!label) {
                    label = labels.find(l => {
                        const texto = normalize(l.textContent);
                        return filtrosNorm.some(f => texto.includes(f));
                    });
                }
                if (!label) return false;
                const input = label.control
                    || label.querySelector('input')
                    || label.previousElementSibling
                    || label.nextElementSibling;
                if (input && input.tagName === 'INPUT') {
                    input.click();
                    if (!input.checked) {
                        input.checked = true;
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                    return input.checked === true;
                }
                label.click();
                return true;
                """

    def click_filtro(self, nome_filtro):
        filtro = str(nome_filtro or "").strip().upper()

        def _norm_text(value: str) -> str:
            s = str(value or "").strip()
            if not s:
                return ""
            s = unicodedata.normalize("NFKD", s)
            s = "".join(ch for ch in s if not unicodedata.combining(ch))
            return s.upper()

        candidatos = [filtro]
        normalizado = _norm_text(filtro)
        if normalizado and normalizado not in candidatos:
            candidatos.append(normalizado)

        def try_click():
            return self.driver.execute_script(
                self._build_filter_click_script(),
                candidatos,
            )

        def try_click_xpath():
            xpath_exato = f"//label[normalize-space()='{filtro}']"
            xpath_parcial = f"//label[contains(normalize-space(), '{filtro}') ]"
            for xp in (xpath_exato, xpath_parcial):
                try:
                    labels = self.driver.find_elements(By.XPATH, xp)
                except Exception:
                    labels = []
                for label in labels:
                    try:
                        if not label.is_displayed():
                            continue
                        self.js_click(label)
                        return True
                    except Exception:
                        continue
            return False

        def is_selected() -> bool:
            try:
                return bool(self.driver.execute_script(
                    "const f = String(arguments[0] || '').trim().toUpperCase();"
                    "const normalize = (value) => String(value || '')"
                    ".normalize('NFD').replace(/\\p{Diacritic}/gu, '')"
                    ".trim().toUpperCase();"
                    "const labels = Array.from(document.querySelectorAll('label'));"
                    "const label = labels.find(l => normalize(l.textContent) === normalize(f));"
                    "if (!label) return false;"
                    "const input = label.control || label.querySelector('input') || label.previousElementSibling || label.nextElementSibling;"
                    "return !!(input && input.checked);",
                    filtro,
                ))
            except Exception:
                return False

        def try_click_and_check() -> bool:
            if try_click() or try_click_xpath():
                return is_selected()
            return False

        self.driver.switch_to.default_content()
        try:
            if try_click_and_check():
                return True
        except Exception:
            pass

        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        for idx, frame in enumerate(frames):
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame(frame)
            try:
                if try_click_and_check():
                    print(f"Clique rápido {filtro} no iframe #{idx}")
                    self.driver.switch_to.default_content()
                    return True
            except Exception:
                pass

        self.driver.switch_to.default_content()
        return False

    def click_pendentes(self):
        return self.click_filtro("PENDENTES")

    def click_todos(self):
        return self.click_filtro("TODOS")

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

    def wait_download_complete(self, timeout=60, existing_files=None):
        seconds = 0
        exts = (".xlsx", ".xls", ".csv")
        arquivos_existentes = set(existing_files or [])
        while seconds < timeout:
            files = os.listdir(self.download_dir)
            arquivos_novos = [f for f in files if f.lower().endswith(exts) and f not in arquivos_existentes]
            has_file = any(arquivos_novos)
            has_partial = any(f.endswith(".crdownload") for f in files)
            if has_file and not has_partial:
                newest = max(
                    arquivos_novos,
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

    def _arquivo_eh_relatorio(self, nome_arquivo):
        nome_normalizado = str(nome_arquivo or "").lower()
        return any(nome_normalizado.startswith(prefixo.lower()) for prefixo in self._prefixos_conhecidos)

    def _arquivo_eh_relatorio_atual(self, nome_arquivo):
        nome_normalizado = str(nome_arquivo or "").lower()
        return nome_normalizado.startswith(self.prefixo_arquivo.lower())

    def _renomear_prefixo_arquivo(self, filename, data_arquivo=None):
        base, ext = os.path.splitext(filename)
        match = re.search(r"(\d{2}-\d{2}-\d{4}(?: \d{2}#\d{2})?)", base)
        if match:
            return f"{self.prefixo_arquivo}-{match.group(1)}{ext}"

        data_arquivo = data_arquivo or time.localtime()
        data_formatada = time.strftime("%d-%m-%Y %H#%M", data_arquivo)
        return f"{self.prefixo_arquivo}-{data_formatada}{ext}"

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

            if os.path.isfile(origem) and self._arquivo_eh_relatorio(item) and item.lower().endswith(extensoes):
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
        nome_final = self._renomear_prefixo_arquivo(filename, data_arquivo)
        destino_dir = self._garantir_diretorio_download(data_arquivo)
        destino = os.path.join(destino_dir, nome_final)

        if os.path.abspath(origem) == os.path.abspath(destino):
            return destino

        destino = self._resolver_conflito_destino(destino)

        for tentativa in range(10):
            try:
                shutil.move(origem, destino)
                print(f"Arquivo movido para: {destino}")
                return destino  # ✅ caminho final completo
            except Exception as e:
                if tentativa == 9:
                    print(f"Erro ao mover arquivo: {e}")
                    return None
                time.sleep(1)

    # =====================================================
    # 🔹 FLUXO COMPLETO
    # =====================================================

    def exportar_relatorio(self):

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

        # Garante que a aba correta esteja ativa antes de clicar nos filtros.
        self.click_tab([
            "Solicitação Genérico e Privilegiado",
            "Solicitacao Generico e Privilegiado",
            "Concessão de acesso Genérico e Privilegiado",
            "Concessao de acesso Generico e Privilegiado",
        ])

        print(f"Clicando em {self.filtro_exportacao}...")
        if not self.click_filtro(self.filtro_exportacao):
            raise Exception(f"Filtro {self.filtro_exportacao} não encontrado")
        self.wait_loading_mask()

        time.sleep(2)

        arquivos_antes = set(os.listdir(self.download_dir))

        # remove relatorios antigos para garantir download novo
        for f in list(arquivos_antes):
            if self._arquivo_eh_relatorio(f) and f.lower().endswith((".xls", ".xlsx", ".csv")):
                try:
                    os.remove(os.path.join(self.download_dir, f))
                except Exception:
                    pass

        arquivos_antes = set(os.listdir(self.download_dir))

        print("Clicando em Excel...")
        self.click_excel()

        print("✅ Exportação acionada!")

        filename = self.wait_download_complete(timeout=self.download_timeout, existing_files=arquivos_antes)
        caminho_final = self._organizar_download(filename)

        if not caminho_final:
            raise Exception("Não foi possível organizar o arquivo baixado.")

        return caminho_final  # ✅ retorna caminho final

    def exportar_relatorio_pendentes(self):
        return self.exportar_relatorio()

    # =====================================================
    # 🔹 EXECUÇÃO
    # =====================================================

    def executar(self):
        try:
            self.iniciar_driver()
            self.login()
            caminho_final = self.exportar_relatorio()
            return caminho_final  # ✅ retorna para ser usado depois (ler planilha / enviar emails)
        finally:
            self.encerrar()


if __name__ == "__main__":
    portal = PortalGPS(fast_mode=True)
    caminho = portal.executar()
    print("✅ Caminho final do arquivo:", caminho)
