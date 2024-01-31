import time
import numpy as np
import re
import logging
import sys
from typing import Dict, List, Tuple

import pandas as pd

from bs4 import BeautifulSoup
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    WebDriverException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from config.scraping_paths import (
    JOBATTRUBUTE_HTML_TAG_CLASS_LIST,
    PATHS_POPUP_BUTTONS,
    HEADLESS_JOBATTRUBUTE_HTML_TAG_CLASS_LIST,
)
from search_criteria import title_filtering, attribute_filtering, SEARCH_KEYWORDS
from manage_jobposts import JobStorageManager
from helper_classes import BrowserManager, ElementFinder
from config.datastructure import DATACOLOUMNS
from log_helpers import log_big_separator, log_small_separator


logger = logging.getLogger(__name__)


def verify_full_list(self, idx, have_been_fully_loaded=0):
    def _retreive_number_of_search_results(self) -> int:
        xpath = """//*[@id="main-content"]/div/h1/span[1]"""
        num_results = ElementFinder(self.driver).find_by_xpath(xpath).text
        if num_results == "1,000+":
            num_results = 1000
        return int(num_results)

    def _retreive_number_of_loaded_results() -> int:
        return len(ElementFinder(self.driver).find_list_by_class("job-search-card"))

    num_res = _retreive_number_of_search_results(self)
    num_loaded = _retreive_number_of_loaded_results()

    logger.info(f"num_loaded/num_results: {num_loaded}/{num_res} - {idx}")

    # if have_been_fully_loaded and (num_res - num_loaded) > 5:
    if (num_res - num_loaded) > 5:
        self.page_loader.ensure_page_has_fully_loaded_joblist()
    return


def _ensure_authorization_wall_not_encountered(driver: WebDriver, href: str):
    logger.info("checking for wall")
    is_wall_encountered = 0
    try:
        ElementFinder(driver).find_by_class("authwall-join-form__title")
    except Exception:
        logger.info("Wall not encountered")
        driver.save_screenshot("screenshots/line_41.png")
        time.sleep(1)
        return is_wall_encountered

    logger.info("Wall encountered")
    is_wall_encountered = 1
    if href is None:
        driver.back()
    else:
        driver.get(href)
    time.sleep(2)

    _ensure_authorization_wall_not_encountered(driver, href)


class ScrapingException(Exception):
    def __init__(
        self,
        message="An exception occurred during scraping.",
        is_next_jobpost_not_found=False,
    ):
        self.message = message
        self.is_next_jobpost_not_found = (
            is_next_jobpost_not_found  # Boolean attribute to control loop exit
        )
        super().__init__(self.message)


class BrowserCrashException(Exception):
    pass


