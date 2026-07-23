import os
import time
import requests
import json
try:
    import undetected_chromedriver as uc
except ImportError:
    uc = None
try:
    import win32gui
    import win32con
except ImportError:
    win32gui = None
    win32con = None
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

def wait_for_condition(predicate, max_wait=5.0, poll_interval=0.2):
    """
    Polls predicate() every poll_interval seconds up to max_wait seconds.
    Returns True as soon as predicate() evaluates to truthy, otherwise False.
    """
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(poll_interval)
    return False

class PlaywrightDriverWrapper:
    def __init__(self, playwright_ctx, context, page):
        self.playwright_ctx = playwright_ctx
        self.context = context
        self.page = page
        self.title = "YT"
        
    @property
    def page_source(self):
        try:
            return self.page.content()
        except:
            return ""
            
    def get(self, url):
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            # retry once on timeout with commit and wait for the page to settle
            print(f"Playwright goto timeout, retrying with commit: {e}")
            try:
                self.page.goto(url, wait_until="commit", timeout=30000)
                time.sleep(5) # Give JavaScript redirects time to execute and settle
            except Exception as e2:
                print(f"Playwright retry failed: {e2}")
            
    def save_screenshot(self, path, timeout=10000):
        try:
            self.page.screenshot(path=path, timeout=timeout)
        except Exception as e:
            print(f"Failed to capture screenshot: {e}")
            
    def quit(self):
        try: self.page.close()
        except: pass
        try: self.context.close()
        except: pass
        try: self.playwright_ctx.stop()
        except: pass
        
    def close(self):
        self.quit()
        
    def execute_script(self, script, *args):
        js_args = [a.element if isinstance(a, PlaywrightElementWrapper) else a for a in args]
        try:
            return self.page.evaluate(
                "(...args) => { return (function() { " + script + " }).apply(null, args); }",
                *js_args
            )
        except Exception as e:
            print(f"Playwright execute_script failed: {e}")
            return None
            
    def execute_async_script(self, script, *args):
        js_args = [a.element if isinstance(a, PlaywrightElementWrapper) else a for a in args]
        wrapped_script = f"""
        (...args) => new Promise((resolve) => {{
            const callback = (res) => resolve(res);
            const allArgs = [...args, callback];
            (function() {{
                {script}
            }}).apply(null, allArgs);
        }})
        """
        try:
            return self.page.evaluate(wrapped_script, *js_args)
        except Exception as e:
            print(f"Playwright execute_async_script failed: {e}")
            return f"Error: {e}"
            
    def find_elements(self, by, selector):
        pw_selector = self._get_playwright_selector(by, selector)
        try:
            elements = self.page.query_selector_all(pw_selector)
            return [PlaywrightElementWrapper(self, el) for el in elements]
        except Exception as e:
            print(f"Playwright find_elements failed for {selector}: {e}")
            return []
            
    def find_element(self, by, selector):
        pw_selector = self._get_playwright_selector(by, selector)
        try:
            el = self.page.query_selector(pw_selector)
            if el:
                return PlaywrightElementWrapper(self, el)
            raise NoSuchElementException(f"Element not found: {selector}")
        except Exception as e:
            raise e
            
    def _get_playwright_selector(self, by, selector):
        if by == By.CSS_SELECTOR:
            return selector
        if by == By.XPATH:
            return f"xpath={selector}"
        if by == By.TAG_NAME:
            return selector
        if by == By.ID:
            return f"#{selector}"
        return selector

class PlaywrightElementWrapper:
    def __init__(self, driver, element):
        self.driver = driver
        self.element = element
        
    @property
    def text(self):
        try:
            return self.element.inner_text()
        except:
            return ""
            
    def get_attribute(self, name):
        try:
            return self.element.get_attribute(name)
        except:
            return None
            
    def click(self):
        try:
            self.element.click(timeout=5000)
        except Exception:
            # Fallback to JS click
            try:
                self.driver.page.evaluate("(el) => el.click()", self.element)
            except:
                pass
                
    def is_displayed(self):
        try:
            return self.element.is_visible()
        except:
            return False
            
    def is_enabled(self):
        try:
            return self.element.is_enabled()
        except:
            return False
            
    def find_elements(self, by, selector):
        pw_selector = self.driver._get_playwright_selector(by, selector)
        try:
            elements = self.element.query_selector_all(pw_selector)
            return [PlaywrightElementWrapper(self.driver, el) for el in elements]
        except:
            return []
            
    def find_element(self, by, selector):
        pw_selector = self.driver._get_playwright_selector(by, selector)
        try:
            el = self.element.query_selector(pw_selector)
            if el:
                return PlaywrightElementWrapper(self.driver, el)
            raise NoSuchElementException("Sub-element not found")
        except Exception as e:
            raise e

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "user_data")
PLAYWRIGHT_USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "user_data_playwright")

def get_playwright_browser():
    try:
        from playwright.sync_api import sync_playwright
        print("  Initializing Playwright context...")
        pw = sync_playwright().start()
        
        # Check if Chrome executable exists to run branded browser
        # otherwise Playwright uses standard Chromium
        browser_context = pw.chromium.launch_persistent_context(
            user_data_dir=PLAYWRIGHT_USER_DATA_DIR,
            headless=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            args=[
                "--window-position=-10000,0",
                "--window-size=1920,1080",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--mute-audio",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-dev-shm-usage"
            ]
        )
        # Load and inject cookies if they exist
        try:
            cookies_path = os.path.expanduser("~/.camofox/cookies/cookies.json")
            if os.path.exists(cookies_path):
                print("  Playwright: Loading cookies from cookies.json...")
                with open(cookies_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                if cookies:
                    pw_cookies = []
                    for c in cookies:
                        clean = {
                            "name": c["name"],
                            "value": c["value"],
                            "domain": c["domain"],
                            "path": c.get("path", "/"),
                        }
                        if "secure" in c: clean["secure"] = c["secure"]
                        if "httpOnly" in c: clean["httpOnly"] = c["httpOnly"]
                        if "expires" in c and c["expires"] > 0:
                            clean["expires"] = int(c["expires"])
                        pw_cookies.append(clean)
                    
                    # Clear existing cookies to avoid pollution
                    browser_context.clear_cookies()
                    browser_context.add_cookies(pw_cookies)
                    print(f"  Playwright: Injected {len(pw_cookies)} cookies successfully.")
        except Exception as ce:
            print(f"  Playwright: Warning: Failed to inject cookies: {ce}")

        page = browser_context.pages[0] if browser_context.pages else browser_context.new_page()
        
        def force_mute():
            try:
                page.evaluate("""
                    window.forceMute = function() {
                        Array.from(document.querySelectorAll('video, audio')).forEach(m => {
                            m.muted = true;
                            m.volume = 0;
                            m.pause();
                        });
                    };
                    window.forceMute();
                    if (!window.muteInterval) {
                        window.muteInterval = setInterval(window.forceMute, 500);
                    }
                """)
            except: pass
            
        wrapper = PlaywrightDriverWrapper(pw, browser_context, page)
        wrapper.force_mute = force_mute
        return wrapper
    except Exception as e:
        print(f"  Playwright initialization failed: {e}")
        return None

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "user_data")

def _get_chrome_version():
    """Detect the installed Chrome major version without launching Chrome."""
    import re

    # 1) Try Windows registry (most reliable on Windows, no process launch)
    try:
        import winreg
        for key_path in [
            r"SOFTWARE\Google\Chrome\BLBeacon",
            r"SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon",
        ]:
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    key = winreg.OpenKey(hive, key_path)
                    version_str, _ = winreg.QueryValueEx(key, "version")
                    winreg.CloseKey(key)
                    m = re.match(r"(\d+)\.", version_str)
                    if m:
                        return int(m.group(1))
                except OSError:
                    pass
    except ImportError:
        pass

    # 2) Try reading version from the chrome.exe folder name (e.g. 148.0.x.y)
    import glob
    for base in [
        r"C:\Program Files\Google\Chrome\Application",
        r"C:\Program Files (x86)\Google\Chrome\Application",
    ]:
        pattern = os.path.join(base, "*", "chrome.exe")
        for exe_path in glob.glob(pattern):
            folder = os.path.basename(os.path.dirname(exe_path))
            m = re.match(r"(\d+)\.", folder)
            if m:
                return int(m.group(1))

    return None


