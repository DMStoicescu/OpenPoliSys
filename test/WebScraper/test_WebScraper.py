import logging
from unittest.mock import patch, MagicMock
from src.WebScraper.WebScraper import WebScraper

# Add detail here for the logger so that the test suite does not fail
DETAIL_LEVEL_NUM = 15
logging.addLevelName(DETAIL_LEVEL_NUM, "DETAIL")
def _detail(self, message, *args, **kwargs):
    if self.isEnabledFor(DETAIL_LEVEL_NUM):
        self._log(DETAIL_LEVEL_NUM, message, args, **kwargs)
logging.Logger.detail = _detail

@patch('src.WebScraper.WebScraper.webdriver.Chrome')
def test_find_privacy_url_direct_match(mock_webdriver):
    mock_driver = MagicMock()
    mock_driver.page_source = '<html><head><title>Privacy Policy</title></head></html>'
    mock_driver.title = 'Privacy Policy'
    mock_driver.current_url = 'https://example.com/privacy'
    mock_webdriver.return_value = mock_driver

    scraper = WebScraper('example.com')
    scraper.page_is_english = lambda: True
    scraper.page_is_valid_privacy_page = lambda: True
    scraper.find_privacy_url()

    assert len(scraper.privacy_subdomains) == 1
    assert scraper.privacy_subdomains[0].lower() == 'https://example.com/privacy'
    # Ensure navigation happens
    mock_driver.get.assert_called()

# Test that the scraper identifies a privacy URL by scanning homepage links for relevant keywords
@patch('src.WebScraper.WebScraper.webdriver.Chrome')
def test_find_privacy_url_from_links(mock_webdriver):
    # Create mock driver and mock link element
    mock_driver = MagicMock()
    mock_link = MagicMock()
    mock_link.text = 'Privacy'
    mock_link.get_attribute.return_value = '/privacy'

    # Mock homepage with link
    mock_driver.find_elements.return_value = [mock_link]

    # When the scraper visits the candidate link, pretend it's a valid privacy page
    mock_driver.page_source = '<html><title>Privacy Policy</title></html>'
    mock_driver.title = 'Privacy Policy'

    # Inject driver into scraper
    mock_webdriver.return_value = mock_driver
    scraper = WebScraper('example.com')
    scraper.page_is_english = lambda: True
    scraper.page_is_valid_privacy_page = lambda: True
    scraper.find_privacy_url()

    # Assert scraper captured the candidate URL
    assert len(scraper.privacy_subdomains) == 1
    assert scraper.privacy_subdomains[0].endswith('/privacy')

# Test that scrolling stops when the page height no longer increases (scroll-to-bottom termination logic)
@patch('src.WebScraper.WebScraper.webdriver.Chrome')
def test_scroll_to_bottom_stops(mock_webdriver):
    mock_driver = MagicMock()
    mock_driver.execute_script.side_effect = [1000, None, 1000]  # simulate fixed scroll height
    mock_webdriver.return_value = mock_driver

    scraper = WebScraper('example.com')
    scraper.driver = mock_driver
    scraper.scroll_to_bottom()

    calls = [call[0][0] for call in mock_driver.execute_script.call_args_list]
    assert "window.scrollTo" in calls[1]

# Test that full policy text is extracted when a privacy URL is defined and page source contains relevant content
@patch('src.WebScraper.WebScraper.webdriver.Chrome')
def test_extract_policies_success(mock_webdriver):
    mock_driver = MagicMock()
    html = "<html><body><h1>Privacy Policy</h1><p>Your info</p></body></html>"
    mock_driver.page_source = html
    mock_driver.find_element.return_value.text = "Privacy Policy"
    mock_webdriver.return_value = mock_driver

    scraper = WebScraper('example.com')
    scraper.driver = mock_driver

    result = scraper.extract_policies(['https://example.com/privacy'])
    assert "privacy" in result.lower()

# Test that the method returns a fallback message when no privacy URL was previously set
@patch('src.WebScraper.WebScraper.webdriver.Chrome')
def test_extract_policies_no_url(mock_webdriver):
    scraper = WebScraper('example.com')
    scraper.driver = MagicMock()

    result = scraper.extract_policies([])
    assert result == 'No privacy url found'
