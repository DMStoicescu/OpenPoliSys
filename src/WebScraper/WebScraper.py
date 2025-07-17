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
import tldextract

# Setup logger for this module
logger = logging.getLogger(__name__)
# Setup for language detector
DetectorFactory.seed = 0

class WebScraper:
    """
        A scraper to locate and extract privacy policy content for a given domain.

        Class Attributes:
            direct_paths (list[str]): Known URL suffixes for privacy pages.
            privacy_name_list (list[str]): Keywords to identify privacy-policy links.
            SCROLL_PAUSE_TIME (float): Delay between scroll actions to load lazy content.
        Instance Attributes:
            url (str): Base URL for the target domain (with a scheme).
            policy_text (str|None): Aggregated extracted policy text.
            driver (webdriver.Chrome): Selenium Chrome WebDriver instance.
    """
    # Common direct endpoints to test before scanning page links
    direct_privacy_subdomains = direct_paths = ['/privacy', '/privacy-policy']

    # Text patterns to match link labels or URLs
    privacy_name_list = [
        'Privacy Policy', 'Privacy Statement',
        'Privacy-statement','Privacy Notice',
        'Privacy-notice', 'privacy',
        'privacy-policy', 'Privacy Centre and Ad Choices',
        'Privacy Centre & Ad Choices', 'Privacy Centre',
        'Privacy-Centre', 'Terms & Privacy Policy',
        'Terms and Privacy Policy'
    ]

    # Value used for lazy loaded content
    SCROLL_PAUSE_TIME = 1.5

    def __init__(self, domain_url):
        """
            Initialize the scraper with headless Chrome for the given domain.

            Args:
                domain_url (str): Domain to scrape (e.g., 'example.com' or 'https://example.com').
        """
        # Normalize URL to include scheme, assume https:// default
        self.needs_review = False
        self.url = domain_url if domain_url.startswith(('http://', 'https://')) else f'https://{domain_url}'

        # To avoid redirects to initial home page
        self.url_2 = domain_url if domain_url.startswith(('http://', 'https://')) else f'https://www.{domain_url}'

        # Assign initial privacy policy subdomain
        self.privacy_url = None

        # Assign intial empty lists for all privacy-related subdomains
        self.privacy_subdomains = []

        # Assign initial empty policy value
        self.policy_text = None

        # Assign initial true value for language attribute
        self.is_en_flag = True

        # Assign timeout domain flag default to false
        self.is_timeout_flag = False

        # Assign outdated domain flag default to false
        self.is_outdated_flag = False

        # Set up the driver for this URL
        self.chrome_options = Options()
        # Run in headless mode for performance purposes
        self.chrome_options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=self.chrome_options)

        # Fail fast on slow pages
        self.driver.set_page_load_timeout(30)
        self.driver.set_script_timeout(30)

        logger.info(f'Initialized scraper for URL: {self.url}')

    def page_is_valid_privacy_page(self):
        """
            Validate that the current page is a privacy policy and not an error.
            Note: only used for direct path policy finder - not for link-based policy finder.

            Returns:
                bool: True if page contains 'privacy' and is not a 404 or error page.
        """
        title = self.driver.title.lower()
        body = self.driver.page_source.lower()

        # Must mention "privacy"
        if "privacy" not in title and "privacy" not in body:
            logger.detail(f"({self.driver.current_url}) no 'privacy' keyword")
            return False

        # Reject 404 or generic error pages
        page_not_found_matches = re.search(r'page you are looking for cannot be found|Page not found|Content not found|ERROR 404|404 ERROR|404 Not Found|Sorry but the page|404 page|Sorry, the page you were looking for was not found|404 Page|That’s an error', body, re.IGNORECASE)
        if page_not_found_matches:
            snippet = page_not_found_matches.group(0)
            logger.warning(f"({self.driver.current_url}) looks like a 404/error page — matched: '{snippet}'")
            return False

        return True

    def page_is_english(self):
        """
            Determine if the current page is in English.

            Tries HTML lang attribute first, falls back to `langdetect` on page text.

            Returns:
                bool: True if page language is English or detection fails; False otherwise.
        """
        current = self.driver.current_url
        self.is_en_flag = True

        # HTML lang attribute check
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
                self.is_en_flag = False
                logger.debug(f"({current}) lang attribute '{lang_attr}' indicates non-English")
        except Exception as e:
            logger.warning(f"({current}) no html lang attribute or error reading it: {e}")

        # Fallback: langdetect on page text
        try:
            html = self.driver.page_source
            text = (
                BeautifulSoup(html, 'html.parser')
                .get_text(separator=' ', strip=True)
                [:5000]
            )
            lang = detect(text)
            if lang == 'en':
                logger.debug(f"({current}) langdetect detected language 'en'")
                self.is_en_flag = True
            else:
                self.is_en_flag = False
                logger.detail(f"({current}) langdetect detected language '{lang}', skipping")
        except Exception as e:
            logger.warning(f"({current}) could not detect language: {e}")
            # default to proceeding if detection fails
            return self.is_en_flag

        return self.is_en_flag

    def find_privacy_url(self):
        """
            Attempts to locate privacy policy URLs.

            Order of operations:
            1. Load homepage and verify English content
            2. Try direct paths (e.g., /privacy, /privacy-policy)
            3. Scan top navigation links by keyword ranking

            Returns:
                list[str]: Discovered privacy policy URLs (can be empty).
        """
        logger.detail(f'Navigating to homepage: {self.url}')

        # Load homepage, and if not possible return []
        try:
            self.driver.get(self.url)
        except TimeoutException as e:
            logger.error(f"Timeout loading homepage {self.url}: {e}")
            self.is_timeout_flag = True
            return self.privacy_subdomains
        except Exception as e:
            logger.error(f"Error loading homepage {self.url}: {e}")
            self.is_outdated_flag = True
            return self.privacy_subdomains
        time.sleep(4)

        # Perform language check
        if not self.page_is_english():
            logger.detail(f"Skipping {self.url} because page is not English")
            return self.privacy_subdomains

        # Try navigation to direct subdomain paths first (direct path check)
        for path in self.direct_paths:
            full_url = urljoin(self.url, path)
            try:
                self.driver.get(full_url)
            except TimeoutException as e:
                logger.warning(f"Timeout loading direct path {full_url}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error loading direct path {full_url}: {e}")
                continue

            time.sleep(2)
            if self.page_is_valid_privacy_page():
                # Set current url to take into account any redirects
                self.privacy_url = self.driver.current_url
                if self.privacy_url not in self.privacy_subdomains and self.privacy_url != (self.url + "/") and self.privacy_url != (self.url_2 + "/"):
                    self.privacy_subdomains.append(self.privacy_url)
                    logger.detail(f'Privacy policy URL found using direct path at {self.privacy_url}.')

        # Try navigation based on elements containing keywords
        # Navigate back to the domain url and restart the process
        try:
            self.driver.get(self.url)
            #Add scrolling to make sure that all elements are captured
            self.scroll_to_bottom()
        except TimeoutException as e:
            logger.error(f"Timeout reloading homepage {self.url}: {e}")
            return self.privacy_subdomains
        except Exception as e:
            logger.error(f"Error loading homepage {self.url}: {e}")
            return self.privacy_subdomains
        time.sleep(2)

        links = self.driver.find_elements(By.TAG_NAME, 'a')
        logger.detail(f'Found {len(links)} hyperlinks on the page.')

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
                # logger.debug(f'Rank 1 candidate: {urljoin(self.url, href)}')
            elif keyword_in_text:
                rank_2_candidate_privacy_url.append(urljoin(self.url, href))
                # logger.debug(f'Rank 2 candidate: {urljoin(self.url, href)}')
            elif keyword_in_href:
                rank_3_candidate_privacy_url.append(urljoin(self.url, href))
                # logger.debug(f'Rank 3 candidate: {urljoin(self.url, href)}')

        # Join based on ranking
        candidate_privacy_url_sorted = (
            rank_1_candidate_privacy_url +
            rank_2_candidate_privacy_url +
            rank_3_candidate_privacy_url
        )

        logger.detail(f'Found {len(candidate_privacy_url_sorted)} hyperlinks that might be related to privacy on the page.')

        # Navigate up to 5 of the best candidates
        for candidate_url in candidate_privacy_url_sorted[:5]:
            try:
                self.driver.get(candidate_url)
            except TimeoutException as e:
                logger.error(f"Timeout loading candidate link {candidate_url}: {e}")
                continue
            except Exception as e:
                logger.error(f"Exception loading candidate link {candidate_url}: {e}")
                continue

            time.sleep(2)
            # Recheck for mention of privacy
            if "privacy" in self.driver.title.lower() or "privacy" in self.driver.page_source.lower():
                self.privacy_url = self.driver.current_url
                if self.privacy_url not in self.privacy_subdomains:
                    # Append if not already present
                    self.privacy_subdomains.append(self.privacy_url)
                    logger.detail(f"Found privacy-related URL via keyword scan at: {self.privacy_url}")

        return self.privacy_subdomains

    def scroll_to_bottom(self):
        """
            Scrolls page to bottom to trigger lazy-loaded elements.
        """
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        count = 0
        while True:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.SCROLL_PAUSE_TIME)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            count += 1
            # Break for infinity scroll pages
            if count > 10:
                break

    @staticmethod
    def similarity(text1, text2):
        """
            Compute a similarity ratio between two strings.

            Args:
                text1 (str),
                text2 (str)
            Returns:
                float: Ratio in [0.0, 1.0]
        """
        return SequenceMatcher(None, text1, text2).ratio()

    @staticmethod
    def remove_boilerplate_elements(soup):
        """
            Remove common non-content elements (headers, navs, banners).

            Args:
                soup (BeautifulSoup): Parsed HTML soup
            Returns:
                BeautifulSoup: Cleaned soup
        """
        # Remove structural tags
        tags_list = ['nav', 'aside', 'header']
        for tag in soup.find_all(tags_list):
            tag.decompose()

        # Remove by CSS selectors
        css_selector_list = ['.navbar' ,'#navbar', '.nav', '#nav', '.site-nav', '#site-nav',
                             '.sidebar', '#sidebar', '.cookie-banner', '#cookie-banner']

        for sel in css_selector_list:
            for elem in soup.select(sel):
                elem.decompose()

        return soup

    def extract_policies(self, privacy_urls_list):
        """
            Extract and concatenate text from discovered privacy URL pages.

            Args:
                privacy_urls_list (list[str]): List of valid privacy policy URLs.
            Returns:
                str: Combined privacy policy text, or a warning string if none found.
        """
        # Navigate to privacy URL
        text_extracted = ''
        if len(privacy_urls_list) != 0:
            for privacy_url in privacy_urls_list:

                # Check if the policy main domain is different from orignal one
                if tldextract.extract(self.url).domain not in privacy_url:
                    self.needs_review = True

                self.driver.get(privacy_url)

                # Allow padding time to let the site load
                time.sleep(3)

                # Ensure all lazy-loaded content is visible
                self.scroll_to_bottom()

                # Use page_source for full HTML access
                html = self.driver.page_source

                # Parse with BeautifulSoup
                soup = BeautifulSoup(html, 'html.parser')

                # Remove text related to boilerplate
                soup = self.remove_boilerplate_elements(soup)

                # Transform to text and do not append unless text is "new"
                text_candidate = soup.get_text(separator='\n', strip=True)
                if text_extracted != '':
                    if text_candidate != '' and self.similarity(text_extracted, text_candidate) <= 0.7:
                        logger.detail(f'Extraction from {privacy_url}, completed successfully.')
                        text_extracted += text_candidate

                else:
                    logger.detail(f'Extraction from {privacy_url}, completed successfully.')
                    text_extracted = text_candidate

            logger.detail('Extraction from found privacy links completed.')
            self.driver.quit()
            return text_extracted

        else:
            self.driver.quit()
            logger.warning('Privacy URL not found.')
            return 'No privacy url found'