_CHROME_VERSION = None  # cached after first detection

def _make_chrome_options():
    """Always returns a brand-new ChromeOptions instance."""
    opt = uc.ChromeOptions()
    opt.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    opt.add_argument("--window-position=-10000,0")
    opt.add_argument("--window-size=1920,1080")
    opt.add_argument("--disable-backgrounding-occluded-windows")
    opt.add_argument("--disable-renderer-backgrounding")
    opt.add_argument("--mute-audio")
    opt.add_argument("--autoplay-policy=no-user-gesture-required")
    return opt

class CamofoxDriverWrapper:
    def __init__(self, base_url=None, user_id=None, session_key="main_session"):
        self.base_url = base_url or os.getenv("CAMOFOX_URL", "http://localhost:9377")
        self.user_id = user_id or os.getenv("CAMOFOX_USER_ID", "motus_leap_default")
        self.session_key = session_key
        self.tab_id = None
        self.title = "YT"
        self.session = requests.Session()
        api_key = os.getenv("CAMOFOX_API_KEY", "my_secret_cookie_key")
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}"
        })
        self._ensure_tab()
        
    def _ensure_tab(self):
        # Validate if existing tab_id is still active on the server
        if self.tab_id:
            try:
                r = self.session.get(f"{self.base_url}/tabs?userId={self.user_id}", timeout=30)
                if r.status_code == 200:
                    data = r.json()
                    tabs = data.get("tabs", [])
                    if any(t["tabId"] == self.tab_id for t in tabs):
                        return # Tab is active and valid!
            except Exception as e:
                print(f"  Camofox error verifying active tab: {e}")
            self.tab_id = None

        # Close any existing tabs to ensure a completely fresh session state
        try:
            r = self.session.get(f"{self.base_url}/tabs?userId={self.user_id}", timeout=30)
            if r.status_code == 200:
                data = r.json()
                tabs = data.get("tabs", [])
                for t in tabs:
                    try:
                        self.session.delete(f"{self.base_url}/tabs/{t['tabId']}", timeout=10)
                    except:
                        pass
        except Exception as e:
            print(f"  Camofox error cleaning up existing tabs: {e}")
            
        # Create a new tab
        try:
            payload = {
                "userId": self.user_id,
                "sessionKey": self.session_key
            }
            r = self.session.post(f"{self.base_url}/tabs", json=payload, timeout=60)
            if r.status_code == 200:
                data = r.json()
                self.tab_id = data["tabId"]
                print(f"  Camofox: Created new tab {self.tab_id}")
                
                # Automatically import saved cookies if cookies.json exists
                try:
                    cookies_path = os.path.expanduser("~/.camofox/cookies/cookies.json")
                    if os.path.exists(cookies_path):
                        print("  Camofox: Loading persisted cookies from cookies.json...")
                        with open(cookies_path, "r", encoding="utf-8") as f:
                            saved_cookies = json.load(f)
                        if saved_cookies:
                            cr = self.session.post(
                                f"{self.base_url}/sessions/{self.user_id}/cookies",
                                json={"cookies": saved_cookies},
                                timeout=30
                            )
                            if cr.status_code == 200:
                                print(f"  Camofox: Successfully auto-imported {len(saved_cookies)} cookies into new session.")
                            else:
                                print(f"  Camofox: Failed to auto-import cookies: {cr.status_code} {cr.text}")
                except Exception as ce:
                    print(f"  Camofox: Warning: Error auto-loading saved cookies: {ce}")
            else:
                raise RuntimeError(f"Failed to create Camofox tab: {r.status_code} {r.text}")
        except Exception as e:
            print(f"  Camofox initialization error: {e}")
            raise e

    @property
    def page_source(self):
        try:
            return self.execute_script("return document.documentElement.outerHTML;")
        except:
            return ""
            
    def force_mute(self):
        try:
            self.execute_script("""
                window.forceMute = function() {
                    Array.from(document.querySelectorAll('video, audio')).forEach(m => {
                        m.muted = true;
                        m.volume = 0;
                        m.pause();
                    });
                };
                window.forceMute();
                if (!window.muteInterval) {
                    window.muteInterval = setInterval(window.forceMute, 500);
                }
            """)
        except Exception as e:
            print(f"  Camofox force_mute error: {e}")

    def get(self, url):
        self._ensure_tab()
        print(f"  Camofox: Navigating to {url}")
        payload = {
            "userId": self.user_id,
            "url": url,
            "skipRefs": True
        }
        r = self.session.post(f"{self.base_url}/tabs/{self.tab_id}/navigate", json=payload, timeout=240)
        if r.status_code != 200:
            print(f"  Camofox navigate failed: {r.status_code} {r.text}")
        self.force_mute()
            
    def save_screenshot(self, path):
        self._ensure_tab()
        try:
            r = self.session.get(f"{self.base_url}/tabs/{self.tab_id}/screenshot?userId={self.user_id}", timeout=120)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
            else:
                print(f"  Camofox screenshot failed: {r.status_code} {r.text}")
        except Exception as e:
            print(f"  Failed to capture screenshot: {e}")
            
    def quit(self):
        if self.tab_id:
            try:
                self.session.delete(f"{self.base_url}/tabs/{self.tab_id}?userId={self.user_id}", timeout=5)
                print(f"  Camofox: Closed tab {self.tab_id}")
            except Exception as e:
                print(f"  Camofox error closing tab: {e}")
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
        r = self.session.post(f"{self.base_url}/tabs/{self.tab_id}/evaluate", json=payload, timeout=240)
        if r.status_code == 200:
            data = r.json()
            if data.get("ok"):
                return data.get("result")
        return None
        
    def execute_async_script(self, script, *args):
        self._ensure_tab()
        arg_exprs = []
        for arg in args:
            if isinstance(arg, CamofoxElementWrapper):
                arg_exprs.append(f"window._camofox_elements[{arg.index}]")
            else:
                arg_exprs.append(json.dumps(arg))
                
        expr = f"""
        (new Promise((resolve) => {{
            const callback = (res) => resolve(res);
            const args = [{", ".join(arg_exprs)}, callback];
            (function() {{
                {script}
            }}).apply(null, args);
        }}))
        """
        payload = {
            "userId": self.user_id,
            "expression": expr
        }
        r = self.session.post(f"{self.base_url}/tabs/{self.tab_id}/evaluate", json=payload, timeout=240)
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
            r = self.session.post(f"{self.base_url}/tabs/{self.tab_id}/evaluate", json=payload, timeout=240)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok") and isinstance(data.get("result"), list):
                    return [CamofoxElementWrapper(self, idx) for idx in data["result"]]
        except Exception as e:
            print(f"  Camofox find_elements error: {e}")
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
            print(f"  CamofoxElementWrapper click failed: {e}")
            
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
            r = self.driver.session.post(f"{self.driver.base_url}/tabs/{self.driver.tab_id}/evaluate", json=payload, timeout=240)
            if r.status_code == 200:
                data = r.json()
                if data.get("ok") and isinstance(data.get("result"), list):
                    return [CamofoxElementWrapper(self.driver, idx) for idx in data["result"]]
        except Exception as e:
            print(f"  CamofoxElementWrapper find_elements error: {e}")
        return []
        
    def find_element(self, by, selector):
        elements = self.find_elements(by, selector)
        if elements:
            return elements[0]
        raise NoSuchElementException(f"Sub-element not found relative to element {self.index}")

