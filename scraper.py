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
    
    def scrape_beermenus(self, url: str) -> tuple[List[Dict], Dict]:
        """Scrape beer data and establishment info from BeerMenus.com."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            beers = []
            
            print(f"Scraping BeerMenus page: {url}")
            
            # Extract establishment details from the page
            establishment_info = self.extract_establishment_info(soup, url)
            print(f"Establishment: {establishment_info['name']} - {establishment_info['location']}")
            
            # Look for the current BeerMenus structure
            # The beer lists are in: ul#on_tap, ul#bottles_cans, etc.
            beer_sections = [
                '#on_tap li.pure-list-item',
                '#bottles_cans li.pure-list-item', 
                '#cider_perry li.pure-list-item',
                '#mead_cyser li.pure-list-item',
                'ul.pure-list-featured li.pure-list-item'  # Recommendations
            ]
            
            for selector in beer_sections:
                items = soup.select(selector)
                if items:
                    print(f"Found {len(items)} items with selector: {selector}")
                    for item in items:
                        # Skip "View all" links
                        if 'pure-list-item-more' in item.get('class', []):
                            continue
                        
                        beer_data = self.parse_beermenus_item(item)
                        if beer_data and beer_data['name']:
                            beers.append(beer_data)
                            
            print(f"Total beers extracted: {len(beers)}")
            
            # If no beers found, it's likely due to JavaScript loading
            if not beers:
                print("No beer data found - likely requires JavaScript rendering")
                print("Page shows beer counts but content loads dynamically")
                
            return beers, establishment_info
            
        except Exception as e:
            print(f"Error scraping BeerMenus {url}: {e}")
            return [], {'name': 'Unknown', 'location': '', 'description': ''}
    
    def extract_establishment_info(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract establishment name, location, and other details from BeerMenus page."""
        info = {
            'name': 'Unknown Establishment',
            'location': '',
            'description': ''
        }
        
        try:
            # Extract name from title or h1
            title_elem = soup.find('title')
            if title_elem:
                title_text = title_elem.get_text()
                # Format: "Name - Beer Menu - Location"
                if ' - Beer Menu - ' in title_text:
                    parts = title_text.split(' - Beer Menu - ')
                    info['name'] = parts[0].strip()
                    if len(parts) > 1:
                        info['location'] = parts[1].strip()
                elif ' - Beer Menu' in title_text:
                    info['name'] = title_text.replace(' - Beer Menu', '').strip()
            
            # Try to get name from h1 if title parsing didn't work well
            h1_elem = soup.find('h1')
            if h1_elem and info['name'] == 'Unknown Establishment':
                info['name'] = h1_elem.get_text().strip()
            
            # Extract beer counts from the page summary
            beer_counts_elem = soup.find('div', class_='pure-u-2-3 text-right')
            if beer_counts_elem:
                counts_text = beer_counts_elem.get_text()
                info['description'] = counts_text.strip()
            
            # Extract meta description for additional info
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and not info['description']:
                info['description'] = meta_desc.get('content', '')
                
        except Exception as e:
            print(f"Error extracting establishment info: {e}")
        
        return info
    
    def parse_beermenus_item(self, item) -> Optional[Dict]:
        """Parse individual beer item from current BeerMenus structure."""
        try:
            # NEW STRUCTURE: <li class="pure-list-item">
            #   <div class="pure-g">
            #     <div class="pure-u-2-3">
            #       <h3><a href="/beers/...">Beer Name</a></h3>
            #       <p class="caption text-gray">Style · ABV% · Location</p>
            #     </div>
            #     <div class="pure-u-1-3">
            #       <p class="caption text-right">Volume Format $Price</p>
            #     </div>
            
            # Extract beer name from h3 > a
            name_link = item.find('h3').find('a') if item.find('h3') else None
            if not name_link:
                return None
            
            name = name_link.get_text().strip()
            
            # Extract style, ABV, and location from caption paragraph
            caption_elem = item.find('p', class_='caption text-gray')
            style = ''
            abv = None
            brewery = ''
            
            if caption_elem:
                caption_text = caption_elem.get_text().strip()
                # Format: "Style · ABV% · Location"
                parts = [part.strip() for part in caption_text.split('·')]
                if len(parts) >= 2:
                    style = parts[0]
                    abv_part = parts[1]
                    abv_match = re.search(r'([\d.]+)%', abv_part)
                    if abv_match:
                        abv = float(abv_match.group(1))
                if len(parts) >= 3:
                    brewery = parts[2]
            
            # Extract price and volume from right column
            price_elem = item.find('div', class_='pure-u-1-3').find('p', class_='caption text-right') if item.find('div', class_='pure-u-1-3') else None
            price = None
            volume_oz = None
            
            if price_elem:
                price_text = price_elem.get_text().strip()
                # Format examples: "13oz Draft $7.50", "12oz Bottle $14", "10oz Snifter $8"
                
                # Extract price
                price_match = re.search(r'\$([\d.]+)', price_text)
                if price_match:
                    price = float(price_match.group(1))
                
                # Extract volume
                volume_match = re.search(r'([\d.]+)oz', price_text, re.IGNORECASE)
                if volume_match:
                    volume_oz = float(volume_match.group(1))
                else:
                    # Check for ml
                    ml_match = re.search(r'([\d.]+)ml', price_text, re.IGNORECASE)
                    if ml_match:
                        volume_oz = float(ml_match.group(1)) * 0.033814
            
            # Default volume if not found
            if volume_oz is None:
                if any(word in price_text.lower() for word in ['draft', 'tap']) if price_elem else False:
                    volume_oz = 16.0  # Draft default
                else:
                    volume_oz = 12.0  # Bottle/can default
            
            return {
                'name': name,
                'volume_oz': volume_oz,
                'abv': abv,
                'price': price,
                'brewery': brewery,
                'style': style
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
    
    def scrape_establishment_menu(self, url: str) -> tuple[List[Dict], Dict]:
        """Main method to scrape beer menu from URL."""
        if 'beermenus.com' in url:
            return self.scrape_beermenus(url)
        else:
            beers = self.scrape_generic_menu(url)
            # For non-BeerMenus sites, extract basic info from URL
            establishment_info = {
                'name': 'Unknown Establishment',
                'location': '',
                'description': f'Generic scrape from {url}'
            }
            return beers, establishment_info
    
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
                beer.get('style') or (ba_data['style'] if ba_data else None),
                ba_data['url'] if ba_data else None
            ))
        
        conn.commit()
        conn.close()
    
    def scrape_establishment(self, url: str, name: str = None, location: str = None) -> tuple[int, Dict]:
        """Scrape establishment from URL, auto-extracting details."""
        print(f"Scraping {url}...")
        
        beers, establishment_info = self.scrape_establishment_menu(url)
        
        # Use extracted info if not provided
        final_name = name or establishment_info['name']
        final_location = location or establishment_info['location']
        
        print(f"Establishment: {final_name}")
        if final_location:
            print(f"Location: {final_location}")
        if establishment_info.get('description'):
            print(f"Details: {establishment_info['description']}")
        
        establishment_id = self.save_establishment(final_name, url, final_location)
        
        if beers:
            self.save_beers(establishment_id, beers)
            print(f"Found {len(beers)} beers at {final_name}")
        else:
            print(f"No beers found at {final_name}")
        
        return len(beers), {
            'name': final_name,
            'location': final_location,
            'description': establishment_info.get('description', '')
        }

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