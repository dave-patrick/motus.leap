import os
import sys
import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

# Import the code structure we designed
import requests
import json

class CamofoxDriverWrapper:
    def __init__(self, base_url="http://localhost:9377", user_id="youtube_playlist_agent_default", session_key="main_session"):
        self.base_url = base_url
        self.user_id = user_id
        self.session_key = session_key
        self.tab_id = None
        self.title = "YouTube"
        self._ensure_tab()
        
    def _ensure_tab(self):
        if self.tab_id:
            return
        # Try to list existing tabs to see if there's one for this user
        try:
            r = requests.get(f"{self.base_url}/tabs?userId={self.user_id}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                tabs = data.get("tabs", [])
                if tabs:
                    self.tab_id = tabs[0]["tabId"]
                    print(f"Camofox: Reusing existing tab {self.tab_id}")
                    return
        except Exception as e:
            print(f"Camofox error checking existing tabs: {e}")
            
        # Create a new tab
        try:
            payload = {
                "userId": self.user_id,
                "sessionKey": self.session_key
            }
            r = requests.post(f"{self.base_url}/tabs", json=payload, timeout=20)
            if r.status_code == 200:
                data = r.json()
                self.tab_id = data["tabId"]
                print(f"Camofox: Created new tab {self.tab_id}")
            else:
                raise RuntimeError(f"Failed to create Camofox tab: {r.status_code} {r.text}")
        except Exception as e:
            print(f"Camofox initialization error: {e}")
            raise e

    @property
    def page_source(self):
        try:
            return self.execute_script("return document.documentElement.outerHTML;")
        except:
            return ""
            
    def get(self, url):
        self._ensure_tab()
        print(f"Camofox: Navigating to {url}")
        payload = {
            "userId": self.user_id,
            "url": url
        }
        r = requests.post(f"{self.base_url}/tabs/{self.tab_id}/navigate", json=payload, timeout=40)
        if r.status_code != 200:
            print(f"Camofox navigate failed: {r.status_code} {r.text}")
            
    def save_screenshot(self, path):
        self._ensure_tab()
        try:
            r = requests.get(f"{self.base_url}/tabs/{self.tab_id}/screenshot?userId={self.user_id}", timeout=20)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
            else:
                print(f"Camofox screenshot failed: {r.status_code} {r.text}")
        except Exception as e:
            print(f"Failed to capture screenshot: {e}")
            
    def quit(self):
        if self.tab_id:
            try:
                requests.delete(f"{self.base_url}/tabs/{self.tab_id}?userId={self.user_id}", timeout=5)
                print(f"Camofox: Closed tab {self.tab_id}")
            except Exception as e:
                print(f"Camofox error closing tab: {e}")
            self.tab_id = None
            
    def close(self):
        self.quit()
        
    def execute_script(self, script, *args):
        self._ensure_tab()
        arg_exprs = []
        for arg in args:
            if isinstance(arg, CamofoxElementWrapper):
                arg_exprs.append(f"window._camofox_elements[{arg.index}]")
            else:
                arg_exprs.append(json.dumps(arg))
                
        expr = f"""
        (function() {{
            const args = [{", ".join(arg_exprs)}];
            return (function() {{
                {script}
            }}).apply(null, args);
        }})()
        """
        payload = {
            "userId": self.user_id,
            "expression": expr
        }
        r = requests.post(f"{self.base_url}/tabs/{self.tab_id}/evaluate", json=payload, timeout=20)
        if r.status_code == 200:
            data = r.json()
            if data.get("ok"):
                return data.get("result")
        return None
        
    def find_elements(self, by, selector):
        self._ensure_tab()
        xpath_flag = "true" if by == By.XPATH else "false"
        js_selector = selector.replace("'", "\\'")
        
        find_expr = f"""
        (function() {{
            let elements = [];
            if ({xpath_flag}) {{
                let result = document.evaluate('{js_selector}', document, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                for (let i = 0; i < result.snapshotLength; i++) {{
                    elements.push(result.snapshotItem(i));
                }}
            }} else {{
                elements = Array.from(document.querySelectorAll('{js_selector}'));
            }}
            window._camofox_elements = window._camofox_elements || [];
            return elements.map(el => {{
                let idx = window._camofox_elements.indexOf(el);
                if (idx === -1) {{
                    idx = window._camofox_elements.length;
                    window._camofox_elements.push(el);
                }}
                return idx;
            }});
        }})()
        """
        payload = {
            "userId": self.user_id,
            "expression": find_expr
        }
        try:
            r = requests.post(f"{self.base_url}/tabs/{self.tab_id}/evaluate", json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok") and isinstance(data.get("result"), list):
                    return [CamofoxElementWrapper(self, idx) for idx in data["result"]]
        except Exception as e:
            print(f"Camofox find_elements error: {e}")
        return []
        
    def find_element(self, by, selector):
        elements = self.find_elements(by, selector)
        if elements:
            return elements[0]
        raise NoSuchElementException(f"Element not found: {selector}")


class CamofoxElementWrapper:
    def __init__(self, driver, index):
        self.driver = driver
        self.index = index
        
    @property
    def text(self):
        try:
            return self.driver.execute_script("return arguments[0].innerText || arguments[0].textContent;", self) or ""
        except:
            return ""
            
    def get_attribute(self, name):
        try:
            return self.driver.execute_script("return arguments[0].getAttribute(arguments[1]);", self, name)
        except:
            return None
            
    def click(self):
        try:
            self.driver.execute_script("arguments[0].click();", self)
        except Exception as e:
            print(f"CamofoxElementWrapper click failed: {e}")
            
    def is_displayed(self):
        try:
            return self.driver.execute_script(
                "return !!(arguments[0].offsetWidth || arguments[0].offsetHeight || arguments[0].getClientRects().length);",
                self
            )
        except:
            return False
            
    def is_enabled(self):
        try:
            return self.driver.execute_script("return !arguments[0].disabled;", self)
        except:
            return False
            
    def find_elements(self, by, selector):
        xpath_flag = "true" if by == By.XPATH else "false"
        js_selector = selector.replace("'", "\\'")
        find_expr = f"""
        (function() {{
            let root = window._camofox_elements[{self.index}];
            if (!root) return [];
            let elements = [];
            if ({xpath_flag}) {{
                let result = document.evaluate('{js_selector}', root, null, XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                for (let i = 0; i < result.snapshotLength; i++) {{
                    elements.push(result.snapshotItem(i));
                }}
            }} else {{
                elements = Array.from(root.querySelectorAll('{js_selector}'));
            }}
            window._camofox_elements = window._camofox_elements || [];
            return elements.map(el => {{
                let idx = window._camofox_elements.indexOf(el);
                if (idx === -1) {{
                    idx = window._camofox_elements.length;
                    window._camofox_elements.push(el);
                }}
                return idx;
            }});
        }})()
        """
        payload = {
            "userId": self.driver.user_id,
            "expression": find_expr
        }
        try:
            r = requests.post(f"{self.driver.base_url}/tabs/{self.driver.tab_id}/evaluate", json=payload, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok") and isinstance(data.get("result"), list):
                    return [CamofoxElementWrapper(self.driver, idx) for idx in data["result"]]
        except Exception as e:
            print(f"CamofoxElementWrapper find_elements error: {e}")
        return []
        
    def find_element(self, by, selector):
        elements = self.find_elements(by, selector)
        if elements:
            return elements[0]
        raise NoSuchElementException(f"Sub-element not found relative to element {self.index}")


if __name__ == "__main__":
    print("Testing CamofoxDriverWrapper...")
    driver = CamofoxDriverWrapper()
    try:
        driver.get("https://example.com")
        time.sleep(2)
        h1 = driver.find_element(By.TAG_NAME, "h1")
        print("H1 Text:", h1.text)
        
        # Test attributes
        p = driver.find_element(By.TAG_NAME, "p")
        print("Paragraph text:", p.text)
        
        # Execute script
        h = driver.execute_script("return document.title;")
        print("Document title:", h)
        
        # Screenshot
        driver.save_screenshot("camofox_test.png")
        print("Screenshot saved to camofox_test.png")
    finally:
        driver.quit()