def get_browser():
    global _CHROME_VERSION
    if os.environ.get("MOCK_YT") == "1":
        class MockDriver:
            def quit(self): pass
            def save_screenshot(self, p): pass
        return MockDriver()
        
    if os.environ.get("DISABLE_CAMOFOX") != "1":
        try:
            print("  Attempting to initialize Camofox stealth browser wrapper...")
            return CamofoxDriverWrapper()
        except Exception as e:
            print(f"  Camofox initialization failed, falling back to Playwright/Chromedriver: {e}")

    print("  Attempting to initialize Playwright Chromium stealth browser...")
    pw_driver = get_playwright_browser()
    if pw_driver:
        return pw_driver
    print("  Playwright Chromium failed, falling back to undetected_chromedriver...")

    if uc is None:
        print("  undetected_chromedriver is not installed. Falling back to Playwright...")
        pw_driver = get_playwright_browser()
        if pw_driver:
            return pw_driver
        raise RuntimeError("Neither undetected_chromedriver nor Playwright could be initialized.")

    # Detect Chrome version once and cache it
    if _CHROME_VERSION is None:
        _CHROME_VERSION = _get_chrome_version()
        if _CHROME_VERSION:
            print(f"  Detected Chrome version {_CHROME_VERSION} — will pass version_main={_CHROME_VERSION} to undetected_chromedriver.")

    for attempt in range(3):
        try:
            # Always create a fresh options object per attempt
            options = _make_chrome_options()
            kwargs = dict(options=options, headless=False, use_subprocess=True)
            if _CHROME_VERSION:
                kwargs["version_main"] = _CHROME_VERSION
            driver = uc.Chrome(**kwargs)

            # Use win32gui to find and hide the window immediately
            time.sleep(1)
            try:
                if win32gui is not None:
                    def hide_window(hwnd, _):
                        if driver.title in win32gui.GetWindowText(hwnd):
                            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
                    win32gui.EnumWindows(hide_window, None)
            except: pass

            # Fallback off-screen positioning
            try:
                driver.set_window_position(-10000, 0)
            except: pass

            # Helper to mute all media immediately and periodically
            def force_mute():
                try:
                    driver.execute_script("""
                        window.forceMute = function() {
                            Array.from(document.querySelectorAll('video, audio')).forEach(m => {
                                m.muted = true;
                                m.volume = 0;
                                m.pause();
                            });
                        };
                        window.forceMute();
                        if (!window.muteInterval) {
                            window.muteInterval = setInterval(window.forceMute, 500);
                        }
                    """)
                except: pass

            driver.force_mute = force_mute
            return driver
        except Exception as e:
            err_msg = str(e)
            # If Chrome version mismatch, update our cached version and retry immediately
            import re as _re
            vm = _re.search(r"Current browser version is (\d+)\.", err_msg)
            if vm:
                _CHROME_VERSION = int(vm.group(1))
                print(f"  Version mismatch detected — updating to version_main={_CHROME_VERSION} and retrying...")
                continue  # retry with updated version, fresh options on next loop
            print(f"  Attempt {attempt+1}/3 to start undetected_chromedriver failed: {e}")
            if attempt == 2:
                print("  All undetected_chromedriver attempts failed. Falling back to Playwright...")
                pw_driver = get_playwright_browser()
                if pw_driver:
                    return pw_driver
                raise e
            time.sleep(3)
    return None


def _wait_for_watch_page_load(driver, timeout=120):
    """Wait until the watch page is fully loaded and no longer in skeleton state."""
    try:
        WebDriverWait(driver, timeout).until(lambda d: d.execute_script("""
            let channel = document.querySelector('ytd-channel-name, #channel-name');
            if (!channel || !channel.innerText.trim()) return false;
            let container = document.querySelector('ytd-watch-metadata, #top-row, ytd-video-primary-info-renderer') || document;
            let buttons = container.querySelectorAll('button');
            return buttons.length > 3;
        """))
        time.sleep(2) # brief settle time
    except Exception as e:
        print(f"  Warning: Timeout/error waiting for watch page elements to load: {e}")
        time.sleep(5)


def _open_save_dialog(driver):
    """Helper to open the 'Save to playlist' dialog on a video page."""
    # Force mute immediately
    if hasattr(driver, 'force_mute'):
        driver.force_mute()
    
    # Check if video is "Made for Kids" or if Save button is disabled
    is_kids = False
    try:
        is_kids = driver.execute_script("""
            let isKids = Array.from(document.querySelectorAll('*')).some(el => el.textContent && el.textContent.includes("Choices for families"));
            let container = document.querySelector('ytd-watch-metadata, #top-row, ytd-video-primary-info-renderer') || document;
            let saveBtn = Array.from(container.querySelectorAll('button')).find(b => {
                let match = b.getAttribute('aria-label') === 'Save to playlist' || 
                            b.innerText.trim() === 'Save' ||
                            (b.querySelector('span') && b.querySelector('span').innerText.trim() === 'Save');
                if (!match) return false;
                let rect = b.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0 && window.getComputedStyle(b).display !== 'none';
            });
            return isKids || (saveBtn && (saveBtn.hasAttribute('disabled') || saveBtn.disabled || saveBtn.getAttribute('aria-disabled') === 'true'));
        """)
    except Exception as e:
        print(f"    Failed to check if video is made for kids: {e}")
        
    if is_kids:
        raise RuntimeError("Video is marked 'Made for Kids' (Save button is disabled) - YT disables saving these to playlists")

    
    # Standard Selenium selectors
    selectors = [
        (By.CSS_SELECTOR, "button[aria-label='Save to playlist']"),
        (By.XPATH, "//button[contains(., 'Save')]"),
        (By.XPATH, "//ytd-button-renderer[contains(., 'Save')]"),
        (By.CSS_SELECTOR, "button[aria-label='More actions']"),
        (By.XPATH, "//button[@aria-label='More actions']")
    ]
    
    found = False
    for by, selector in selectors:
        try:
            print(f"    Trying selector: {selector}")
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((by, selector)))
            # Try to scroll into view first
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
            time.sleep(0.5)
            btn.click()
            time.sleep(2)
            
            # Check if we clicked 'More actions' or if dialog didn't appear yet
            # If a menu appeared, look for 'Save' inside it
            try:
                # Look for 'Save' in any popup menu
                save_items = driver.find_elements(By.XPATH, "//ytd-menu-service-item-renderer[contains(., 'Save')] | //tp-yt-paper-item[contains(., 'Save')]")
                if save_items:
                    print("    Found 'Save' in menu, clicking...")
                    save_items[0].click()
                    time.sleep(2)
            except: pass
            
            # Check if any dialog appeared (old or new)
            try:
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "yt-sheet-view-model, ytd-add-to-playlist-create-renderer, #playlists, ytd-add-to-playlist-renderer")))
                found = True
                break
            except:
                continue
        except:
            continue
    
    if not found:
        print("    Attempting JS click fallback for Save button...")
        try:
            driver.execute_script("""
                let saveBtn = Array.from(document.querySelectorAll('button')).find(b => {
                    let match = b.getAttribute('aria-label') === 'Save to playlist' || 
                                b.innerText.trim() === 'Save' ||
                                (b.querySelector('span') && b.querySelector('span').innerText.trim() === 'Save');
                    if (!match) return false;
                    let rect = b.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && window.getComputedStyle(b).display !== 'none';
                });
                if (saveBtn) {
                    saveBtn.scrollIntoView({block: 'center'});
                    saveBtn.click();
                } else {
                    let moreBtn = document.querySelector('button[aria-label="More actions"]');
                    if (moreBtn) moreBtn.click();
                }
            """)
            time.sleep(2.5)
            # Check if any menu/dialog appeared
            try:
                # Look for Save in menu
                save_items = driver.find_elements(By.XPATH, "//ytd-menu-service-item-renderer[contains(., 'Save')] | //tp-yt-paper-item[contains(., 'Save')]")
                if save_items:
                    driver.execute_script("arguments[0].click();", save_items[0])
                    time.sleep(2)
            except: pass
            
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "yt-sheet-view-model, ytd-add-to-playlist-create-renderer, #playlists, ytd-add-to-playlist-renderer")))
            found = True
            print("    JS click fallback succeeded!")
        except Exception as e:
            print(f"    JS click fallback failed: {e}")
            
    if not found:
        print("    Warning: Save dialog did not appear.")

