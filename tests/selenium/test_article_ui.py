"""
LightPress CMS 文章管理 UI 测试（Selenium）。

测试仪表盘渲染、侧边栏导航、文章创建/列表/筛选等前端交互流程。
"""
import os
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

APP_URL = os.environ.get("APP_URL", "http://127.0.0.1:8000")


@pytest.mark.selenium
class TestDashboardUI:
    def test_dashboard_shows_stats_cards(self, logged_in_driver):
        """仪表盘应显示 4 个统计卡片（文章总数、已发布、待审核、用户数）。"""
        driver = logged_in_driver
        cards = driver.find_elements(By.CSS_SELECTOR, ".grid.grid-cols-2.lg\\:grid-cols-4 > div")
        assert len(cards) == 4

    def test_dashboard_shows_quick_actions(self, logged_in_driver):
        """仪表盘应显示 '+ 写文章' 快捷操作按钮。"""
        driver = logged_in_driver
        buttons = driver.find_elements(By.CSS_SELECTOR, "button")
        btn_texts = [b.text for b in buttons]
        assert any("写文章" in t for t in btn_texts)


@pytest.mark.selenium
class TestArticleListUI:
    def test_navigate_to_articles(self, logged_in_driver):
        """点击侧边栏 '文章管理' 应加载文章列表页（含表格）。"""
        driver = logged_in_driver
        for link in driver.find_elements(By.CSS_SELECTOR, "nav a"):
            if "文章管理" in link.text:
                link.click()
                break
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
        )
        assert "文章管理" in driver.page_source

    def test_article_list_has_filters(self, logged_in_driver):
        """文章列表页应有状态下拉筛选和搜索输入框。"""
        driver = logged_in_driver
        for link in driver.find_elements(By.CSS_SELECTOR, "nav a"):
            if "文章管理" in link.text:
                link.click()
                break
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "select"))
        )
        selects = driver.find_elements(By.CSS_SELECTOR, "select")
        assert len(selects) >= 2
        search_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder='搜索文章...']")
        assert search_input.is_displayed()

    def test_create_article_via_ui(self, logged_in_driver):
        """点击 '+ 写文章' 按钮进入编辑器，填写表单后保存草稿。"""
        driver = logged_in_driver
        for link in driver.find_elements(By.CSS_SELECTOR, "nav a"):
            if "文章管理" in link.text:
                link.click()
                break
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button"))
        )
        for btn in driver.find_elements(By.CSS_SELECTOR, "button"):
            if "写文章" in btn.text:
                btn.click()
                break
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='标题']"))
        )
        driver.find_element(By.CSS_SELECTOR, "input[placeholder='标题']").send_keys("Selenium Test Article")
        driver.find_element(By.CSS_SELECTOR, "textarea[placeholder='正文']").send_keys("Content created by Selenium UI test.")
        for btn in driver.find_elements(By.CSS_SELECTOR, "button"):
            if "保存草稿" in btn.text:
                btn.click()
                break
        WebDriverWait(driver, 3).until(
            lambda d: "文章管理" in d.page_source
        )
        assert "Selenium Test Article" in driver.page_source


@pytest.mark.selenium
class TestNavigation:
    def test_navigate_to_categories(self, logged_in_driver):
        """点击侧边栏 '分类管理' 应导航到分类管理页面。"""
        driver = logged_in_driver
        for link in driver.find_elements(By.CSS_SELECTOR, "nav a"):
            if "分类管理" in link.text:
                link.click()
                break
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h2"))
        )
        assert "分类管理" in driver.page_source

    def test_navigate_to_tags(self, logged_in_driver):
        """点击侧边栏 '标签管理' 应导航到标签管理页面。"""
        driver = logged_in_driver
        for link in driver.find_elements(By.CSS_SELECTOR, "nav a"):
            if "标签管理" in link.text:
                link.click()
                break
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h2"))
        )
        assert "标签管理" in driver.page_source

    def test_logout(self, logged_in_driver):
        """点击退出登录按钮应返回登录页面。"""
        driver = logged_in_driver
        for btn in driver.find_elements(By.CSS_SELECTOR, "button"):
            if "退出登录" in btn.text:
                btn.click()
                break
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='用户名']"))
        )
        assert driver.find_element(By.CSS_SELECTOR, "input[placeholder='用户名']").is_displayed()