class PageLoader:
    """Class responsible for loading and preparing job search pages for scraping"""

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.element_finder = ElementFinder(driver)
        self.job_element_handler = JobElementHandler(driver)

    def page_scroll(self, direction: str):
        if direction == "up":
            sign = "-"
        else:
            sign = ""

        self.driver.execute_script(
            f"window.scrollTo(0, {sign}document.body.scrollHeight);"
        )
        return

    def ensure_page_has_fully_loaded_joblist(self):
        """
        Linkedin stream search results lazily.
        A dictionary of unique search results is made in order to ensure that
        the page have loaded all job posts. The method will continue to load more
        listed job posts until given stopping criteria have been reached.

        Len of list should be equal the shown number of results shown in top of
        page.
        """

        def _retreive_number_of_search_results() -> int:
            xpath = """//*[@id="main-content"]/div/h1/span[1]"""
            num_results = ElementFinder(self.driver).find_by_xpath(xpath).text
            if num_results == "1,000+":
                num_results = 1000
            return int(num_results)

        def _retreive_number_of_loaded_results() -> int:
            return len(ElementFinder(self.driver).find_list_by_class("job-search-card"))

        def _check_if_bottom_is_reached() -> bool:
            """Checking if bottom of search list element have been reached"""
            is_bottom_not_reached = 0
            try:
                ele_txt = (
                    ElementFinder(self.driver)
                    .find_by_xpath("""//*[@id="main-content"]/section[2]/div[2]/p""")
                    .text
                )

            except Exception:
                ele_txt = (
                    ElementFinder(self.driver)
                    .find_by_xpath("""//*[@id="main-content"]/section[2]/div/p""")
                    .text
                )
            if (
                ele_txt == "You've viewed all jobs for this search"
                or ele_txt == "Du har set alle jobbene for denne søgning"
            ):
                is_bottom_not_reached = 1
            return is_bottom_not_reached

        log_small_separator(logger, "Ensure full loading of joblist")

        num_results = _retreive_number_of_search_results()
        num_loaded = _retreive_number_of_loaded_results()
        unique_result_id_list = []
        num_loaded_prev, is_search_active = 0, 1

        logger.info(f"Number of results to find:   {num_results}")
        jdx = 1
        while is_search_active:
            # collecting all newly loaded jobs
            while jdx < num_loaded:
                xpath = (
                    self.job_element_handler.find_correct_xpath_to_listed_jobelement(
                        jdx
                    )
                )
                html_str = self.element_finder.find_by_xpath(xpath).get_attribute(
                    "outerHTML"
                )
                job_id = self.job_element_handler.find_job_id(
                    html_str, element_type="listed"
                )

                if job_id not in unique_result_id_list:
                    unique_result_id_list.append(job_id)
                jdx += 1

            # checking if stopping criteria have been reached
            logger.info(f"Found:   {len(unique_result_id_list)}")
            if (
                len(unique_result_id_list) >= num_results
                or len(unique_result_id_list) >= 950
            ):
                is_search_active = 0
                break

            # get more results
            num_loaded_prev = num_loaded
            while 1:
                attempt = 1
                try:
                    self.element_finder.find_by_xpath(
                        """//*[@id="main-content"]/section[2]/button"""
                    ).click()
                    time.sleep(1)
                except Exception:
                    try:
                        if _check_if_bottom_is_reached():
                            is_search_active = 0
                            break
                        elif num_loaded >= 1000:
                            is_search_active = 0
                            break
                        else:
                            self.page_scroll("up")
                            time.sleep(1)
                            pass

                    except Exception:
                        self.page_scroll("up")
                        time.sleep(1)
                        pass

                self.page_scroll("down")
                time.sleep(1)
                num_loaded = _retreive_number_of_loaded_results()
                if num_loaded_prev < num_loaded:
                    break
                num_loaded_prev = num_loaded
                attempt += 1

        logger.info("Full joblist loaded")

    def search_and_prepare_page_for_scraping(self, url):
        """
        Search for jobs, wait for page loading and prepare for scraping.
        """
        log_big_separator(logger, "Prepare page for scraping")

        self.driver.maximize_window()
        self.driver.get(url)

        # check that a page with a joblist is retreived
        try:
            self.element_finder.find_by_class("results-context-header")

        except NoSuchElementException:
            # try to load page again
            self.search_and_prepare_page_for_scraping(url)

        # remove popups if they appear
        for xpath in PATHS_POPUP_BUTTONS[:3]:
            try:
                time.sleep(2)
                self.element_finder.find_by_xpath(xpath).click()
            except ElementNotInteractableException as e:
                pass
            except NoSuchElementException as e:
                pass

        self.ensure_page_has_fully_loaded_joblist()
        return


