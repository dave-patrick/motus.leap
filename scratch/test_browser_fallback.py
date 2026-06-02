import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure the parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBrowserFallback(unittest.TestCase):
    def setUp(self):
        # Clean up modules in sys.modules to allow clean imports
        self.cleanup_sys_modules()

    def cleanup_sys_modules(self):
        for mod in ['core', 'undetected_chromedriver']:
            if mod in sys.modules:
                del sys.modules[mod]

    def test_1_import_error_fallback(self):
        print("\n--- Scenario 1: Testing ImportError Fallback ---")
        
        # 1. Mock undetected_chromedriver import failure
        sys.modules['undetected_chromedriver'] = None
        
        # 2. Import core
        import core
        self.assertIsNone(core.uc)
        print("  Imported core successfully. core.uc is None as expected.")
        
        # 3. Get browser (should fall back to Playwright)
        print("  Calling get_browser()...")
        driver = core.get_browser()
        self.assertIsNotNone(driver)
        
        # Verify it's a Playwright wrapper
        from core import PlaywrightDriverWrapper
        self.assertIsInstance(driver, PlaywrightDriverWrapper)
        print("  Successfully got PlaywrightDriverWrapper fallback!")
        
        # 4. Navigate and save screenshot
        print("  Navigating to https://example.com...")
        driver.get("https://example.com")
        
        screenshot_path = os.path.join(os.path.dirname(__file__), "screenshot_import_fallback.png")
        print(f"  Saving screenshot to {screenshot_path}...")
        driver.save_screenshot(screenshot_path)
        self.assertTrue(os.path.exists(screenshot_path))
        print("  Screenshot saved successfully!")
        
        # 5. Clean up
        driver.quit()
        print("  Driver quit successfully.")

    def test_2_launch_exception_fallback(self):
        print("\n--- Scenario 2: Testing Launch Exception Fallback ---")
        
        # 1. Mock undetected_chromedriver to raise exception on uc.Chrome launch
        mock_uc = MagicMock()
        mock_uc.ChromeOptions = MagicMock()
        mock_uc.Chrome.side_effect = Exception("Mocked driver crash during uc.Chrome initialization")
        sys.modules['undetected_chromedriver'] = mock_uc
        
        # 2. Import core
        import core
        self.assertEqual(core.uc, mock_uc)
        print("  Imported core successfully. core.uc is mocked.")
        
        # 3. Get browser (should fail uc launch and fall back to Playwright)
        print("  Calling get_browser()...")
        driver = core.get_browser()
        self.assertIsNotNone(driver)
        
        # Verify it's a Playwright wrapper
        from core import PlaywrightDriverWrapper
        self.assertIsInstance(driver, PlaywrightDriverWrapper)
        print("  Successfully got PlaywrightDriverWrapper fallback after launcher exception!")
        
        # 4. Navigate and save screenshot
        print("  Navigating to https://example.com...")
        driver.get("https://example.com")
        
        screenshot_path = os.path.join(os.path.dirname(__file__), "screenshot_launch_fallback.png")
        print(f"  Saving screenshot to {screenshot_path}...")
        driver.save_screenshot(screenshot_path)
        self.assertTrue(os.path.exists(screenshot_path))
        print("  Screenshot saved successfully!")
        
        # 5. Clean up
        driver.quit()
        print("  Driver quit successfully.")

if __name__ == "__main__":
    unittest.main()
