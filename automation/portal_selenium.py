from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from dotenv import load_dotenv
import os
import time

load_dotenv()

USERNAME = os.getenv("PORTAL_USER")
PASSWORD = os.getenv("PORTAL_PASS")

LOGIN_URL = "https://portal.gpssa.com.br/gps/login.aspx"
FAST_MODE = True


def js_click(driver, element):
    driver.execute_script("arguments[0].click();", element)


def switch_to_frame_with_xpath(driver, wait, xpath, timeout=5):
    driver.switch_to.default_content()
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        return True
    except Exception:
        pass

    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(frames):
        driver.switch_to.default_content()
        driver.switch_to.frame(frame)
        try:
            WebDriverWait(driver, 2 if FAST_MODE else 4).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            print(f"Elemento encontrado no iframe #{idx}")
            return True
        except Exception:
            continue

    driver.switch_to.default_content()
    return False


def click_tree_item(driver, wait, text, expand_only=False):
    safe_text = text.replace("'", "\"")
    node_xpath = (
        "//span[contains(@class,'x-tree-node-text') and "
        f"contains(normalize-space(), '{safe_text}')]"
    )
    node = wait.until(EC.presence_of_element_located((By.XPATH, node_xpath)))
    driver.execute_script("arguments[0].scrollIntoView(true);", node)
    time.sleep(0.2 if FAST_MODE else 0.5)

    # tenta expandir usando o ícone de expander, se existir
    try:
        row = node.find_element(By.XPATH, "./ancestor::tr[1]")
        expander = row.find_element(
            By.XPATH, ".//img[contains(@class,'x-tree-ec-icon')]"
        )
        js_click(driver, expander)
        time.sleep(0.2 if FAST_MODE else 0.5)
    except Exception:
        pass

    if not expand_only:
        js_click(driver, node)
        time.sleep(0.2 if FAST_MODE else 0.5)
def log_tree_nodes(driver):
    nodes = driver.find_elements(By.XPATH, "//span[contains(@class,'x-tree-node-text')]")
    print("\n=== NÓS DA ÁRVORE VISÍVEIS ===")
    for n in nodes:
        texto = n.text.strip()
        if texto:
            print("NODE:", texto)


def click_tree_child(driver, wait, parent_text, child_text):
    safe_parent = parent_text.replace("'", "\"")
    safe_child = child_text.replace("'", "\"")
    parent_xpath = (
        "//span[contains(@class,'x-tree-node-text') and "
        f"contains(normalize-space(), '{safe_parent}')]/ancestor::tr[1]"
    )
    parent_row = wait.until(EC.presence_of_element_located((By.XPATH, parent_xpath)))
    driver.execute_script("arguments[0].scrollIntoView(true);", parent_row)
    time.sleep(0.2 if FAST_MODE else 0.5)

    child_xpath = (
        "//span[contains(@class,'x-tree-node-text') and "
        f"contains(normalize-space(), '{safe_child}')]"
    )

    # garante expandido (tenta múltiplas vezes até aparecer o filho)
    for _ in range(3 if FAST_MODE else 5):
        try:
            WebDriverWait(driver, 1).until(
                EC.presence_of_element_located((By.XPATH, child_xpath))
            )
            break
        except Exception:
            pass

        try:
            expander = parent_row.find_element(
                By.XPATH, ".//img[contains(@class,'x-tree-ec-icon')]"
            )
            ActionChains(driver).move_to_element(expander).click().perform()
            time.sleep(0.3 if FAST_MODE else 0.8)
            continue
        except Exception:
            pass

        try:
            parent_text_el = parent_row.find_element(
                By.XPATH, ".//span[contains(@class,'x-tree-node-text')]"
            )
            ActionChains(driver).move_to_element(parent_text_el).double_click().perform()
            time.sleep(0.3 if FAST_MODE else 0.8)
        except Exception:
            pass

    child = wait.until(EC.presence_of_element_located((By.XPATH, child_xpath)))
    driver.execute_script("arguments[0].scrollIntoView(true);", child)
    time.sleep(0.2 if FAST_MODE else 0.5)
    js_click(driver, child)