class JobElementHandler:
    """Class for handling job post elements in either listed or extended format."""

    def __init__(self, driver: WebDriver):
        self.driver = driver
        self.element_finder = ElementFinder(driver)

    def find_correct_xpath_to_listed_jobelement(self, idx: int) -> str:
        """Find the corret xpath for listed job element since the correct path
        can vary along the search list."""

        xpath_patterns = [
            f'//*[@id="main-content"]/section[2]/ul/li[{idx}]/div',
            f'//*[@id="main-content"]/section[2]/ul/li[{idx}]/a',
            f'//*[@id="main-content"]/section[2]/ul/li[{idx}]/div/a',
        ]

        for attempt_action, xpath in enumerate(xpath_patterns):
            try:
                self.element_finder.find_by_xpath(xpath)

                html_content = self.driver.page_source
                file_path = "screenshots/success_xpath.html"
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(html_content)

                return xpath
            except Exception:
                logger.info(f"xpath failed - {attempt_action}")
                verify_full_list(self, idx)
                time.sleep(1)
                if (attempt_action + 1) == len(xpath_patterns):
                    log_small_separator(logger, "listed job element could not be found")
                    self.driver.save_screenshot("screenshots/failed_xpath.png")

                    html_content = self.driver.page_source
                    file_path = "screenshots/failed_xpath.html"
                    with open(file_path, "w", encoding="utf-8") as file:
                        file.write(html_content)

                    sys.exit()
                continue
                # continue

    def ensure_correct_job_is_loaded(self, xpath: str, id_to_find: str, attempt: int):
        """Ensures that the loaded, extended job element the intended listed job
        element by matching their IDs. The method recursively continues to search
        for the correct extended job element until it has been found or 3 attempts
        have been made."""

        time.sleep(2)
        logger.info("line 274")
        self.driver.save_screenshot("screenshots/line_274.png")

        # recursive ensurance of loading the correct, extended job element
        xpath_to_extended_job_post_id = """//*[@id="decoratedJobPostingId"]"""
        html_with_id = self.element_finder.find_by_xpath(
            xpath_to_extended_job_post_id
        ).get_attribute("outerHTML")
        id_found = self.find_job_id(html_with_id, element_type="extended")

        logger.info(f"id_found: {id_found} - id_to_find: {id_to_find}")

        # return if
        if id_found == id_to_find:
            return True

        # go back to search page to retry
        logger.info("Searching for new ID")
        self.driver.back()
        time.sleep(2)
        self.driver.save_screenshot("screenshots/line_307.png")

        is_wall, idx = 1, 1
        while is_wall:
            try:
                ElementFinder(self.driver).find_by_class(
                    """//*[@id="main-content"]/section/ul"""
                )
                is_wall = 0
            except Exception:
                if idx % 2 != 0:
                    logger.info("Line_352")
                    self.driver.back()
                else:
                    logger.info("Line_355")
                    self.driver.forward()
                time.sleep(1)

        self.driver.save_screenshot("screenshots/line_320.png")
        search_page = self.driver.current_url
        _ensure_authorization_wall_not_encountered(self.driver, search_page)

        # open another (the first) element on the list
        # xpath_to_first_listed_job_ele = self.find_correct_xpath_to_listed_jobelement(1)
        # self.element_finder.find_by_xpath(xpath_to_first_listed_job_ele).click()
        # _ensure_authorization_wall_not_encountered(self.driver, search_page)

        # logger.info("line 298")
        # self.driver.save_screenshot("line_298.png")
        # time.sleep(2)

        # Try to open intended job element again
        self.element_finder.find_by_xpath(xpath).click()
        _ensure_authorization_wall_not_encountered(self.driver, search_page)

        logger.info("line 306")
        self.driver.save_screenshot("screenshots/line_306.png")
        time.sleep(2)
        logger.info("line 307")

        attempt += 1
        if attempt > 3:
            raise ScrapingException("ID could not be ensured - skipping job")

        self.ensure_correct_job_is_loaded(xpath, id_to_find, attempt)
        return

    def find_job_id(self, html: str, element_type: str) -> int:
        """Find the job post ID via the data-entity-urn. The ID using is found
        from either of two ways depending on if the job post element is listed
        or extended."""

        if element_type == "listed":
            pattern = r'data-entity-urn="(.*?)"'
            extract_numbers = r"\d+\.\d+|\d+"
            id = int(re.search(extract_numbers, re.search(pattern, html).group(1))[0])
        elif "extended":
            id = int(re.findall(r"\d+\.\d+|\d+", html)[0])

        return id

    def scrape_metadata(self, xpath: str, job_info_dic: Dict) -> Dict:
        """Scrape metadata from the listed job element"""

        logger.info("Get metadata")
        logger.info(xpath)
        self.driver.save_screenshot("screenshots/metadata.png")

        try:
            # scrape metadata from listed jobpost element
            full_ele_outerHTML = self.element_finder.find_by_xpath(xpath).get_attribute(
                "outerHTML"
            )
            job_info_dic["id"] = self.find_job_id(
                full_ele_outerHTML, element_type="listed"
            )
            job_info_dic["is_active"] = 1
            job_info_dic["date"] = re.search(
                r'datetime="([^"]+)"', full_ele_outerHTML
            ).group(1)
            job_info_dic["href"] = re.search(r'href="(.*?)"', full_ele_outerHTML).group(
                1
            )

            logger.info("Metadata found")
        except Exception as e:
            logger.error(f"An exception occurred: {e}")

        return job_info_dic

    def scrape_job_attributes(self, job_info_dic: Dict) -> Dict:
        """Scrape job attributes from the extended job element"""

        logger.info("Get job attributes")

        # scrape full extended jobpost
        # xpath_full_jobpost_ele = """/html/body/div[1]/div/section/div[2]"""       # for non-headless browsing
        xpath_full_jobpost_ele = (
            """/html/body/main/section[1]/div"""  # for headless browsing
        )

        try:
            ele_outerHTML = self.element_finder.find_by_xpath(
                xpath_full_jobpost_ele
            ).get_attribute("outerHTML")
        except WebDriverException:
            raise ScrapingException("Job post not found", is_next_jobpost_not_found=1)

        # retreive individual job attributes from static html element using bs4
        soup = BeautifulSoup(ele_outerHTML, "html.parser")

        logger.info(soup.text[:20])

        job_attributes = [
            "jobpost_title",
            "company",
            "location",
            "num_applicants",
            "description",
        ]

        logger.info("Here2")

        for att in job_attributes:
            ele = soup.find(
                HEADLESS_JOBATTRUBUTE_HTML_TAG_CLASS_LIST[att][0],
                HEADLESS_JOBATTRUBUTE_HTML_TAG_CLASS_LIST[att][1],
            )

            if ele is None and att == "num_applicants":
                ele = soup.find(
                    HEADLESS_JOBATTRUBUTE_HTML_TAG_CLASS_LIST["num_applicants_alt"][0],
                    HEADLESS_JOBATTRUBUTE_HTML_TAG_CLASS_LIST["num_applicants_alt"][1],
                )

            logger.info("Here3")

            # choose suitable bs4 output
            if att != "description":
                content = ele.text
            else:
                content_list = ele.contents

            # extract num applicants with regex
            if att == "num_applicants":
                content = re.findall(r"\d+\.\d+|\d+", content)[0].replace(".", "")

            # convert description from html to text and clean
            elif att == "description":
                content = " ".join(
                    [BeautifulSoup(str(x), "html.parser").text for x in content_list]
                )

            # clean and format content
            if att != "num_applicants":
                val = content.strip().replace("\n", "").replace("*", "")
            else:
                val = int(content)

            logger.info("Here4")

            job_info_dic[att] = val

        # get job criteria attributes from span elements - number of elements vary
        job_criteria_key_ele = soup.find_all(
            JOBATTRUBUTE_HTML_TAG_CLASS_LIST["criteria_key"][0],
            JOBATTRUBUTE_HTML_TAG_CLASS_LIST["criteria_key"][1],
        )

        job_criteria_val_el = soup.find_all(
            JOBATTRUBUTE_HTML_TAG_CLASS_LIST["criteria_value"][0],
            JOBATTRUBUTE_HTML_TAG_CLASS_LIST["criteria_value"][1],
        )

        for jdx, ele in enumerate(job_criteria_val_el):
            clean_key = job_criteria_key_ele[jdx].text.strip().replace("\n", "")
            clean_val = ele.text.strip().replace("\n", "")
            job_info_dic[clean_key] = clean_val
            logger.info("Here2")

        expected_keys = [
            "Seniority level",
            "Job function",
            "Employment type",
            "Industries",
        ]
        for key in expected_keys:
            if key not in job_info_dic.keys():
                job_info_dic[key] = None

        job_info_dic["score"] = None
        job_info_dic["deadline"] = None
        job_info_dic["score_details"] = None

        # reorder dict to align with worksheet cols
        order = DATACOLOUMNS

        logger.info("Here3")
        return {key: job_info_dic[key] for key in order}

    def scrape_job_data(self, job_list_idx: int, id_to_find: int, url: str) -> Dict:
        """Create dictionary containing job information of the listed job element
        having the designated list idx."""

        log_small_separator(logger, "Scraping new jobpost")
        time.sleep(4)
        self.driver.save_screenshot("screenshots/line_477.png")
        job_info_dic = {}

        # find correct xpath to listed job element
        is_no_exception = 1
        try:
            xpath_to_listed_job = self.find_correct_xpath_to_listed_jobelement(
                job_list_idx
            )
        except Exception as e:
            logger.error(f"An exception occurred: {e}")
            is_no_exception = 0

        if is_no_exception:
            # scrape metadata from listed job element
            job_info_dic = self.scrape_metadata(xpath_to_listed_job, job_info_dic)

            logger.info("line 494")
            is_extended_jobpost_not_found = 1
            search_page = self.driver.current_url
            while is_extended_jobpost_not_found:
                # access the expanded job element and ensure the correct is loaded
                try:
                    logger.info("line_500")
                    self.driver.save_screenshot("screenshots/line_500.png")
                    self.element_finder.find_by_xpath(xpath_to_listed_job).click()
                    logger.info("line_503")
                    self.driver.save_screenshot("screenshots/line_503.png")
                    if not _ensure_authorization_wall_not_encountered(
                        self.driver, search_page
                    ):
                        # verify that jobpost page is reached
                        try:
                            xpath = """//*[@id="main-content"]/section[1]/div/section[2]/div/div[1]/div/h1"""
                            self.element_finder.find_by_xpath(xpath)
                            is_extended_jobpost_not_found = 0
                        except Exception:
                            logger.info("Jobpage not found")
                            time.sleep(2)
                            pass
                # except Exception as e:
                except Exception:
                    verify_full_list(self, job_list_idx)
                    self.driver.save_screenshot("screenshots/line_511.png")
                    logger.error("Exception occured 488 - exiting")
                    sys.exit()
                    # logger.error(f"An exception occurred while finding xpath: {e}")

            logger.info("Jobpost page found")
            self.driver.save_screenshot("screenshots/line_page527.png")

            try:
                self.ensure_correct_job_is_loaded(
                    xpath_to_listed_job, id_to_find, attempt=0
                )
            # except Exception as e:
            #    logger.error(f"An exception occurred while finding xpath: {e}")
            except Exception:
                logger.error("Exception occured 498 - exiting")
                sys.exit()

            # scrape job attributes from expanded job element
            try:
                job_info_dic = self.scrape_job_attributes(job_info_dic)
            # except Exception as e:
            # logger.error(f"An exception occurred: {e}")
            except Exception:
                logger.error("Exception occured 507 - exiting")
                sys.exit()

        return job_info_dic


