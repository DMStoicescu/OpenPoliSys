import logging
from src.WebScraper.WebScraper import WebScraper

def configure_logger():
    # Configure logging globally
    logging.basicConfig(
        level=logging.INFO,  # Or DEBUG for more verbose output
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # Output to console
            logging.FileHandler('scraper.log', mode='w')  # Output to file
        ]
    )

if __name__ == '__main__':

    # Logger setup
    configure_logger()
    logger = logging.getLogger(__name__)

    url = input('Enter URL: ')
    scraper = WebScraper(url)
    scraper.find_privacy_url()
    policies = scraper.extract_policies()
    print(policies)