def click_by_any_xpath(driver, wait, xpaths, timeout=10):
    last_err = None
    for xp in xpaths:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            time.sleep(0.2 if FAST_MODE else 0.5)
            js_click(driver, el)
            return True
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        raise last_err
    return False


def click_by_any_xpath_anywhere(driver, xpaths, timeout=10):
    last_err = None
    driver.switch_to.default_content()

    # tenta no contexto principal
    for xp in xpaths:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            time.sleep(0.2 if FAST_MODE else 0.5)
            js_click(driver, el)
            return True
        except Exception as exc:
            last_err = exc

    # tenta em iframes
    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(frames):
        driver.switch_to.default_content()
        driver.switch_to.frame(frame)
        for xp in xpaths:
            try:
                el = WebDriverWait(driver, timeout).until(
                    EC.element_to_be_clickable((By.XPATH, xp))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", el)
                time.sleep(0.2 if FAST_MODE else 0.5)
                js_click(driver, el)
                print(f"Clique encontrado no iframe #{idx}")
                driver.switch_to.default_content()
                return True
            except Exception as exc:
                last_err = exc
                continue

    driver.switch_to.default_content()
    if last_err:
        raise last_err
    return False


def wait_loading_mask(driver, timeout=20):
    try:
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class,'x-mask-msg') and contains(.,'Carregando')]")
            )
        )
    except Exception:
        pass


def save_debug_screenshot(driver, name):
    if FAST_MODE:
        return
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(os.getcwd(), "planilhas", f"debug_{name}_{ts}.png")
    driver.save_screenshot(path)
    print(f"Screenshot salvo: {path}")


