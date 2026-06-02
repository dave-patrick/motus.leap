from core import get_browser
import time

driver = get_browser()
try:
    driver.get("https://www.youtube.com")
    time.sleep(5)
    driver.save_screenshot("check_login_selenium.png")
    page_source = driver.page_source
    if "Sign in" in page_source:
        print("NOT LOGGED IN")
    else:
        print("LOGGED IN")
finally:
    driver.quit()
