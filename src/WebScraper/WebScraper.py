import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin

# Setup logger for this module
logger = logging.getLogger(__name__)

class WebScraper:
    privacy_name_list = ['Privacy Policy', 'privacy', 'privacy-policy', 'Privacy Statement']

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
        self.driver.get(self.url)

        # Take all the elements that include hyperlinks and search the privacy related ones
        links = self.driver.find_elements(By.TAG_NAME, 'a')

        for link in links:
            link_text = link.text.lower()
            href = link.get_attribute('href')

            # Check if any keyword is in the link text
            keyword_in_text = any(keyword.lower() in link_text for keyword in self.privacy_name_list)

            # Check if any keyword is in the href (if href exists)
            keyword_in_href = any(keyword.lower() in href.lower() for keyword in self.privacy_name_list) if href else False

            rank_1_candidate_privacy_url = []
            rank_2_candidate_privacy_url = []
            rank_3_candidate_privacy_url = []
            # If any exists, then assign the privacy_subdomain based on ranking system
            if keyword_in_text and keyword_in_href:
                rank_1_candidate_privacy_url.append(urljoin(self.url, href))
            elif keyword_in_text and not keyword_in_href:
                rank_2_candidate_privacy_url.append(urljoin(self.url, href))
            elif keyword_in_href and not keyword_in_text:
                rank_3_candidate_privacy_url.append(urljoin(self.url, href))

        # Join based on ranking
        candidate_privacy_url_sorted = [rank_1_candidate_privacy_url , rank_2_candidate_privacy_url , rank_3_candidate_privacy_url]



    def extract_policies(self):
        # Navigate to privacy URL
        if self.privacy_url:
            self.driver.get(self.privacy_url)

            # Allow padding time to let the site load
            time.sleep(5)
            text_extracted = self.driver.find_element(By.TAG_NAME, 'body').text
            self.driver.quit()

            return text_extracted
        else:
            self.driver.quit()
            return 'No privacy url found'
