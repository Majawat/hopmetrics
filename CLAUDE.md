# HopMetrics Project Memory

## Project Overview
HopMetrics is a web application that scrapes beer menu data from restaurants and bars to help users find the best "bang for your buck" beers, ranked by alcohol content per dollar.

## Version
v1.0.1 - Fixed Docker build issues and updated dependencies

### Changelog
- v1.0.1: Fixed Docker build errors, updated dependencies to latest versions, removed obsolete docker-compose version field
- v1.0.0: Initial release with BeerMenus.com and BeerAdvocate integration

## Architecture

### Tech Stack
- **Backend**: Python Flask
- **Database**: SQLite
- **Frontend**: HTML/CSS with Jinja2 templates
- **Scraping**: BeautifulSoup, requests
- **Deployment**: Docker + docker-compose

### Key Components

1. **app.py** - Main Flask application
   - Routes: /, /scrape, /establishments, /api/beers
   - Database initialization and management
   - Template rendering

2. **scraper.py** - Web scraping engine
   - `BeerScraper` class with specialized parsers
   - BeerMenus.com integration (primary target)
   - BeerAdvocate integration for ratings/styles
   - Generic scraper fallback for other sites

3. **templates/** - Web interface
   - index.html: Main beer listing with value scores
   - scrape.html: Manual scraping interface  
   - establishments.html: Management of tracked places

### Database Schema

**establishments**
- id, name, url, location, last_scraped

**beers** 
- id, establishment_id, name, volume_oz, abv, price, value_score
- brewery, ba_rating, ba_style, ba_url, scraped_at

### Value Calculation
```
Value Score = (Volume in oz × ABV%) ÷ Price
```

## Data Sources

### Primary: BeerMenus.com
- URL format: `https://www.beermenus.com/places/[id]-[name]`
- Extracts: beer name, brewery, ABV, price
- Volume estimation when not provided (16oz draft, 12oz bottle/can)

### Secondary: BeerAdvocate.com  
- Fetches quality ratings (0-5 scale)
- Beer style classification
- Cross-referenced by beer name + brewery

### Workflow
1. User adds establishment URL via /scrape interface
2. BeerMenus scraper extracts beer data
3. Each beer is cross-referenced with BeerAdvocate
4. Value scores calculated and stored
5. Results displayed ranked by value score

## Development Notes

### User Request History
- Initial ask: Create webapp for "best bang for buck" beers
- Specified BeerMenus.com as primary source (from previous Excel version)
- Requested BeerAdvocate cross-referencing for quality
- Wanted manual "scrape" button vs automated
- Docker deployment preference
- No specific tech stack preference

### Key Decisions
- Manual scraping approach (user-triggered vs scheduled)
- SQLite for simplicity in Docker environment  
- BeerAdvocate integration with 1s delays for politeness
- Volume estimation when missing from BeerMenus
- Focus on US establishments (BeerMenus coverage)

### Development Philosophy
- Focus on proper solutions to problems and features, never quick fixes

### Testing
- Test establishment: Bavarian Lodge (BeerMenus ID: 1239)
- URL: https://www.beermenus.com/places/1239-bavarian-lodge

## Deployment

### Docker Commands
```bash
# Build and run
docker-compose up --build

# Run scraper service (optional)
docker-compose --profile scraper up scraper
```

### Development
```bash
pip install -r requirements.txt
python app.py
```

## Future Enhancements Considered
- Scheduled scraping with cron jobs
- Additional beer sites (Untappd, brewery websites)
- Geographic filtering
- User preferences/favorites
- Export functionality
- Mobile app