def click_pendentes_fast(driver):
    def try_click():
        return driver.execute_script(
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

    driver.switch_to.default_content()
    try:
        if try_click():
            return True
    except Exception:
        pass

    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(frames):
        driver.switch_to.default_content()
        driver.switch_to.frame(frame)
        try:
            if try_click():
                print(f"Clique rápido PENDENTES no iframe #{idx}")
                driver.switch_to.default_content()
                return True
        except Exception:
            pass

    driver.switch_to.default_content()
    return False


def click_excel_fast(driver):
    def try_click():
        return driver.execute_script(
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

    driver.switch_to.default_content()
    try:
        if try_click():
            return True
    except Exception:
        pass

    frames = driver.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(frames):
        driver.switch_to.default_content()
        driver.switch_to.frame(frame)
        try:
            if try_click():
                print(f"Clique rápido Excel no iframe #{idx}")
                driver.switch_to.default_content()
                return True
        except Exception:
            pass

    driver.switch_to.default_content()
    return False

def testar_login():
    options = Options()
    options.add_argument("--start-maximized")

    download_dir = os.path.abspath(os.path.join(os.getcwd(), "planilhas"))
    os.makedirs(download_dir, exist_ok=True)
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    wait = WebDriverWait(driver, 12 if FAST_MODE else 20)

    # 🔹 Acessa página de login
    print("Acessando página de login...")
    driver.get(LOGIN_URL)

    # 🔹 Localiza campos
    print("Localizando campos...")
    user_input = wait.until(
        EC.presence_of_element_located((By.ID, "txtUsername-inputEl"))
    )

    pass_input = wait.until(
        EC.presence_of_element_located((By.ID, "txtPassword-inputEl"))
    )

    # 🔹 Preenche credenciais
    print("Preenchendo credenciais...")
    user_input.clear()
    user_input.send_keys(USERNAME)

    pass_input.clear()
    pass_input.send_keys(PASSWORD)

    # 🔥 Login via ENTER (necessário para ExtJS)
    pass_input.send_keys(Keys.RETURN)

    # 🔹 Aguarda redirecionamento
    print("Aguardando redirecionamento...")
    wait.until(EC.url_contains("Portal.aspx"))

    print("✅ Login realizado com sucesso!")
    print("URL atual:", driver.current_url)

    time.sleep(1 if FAST_MODE else 3)

    # 🔎 DEBUG: listar textos visíveis após login
    if not FAST_MODE:
        print("\n=== ELEMENTOS VISÍVEIS APÓS LOGIN ===")
        elementos = driver.find_elements(By.XPATH, "//*[text()]")
        for el in elementos:
            texto = el.text.strip()
            if texto:
                print("TEXTO:", texto)

    # =====================================================
    # 🔹 ABRINDO MENU CONTROLE DE ACESSO (EXTJS TREE)
    # =====================================================

    print("\nTentando abrir menu Controle de Acesso...")

    menu_xpath = (
        "//span[contains(@class,'x-tree-node-text') and "
        "contains(normalize-space(),'Controle de Acesso')]"
    )
    if not switch_to_frame_with_xpath(driver, wait, menu_xpath):
        raise Exception("Menu 'Controle de Acesso' não encontrado em nenhum iframe")

    click_tree_item(driver, wait, "Controle de Acesso", expand_only=True)
    print("Menu Controle de Acesso expandido")

    time.sleep(0.8 if FAST_MODE else 2)
    if not FAST_MODE:
        log_tree_nodes(driver)

    # =====================================================
    # 🔹 CLICANDO NA CONCESSÃO
    # =====================================================

    print("\nTentando clicar em Concessão de acesso Genérico e Privilegiado...")

    try:
        click_tree_child(
            driver,
            wait,
            "Controle de Acesso",
            "Concessão de acesso Genérico e Privilegiado",
        )
    except Exception:
        click_tree_child(driver, wait, "Controle de Acesso", "Concessão de acesso")
    print("✅ Clique realizado em Concessão de acesso!")

    time.sleep(1 if FAST_MODE else 3)

    # =====================================================
    # 🔹 DENTRO DA TELA: FILTRO PENDENTES E EXPORTAR EXCEL
    # =====================================================

    pendentes_xpath = (
        "//span[normalize-space()='PENDENTES'] | "
        "//button[normalize-space()='PENDENTES'] | "
        "//a[normalize-space()='PENDENTES']"
    )
    print("\nClicando em PENDENTES...")
    save_debug_screenshot(driver, "antes_pendentes")
    if not click_pendentes_fast(driver):
        click_by_any_xpath_anywhere(
            driver,
            [
                "//span[normalize-space()='PENDENTES']",
                "//button[normalize-space()='PENDENTES']",
                "//a[normalize-space()='PENDENTES']",
                "//label[normalize-space()='PENDENTES']",
                "//label[normalize-space()='PENDENTES']/preceding-sibling::input[@type='radio']",
                "//label[normalize-space()='PENDENTES']/following-sibling::input[@type='radio']",
                "//input[@type='radio' and @value='PENDENTES']",
            ],
        )

    wait_loading_mask(driver, timeout=15 if FAST_MODE else 30)
    save_debug_screenshot(driver, "depois_pendentes")

    time.sleep(2)

    print("\nClicando em Excel...")
    save_debug_screenshot(driver, "antes_excel")
    if not click_excel_fast(driver):
        click_by_any_xpath_anywhere(
            driver,
            [
                "//span[normalize-space()='Excel']",
                "//button[normalize-space()='Excel']",
                "//a[normalize-space()='Excel']",
                "//span[contains(@class,'x-btn') and .//span[normalize-space()='Excel']]",
                "//div[contains(@class,'x-toolbar')]//span[normalize-space()='Excel']",
            ],
        )
    save_debug_screenshot(driver, "depois_excel")

    print("✅ Exportação para Excel acionada!")

    time.sleep(5)

    print("\nFluxo concluído para teste.")

    # driver.quit()  # deixe comentado enquanto estiver debugando


if __name__ == "__main__":
    testar_login()
