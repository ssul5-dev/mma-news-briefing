import sys
import unittest
from unittest.mock import patch, MagicMock

# Import the scraping and utility functions from main
from main import clean_html_tags, scrape_article_content

class TestNewsScraper(unittest.TestCase):

    def test_clean_html_tags(self):
        raw_html = "<b>병무청</b>, 2026년 &quot;청년&quot; 지원 안내"
        expected = "병무청, 2026년 \"청년\" 지원 안내"
        self.assertEqual(clean_html_tags(raw_html), expected)

    def test_clean_html_tags_empty(self):
        self.assertEqual(clean_html_tags(None), "")
        self.assertEqual(clean_html_tags(""), "")

    @patch('requests.get')
    def test_scrape_naver_news_content(self, mock_get):
        # Mock HTML response for Naver News article
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <body>
                <div id="dic_area">
                    이것은 실제 뉴스 본문 데이터입니다.
                    <script>var x = 1;</script>
                    <style>body { color: black; }</style>
                    <iframe src="dummy"></iframe>
                </div>
            </body>
        </html>
        """
        mock_get.return_value = mock_response

        url = "https://n.news.naver.com/mnews/article/001/00012345"
        result = scrape_article_content(url)
        
        # Script, style, and iframe tags should be removed, and only text remains
        self.assertIsNotNone(result)
        self.assertIn("이것은 실제 뉴스 본문 데이터입니다.", result)
        self.assertNotIn("var x", result)
        self.assertNotIn("color: black", result)

    @patch('requests.get')
    def test_scrape_generic_content(self, mock_get):
        # Mock HTML response for generic news site
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <header>Unwanted Header</header>
            <body>
                <p>첫 번째 뉴스 문단 내용이 여기에 들어갑니다. 길이가 적절해야 파싱이 됩니다.</p>
                <p>두 번째 뉴스 문단 내용도 동일하게 들어갑니다. 충분히 긴 내용이어야 파싱이 완료됩니다.</p>
                <footer>Unwanted Footer</footer>
            </body>
        </html>
        """
        mock_get.return_value = mock_response

        url = "https://www.somepress.co.kr/news/123"
        result = scrape_article_content(url)

        self.assertIsNotNone(result)
        self.assertIn("첫 번째 뉴스 문단 내용이 여기에 들어갑니다.", result)
        self.assertNotIn("Unwanted Header", result)
        self.assertNotIn("Unwanted Footer", result)

if __name__ == '__main__':
    unittest.main()