def _toggle_playlist_in_dialog(driver, playlist_name: str, should_be_checked: bool) -> bool:
    """Helper to find a playlist in the dialog (with scrolling) and toggle its state."""
    try:
        # Wait for items to load
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "yt-list-item-view-model, ytd-playlist-add-to-option-renderer, toggleable-list-item-view-model")))
        
        last_item_count = 0
        for _ in range(30): # Max scrolls
            items = driver.find_elements(By.CSS_SELECTOR, "yt-list-item-view-model, ytd-playlist-add-to-option-renderer, toggleable-list-item-view-model")
            
            for item in items:
                try:
                    # Find title using various methods
                    title = ""
                    title_els = item.find_elements(By.CSS_SELECTOR, ".ytListItemViewModelTitle, #label, .ytListItemViewModelTitleWrapper, span")
                    for el in title_els:
                        t = el.text.strip()
                        if t: 
                            title = t
                            break
                    
                    if not title: continue
                    
                    if title.lower() == playlist_name.lower():
                        # Determine current state - YT's new UI uses aria-label text or aria-pressed
                        is_checked = False
                        try:
                            aria_label = (item.get_attribute("aria-label") or "").lower()
                            aria_pressed = (item.get_attribute("aria-pressed") or "").lower()
                            
                            if aria_pressed == "true":
                                is_checked = True
                            elif "selected" in aria_label and "not selected" not in aria_label:
                                is_checked = True
                            else:
                                # Fallback to older attributes or sub-elements
                                val = item.get_attribute("aria-checked") or item.get_attribute("aria-selected")
                                if val == "true":
                                    is_checked = True
                                else:
                                    try:
                                        btn = item.find_element(By.TAG_NAME, "button")
                                        btn_label = (btn.get_attribute("aria-label") or "").lower()
                                        if btn.get_attribute("aria-pressed") == "true" or btn.get_attribute("aria-checked") == "true" or ("selected" in btn_label and "not selected" not in btn_label):
                                            is_checked = True
                                    except:
                                        try:
                                            checkbox = item.find_element(By.CSS_SELECTOR, "tp-yt-paper-checkbox, #checkbox")
                                            if checkbox.get_attribute("aria-checked") == "true":
                                                is_checked = True
                                        except: pass
                        except: pass
                        
                        if is_checked != should_be_checked:
                            print(f"    -> Toggling '{title}' (setting to {should_be_checked})")
                            # Use JS click if standard click fails
                            try:
                                item.click()
                            except:
                                driver.execute_script("arguments[0].click();", item)
                            time.sleep(1.5)
                        else:
                            print(f"    -> '{title}' already in state {should_be_checked}")
                        return True
                except:
                    continue
            
            # Scroll down the dialog
            driver.execute_script("""
                var container = document.querySelector('yt-sheet-view-model #content, ytd-add-to-playlist-create-renderer #playlists, #content-icon-view-model');
                if (container) {
                    container.scrollTop += 600;
                } else {
                    window.scrollBy(0, 600);
                }
            """)
            time.sleep(1.5)
            
            if len(items) == last_item_count:
                # Try one more scroll method if count didn't change
                driver.execute_script("window.dispatchEvent(new KeyboardEvent('keydown', {'key': 'PageDown'}));")
                time.sleep(1)
                
            last_item_count = len(items)
            
        print(f"    Warning: Playlist '{playlist_name}' not found in dialog.")
        return False
    except Exception as e:
        print(f"    Error in dialog interaction: {e}")
        return False
def add_video_to_playlist(video_url: str, playlist_name: str, driver=None) -> bool:
    """Adds a video to a specific playlist by name using fast async JS execution."""
    if os.environ.get("MOCK_YT") == "1":
        print(f"MOCK: Added {video_url} to playlist '{playlist_name}'")
        return True
    own_driver = False
    if not driver:
        driver = get_browser()
        own_driver = True
    try:
        if video_url.startswith("/"):
            video_url = "https://www.youtube.com" + video_url
        print(f"  Navigating to {video_url}...")
        driver.get(video_url)
        _wait_for_watch_page_load(driver)
        
        result = driver.execute_async_script(f"""
            const done = arguments[arguments.length - 1];
            async function add() {{
                // 0. Mute all videos immediately
                document.querySelectorAll('video').forEach(v => {{
                    v.muted = true;
                    v.pause();
                }});

                // 0.5. Detect bot-check wall or sign-in requirement
                let pageText = document.body ? document.body.innerText : '';
                if (pageText.includes("Sign in to confirm you're not a bot") || 
                    pageText.includes("Sign in to add this video to a playlist") ||
                    document.querySelector('ytd-enforcement-message-view-model') ||
                    document.querySelector('[data-layer-name="sign-in-to-add-to-playlist-confirmation"]')) {{
                    return "Browser not logged in: YouTube is showing a sign-in wall. Import YouTube cookies via Settings > Admin Tools.";
                }}

                let isKids = Array.from(document.querySelectorAll('*')).some(el => el.textContent && el.textContent.includes("Choices for families"));
                let container = document.querySelector('ytd-watch-metadata, #top-row, ytd-video-primary-info-renderer') || document;
                let saveBtn = Array.from(container.querySelectorAll('button')).find(b => {{
                    let match = b.getAttribute('aria-label') === 'Save to playlist' || 
                                b.innerText.trim() === 'Save' ||
                                (b.querySelector('span') && b.querySelector('span').innerText.trim() === 'Save');
                    if (!match) return false;
                    let rect = b.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && window.getComputedStyle(b).display !== 'none';
                }});
                
                if (isKids || (saveBtn && (saveBtn.hasAttribute('disabled') || saveBtn.disabled || saveBtn.getAttribute('aria-disabled') === 'true'))) {{
                    return "Video is marked 'Made for Kids' (Save button is disabled) - YT disables saving these to playlists";
                }}

                if (!saveBtn) {{
                    let moreBtn = container.querySelector('button[aria-label="More actions"]');
                    if (moreBtn) {{
                        moreBtn.click();
                        await new Promise(r => setTimeout(r, 1000));
                        let saveItem = Array.from(document.querySelectorAll('tp-yt-paper-item, yt-list-item-view-model')).find(i => i.innerText.includes('Save'));
                        if (saveItem) saveItem.click();
                    }}
                }} else {{
                    saveBtn.click();
                }}
                
                // 2. Wait for dialog items to appear (with retries)
                let items = [];
                for (let i = 0; i < 30; i++) {{
                    await new Promise(r => setTimeout(r, 1000));
                    let dialog = document.querySelector('ytd-add-to-playlist-renderer, yt-sheet-view-model, yt-action-sheet-view-model, #playlists-list, #playlists');
                    if (dialog) {{
                        items = Array.from(dialog.querySelectorAll('ytd-playlist-add-to-option-renderer, yt-list-item-view-model, tp-yt-paper-item, [role="checkbox"], [role="menuitemcheckbox"], .ytd-add-to-playlist-renderer, #playlists-list > *'));
                        if (items.length > 3) break;
                    }}
                }}
                
                let foundNames = items.map(i => (i.innerText || i.textContent || "").split("\\n")[0].trim()).filter(n => n).join(", ");
                if (items.length === 0) {{
                    let dialog = document.querySelector('ytd-add-to-playlist-renderer, yt-sheet-view-model, yt-action-sheet-view-model, #playlists-list, #playlists');
                    return "No items found. Dialog HTML: " + (dialog ? dialog.innerHTML.substring(0, 500) : "Dialog not found");
                }}
                
                function isChecked(el) {{
                    if (el.getAttribute('aria-pressed') === 'true') return true;
                    let label = el.getAttribute('aria-label') || '';
                    if (label.includes(', Selected') || (label.includes('Selected') && !label.includes('Not selected'))) return true;
                    let btn = el.querySelector('button[aria-pressed="true"]');
                    if (btn) return true;
                    if (el.getAttribute('aria-checked') === 'true') return true;
                    let cb = el.querySelector('tp-yt-paper-checkbox, input[type="checkbox"], [role="checkbox"]');
                    if (cb && cb.getAttribute('aria-checked') === 'true') return true;
                    if (cb && cb.checked) return true;
                    return false;
                }}

                function clickItem(el) {{
                    let btn = el.querySelector('button, .yt-list-item-view-model-wiz__checkbox, tp-yt-paper-checkbox');
                    if (btn) btn.click(); else el.click();
                }}

                let targetItem = items.find(o => o.textContent.toLowerCase().includes("{playlist_name.lower()}"));
                if (targetItem) {{
                    if (!isChecked(targetItem)) {{
                        clickItem(targetItem);
                        return "Successfully added";
                    }} else {{
                        return "Already in playlist";
                    }}
                }}
                return "Playlist '{playlist_name}' not found. Items found: " + foundNames;
            }}
            add().then(done).catch(err => done("Error: " + err));
        """)
        
        print(f"  Add result: {result}")
        if result and ("Successfully added" in result or "Already in playlist" in result):
            return True
        raise RuntimeError(result)
    finally:
        # Close dialog escape
        try:
            driver.execute_script("document.dispatchEvent(new KeyboardEvent('keydown', {'key': 'Escape'}));")
        except: pass
        if own_driver:
            driver.quit()

