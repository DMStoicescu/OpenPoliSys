import time
import logging
from selenium import webdriver
from selenium.common import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin
from bs4 import BeautifulSoup

# Setup logger for this module
logger = logging.getLogger(__name__)

class WebScraper:
    direct_privacy_subdomains = direct_paths = ['/privacy', '/privacy-policy']
    privacy_name_list = ['Privacy Policy', 'privacy', 'privacy-policy', 'Privacy Statement']
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

        logger.info(f'Initialized scraper for URL: {self.url}')

    def find_privacy_url(self):
        # Navigate to the domain URL
        logger.info(f'Navigating to homepage: {self.url}')
        self.driver.get(self.url)
        time.sleep(2)

        # Try navigation to direct subdomain paths first
        for path in self.direct_paths:
            try:
                full_url = urljoin(self.url, path)
                self.driver.get(full_url)
                if "privacy" in self.driver.title.lower() or "privacy" in self.driver.page_source.lower():
                    self.privacy_url = full_url
                    logger.info(f'Privacy policy URL found using direct path at {self.privacy_url}.')
                    return

            except WebDriverException:
                logger.info(f'Privacy policy URL NOT found using direct path {path}.')
                continue

        # Try navigation based on elements containing keywords
        # Navigate back to the domain url and restart the process
        self.driver.get(self.url)
        time.sleep(2)
        # Take all the elements that include hyperlinks and search the privacy related ones
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

            # If any exists, then assign the privacy_subdomain based on ranking system
            if keyword_in_text and keyword_in_href:
                candidate_url = urljoin(self.url, href)
                rank_1_candidate_privacy_url.append(candidate_url)
                logger.debug(f'Rank 1 candidate: {candidate_url}')

            elif keyword_in_text and not keyword_in_href:
                candidate_url = urljoin(self.url, href)
                rank_2_candidate_privacy_url.append(candidate_url)
                logger.debug(f'Rank 1 candidate: {candidate_url}')

            elif keyword_in_href and not keyword_in_text:
                candidate_url = urljoin(self.url, href)
                rank_3_candidate_privacy_url.append(candidate_url)
                logger.debug(f'Rank 1 candidate: {candidate_url}')


        # Join based on ranking
        candidate_privacy_url_sorted = []
        candidate_privacy_url_sorted.extend(rank_1_candidate_privacy_url)
        candidate_privacy_url_sorted.extend(rank_2_candidate_privacy_url)
        candidate_privacy_url_sorted.extend(rank_3_candidate_privacy_url)

        for candidate_url in candidate_privacy_url_sorted[:5]:
            try:
                self.driver.get(candidate_url)
                if "privacy" in self.driver.title.lower() or "privacy" in self.driver.page_source.lower():
                    self.privacy_url = candidate_url
                    logger.info(f"Found privacy URL via keyword scan at: {self.privacy_url}")
                    return
            except WebDriverException:
                continue

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
