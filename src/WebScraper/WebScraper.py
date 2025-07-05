import time
import logging
import regex as re
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from langdetect import detect, DetectorFactory
from difflib import SequenceMatcher


# Setup logger for this module
logger = logging.getLogger(__name__)
# Setup for language detector
DetectorFactory.seed = 0

class WebScraper:
    direct_privacy_subdomains = direct_paths = ['/privacy', '/privacy-policy']
    privacy_name_list = [
        'Privacy Policy',
        'Privacy Statement', 'Privacy-statement',
        'Privacy Notice', 'Privacy-notice',
        'privacy', 'privacy-policy'
    ]
    SCROLL_PAUSE_TIME = 1.5

    def __init__(self, domain_url):
        # Assign the URL of the domain
        self.url = domain_url if domain_url.startswith(('http://', 'https://')) else f'https://{domain_url}'

        # Assign initial privacy policy subdomain
        self.privacy_url = None

        # Assign initial empty policy value
        self.policy_text = None

        # Set up the driver for this URL
        self.chrome_options = Options()
        # Run in headless mode for performance purposes
        self.chrome_options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=self.chrome_options)

        # fail fast on slow pages
        self.driver.set_page_load_timeout(30)
        self.driver.set_script_timeout(30)

        logger.info(f'Initialized scraper for URL: {self.url}')

    def _is_valid_privacy_page(self) -> bool:
        title = self.driver.title.lower()
        body = self.driver.page_source.lower()

        # must mention "privacy"
        if "privacy" not in title and "privacy" not in body:
            logger.debug(f"({self.driver.current_url}) no 'privacy' keyword")
            return False

        # reject if it's clearly an error or 404
        m = re.search(r'page you are looking for cannot be found|Page not found|Content not found|ERROR 404|404 ERROR|404 Not Found|Sorry but the page|404 page|Sorry, the page you were looking for was not found|404 Page', body, re.IGNORECASE)

        if m:
            snippet = m.group(0)
            logger.warning(f"({self.driver.current_url}) looks like a 404/error page — matched: '{snippet}'")
            return False

        return True

    def _page_is_english(self) -> bool:
        current = self.driver.current_url
        is_en_flag = True

        # 1) HTML lang attribute
        try:
            lang_attr = (
                    self.driver
                    .find_element(By.TAG_NAME, 'html')
                    .get_attribute('lang')
                    or ''
            ).lower()
            if lang_attr.startswith('en'):
                logger.debug(f"({current}) lang attribute '{lang_attr}' indicates English")
            else:
                is_en_flag = False
                logger.debug(f"({current}) lang attribute '{lang_attr}' indicates non-English")
        except Exception as e:
            logger.debug(f"({current}) no html lang attribute or error reading it: {e}")

        # 2) Fallback: langdetect on page text
        try:
            html = self.driver.page_source
            text = (
                BeautifulSoup(html, 'html.parser')
                .get_text(separator=' ', strip=True)
                [:2000]
            )
            lang = detect(text)
            if lang == 'en':
                logger.debug(f"({current}) langdetect detected language 'en'")
                is_en_flag = True
            else:
                is_en_flag = False
                logger.info(f"({current}) langdetect detected language '{lang}', skipping")
        except Exception as e:
            logger.warning(f"({current}) could not detect language: {e}")
            # default to proceeding if detection fails
            return is_en_flag

        return is_en_flag

    def find_privacy_url(self):
        # Navigate to the domain URL
        privacy_urls = []

        logger.info(f'Navigating to homepage: {self.url}')
        try:
            self.driver.get(self.url)
        except TimeoutException as e:
            logger.warning(f"Timeout loading homepage {self.url}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error loading homepage {self.url}: {e}")
            return []
        time.sleep(4)

        # Perform language check
        if not self._page_is_english():
            logger.info(f"Skipping {self.url} because page is not English")
            return []

        # Try navigation to direct subdomain paths first
        for path in self.direct_paths:
            full_url = urljoin(self.url, path)
            try:
                self.driver.get(full_url)
            except TimeoutException as e:
                logger.warning(f"Timeout loading direct path {full_url}: {e}")
                continue
            except Exception as e:
                logger.info(f"Error loading direct path {full_url}: {e}")
                continue

            time.sleep(2)
            if self._is_valid_privacy_page():
                # Set current url to take into account any redirects
                self.privacy_url = self.driver.current_url
                if self.privacy_url not in privacy_urls:
                    privacy_urls.append(self.privacy_url)
                    logger.info(f'Privacy policy URL found using direct path at {self.privacy_url}.')

        # Try navigation based on elements containing keywords
        # Navigate back to the domain url and restart the process
        try:
            self.driver.get(self.url)
        except TimeoutException as e:
            logger.warning(f"Timeout reloading homepage {self.url}: {e}")
            return privacy_urls
        except Exception as e:
            logger.info(f"Error reloading homepage {self.url}: {e}")
            return privacy_urls
        time.sleep(2)

        links = self.driver.find_elements(By.TAG_NAME, 'a')
        logger.info(f'Found {len(links)} hyperlinks on the page.')

        # Define the 3 classes of the privacy url ranking system
        rank_1_candidate_privacy_url = []
        rank_2_candidate_privacy_url = []
        rank_3_candidate_privacy_url = []

        for link in links:
            link_text = link.text.lower()
            href = link.get_attribute('href')

            # Check if any keyword is in the link text
            keyword_in_text = any(keyword.lower() in link_text for keyword in self.privacy_name_list)

            # Check if any keyword is in the href (if href exists)
            keyword_in_href = any(keyword.lower() in href.lower() for keyword in self.privacy_name_list) if href else False

            # Assign candidates based on ranking
            if keyword_in_text and keyword_in_href:
                rank_1_candidate_privacy_url.append(urljoin(self.url, href))
                logger.debug(f'Rank 1 candidate: {urljoin(self.url, href)}')
            elif keyword_in_text:
                rank_2_candidate_privacy_url.append(urljoin(self.url, href))
                logger.debug(f'Rank 2 candidate: {urljoin(self.url, href)}')
            elif keyword_in_href:
                rank_3_candidate_privacy_url.append(urljoin(self.url, href))
                logger.debug(f'Rank 3 candidate: {urljoin(self.url, href)}')

        # Join based on ranking
        candidate_privacy_url_sorted = (
            rank_1_candidate_privacy_url +
            rank_2_candidate_privacy_url +
            rank_3_candidate_privacy_url
        )

        for candidate_url in candidate_privacy_url_sorted[:5]:
            try:
                self.driver.get(candidate_url)
            except TimeoutException as e:
                logger.warning(f"Timeout loading candidate link {candidate_url}: {e}")
                continue
            except Exception:
                continue

            time.sleep(2)
            if "privacy" in self.driver.title.lower() or "privacy" in self.driver.page_source.lower():
                # Account for redirects
                self.privacy_url = self.driver.current_url
                if self.privacy_url not in privacy_urls:
                    privacy_urls.append(self.privacy_url)
                    logger.info(f"Found privacy URL via keyword scan at: {self.privacy_url}")
                return privacy_urls

        return privacy_urls

    def scroll_to_bottom(self):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.SCROLL_PAUSE_TIME)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    @staticmethod
    def similarity(text1, text2):
        return SequenceMatcher(None, text1, text2).ratio()

    def extract_policies(self, privacy_urls_list):
        # Navigate to privacy URL
        text_extracted = ''
        if len(privacy_urls_list) != 0:
            for privacy_url in privacy_urls_list:
                self.driver.get(privacy_url)

                # Allow padding time to let the site load
                time.sleep(3)

                # Ensure all lazy-loaded content is visible
                self.scroll_to_bottom()

                # Use page_source for full HTML access
                html = self.driver.page_source

                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')
                text_candidate = soup.get_text(separator='\n', strip=True)
                if text_extracted != '':
                    if text_candidate != '' and self.similarity(text_extracted, text_candidate) <= 0.7:
                        text_extracted += text_candidate

                else:
                    text_extracted = text_candidate

            logger.info('Extracted policy text using full DOM parsing.')
            self.driver.quit()
            return text_extracted

        else:
            self.driver.quit()
            logger.warning('Privacy URL not found.')
            return 'No privacy url found'

