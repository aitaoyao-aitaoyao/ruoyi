import os
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    webdriver_path = os.environ.get("CHROMEDRIVER_PATH")
    try:
        if webdriver_path:
            return webdriver.Chrome(executable_path=webdriver_path, options=options)
        return webdriver.Chrome(options=options)
    except Exception as exc:
        pytest.skip(f"Chrome WebDriver not available: {exc}")


APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8000")


@pytest.mark.selenium
def test_login_page_loads():
    driver = _driver()
    try:
        driver.get(f"{APP_URL}/static/login.html")
        assert "登录" in driver.page_source or "login" in driver.page_source.lower()
        username = driver.find_element(By.ID, "username")
        password = driver.find_element(By.ID, "password")
        assert username is not None
        assert password is not None
    finally:
        driver.quit()


@pytest.mark.selenium
def test_login_form_submit():
    driver = _driver()
    try:
        driver.get(f"{APP_URL}/static/login.html")
        driver.find_element(By.ID, "username").send_keys("demo")
        driver.find_element(By.ID, "password").send_keys("demo123")
        driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        WebDriverWait(driver, 5).until(
            lambda d: "/static/index.html" in d.current_url
        )
        assert "/static/index.html" in driver.current_url
    finally:
        driver.quit()


@pytest.mark.selenium
def test_register_tab_switch():
    driver = _driver()
    try:
        driver.get(f"{APP_URL}/static/login.html")
        driver.find_element(By.ID, "registerTab").click()
        email_input = driver.find_element(By.ID, "email")
        assert email_input.is_displayed()
    finally:
        driver.quit()


@pytest.mark.selenium
def test_login_wrong_password_message():
    driver = _driver()
    try:
        driver.get(f"{APP_URL}/static/login.html")
        driver.find_element(By.ID, "username").send_keys("demo")
        driver.find_element(By.ID, "password").send_keys("wrongpass")
        driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()

        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".message.error"))
        )
        msg = driver.find_element(By.CSS_SELECTOR, ".message.error")
        assert "失败" in msg.text or "Incorrect" in msg.text
    finally:
        driver.quit()
