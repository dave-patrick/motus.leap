import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import core
from selenium.webdriver.common.by import By
import time

print("Imported core successfully. Testing get_browser()...")
driver = core.get_browser()
print("Driver type:", type(driver).__name__)

try:
    print("Navigating to example.com...")
    driver.get("https://example.com")
    h1 = driver.find_element(By.TAG_NAME, "h1")
    print("H1 tag text:", h1.text)
    
    # Test execute_script
    res = driver.execute_script("return 1 + 2;")
    print("Result of 1 + 2 execution:", res)
    assert res == 3, "Script execution returned unexpected result"
    
    print("Test passed successfully!")
finally:
    driver.quit()
