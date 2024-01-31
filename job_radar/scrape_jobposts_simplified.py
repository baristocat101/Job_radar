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
        # self.job_element_handler = JobElementHandler(driver)

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
                try:
                    ele_txt = (
                        ElementFinder(self.driver)
                        .find_by_xpath("""//*[@id="main-content"]/section[2]/div/p""")
                        .text
                    )
                except Exception as e:
                    logger.error(f"{e}")
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
                xpath = JobElementHandler(
                    self.driver
                ).find_correct_xpath_to_listed_jobelement(jdx)
                html_str = self.element_finder.find_by_xpath(xpath).get_attribute(
                    "outerHTML"
                )
                job_id = JobElementHandler(self.driver).find_job_id(
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
        if (num_res - num_loaded) < 20:
            is_full_list = 1
        else:
            is_full_list = 0
        return is_full_list

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
                return xpath
            except Exception:
                logger.info(f"xpath failed - {attempt_action}")
                time.sleep(1)
                if (attempt_action + 1) == len(xpath_patterns):
                    log_small_separator(logger, "listed job element could not be found")
                    is_fully_loaded = verify_full_list(self, idx)
                    if not is_fully_loaded:
                        PageLoader(self.driver).ensure_page_has_fully_loaded_joblist()
                    xpath = self.find_correct_xpath_to_listed_jobelement(idx)
                    return xpath
                # continue

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

    def scrape_metadata(self, job_ele_driver: str, df) -> Dict:
        """Scrape metadata from the listed job element"""

        logger.info("Get metadata")

        try:
            # scrape metadata from listed jobpost element
            full_ele_outerHTML = job_ele_driver.get_attribute("outerHTML")

            # insert new row
            df.loc[len(df)] = [None] * len(df.columns)

            df.loc[df.index[-1], "id"] = self.find_job_id(
                full_ele_outerHTML, element_type="listed"
            )

            df.loc[df.index[-1], "is_active"] = 1

            df.loc[df.index[-1], "date"] = re.search(
                r'datetime="([^"]+)"', full_ele_outerHTML
            ).group(1)

            df.loc[df.index[-1], "href"] = re.search(
                r'href="(.*?)"', full_ele_outerHTML
            ).group(1)

            logger.info("Metadata found")
        except Exception as e:
            logger.error(f"An exception occurred: {e}")

        return df

    def scrape_job_attributes(self, df, job_idx) -> Dict:
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

            df.loc[job_idx, att] = val

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
            df.loc[job_idx, clean_key] = clean_val
            logger.info("Here2")

        expected_keys = [
            "Seniority level",
            "Job function",
            "Employment type",
            "Industries",
        ]
        for key in expected_keys:
            if key not in df.columns:
                df.loc[job_idx, key] = None

        df.loc[job_idx, "score"] = None
        df.loc[job_idx, "deadline"] = None
        df.loc[job_idx, "score_details"] = None

        logger.info("Here3")
        return df


class ScrapeHandler:
    def __init__(self, browser_manager, page_loader):
        self.driver = browser_manager.driver
        self.browser_manager = browser_manager
        self.page_loader = page_loader
        self.element_finder = ElementFinder(browser_manager.driver)
        self.job_ele_handler = JobElementHandler(browser_manager.driver)

    def extract_relevant_search_results(
        self, search_idx: int, df_new_jobposts
    ) -> Tuple[List[int], List[int]]:
        """Extract the relevant listed job elements based on title filtering.

        Returns a list of the search list idx of the relevant job posting and
        a list of their IDs.
        """

        def _retreive_relevant_result_idx(
            job_element_list: List[WebElement], current_domain_idx: int, df_new_jobposts
        ) -> Tuple[List[int], List[str]]:
            log_big_separator(logger, "Retreiving relevant results")

            num_relevant = 0
            for job_ele_driver in job_element_list:
                job_ele_handler = JobElementHandler(job_ele_driver)
                title = job_ele_handler.element_finder.find_by_class(
                    "base-search-card__title"
                ).text
                if title_filtering(title, current_domain_idx):
                    # scrape metadata from listed job element
                    df_new_jobposts = self.job_ele_handler.scrape_metadata(
                        job_ele_driver, df_new_jobposts
                    )

                    num_relevant += 1

            logger.info(
                "Number of relevant results: "
                + str(num_relevant)
                + " / "
                + str(len(job_element_list))
                + "\n"
            )
            return df_new_jobposts

        # collect list index of relevant, listed jobpost elements based on titles
        listed_jobpost_list = self.element_finder.find_list_by_class(
            """job-search-card"""
        )

        df_new_jobposts = _retreive_relevant_result_idx(
            listed_jobpost_list, search_idx, df_new_jobposts
        )

        return df_new_jobposts

    def stage_jobpost_for_storage(
        self, df_new_jobposts: pd.DataFrame, job_idx: int, num_relevant_results: int
    ):
        log_small_separator(logger, "Staging jobpost for storage")

        # only store job positions that fulfill designated criteria
        if not attribute_filtering(df_new_jobposts, job_idx):
            df_new_jobposts = df_new_jobposts.drop(job_idx)
        else:
            logger.info("\nJob collected")

        logger.info(str(job_idx + 1) + " / " + str(num_relevant_results) + "\n")
        return df_new_jobposts

    def scrape_search_results(self, url: str, search_idx: int):
        """Find, scrape and store relevant job posts."""

        logger.info("Start job scraping")

        # setup df for staging jobposts
        df_new_jobposts = pd.DataFrame(columns=DATACOLOUMNS)

        df_new_jobposts = self.extract_relevant_search_results(
            search_idx, df_new_jobposts
        )

        num_relevant_results = df_new_jobposts.shape[0]

        # loop through the relevant jobpost elements
        for job_idx in np.arange(num_relevant_results):
            log_small_separator(logger, "Scraping new job attributes")

            # go to extended jobpage
            jobpage_not_reached = 1
            while jobpage_not_reached:
                self.driver.get(df_new_jobposts.loc[job_idx, "href"])
                try:
                    ElementFinder(self.driver).find_by_xpath(
                        """//*[@id="main-content"]/section[1]/div/section[2]/div/div[1]"""
                    )
                    jobpage_not_reached = 0
                except:
                    time.sleep(3)
                    self.driver.back()
                    time.sleep(3)
                    continue

            df_new_jobposts = self.job_ele_handler.scrape_job_attributes(
                df_new_jobposts, job_idx
            )

            df_new_jobposts = self.stage_jobpost_for_storage(
                df_new_jobposts, job_idx, num_relevant_results
            )

        job_storage_manager = JobStorageManager(spreadsheet_name="Job_radar_aktiv")
        logger.info("line 733")
        job_storage_manager.store_new_jobposts(df_new_jobposts, search_idx + 1)
        # cooldown before making more request to google api
        time.sleep(90)


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