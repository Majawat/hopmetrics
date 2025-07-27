# HopMetrics 🍺

A web application that scrapes beer menu data from restaurants and bars to find the best bang for your buck - ranking beers by alcohol content per dollar.

## Features

- **BeerMenus.com Integration**: Specialized scraper for BeerMenus.com with structured data extraction
- **BeerAdvocate Ratings**: Automatically fetches quality ratings and beer styles from BeerAdvocate
- **Value Calculation**: Calculates alcohol per dollar ratio (volume × ABV ÷ price)
- **Manual Scraping**: Web interface with "scrape" button for on-demand data collection
- **Comprehensive Beer Data**: Name, brewery, volume, ABV, price, style, and ratings
- **Docker Ready**: Easy deployment with Docker containers
- **SQLite Database**: Lightweight storage for scraped data
- **Responsive UI**: Clean interface showing value scores, ratings, and establishment info

## Quick Start

### Using Docker (Recommended)

1. **Build and run the container:**
   ```bash
   docker-compose up --build
   ```

2. **Access the application:**
   Open http://localhost:5000 in your browser

3. **Run the scraper (optional):**
   ```bash
   docker-compose --profile scraper up scraper
   ```

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python app.py
   ```

3. **Run the scraper:**
   ```bash
   python scraper.py
   ```

## How It Works

### Value Calculation
The "value score" is calculated as:
```
Value Score = (Volume in oz × ABV%) ÷ Price
```

This gives you the amount of alcohol per dollar spent.

### Web Scraping
The scraper looks for common beer menu patterns and extracts:
- Beer name
- Volume (oz or ml)
- ABV percentage
- Price

### Database Schema
- **establishments**: Restaurant/bar information
- **beers**: Individual beer entries with calculated value scores

## Customization

### Adding New Establishments
Use the web interface at `/scrape` to add new establishments:

1. Navigate to http://localhost:5000/scrape
2. Enter the restaurant/bar name
3. Paste the BeerMenus.com URL
4. Add location (optional)
5. Click "Scrape Beer Data"

**Supported URLs:**
- BeerMenus.com (optimized): `https://www.beermenus.com/places/[id]-[name]`
- Other sites (basic support): Various beer menu websites

### Custom Scrapers
For websites with unique layouts, extend the `BeerScraper` class with custom parsing methods.

## API Endpoints

- `GET /` - Main web interface showing ranked beers
- `GET /scrape` - Manual scraping interface  
- `POST /scrape` - Add new establishment and scrape data
- `GET /establishments` - View all tracked establishments
- `GET /api/beers` - JSON API for beer data with ratings

## Environment Variables

- `FLASK_ENV` - Set to `production` for deployment
- `FLASK_APP` - Application entry point (default: `app.py`)

## Docker Services

- **hopmetrics**: Main web application
- **scraper**: Optional scheduled scraping service

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your improvements
4. Test with Docker
5. Submit a pull request

## Legal Note

Please ensure you have permission to scrape target websites and respect robots.txt files and rate limits.