class ScrapeHandler:
    def __init__(self, browser_manager, page_loader):
        self.driver = browser_manager.driver
        self.browser_manager = browser_manager
        self.page_loader = page_loader
        self.element_finder = ElementFinder(browser_manager.driver)
        self.job_ele_handler = JobElementHandler(browser_manager.driver)
        self.num_to_scrape = 10

    def extract_relevant_search_results(
        self, search_idx: int
    ) -> Tuple[List[int], List[int]]:
        """Extract the relevant listed job elements based on title filtering.

        Returns a list of the search list idx of the relevant job posting and
        a list of their IDs.
        """

        def _retreive_relevant_result_idx(
            job_element_list: List[WebElement], current_domain_idx: int
        ) -> Tuple[List[int], List[str]]:
            log_big_separator(logger, "Retreiving relevant results")

            relevant_result_list, relevant_id_list = [], []
            for res_idx, job_ele_driver in enumerate(job_element_list):
                job_ele_handler = JobElementHandler(job_ele_driver)
                title = job_ele_handler.element_finder.find_by_class(
                    "base-search-card__title"
                ).text
                if title_filtering(title, current_domain_idx):
                    relevant_result_list.append(res_idx + 1)
                    relevant_id_list.append(
                        job_ele_handler.find_job_id(
                            job_ele_driver.get_attribute("outerHTML"),
                            element_type="listed",
                        )
                    )

            logger.info(
                "Number of relevant results: "
                + str(len(relevant_result_list))
                + " / "
                + str(len(job_element_list))
                + "\n"
            )
            return relevant_result_list, relevant_id_list

        # collect list index of relevant, listed jobpost elements based on titles
        listed_jobpost_list = self.element_finder.find_list_by_class(
            """job-search-card"""
        )
        relevant_result_idx, relevant_id_list = _retreive_relevant_result_idx(
            listed_jobpost_list, search_idx
        )

        return relevant_result_idx, relevant_id_list

    def stage_jobpost_for_storage(
        self,
        job_info_dic: Dict,
        relevant_result_idx: int,
        df_new_jobposts: pd.DataFrame,
        l_idx: int,
    ):
        log_small_separator(logger, "Staging jobpost for storage")

        # only store job positions that fulfill designated criteria
        if attribute_filtering(job_info_dic):
            df_new_jobposts.loc[len(df_new_jobposts)] = job_info_dic

            logger.info(f"\nJob collected: {job_info_dic['id']}")

        logger.info(str(l_idx + 1) + " / " + str(len(relevant_result_idx)) + "\n")
        return df_new_jobposts

    def scrape_search_results(self, url: str, search_idx: int):
        """Find, scrape and store relevant job posts."""

        relevant_result_idx, relevant_id_list = self.extract_relevant_search_results(
            search_idx
        )

        logger.info("Start job scraping")

        # setup df for staging jobposts
        df_new_jobposts = pd.DataFrame(columns=DATACOLOUMNS)

        # loop through the relevant jobpost elements
        for l_idx, res_idx in enumerate(relevant_result_idx[: self.num_to_scrape]):
            try:
                job_info_dic = self.job_ele_handler.scrape_job_data(
                    res_idx, relevant_id_list[l_idx], url
                )

                if job_info_dic:
                    df_new_jobposts = self.stage_jobpost_for_storage(
                        job_info_dic, relevant_result_idx, df_new_jobposts, l_idx
                    )

                try:
                    ElementFinder(self.driver).find_by_class(
                        """//*[@id="main-content"]/section/ul"""
                    )
                    is_jobpage_reached = 0
                except Exception:
                    is_jobpage_reached = 1

                if is_jobpage_reached:
                    logger.info("jobpage reached - going back to list")
                    self.driver.back()
                    _ensure_authorization_wall_not_encountered(self.driver, url)
                    self.driver.save_screenshot("screenshots/after_back_command.png")

            except ScrapingException:
                logger.error("Other ScrapingException occurred:")

                # test if browser session is still active
                try:
                    self.job_ele_handler.find_correct_xpath_to_listed_jobelement(
                        res_idx
                    )
                except Exception:
                    raise BrowserCrashException

            except BrowserCrashException:
                logger.error("Session crashed - restarting browser profile")
                browser_manager = BrowserManager.start_browser_session()
                page_loader = PageLoader(browser_manager.driver)
                page_loader.search_and_prepare_page_for_scraping(url)

        job_storage_manager = JobStorageManager(spreadsheet_name="Job_radar_aktiv")
        job_storage_manager.store_new_jobposts(df_new_jobposts, search_idx + 1)