def remove_video_from_playlist(video_url: str, playlist_name: str, driver=None) -> bool:
    """Removes a video from a specific playlist by name using fast async JS execution."""
    if os.environ.get("MOCK_YT") == "1":
        print(f"MOCK: Removed {video_url} from playlist '{playlist_name}'")
        return True
    own_driver = False
    if not driver:
        driver = get_browser()
        own_driver = True
    try:
        if video_url.startswith("/"):
            video_url = "https://www.youtube.com" + video_url
        print(f"  Navigating to {video_url}...")
        driver.get(video_url)
        _wait_for_watch_page_load(driver)
        
        result = driver.execute_async_script(f"""
            const done = arguments[arguments.length - 1];
            async function remove() {{
                // 0. Mute all videos immediately
                document.querySelectorAll('video').forEach(v => {{
                    v.muted = true;
                    v.pause();
                }});

                // 0.5. Detect bot-check wall or sign-in requirement
                let pageText = document.body ? document.body.innerText : '';
                if (pageText.includes("Sign in to confirm you're not a bot") || 
                    pageText.includes("Sign in to add this video to a playlist") ||
                    document.querySelector('ytd-enforcement-message-view-model') ||
                    document.querySelector('[data-layer-name="sign-in-to-add-to-playlist-confirmation"]')) {{
                    return "Browser not logged in: YouTube is showing a sign-in wall. Import YouTube cookies via Settings > Admin Tools.";
                }}

                let isKids = Array.from(document.querySelectorAll('*')).some(el => el.textContent && el.textContent.includes("Choices for families"));
                let container = document.querySelector('ytd-watch-metadata, #top-row, ytd-video-primary-info-renderer') || document;
                let saveBtn = Array.from(container.querySelectorAll('button')).find(b => {{
                    let match = b.getAttribute('aria-label') === 'Save to playlist' || 
                                b.innerText.trim() === 'Save' ||
                                (b.querySelector('span') && b.querySelector('span').innerText.trim() === 'Save');
                    if (!match) return false;
                    let rect = b.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && window.getComputedStyle(b).display !== 'none';
                }});
                
                if (isKids || (saveBtn && (saveBtn.hasAttribute('disabled') || saveBtn.disabled || saveBtn.getAttribute('aria-disabled') === 'true'))) {{
                    return "Video is marked 'Made for Kids' (Save button is disabled) - YT disables saving these to playlists";
                }}

                if (!saveBtn) {{
                    let moreBtn = container.querySelector('button[aria-label="More actions"]');
                    if (moreBtn) {{
                        moreBtn.click();
                        await new Promise(r => setTimeout(r, 1000));
                        let saveItem = Array.from(document.querySelectorAll('tp-yt-paper-item, yt-list-item-view-model')).find(i => i.innerText.includes('Save'));
                        if (saveItem) saveItem.click();
                    }}
                }} else {{
                    saveBtn.click();
                }}
                
                // 2. Wait for dialog items to appear (with retries)
                let items = [];
                for (let i = 0; i < 30; i++) {{
                    await new Promise(r => setTimeout(r, 1000));
                    let dialog = document.querySelector('ytd-add-to-playlist-renderer, yt-sheet-view-model, yt-action-sheet-view-model, #playlists-list, #playlists');
                    if (dialog) {{
                        items = Array.from(dialog.querySelectorAll('ytd-playlist-add-to-option-renderer, yt-list-item-view-model, tp-yt-paper-item, [role="checkbox"], [role="menuitemcheckbox"], .ytd-add-to-playlist-renderer, #playlists-list > *'));
                        if (items.length > 3) break;
                    }}
                }}
                
                let foundNames = items.map(i => (i.innerText || i.textContent || "").split("\\n")[0].trim()).filter(n => n).join(", ");
                if (items.length === 0) {{
                    let dialog = document.querySelector('ytd-add-to-playlist-renderer, yt-sheet-view-model, yt-action-sheet-view-model, #playlists-list, #playlists');
                    return "No items found. Dialog HTML: " + (dialog ? dialog.innerHTML.substring(0, 500) : "Dialog not found");
                }}
                
                function isChecked(el) {{
                    if (el.getAttribute('aria-pressed') === 'true') return true;
                    let label = el.getAttribute('aria-label') || '';
                    if (label.includes(', Selected') || (label.includes('Selected') && !label.includes('Not selected'))) return true;
                    let btn = el.querySelector('button[aria-pressed="true"]');
                    if (btn) return true;
                    if (el.getAttribute('aria-checked') === 'true') return true;
                    let cb = el.querySelector('tp-yt-paper-checkbox, input[type="checkbox"], [role="checkbox"]');
                    if (cb && cb.getAttribute('aria-checked') === 'true') return true;
                    if (cb && cb.checked) return true;
                    return false;
                }}

                function clickItem(el) {{
                    let btn = el.querySelector('button, .yt-list-item-view-model-wiz__checkbox, tp-yt-paper-checkbox');
                    if (btn) btn.click(); else el.click();
                }}

                let sourceItem = items.find(o => o.textContent.toLowerCase().includes("{playlist_name.lower()}"));
                if (sourceItem) {{
                    if (isChecked(sourceItem)) {{
                        clickItem(sourceItem);
                        return "Successfully removed";
                    }} else {{
                        return "Already removed from playlist";
                    }}
                }}
                return "Playlist '{playlist_name}' not found. Items found: " + foundNames;
            }}
            remove().then(done).catch(err => done("Error: " + err));
        """)
        
        print(f"  Remove result: {result}")
        if result and ("Successfully removed" in result or "Already removed from playlist" in result):
            return True
        raise RuntimeError(result)
    finally:
        # Close dialog escape
        try:
            driver.execute_script("document.dispatchEvent(new KeyboardEvent('keydown', {'key': 'Escape'}));")
        except: pass
        if own_driver:
            driver.quit()

