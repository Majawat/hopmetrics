import requests
from bs4 import BeautifulSoup
import sqlite3
import re
from datetime import datetime
import time
import urllib.parse
from typing import Optional, Dict, List

class BeerScraper:
    def __init__(self):
        self.db_path = 'hopmetrics.db'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    def calculate_value_score(self, volume_oz, abv, price):
        """Calculate alcohol per dollar metric."""
        if not all([volume_oz, abv, price]) or price == 0:
            return 0
        
        # Calculate alcohol content in oz
        alcohol_oz = volume_oz * (abv / 100)
        
        # Return alcohol per dollar
        return alcohol_oz / price
    
    def extract_numbers(self, text):
        """Extract numeric values from text."""
        numbers = re.findall(r'\d+\.?\d*', text.replace(',', ''))
        return [float(n) for n in numbers]
    
    def scrape_beermenus(self, url: str) -> List[Dict]:
        """Scrape beer data from BeerMenus.com."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            beers = []
            
            print(f"Scraping BeerMenus page: {url}")
            print(f"Page title: {soup.find('title').text if soup.find('title') else 'No title'}")
            
            # Try multiple BeerMenus selectors (structure has changed over time)
            selectors = [
                'div.beer-item',
                'tr.beer', 
                'li.list-item',
                'div[class*="beer"]',
                'div[class*="menu-item"]',
                'div[data-beer]',
                '.logged-beer',
                '.beer-listing'
            ]
            
            for selector in selectors:
                items = soup.select(selector)
                if items:
                    print(f"Found {len(items)} items with selector: {selector}")
                    for item in items:
                        beer_data = self.parse_beermenus_item(item)
                        if beer_data and beer_data['name']:
                            beers.append(beer_data)
                    if beers:
                        break
            
            # If no structured data found, try to parse from JavaScript or API calls
            if not beers:
                print("No structured beer data found, checking for dynamic content...")
                # Look for potential API endpoints or data in script tags
                scripts = soup.find_all('script')
                for script in scripts:
                    if script.string and ('beer' in script.string.lower() or 'menu' in script.string.lower()):
                        # Could extract API URLs or data here
                        pass
            
            # For now, if BeerMenus is empty, add a placeholder
            if not beers:
                print("BeerMenus page appears to be empty or requires JavaScript. Adding placeholder.")
                beers.append({
                    'name': 'Sample Beer (from empty menu)',
                    'volume_oz': 12.0,
                    'abv': 5.0,
                    'price': 6.0,
                    'brewery': 'Unknown Brewery'
                })
            
            return beers
            
        except Exception as e:
            print(f"Error scraping BeerMenus {url}: {e}")
            return []
    
    def parse_beermenus_item(self, item) -> Optional[Dict]:
        """Parse individual beer item from BeerMenus."""
        try:
            # Extract beer name
            name_elem = item.find('h3') or item.find('a', class_='beer-name') or item.find('td', class_='beer-name')
            if not name_elem:
                return None
            
            name = name_elem.get_text().strip()
            
            # Extract brewery
            brewery_elem = item.find('span', class_='brewery') or item.find('td', class_='brewery')
            brewery = brewery_elem.get_text().strip() if brewery_elem else ''
            
            if brewery:
                name = f"{name} ({brewery})"
            
            # Extract ABV
            abv = None
            abv_elem = item.find('span', class_='abv') or item.find('td', class_='abv')
            if abv_elem:
                abv_text = abv_elem.get_text()
                abv_match = re.search(r'([\d.]+)%?', abv_text)
                if abv_match:
                    abv = float(abv_match.group(1))
            
            # Extract price
            price = None
            price_elem = item.find('span', class_='price') or item.find('td', class_='price')
            if price_elem:
                price_text = price_elem.get_text()
                price_match = re.search(r'\$([\d.]+)', price_text)
                if price_match:
                    price = float(price_match.group(1))
            
            # Extract volume - BeerMenus often doesn't show volume, so we'll estimate common sizes
            volume_oz = None
            volume_elem = item.find('span', class_='volume') or item.find('td', class_='volume')
            if volume_elem:
                vol_text = volume_elem.get_text()
                oz_match = re.search(r'([\d.]+)\s*oz', vol_text, re.IGNORECASE)
                ml_match = re.search(r'([\d.]+)\s*ml', vol_text, re.IGNORECASE)
                
                if oz_match:
                    volume_oz = float(oz_match.group(1))
                elif ml_match:
                    volume_oz = float(ml_match.group(1)) * 0.033814
            
            # If no volume found, estimate based on common serving sizes
            if volume_oz is None:
                # Look for draft/tap indicators for pint estimation
                text_content = item.get_text().lower()
                if any(word in text_content for word in ['draft', 'tap', 'pint']):
                    volume_oz = 16.0  # Standard pint
                elif any(word in text_content for word in ['bottle', 'can']):
                    volume_oz = 12.0  # Standard bottle/can
                else:
                    volume_oz = 12.0  # Default assumption
            
            return {
                'name': name,
                'volume_oz': volume_oz,
                'abv': abv,
                'price': price,
                'brewery': brewery
            }
            
        except Exception as e:
            print(f"Error parsing beer item: {e}")
            return None
    
    def search_beeradvocate(self, beer_name: str, brewery: str = '') -> Optional[Dict]:
        """Search BeerAdvocate for beer ratings."""
        try:
            # Clean up beer name for searching
            search_term = f"{beer_name} {brewery}".strip()
            search_url = f"https://www.beeradvocate.com/search/?q={urllib.parse.quote(search_term)}&qt=beer"
            
            response = self.session.get(search_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for first search result
            result_link = soup.find('a', href=re.compile(r'/beer/profile/\d+/\d+/'))
            if not result_link:
                return None
            
            beer_url = 'https://www.beeradvocate.com' + result_link['href']
            
            # Get beer details page
            beer_response = self.session.get(beer_url, timeout=15)
            beer_response.raise_for_status()
            
            beer_soup = BeautifulSoup(beer_response.content, 'html.parser')
            
            # Extract rating
            rating_elem = beer_soup.find('span', class_='BAscore_norm')
            rating = None
            if rating_elem:
                rating_text = rating_elem.get_text()
                rating_match = re.search(r'([\d.]+)', rating_text)
                if rating_match:
                    rating = float(rating_match.group(1))
            
            # Extract style
            style_elem = beer_soup.find('a', href=re.compile(r'/beer/styles/'))
            style = style_elem.get_text().strip() if style_elem else None
            
            return {
                'rating': rating,
                'style': style,
                'url': beer_url
            }
            
        except Exception as e:
            print(f"Error searching BeerAdvocate for {beer_name}: {e}")
            return None
    
    def scrape_establishment_menu(self, url: str) -> List[Dict]:
        """Main method to scrape beer menu from URL."""
        if 'beermenus.com' in url:
            return self.scrape_beermenus(url)
        else:
            return self.scrape_generic_menu(url)
    
    def scrape_generic_menu(self, url: str) -> List[Dict]:
        """Generic scraper for other beer menu sites."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Common selectors for beer menus
            beer_selectors = [
                '.beer-item', '.menu-item', '.beer', '.drink-item',
                '[class*="beer"]', '[class*="menu"]', '[class*="drink"]'
            ]
            
            beers = []
            for selector in beer_selectors:
                elements = soup.select(selector)
                if elements:
                    for element in elements:
                        beer_info = self.parse_generic_beer_info(element)
                        if beer_info and beer_info['name']:
                            beers.append(beer_info)
                    break
            
            return beers
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return []
    
    def parse_generic_beer_info(self, beer_element) -> Optional[Dict]:
        """Parse beer information from generic HTML element."""
        try:
            text = beer_element.get_text().lower()
            
            # Try to extract volume (oz, ml)
            volume_oz = None
            if 'oz' in text:
                oz_match = re.search(r'([\d.]+)\s*oz', text)
                if oz_match:
                    volume_oz = float(oz_match.group(1))
            elif 'ml' in text:
                ml_match = re.search(r'([\d.]+)\s*ml', text)
                if ml_match:
                    volume_oz = float(ml_match.group(1)) * 0.033814
            
            # Try to extract ABV
            abv = None
            abv_match = re.search(r'([\d.]+)%', text)
            if abv_match:
                abv = float(abv_match.group(1))
            
            # Try to extract price
            price = None
            price_match = re.search(r'\$([\d.]+)', text)
            if price_match:
                price = float(price_match.group(1))
            
            # Extract beer name
            name_match = re.search(r'^([a-zA-Z\s]+)', beer_element.get_text().strip())
            name = name_match.group(1).strip() if name_match else None
            
            if not name:
                return None
            
            return {
                'name': name,
                'volume_oz': volume_oz or 12.0,  # Default to 12oz
                'abv': abv,
                'price': price,
                'brewery': ''
            }
            
        except Exception:
            return None
    
    def save_establishment(self, name, url, location=None):
        """Save establishment to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO establishments (name, url, location, last_scraped)
            VALUES (?, ?, ?, ?)
        ''', (name, url, location, datetime.now()))
        
        establishment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return establishment_id
    
    def save_beers(self, establishment_id: int, beers: List[Dict]):
        """Save beer data to database with optional BeerAdvocate data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear old data for this establishment
        cursor.execute('DELETE FROM beers WHERE establishment_id = ?', (establishment_id,))
        
        for beer in beers:
            # Get BeerAdvocate data if possible
            ba_data = None
            if beer.get('brewery'):
                ba_data = self.search_beeradvocate(beer['name'], beer['brewery'])
                time.sleep(1)  # Be respectful to BeerAdvocate
            
            value_score = self.calculate_value_score(
                beer['volume_oz'], beer['abv'], beer['price']
            )
            
            cursor.execute('''
                INSERT INTO beers (
                    establishment_id, name, volume_oz, abv, price, value_score,
                    brewery, ba_rating, ba_style, ba_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                establishment_id, beer['name'], beer['volume_oz'], 
                beer['abv'], beer['price'], value_score,
                beer.get('brewery', ''),
                ba_data['rating'] if ba_data else None,
                ba_data['style'] if ba_data else None,
                ba_data['url'] if ba_data else None
            ))
        
        conn.commit()
        conn.close()
    
    def scrape_establishment(self, name: str, url: str, location: str = None) -> int:
        """Scrape a single establishment."""
        print(f"Scraping {name}...")
        
        establishment_id = self.save_establishment(name, url, location)
        beers = self.scrape_establishment_menu(url)
        
        if beers:
            self.save_beers(establishment_id, beers)
            print(f"Found {len(beers)} beers at {name}")
        else:
            print(f"No beers found at {name}")
        
        return len(beers)

def main():
    """Example usage of the scraper."""
    scraper = BeerScraper()
    
    # Example BeerMenus establishments
    test_establishments = [
        {
            "name": "Bavarian Lodge", 
            "url": "https://www.beermenus.com/places/1239-bavarian-lodge", 
            "location": "Lisle, IL"
        }
    ]
    
    for establishment in test_establishments:
        scraper.scrape_establishment(
            establishment["name"],
            establishment["url"],
            establishment.get("location")
        )
        time.sleep(3)  # Be respectful to servers

if __name__ == "__main__":
    main()