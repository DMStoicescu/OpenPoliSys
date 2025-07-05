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
            logging.FileHandler('./out/scraper.log', mode='w')  # Output to file
        ]
    )

def save_to_csv(domain, privacy_url, policy_text, filename='./out/policy_scrape_output.csv'):
    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)

        # Write header only once
        if not file_exists:
            writer.writerow(['Input Domain', 'Privacy Policy URL', 'Policy Text'])

        writer.writerow([domain, privacy_url or 'Not Found', policy_text.strip()])


def load_ground_truth_domains(filename='datasets/performance_analysis_dataset.csv'):
    domains = []
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"Domain list not found: {filename}")
    with open(filename, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # assume there's a "domain" column
        dom_col = 'domain' if 'domain' in reader.fieldnames else reader.fieldnames[0]
        for row in reader:
            dom = row.get(dom_col, '').strip()
            if dom:
                domains.append(dom)
    return domains


if __name__ == '__main__':

    # Logger setup
    configure_logger()
    logger = logging.getLogger(__name__)

    # Domain list setup
    try:
        domains = load_ground_truth_domains()
    except FileNotFoundError:
        logger.info('Domain list not found')
        exit(1)


    # url = input('Enter URL: ')
    for url in domains:
        try:
            scraper = WebScraper(url)
            privacy_urls = scraper.find_privacy_url()
            policies = scraper.extract_policies(privacy_urls)
            save_to_csv(url, privacy_urls, policies)
        except Exception as e:
            logger.exception(f"Failed to extract privacy urls, for{url}, {e} -------------------------------------------")
            continue


        # print(policies)