def move_video(video_url: str, source_playlist_name: str, target_playlist_name: str, driver=None) -> bool:
    if os.environ.get("MOCK_YT") == "1":
        print(f"MOCK: Moved {video_url} from '{source_playlist_name}' to '{target_playlist_name}'")
        return True
    own_driver = False
    if not driver:
        driver = get_browser()
        own_driver = True
    try:
        if video_url.startswith("/"):
            video_url = "https://www.youtube.com" + video_url

        # Attempt direct move on current page first to bypass bot-check walls on watch pages
        import re
        video_id = None
        m = re.search(r"[?&]v=([^&#]+)", video_url)
        if m:
            video_id = m.group(1)
        elif "youtu.be/" in video_url:
            video_id = video_url.split("youtu.be/")[-1].split("?")[0]
        elif "/watch?v=" in video_url:
            video_id = video_url.split("v=")[-1].split("&")[0]

        if video_id:
            try:
                print(f"  Attempting direct move on current page for video {video_id}...")
                result = driver.execute_async_script(f"""
                    const done = arguments[arguments.length - 1];
                    async function moveDirectly() {{
                        try {{
                            let videoId = "{video_id}";
                            let row = Array.from(document.querySelectorAll('ytd-playlist-video-renderer')).find(r => {{
                                let link = r.querySelector('a[href*="' + videoId + '"]');
                                return link !== null;
                            }});
                            if (!row) return "Row not found";
                            
                            let menuBtn = row.querySelector('button[aria-label="Action menu"], yt-icon-button#button, #menu button, ytd-menu-renderer button');
                            if (!menuBtn) return "Menu button not found";
                            menuBtn.click();
                            
                            let savePlaylistItem = null;
                            for (let i = 0; i < 15; i++) {{
                                await new Promise(r => setTimeout(r, 200));
                                let menuItems = Array.from(document.querySelectorAll('tp-yt-paper-item, yt-list-item-view-model, ytd-menu-service-item-renderer, ytd-menu-navigation-item-renderer'));
                                savePlaylistItem = menuItems.find(item => item.textContent.includes("Save to playlist"));
                                if (savePlaylistItem) break;
                            }}
                            if (!savePlaylistItem) {{
                                document.body.click();
                                return "Save to playlist option not found";
                            }}
                            savePlaylistItem.click();
                            
                            let items = [];
                            for (let i = 0; i < 20; i++) {{
                                await new Promise(r => setTimeout(r, 250));
                                let dialog = document.querySelector('ytd-add-to-playlist-renderer, #playlists-list');
                                if (dialog) {{
                                    items = Array.from(dialog.querySelectorAll('ytd-playlist-add-to-option-renderer, yt-list-item-view-model, tp-yt-paper-item, [role="checkbox"], [role="menuitemcheckbox"], .ytd-add-to-playlist-renderer, #playlists-list > *'));
                                    if (items.length > 3) break;
                                }}
                            }}
                            
                            let foundNames = items.map(i => (i.innerText || i.textContent || "").split("\\\\n")[0].trim()).filter(n => n).join(", ");
                            if (items.length === 0) {{
                                return "Playlist dialog items not found";
                            }}
                            
                            function isChecked(el) {{
                                if (el.getAttribute('aria-pressed') === 'true') return true;
                                let label = el.getAttribute('aria-label') || '';
                                if (label.includes(', Selected') || (label.includes('Selected') && !label.includes('Not selected'))) return true;
                                let btn = el.querySelector('button[aria-pressed="true"]');
                                if (btn) return true;
                                if (el.getAttribute('aria-checked') === 'true') return true;
                                let cb = el.querySelector('tp-yt-paper-checkbox, input[type="checkbox"], [role="checkbox"]');
                                if (cb && cb.getAttribute('aria-checked') === 'true') return true;
                                if (cb && cb.checked) return true;
                                if (el.querySelector('[aria-checked="true"]') !== null) return true;
                                return false;
                            }}
                            
                            function clickItem(el) {{
                                let btn = el.querySelector('button, .yt-list-item-view-model-wiz__checkbox, tp-yt-paper-checkbox');
                                if (btn) btn.click(); else el.click();
                            }}
                            
                            let targetItem = items.find(o => o.textContent.toLowerCase().includes("{target_playlist_name.lower()}"));
                            let sourceItem = items.find(o => o.textContent.toLowerCase().includes("{source_playlist_name.lower()}"));
                            
                            let status = [];
                            
                            if (targetItem) {{
                                if (!isChecked(targetItem)) {{
                                    clickItem(targetItem);
                                    status.push("Added to target");
                                }} else {{
                                    status.push("Already in target");
                                }}
                            }} else {{
                                status.push("Target '{target_playlist_name}' not found");
                            }}
                            
                            await new Promise(r => setTimeout(r, 1000));
                            
                            if (sourceItem) {{
                                if (isChecked(sourceItem)) {{
                                    clickItem(sourceItem);
                                    status.push("Removed from source");
                                }} else {{
                                    status.push("Already removed from source");
                                }}
                            }} else {{
                                status.push("Source '{source_playlist_name}' not found");
                            }}
                            
                            let closeBtn = document.querySelector('ytd-add-to-playlist-renderer button[aria-label="Close"], #playlists-list button[aria-label="Close"], ytd-add-to-playlist-renderer #close-button button');
                            if (closeBtn) closeBtn.click(); else document.body.click();
                            
                            return status.join(", ") + " | Items found: " + items.length + " | Names: " + foundNames;
                        }} catch (err) {{
                            return "Error: " + err;
                        }}
                    }}
                    moveDirectly().then(done).catch(err => done("Error: " + err));
                """)
                print(f"  Direct move attempt result: {result}")
                if result and "not found" not in result and "Error" not in result and "Row not found" not in result:
                    print(f"  Direct move succeeded without navigating watch page!")
                    return True
                else:
                    print(f"  Direct move not possible ({result}). Falling back to watch page navigation...")
            except Exception as de:
                print(f"  Direct move failed with exception: {de}. Falling back to watch page navigation...")

        print(f"  Navigating to {video_url}...")
        driver.get(video_url)
        _wait_for_watch_page_load(driver)
        
        # Save a debug screenshot of the page before opening dialog
        driver.save_screenshot("move_debug_pre.png")
        
        # Use a powerful JS script to do the entire move operation
        # This script finds the save button, opens the dialog, checks target, and unchecks source.
        result = driver.execute_async_script(f"""
            const done = arguments[arguments.length - 1];
            async function move() {{
                // 0. Mute all videos immediately
                document.querySelectorAll('video').forEach(v => {{
                    v.muted = true;
                    v.pause();
                }});

                // 0.5. Detect bot-check wall or sign-in requirement
                let pageText = document.body ? document.body.innerText : '';
                if (pageText.includes("Sign in to confirm you're not a bot") || 
                    pageText.includes("Sign in to add this video to a playlist") ||
                    document.querySelector('ytd-enforcement-message-view-model') ||
                    document.querySelector('[data-layer-name="sign-in-to-add-to-playlist-confirmation"]')) {{
                    return "Browser not logged in: YouTube is showing a sign-in wall. Import YouTube cookies via Settings > Admin Tools.";
                }}

                // Check if the video is "Made for Kids" or if the Save button is disabled
                let isKids = Array.from(document.querySelectorAll('*')).some(el => el.textContent && el.textContent.includes("Choices for families"));
                let container = document.querySelector('ytd-watch-metadata, #top-row, ytd-video-primary-info-renderer') || document;
                let saveBtn = Array.from(container.querySelectorAll('button')).find(b => {{
                    let match = b.getAttribute('aria-label') === 'Save to playlist' || 
                                b.innerText.trim() === 'Save' ||
                                (b.querySelector('span') && b.querySelector('span').innerText.trim() === 'Save');
                    if (!match) return false;
                    let rect = b.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0 && window.getComputedStyle(b).display !== 'none';
                }});
                
                if (isKids || (saveBtn && (saveBtn.hasAttribute('disabled') || saveBtn.disabled || saveBtn.getAttribute('aria-disabled') === 'true'))) {{
                    return "Video is marked 'Made for Kids' (Save button is disabled) - YT disables saving these to playlists";
                }}

                if (!saveBtn) {{
                    let moreBtn = container.querySelector('button[aria-label="More actions"]');
                    if (moreBtn) {{
                        moreBtn.click();
                        await new Promise(r => setTimeout(r, 1000));
                        let saveItem = Array.from(document.querySelectorAll('tp-yt-paper-item, yt-list-item-view-model')).find(i => i.innerText.includes('Save'));
                        if (saveItem) saveItem.click();
                    }}
                }} else {{
                    saveBtn.click();
                }}
                
                // 2. Wait for dialog items to appear (with retries)
                let items = [];
                for (let i = 0; i < 30; i++) {{
                    await new Promise(r => setTimeout(r, 1000));
                    let dialog = document.querySelector('ytd-add-to-playlist-renderer, yt-sheet-view-model, yt-action-sheet-view-model, #playlists-list, #playlists');
                    if (dialog) {{
                        items = Array.from(dialog.querySelectorAll('ytd-playlist-add-to-option-renderer, yt-list-item-view-model, tp-yt-paper-item, [role="checkbox"], [role="menuitemcheckbox"], .ytd-add-to-playlist-renderer, #playlists-list > *'));
                        if (items.length > 3) break;
                    }}
                }}
                
                let foundNames = items.map(i => (i.innerText || i.textContent || "").split("\\n")[0].trim()).filter(n => n).join(", ");
                if (items.length === 0) {{
                    let dialog = document.querySelector('ytd-add-to-playlist-renderer, yt-sheet-view-model, yt-action-sheet-view-model, #playlists-list, #playlists');
                    return "No items found. Dialog HTML: " + (dialog ? dialog.innerHTML.substring(0, 500) : "Dialog not found");
                }}
                
                function isChecked(el) {{
                    // Newest YT UI uses aria-pressed="true" or "Selected" in aria-label
                    if (el.getAttribute('aria-pressed') === 'true') return true;
                    let label = el.getAttribute('aria-label') || '';
                    if (label.includes(', Selected') || (label.includes('Selected') && !label.includes('Not selected'))) return true;
                    
                    let btn = el.querySelector('button[aria-pressed="true"]');
                    if (btn) return true;

                    // Fallbacks for older UI
                    if (el.getAttribute('aria-checked') === 'true') return true;
                    let cb = el.querySelector('tp-yt-paper-checkbox, input[type="checkbox"], [role="checkbox"]');
                    if (cb && cb.getAttribute('aria-checked') === 'true') return true;
                    if (cb && cb.checked) return true;
                    if (el.querySelector('[aria-checked="true"]') !== null) return true;
                    if (el.innerHTML.includes('checked=""') || el.innerHTML.includes('checked="true"')) return true;
                    return false;
                }}

                function clickItem(el) {{
                    // Try to click the specific button inside if it exists, otherwise the whole element
                    let btn = el.querySelector('button, .yt-list-item-view-model-wiz__checkbox, tp-yt-paper-checkbox');
                    if (btn) btn.click(); else el.click();
                }}

                let targetItem = items.find(o => o.textContent.toLowerCase().includes("{target_playlist_name.lower()}"));
                let sourceItem = items.find(o => o.textContent.toLowerCase().includes("{source_playlist_name.lower()}"));
                
                let status = [];
                
                if (targetItem) {{
                    if (!isChecked(targetItem)) {{
                        clickItem(targetItem);
                        status.push("Added to target");
                    }} else {{
                        status.push("Already in target");
                    }}
                }} else {{
                    status.push("Target '{target_playlist_name}' not found");
                }}
                
                await new Promise(r => setTimeout(r, 1500));
                
                if (sourceItem) {{
                    if (isChecked(sourceItem)) {{
                        clickItem(sourceItem);
                        status.push("Removed from source");
                    }} else {{
                        status.push("Already removed from source");
                    }}
                }} else {{
                    status.push("Source '{source_playlist_name}' not found");
                }}
                
                return status.join(", ") + " | Items found: " + items.length + " | Names: " + foundNames;
            }}
            move().then(done).catch(err => done("Error: " + err));
        """)
        
        # Save a debug screenshot of the dialog
        driver.save_screenshot("move_debug_dialog.png")
        
        print(f"  Result: {result}")
        time.sleep(2)
        
        if "Video is marked 'Made for Kids'" in result:
            raise RuntimeError(result)
        if "Browser not logged in" in result:
            raise RuntimeError(result)
        if "Dialog not found" in result or "No items found" in result:
            raise RuntimeError(result)
        if "not found" in result:
            raise RuntimeError(f"Move failed: {result}")
            
        return True
    finally:
        if own_driver:
            driver.quit()

