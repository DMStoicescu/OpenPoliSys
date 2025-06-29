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


# Setup logger for this module
logger = logging.getLogger(__name__)
# Setup for language detector

class WebScraper:
    direct_privacy_subdomains = direct_paths = ['/privacy', '/privacy-policy']
    privacy_name_list = [
        'Privacy Policy', 'privacy', 'privacy-policy',
        'Privacy Statement', 'Privacy-statement',
        'Privacy Notice', 'Privacy-notice'
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

    def direct_is_valid_privacy_page(self) -> bool:
        title = self.driver.title.lower()
        body = self.driver.page_source.lower()

        # must mention "privacy"
        if "privacy" not in title and "privacy" not in body:
            logger.debug(f"({self.driver.current_url}) no 'privacy' keyword")
            return False

        # reject if it's clearly an error or 404
        m = re.search(r'page you are looking for cannot be found|Page not found|Content not found|ERROR 404|404 ERROR', body, re.IGNORECASE)
        if m:
            snippet = m.group(0)
            logger.warning(f"({self.driver.current_url}) looks like a 404/error page — matched: '{snippet}'")
            return False

        return True

    def _page_is_english(self) -> bool:
        current = self.driver.current_url

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
                return True
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
                return True
            logger.info(f"({current}) langdetect detected language '{lang}', skipping")
            return False
        except Exception as e:
            logger.warning(f"({current}) could not detect language: {e}")
            # default to proceeding if detection fails
            return True

    def find_privacy_url(self):
        # Navigate to the domain URL
        logger.info(f'Navigating to homepage: {self.url}')
        try:
            self.driver.get(self.url)
        except TimeoutException as e:
            logger.warning(f"Timeout loading homepage {self.url}: {e}")
            return
        except Exception as e:
            logger.warning(f"Error loading homepage {self.url}: {e}")
            return
        time.sleep(2)

        # Perform language check
        if not self._page_is_english():
            logger.info(f"Skipping {self.url} because page is not English")
            return

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

            time.sleep(1)
            if self.direct_is_valid_privacy_page():
                # Set current url to take into account any redirects
                self.privacy_url = self.driver.current_url
                logger.info(f'Privacy policy URL found using direct path at {self.privacy_url}.')
                return

        # Try navigation based on elements containing keywords
        # Navigate back to the domain url and restart the process
        try:
            self.driver.get(self.url)
        except TimeoutException as e:
            logger.warning(f"Timeout reloading homepage {self.url}: {e}")
            return
        except Exception as e:
            logger.info(f"Error reloading homepage {self.url}: {e}")
            return
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

            if "privacy" in self.driver.title.lower() or "privacy" in self.driver.page_source.lower():
                # Account for redirects
                self.privacy_url = self.driver.current_url
                logger.info(f"Found privacy URL via keyword scan at: {self.privacy_url}")
                return

    def scroll_to_bottom(self):
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.SCROLL_PAUSE_TIME)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def extract_policies(self):
        # Navigate to privacy URL
        if self.privacy_url:
            self.driver.get(self.privacy_url)

            # Allow padding time to let the site load
            time.sleep(3)

            # Ensure all lazy-loaded content is visible
            self.scroll_to_bottom()

            # Use page_source for full HTML access
            html = self.driver.page_source
            self.driver.quit()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            text_extracted = soup.get_text(separator='\n')
            logger.info('Extracted policy text using full DOM parsing.')

            return text_extracted
        else:
            self.driver.quit()
            logger.warning('Privacy URL not found.')
            return 'No privacy url found'
