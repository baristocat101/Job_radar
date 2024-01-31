import random
import logging
import os

from gologin import GoLogin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from config.tokens import gologin_tokens

logger = logging.getLogger(__name__)

############################################################################
# Start GoLogin-profile browser and setup remote control
############################################################################
"""
Gologin provides browser profiles that utilize proxies and unique 
fingerprints to hide the underlying browser instance. The browser profile is 
remote controlled using selenium and chromedriver.
"""


def _provide_gl_browser_profile():
    # Generate a random port within the privat port range
    random_client_port = random.randint(49152, 65535)

    token = gologin_tokens["token"]
    profile_id_list = gologin_tokens["profile_id_list"]
    random_profile_id = random.choice(profile_id_list)

    gl = GoLogin(
        {"token": token, "profile_id": random_profile_id, "port": random_client_port}
    )

    return gl


def start_remote_debug_gologin_browser():
    logger.info("Starting new browser session")
    # start gologin-profile-browser as a remote debugging instance
    gl = _provide_gl_browser_profile()

    try:
        debugger_address = gl.start()

        # setup remote control with chrome driver
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--incognito")
        options.add_experimental_option("debuggerAddress", debugger_address)
        project_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        webdriver_path = os.path.join(
            project_directory, "webdriver_19", "chromedriver.exe"
        )
        service = Service(executable_path=webdriver_path)
    except Exception as e:
        logger.error(f"An exception occurred: {e}")

    return webdriver.Chrome(service=service, options=options), gl