def create_playlist(video_url: str, playlist_name: str, privacy: str = "Private") -> bool:
    if os.environ.get("MOCK_YT") == "1":
        print(f"MOCK: Created playlist '{playlist_name}'")
        return True
    driver = get_browser()
    try:
        driver.get(video_url)
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "video")))
        time.sleep(2)
        
        _open_save_dialog(driver)
        
        dialog = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-add-to-playlist-renderer"))
        )
        
        create_btn = dialog.find_element(By.XPATH, "//ytd-compact-link-renderer[contains(., 'Create new playlist')]")
        create_btn.click()
        
        input_field = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Enter playlist name...']"))
        )
        input_field.send_keys(playlist_name)
        
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Create']")
        submit_btn.click()
        
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//tp-yt-paper-toast[contains(., 'Playlist created')]"))
        )
        return True
    finally:
        driver.quit()

def get_all_playlists() -> list:
    """Gets a list of all playlists from the feed/playlists page."""
    if os.environ.get("MOCK_YT") == "1":
        return [
            {"name": "Watch Later", "url": "https://www.youtube.com/playlist?list=WL"},
            {"name": "AI", "url": "https://www.youtube.com/playlist?list=PL_AI"},
            {"name": "Auto", "url": "https://www.youtube.com/playlist?list=PL_Auto"},
            {"name": "Overland", "url": "https://www.youtube.com/playlist?list=PL_Overland"},
            {"name": "Drones", "url": "https://www.youtube.com/playlist?list=PL_Drones"},
            {"name": "Football", "url": "https://www.youtube.com/playlist?list=PL_Football"},
            {"name": "Music", "url": "https://www.youtube.com/playlist?list=PL_Music"}
        ]
    driver = get_browser()
    try:
        driver.get("https://www.youtube.com/feed/playlists")
        time.sleep(5)
        
        # Scroll to load all playlists
        last_height = driver.execute_script("return document.documentElement.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(3)
            new_height = driver.execute_script("return document.documentElement.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
        
        playlists = []
        playlists_dict = {}
        
        # Try different selectors for links
        selectors = [
            "//a[contains(@href, 'list=')]",
            "//ytd-playlist-renderer//a[@id='video-title']",
            "//ytd-grid-playlist-renderer//a[@id='video-title']"
        ]
        
        links = []
        for selector in selectors:
            try:
                found = driver.find_elements(By.XPATH, selector)
                if found:
                    links.extend(found)
            except:
                continue
        
        if not links:
            # Try finding all links in the main content
            try:
                main = driver.find_element(By.ID, "page-manager")
                links = main.find_elements(By.TAG_NAME, "a")
            except:
                pass

        for link in links:
            try:
                href = link.get_attribute("href")
                if not href or "list=" not in href:
                    continue
                    
                text = link.text.strip().replace("\n", " ")
                title = link.get_attribute("title")
                name = text if text else title
                
                if not name or not href:
                    continue
                    
                name_lower = name.lower()
                # Skip metadata links like "300 videos" or "View full playlist"
                if any(k in name_lower for k in [" videos", " video", " lessons", "play all", "view full playlist"]):
                    continue
                    
                clean_url = "https://www.youtube.com/playlist?list=" + href.split("list=")[1].split("&")[0]
                
                # If we already have a name for this URL, only replace if the new name is better (longer/descriptive)
                if clean_url not in playlists_dict or len(name) > len(playlists_dict[clean_url]):
                    playlists_dict[clean_url] = name
            except:
                continue
                
        # Always include Watch Later
        if "https://www.youtube.com/playlist?list=WL" not in playlists_dict:
            playlists_dict["https://www.youtube.com/playlist?list=WL"] = "Watch later"
            
        for url, name in playlists_dict.items():
            playlists.append({"name": name, "url": url})
            
        print(f"Discovered {len(playlists)} playlists.")
        return playlists
    finally:
        driver.quit()

def list_videos_in_playlist(playlist_name_or_url: str, driver=None) -> list:
    """Lists all videos in a given playlist by name or direct URL."""
    if os.environ.get("MOCK_YT") == "1":
        import random
        suffix = playlist_name_or_url.split("list=")[-1] if "list=" in playlist_name_or_url else playlist_name_or_url
        return [
            {
                "title": f"Mock Video {i} in {suffix[:10]}",
                "url": f"https://www.youtube.com/watch?v=mockvid{i}_{suffix[:5]}",
                "channel": random.choice(["Tech Insider", "Linus Tech Tips", "Car Wow", "NFL", "DJI Creator"]),
                "published": f"{random.randint(1, 11)} months ago"
            }
            for i in range(1, 15)
        ]
    own_driver = False
    if not driver:
        driver = get_browser()
        own_driver = True
    try:
        if "youtube.com" in playlist_name_or_url and "list=" in playlist_name_or_url:
            # Extract list ID and go directly to the playlist page
            list_id = playlist_name_or_url.split("list=")[1].split("&")[0]
            driver.get(f"https://www.youtube.com/playlist?list={list_id}")
        elif playlist_name_or_url in ["WL", "LL"]:
            driver.get(f"https://www.youtube.com/playlist?list={playlist_name_or_url}")
        else:
            driver.get("https://www.youtube.com/")
            
            # Ensure left guide is open
            try:
                guide = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "guide-inner-content"))
                )
                if not guide.is_displayed():
                    driver.find_element(By.CSS_SELECTOR, "button#guide-icon").click()
                    time.sleep(1)
            except TimeoutException:
                pass
                
            # Click Show more if needed
            try:
                show_more = driver.find_element(By.XPATH, "//ytd-guide-collapsible-entry-renderer//*[contains(text(), 'Show more')]")
                if show_more.is_displayed():
                    show_more.click()
                    time.sleep(1)
            except Exception:
                pass
                
            # Click the playlist
            try:
                playlist_link = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, f"//div[@id='guide-inner-content']//a[@title='{playlist_name_or_url}' or contains(., '{playlist_name_or_url}')]"))
                )
                playlist_link.click()
            except TimeoutException:
                raise Exception(f"Playlist '{playlist_name_or_url}' not found in the sidebar menu. Try providing the direct playlist URL instead.")
            
        # Give page some extra time to settle before querying
        time.sleep(10)
        
        # Wait for initial load
        try:
            WebDriverWait(driver, 90).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-playlist-video-renderer"))
            )
        except TimeoutException:
            print("Timeout waiting for playlist video elements. Saving screenshot to debug_timeout_wl.png...")
            try:
                driver.save_screenshot("debug_timeout_wl.png")
            except Exception as se:
                print(f"Failed to capture debug screenshot: {se}")
            return []

        # Get initial count of loaded videos
        initial_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        video_count = len(initial_elements)
        
        # If there are fewer than 100 videos initially, they are all loaded on the first page.
        # Just force a single paint to render lazy elements and skip the scroll loop.
        if video_count < 100:
            try:
                if hasattr(driver, 'get_screenshot_as_png'):
                    driver.get_screenshot_as_png()
                elif hasattr(driver, 'page') and hasattr(driver.page, 'screenshot'):
                    driver.page.screenshot()
            except Exception as pe:
                pass
            time.sleep(1)
            video_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
            video_count = len(video_elements)
            print(f"  Fewer than 100 videos ({video_count}). Skipping scroll loop.")
        else:
            # Scroll to the bottom to load all videos
            print(f"Scrolling to load all videos in {playlist_name_or_url}...")
            consecutive_same_count = 0
            while True:
                # Scroll down and wait
                driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
                time.sleep(3)
                
                # Force layout calculation to trigger IntersectionObserver in hidden/offscreen windows without software screenshot rendering
                try:
                    driver.execute_script("window.dispatchEvent(new Event('resize')); document.body.offsetHeight;")
                except Exception as pe:
                    print(f"  Warning: failed to force layout: {pe}")
                time.sleep(2)
                
                new_video_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
                new_count = len(new_video_elements)
                print(f"  Found {new_count} videos so far...")
                
                if new_count == video_count:
                    consecutive_same_count += 1
                    if consecutive_same_count >= 5: # Increased from 3 to 5 retries
                        break
                else:
                    video_count = new_count
                    consecutive_same_count = 0
                    
                # Safety break for extremely large playlists
                if video_count > 2000: # Increased from 1000
                    break
        
        results = []
        video_elements = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        if not video_elements:
            print("No video elements found on the page.")
            driver.save_screenshot("debug_empty_wl.png")
            return []
        for v in video_elements:
            try:
                title_el = v.find_element(By.CSS_SELECTOR, "#video-title")
                title = title_el.get_attribute("title")
                if not title:
                    title = title_el.text.strip()
                else:
                    title = title.strip()
                href = title_el.get_attribute("href")
                
                channel = ""
                try:
                    channel_el = v.find_element(By.CSS_SELECTOR, "ytd-channel-name a, #byline a, #text-container.ytd-channel-name")
                    channel = channel_el.text.strip()
                except Exception:
                    pass
                    
                published = ""
                try:
                    metadata_spans = v.find_elements(By.CSS_SELECTOR, "#metadata-line span, .inline-metadata-item, #video-info span")
                    if not metadata_spans:
                        try:
                            info_el = v.find_element(By.CSS_SELECTOR, "#video-info")
                            if info_el:
                                metadata_spans = [info_el]
                        except Exception:
                            pass
                    
                    time_keywords = ["ago", "yesterday", "hours", "days", "weeks", "months", "years", "hour", "day", "week", "month", "year", "minutes", "minute", "seconds", "second"]
                    for span in metadata_spans:
                        text = span.text.strip()
                        if text:
                            parts = [p.strip() for p in text.split("•")]
                            for part in parts:
                                if any(k in part.lower() for k in time_keywords):
                                    published = part
                                    break
                            if published:
                                break
                                
                    if not published and metadata_spans:
                        last_text = metadata_spans[-1].text.strip()
                        parts = [p.strip() for p in last_text.split("•")]
                        for part in parts:
                            if part and not any(k in part.lower() for k in ["view", "watching"]):
                                published = part
                                break
                except Exception:
                    pass
                    
                duration = ""
                try:
                    duration_el = v.find_element(By.CSS_SELECTOR, "ytd-thumbnail-overlay-time-status-renderer")
                    duration = duration_el.text.strip()
                except Exception:
                    pass

                if href:
                    url = href.split("&list=")[0]
                    results.append({
                        "title": title,
                        "url": url,
                        "channel": channel,
                        "published": published if published else "Unknown",
                        "duration": duration if duration else "Unknown"
                    })
            except Exception:
                continue
                
        return results
    finally:
        if own_driver:
            driver.quit()
