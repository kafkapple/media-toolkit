import cloudscraper
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List
from .base import MediaExtractor, MediaItem

class WebImageExtractor(MediaExtractor):
    def is_supported(self, url: str) -> bool:
        # Fallback for generic websites
        return True

    def extract(self, url: str) -> List[MediaItem]:
        items = []
        # Cloudscraper creates a session that mimics a browser and solves simple JS challenges
        scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'darwin', 'desktop': True})

        try:
            response = scraper.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            images = soup.find_all('img')

            seen_urls = set()

            for img in images:
                src = img.get('src')
                if not src:
                    continue

                absolute_url = urljoin(url, src)

                # Basic dedup
                if absolute_url in seen_urls:
                    continue
                seen_urls.add(absolute_url)

                # Check for cached width/height attributes to filter tiny icons
                width = img.get('width')
                height = img.get('height')

                # Prepare title from alt or filename
                alt = img.get('alt', '')
                filename = urlparse(absolute_url).path.split('/')[-1]
                title = alt if alt else filename

                items.append(MediaItem(
                    url=absolute_url,
                    type='image',
                    thumbnail_url=absolute_url, # Use the image itself as thumbnail
                    title=title,
                    file_size="Unknown",
                    original_data={'alt': alt, 'width': width, 'height': height}
                ))

        except requests.exceptions.HTTPError as e:
             raise Exception(f"HTTP Error {e.response.status_code}: {e.response.reason} for {url}")
        except requests.exceptions.ConnectionError:
             raise Exception(f"Connection failed to {url}. Check internet or URL.")
        except requests.exceptions.Timeout:
             raise Exception(f"Request timed out for {url}")
        except Exception as e:
            raise Exception(f"Web scraping failed: {str(e)}")

        return items
