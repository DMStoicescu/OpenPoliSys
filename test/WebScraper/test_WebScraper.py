from unittest.mock import patch, MagicMock
from src.WebScraper.WebScraper import WebScraper

@patch('src.WebScraper.WebScraper.webdriver.Chrome')
def test_find_privacy_url_direct_match(mock_webdriver):
    mock_driver = MagicMock()
    mock_driver.page_source = '<html><head><title>Privacy Policy</title></head></html>'
    mock_driver.title = 'Privacy Policy'
    mock_webdriver.return_value = mock_driver

    scraper = WebScraper('example.com')
    scraper.find_privacy_url()

    assert scraper.privacy_url is not None
    assert 'privacy' in scraper.privacy_url.lower()
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
    scraper.find_privacy_url()

    # Assert scraper captured the candidate URL
    assert scraper.privacy_url is not None
    assert scraper.privacy_url.endswith('/privacy')

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
    scraper.privacy_url = 'https://example.com/privacy'

    result = scraper.extract_policies()
    assert "privacy" in result.lower()

# Test that the method returns a fallback message when no privacy URL was previously set
@patch('src.WebScraper.WebScraper.webdriver.Chrome')
def test_extract_policies_no_url(mock_webdriver):
    scraper = WebScraper('example.com')
    scraper.driver = MagicMock()

    result = scraper.extract_policies()
    assert result == 'No privacy url found'
