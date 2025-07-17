import csv
import os
import logging
from colorlog import ColoredFormatter
from src.WebScraper.WebScraper import WebScraper


def configure_logger():
    """
        Sets up global logging configuration with a custom "DETAIL" level (15),
        and applies colored output for console logs.

        - DETAIL messages appear in blue
        - INFO messages appear in green
        - DEBUG, WARNING, ERROR, CRITICAL get their own associated colors
    """
    # Define and register a new log level DETAIL (between DEBUG=10 and INFO=20)
    DETAIL_LEVEL_NUM = 15
    logging.addLevelName(DETAIL_LEVEL_NUM, "DETAIL")
    logging.Logger.detail = (
        lambda self, message, *args, **kwargs:
        self._log(DETAIL_LEVEL_NUM, message, args, **kwargs)
        if self.isEnabledFor(DETAIL_LEVEL_NUM) else None
    )

    # Basic configuration: console and file handlers, capturing DETAIL
    logging.basicConfig(
        level=DETAIL_LEVEL_NUM,  # Or DEBUG for more verbose output
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # Output to console
            logging.FileHandler('./out/scraper.log', mode='w')  # Output to file
        ]
    )

    # Define colored format and color mapping for log levels
    colored_fmt = (
        "%(log_color)s"  # injects the color code
        "%(asctime)s - %(levelname)-8s - %(message)s"
        "%(reset)s"  # resets color back to normal
    )
    color_map = {
        'DETAIL': 'blue',
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
    color_formatter = ColoredFormatter(
        colored_fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors=color_map,
        reset=True
    )

    # Replace formatter on console handler only
    root = logging.getLogger()
    for handler in root.handlers:
        # only colorize real console handlers, not the file handler
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setFormatter(color_formatter)

def save_to_csv(domain, privacy_url, policy_text, needs_review, filename='./out/policy_scrape_output.csv'):
    """
        Append a row to the output CSV with:
          - Input domain
          - Privacy policy URL (or 'Not Found')
          - Extracted policy text (stripped of extra whitespace)

        Writes header row if the file does not yet exist.

        :param needs_review:
        :param domain: The domain that was scraped (e.g., 'example.com')
        :param privacy_url: The full URL of the privacy policy page, or None
        :param policy_text: The extracted text of the privacy policy
        :param filename: Path to the CSV output file
    """
    file_exists = os.path.isfile(filename)

    with open(filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)

        # Write header only once
        if not file_exists:
            writer.writerow(['Input Domain', 'Privacy Policy URL', 'Policy Text', 'Needs Review'])

        # Write the data row
        writer.writerow([domain, privacy_url or 'Not Found', policy_text.strip(), needs_review])


def load_domains(filename='datasets/performance_analysis_dataset.csv'):
    """
        Reads a CSV file of domains and returns a list of domain strings.

        Expects a header row; uses a column named 'domain' if present, otherwise the first column.

        :param filename: Path to the CSV file containing domain list
        :return: List of non-empty domain strings
        :raises FileNotFoundError: If the file does not exist
    """
    domains = []
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"Domain list not found: {filename}")

    with open(filename, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # Choose 'domain' column if present, else default to first field
        dom_col = 'domain' if 'domain' in reader.fieldnames else reader.fieldnames[0]
        for row in reader:
            dom = row.get(dom_col, '').strip()
            if dom:
                domains.append(dom)
    return domains


if __name__ == '__main__':
    # Initialize logging
    configure_logger()
    logger = logging.getLogger(__name__)

    # Load list of domains; exit if missing
    try:
        domains = load_domains(filename='datasets/tranco_top_3000_analysis_dataset.csv')
    except FileNotFoundError:
        logger.error('Domain list not found')
        exit(1)

    # Iterate through domains, scrape policies, and save results
    for url in domains:
        try:
            scraper = WebScraper(url)
            privacy_urls = scraper.find_privacy_url()
            policies = scraper.extract_policies(privacy_urls)

            if scraper.is_timeout_flag:
                save_to_csv(url, ['DOMAIN TIMED OUT'], 'No privacy url found', needs_review= False)
            elif scraper.is_outdated_flag:
                save_to_csv(url, ['DOMAIN OUTDATED'], 'No privacy url found', needs_review= False)
            elif not scraper.is_en_flag:
                save_to_csv(url, ['DOMAIN NOT IN ENGLISH'], 'No privacy url found', needs_review= False)
            else:
                save_to_csv(url, privacy_urls, policies, needs_review = scraper.needs_review)
        except Exception as e:
            logger.error(f"Failed to extract privacy urls, for {url}, with the following error: {e}")
            continue