def scrape_and_store_new_jobposts():
    log_big_separator(logger, "SEARCH 'N' SCRAPE LOOP STARTED")
    start_time = time.time()

    # Initialize the browser manager
    browser_manager = BrowserManager()

    kws1 = SEARCH_KEYWORDS[0]
    kws2 = SEARCH_KEYWORDS[1]

    for kw_idx in np.arange(len(kws1)):
        # for kw_idx in np.arange(0, 1):
        for loc_idx in np.arange(len(kws2)):
            if kw_idx == 0:
                try:
                    browser_manager.start_browser_session()
                except Exception as e:
                    logger.error(f"An exception occurred 2: {e}")
            else:
                # restart browser session after each search for better stability
                browser_manager.restart_browser_session()

            logger.info("Session successfully started")
            # initialize pageloader, avigate to the job search page and prepare page for scraping
            page_loader = PageLoader(browser_manager.driver)
            logger.info("Pageloader started")
            job_search_url = 'https://www.linkedin.com/jobs/search?keywords={}&{}&"pageNum=0"'.format(
                kws1[kw_idx], kws2[loc_idx]
            )
            page_loader.search_and_prepare_page_for_scraping(job_search_url)

            # initialize scrape handler and scrape search results
            scrape_handler = ScrapeHandler(browser_manager, page_loader)
            scrape_handler.scrape_search_results(job_search_url, kw_idx)

    browser_manager.stop_browser_session()
    completion_time = start_time - time.time()
    log_small_separator(
        logger, f"All searches are completed - completion time {completion_time}"
    )
