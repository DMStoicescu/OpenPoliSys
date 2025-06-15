import csv
import os
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

def save_to_csv(domain, privacy_url, policy_text, filename='policy_scrape_output.csv'):
    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)

        # Write header only once
        if not file_exists:
            writer.writerow(['Input Domain', 'Privacy Policy URL', 'Policy Text'])

        writer.writerow([domain, privacy_url or 'Not Found', policy_text.strip()])

if __name__ == '__main__':

    # Logger setup
    configure_logger()
    logger = logging.getLogger(__name__)

    url = input('Enter URL: ')
    scraper = WebScraper(url)
    scraper.find_privacy_url()
    policies = scraper.extract_policies()

    save_to_csv(url, scraper.privacy_url, policies)
    print(policies)


