"""
LightPress CMS 登录/注册 UI 测试（Selenium）。

测试登录表单渲染、注册切换、错误提示、成功跳转等用户交互流程。
"""
import os
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8000")


@pytest.mark.selenium
class TestLoginPage:
    def test_login_form_renders(self, driver):
        """登录表单应显示用户名、密码输入框和提交按钮。"""
        driver.get(f"{APP_URL}/static/index.html")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='用户名']"))
        )
        assert driver.find_element(By.CSS_SELECTOR, "input[placeholder='用户名']").is_displayed()
        assert driver.find_element(By.CSS_SELECTOR, "input[placeholder='密码']").is_displayed()
        assert driver.find_element(By.CSS_SELECTOR, "button[type='submit']").is_displayed()

    def test_register_tab_switches_form(self, driver):
        """点击注册标签应显示邮箱和姓名输入框。"""
        driver.get(f"{APP_URL}/static/index.html")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='用户名']"))
        )
        register_btn = driver.find_elements(By.CSS_SELECTOR, "button.flex-1")[1]
        register_btn.click()
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='姓名']"))
        )
        assert driver.find_element(By.CSS_SELECTOR, "input[placeholder='姓名']").is_displayed()
        assert driver.find_element(By.CSS_SELECTOR, "input[placeholder='邮箱']").is_displayed()

    def test_login_with_wrong_password_shows_error(self, driver):
        """输入错误密码应显示错误提示消息。"""
        driver.get(f"{APP_URL}/static/index.html")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='用户名']"))
        )
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='用户名']").send_keys("admin")
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='密码']").send_keys("wrongpass")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".text-red-400"))
        )
        error = driver.find_element(By.CSS_SELECTOR, ".text-red-400")
        assert error.is_displayed()

    def test_login_success_navigates_to_dashboard(self, driver):
        """登录成功应跳转到仪表盘页面，显示侧边栏和统计卡片。"""
        driver.get(f"{APP_URL}/static/index.html")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='用户名']"))
        )
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='用户名']").send_keys("admin")
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='密码']").send_keys("admin123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h2"))
        )
        assert "仪表盘" in driver.page_source

    def test_register_new_user(self, driver):
        """注册新用户应显示成功提示消息。"""
        driver.get(f"{APP_URL}/static/index.html")
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='用户名']"))
        )
        driver.find_elements(By.CSS_SELECTOR, "button.flex-1")[1].click()
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='姓名']"))
        )
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='姓名']").send_keys("Selenium Tester")
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='用户名']").send_keys("selenium_test")
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='邮箱']").send_keys("sel@test.com")
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='密码']").send_keys("test1234")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".text-green-400"))
        )
        success = driver.find_element(By.CSS_SELECTOR, ".text-green-400")
        assert "注册成功" in success.text
