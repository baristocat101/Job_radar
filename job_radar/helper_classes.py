import logging
import psutil

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from setup_gologin import start_remote_debug_gologin_browser

logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self):
        self.driver = None
        self.gl = None

    def start_browser_session(self):
        # make sure old processes are shut down
        def _terminate_activer_browser_instances(
            process_name_to_shut, ppid_not_to_shut
        ):
            for process in psutil.process_iter(["pid", "name", "ppid"]):
                if (
                    process.info["name"] == process_name_to_shut
                    and process.info["ppid"] != ppid_not_to_shut
                ):
                    try:
                        process.terminate()
                        print(
                            f"Terminated process '{process_name_to_shut}' with PPID {process.info['ppid']}"
                        )
                    except psutil.NoSuchProcess as e:
                        print(
                            f"Error terminating process '{process_name_to_shut}': {e}"
                        )

        def _ensure_only_one_webdriver_window(self):
            if len(self.driver.window_handles) > 1:
                current_window_handle = driver.current_window_handle
                for handle in self.driver.window_handles:
                    if handle != current_window_handle:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                self.driver.switch_to.window(current_window_handle)

        # shut any active chrome sessions
        _terminate_activer_browser_instances("chrome.exe", None)

        driver, gl = start_remote_debug_gologin_browser()
        driver.implicitly_wait(3)
        self.driver = driver
        self.gl = gl

        # ensure only one webdriver window exist
        _ensure_only_one_webdriver_window(self)

    def stop_browser_session(self):
        try:
            self.driver.quit()
            self.gl.stop()
        except Exception:
            pass

    def restart_browser_session(self):
        self.stop_browser_session()
        logger.info("Stopped browser")
        self.start_browser_session()
        logger.info("Started browser")


def try_except_decorator(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"An exception occurred: {e}")

    return wrapper


class ElementFinder:
    def __init__(self, driver: WebElement):
        self.driver = driver

    # @try_except_decorator
    def find_by_xpath(self, xpath):
        return self.driver.find_element(By.XPATH, xpath)

    # @try_except_decorator
    def find_list_by_xpath(self, xpath):
        return self.driver.find_elements(By.XPATH, xpath)

    # @try_except_decorator
    def find_by_class(self, class_):
        return self.driver.find_element(By.CLASS_NAME, class_)

    # @try_except_decorator
    def find_list_by_class(self, class_):
        return self.driver.find_elements(By.CLASS_NAME, class_)
