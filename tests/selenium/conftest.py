"""
LightPress CMS Selenium UI 测试夹具。

提供:
    - driver: 函数级无头 Chrome WebDriver
    - logged_in_driver: 已登录 admin 账号的 WebDriver

环境变量:
    APP_URL — 应用地址，默认 http://127.0.0.1:8000
    CHROMEDRIVER_PATH — ChromeDriver 可执行文件路径（可选）
"""
import os
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8000")


def _chrome_options():
    """配置无头 Chrome 选项 — headless=new 兼容新版 Chrome。"""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1920,1080")
    return options


def create_driver():
    """创建无头 Chrome WebDriver。如果 Chrome 不可用则跳过测试。"""
    options = _chrome_options()
    webdriver_path = os.environ.get("CHROMEDRIVER_PATH")
    try:
        if webdriver_path:
            return webdriver.Chrome(executable_path=webdriver_path, options=options)
        return webdriver.Chrome(options=options)
    except Exception as exc:
        pytest.skip(f"Chrome WebDriver 不可用: {exc}")


@pytest.fixture(scope="function")
def driver():
    """函数级无头 Chrome WebDriver，测试结束后自动退出。"""
    drv = create_driver()
    yield drv
    drv.quit()


@pytest.fixture(scope="function")
def logged_in_driver(driver):
    """已登录的 WebDriver（admin 账号）。

    自动完成登录流程:
        1. 打开 SPA 首页
        2. 等待登录表单渲染
        3. 输入 admin 凭据并提交
        4. 等待仪表盘加载完成
    """
    driver.get(f"{APP_URL}/static/index.html")
    # 未登录时 SPA 显示登录表单
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='用户名']"))
    )
    driver.find_element(By.CSS_SELECTOR, "input[placeholder='用户名']").send_keys("admin")
    driver.find_element(By.CSS_SELECTOR, "input[placeholder='密码']").send_keys("admin123")
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

    # 等待仪表盘加载
    WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "h2"))
    )
    return driver
