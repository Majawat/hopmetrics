from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import sqlite3
from datetime import datetime
import os
from scraper import BeerScraper

app = Flask(__name__)

def init_db():
    """Initialize the database with required tables."""
    conn = sqlite3.connect('hopmetrics.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS establishments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT UNIQUE,
            location TEXT,
            last_scraped TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS beers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            establishment_id INTEGER,
            name TEXT NOT NULL,
            volume_oz REAL,
            abv REAL,
            price REAL,
            value_score REAL,
            brewery TEXT,
            ba_rating REAL,
            ba_style TEXT,
            ba_url TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (establishment_id) REFERENCES establishments (id)
        )
    ''')
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """Main page showing best value beers."""
    conn = sqlite3.connect('hopmetrics.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT b.name, e.name as establishment, b.volume_oz, b.abv, b.price, b.value_score, 
               b.brewery, b.ba_rating, b.ba_style, e.url, e.location
        FROM beers b
        JOIN establishments e ON b.establishment_id = e.id
        WHERE b.volume_oz IS NOT NULL AND b.abv IS NOT NULL AND b.price IS NOT NULL
        ORDER BY b.value_score DESC
        LIMIT 50
    ''')
    
    beers = cursor.fetchall()
    conn.close()
    
    return render_template('index.html', beers=beers)

@app.route('/api/beers')
def api_beers():
    """API endpoint for beer data."""
    conn = sqlite3.connect('hopmetrics.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT b.name, e.name as establishment, b.volume_oz, b.abv, b.price, b.value_score,
               b.brewery, b.ba_rating, b.ba_style, e.url, e.location
        FROM beers b
        JOIN establishments e ON b.establishment_id = e.id
        WHERE b.volume_oz IS NOT NULL AND b.abv IS NOT NULL AND b.price IS NOT NULL
        ORDER BY b.value_score DESC
    ''')
    
    beers = cursor.fetchall()
    conn.close()
    
    beer_list = []
    for beer in beers:
        beer_list.append({
            'name': beer[0],
            'establishment': beer[1],
            'volume_oz': beer[2],
            'abv': beer[3],
            'price': beer[4],
            'value_score': beer[5],
            'brewery': beer[6],
            'ba_rating': beer[7],
            'ba_style': beer[8],
            'establishment_url': beer[9],
            'location': beer[10]
        })
    
    return jsonify(beer_list)

@app.route('/scrape', methods=['GET', 'POST'])
def scrape_page():
    """Page for manual scraping."""
    if request.method == 'POST':
        name = request.form.get('name')
        url = request.form.get('url')
        location = request.form.get('location', '')
        
        if not name or not url:
            flash('Name and URL are required!')
            return redirect(url_for('scrape_page'))
        
        try:
            scraper = BeerScraper()
            beer_count = scraper.scrape_establishment(name, url, location)
            flash(f'Successfully scraped {beer_count} beers from {name}!')
        except Exception as e:
            flash(f'Error scraping {name}: {str(e)}')
        
        return redirect(url_for('index'))
    
    # Get existing establishments for reference
    conn = sqlite3.connect('hopmetrics.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name, url, location, last_scraped FROM establishments ORDER BY last_scraped DESC')
    establishments = cursor.fetchall()
    conn.close()
    
    return render_template('scrape.html', establishments=establishments)

@app.route('/establishments')
def establishments():
    """Show all tracked establishments."""
    conn = sqlite3.connect('hopmetrics.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT e.name, e.url, e.location, e.last_scraped, COUNT(b.id) as beer_count
        FROM establishments e
        LEFT JOIN beers b ON e.id = b.establishment_id
        GROUP BY e.id
        ORDER BY e.last_scraped DESC
    ''')
    
    establishments = cursor.fetchall()
    conn.close()
    
    return render_template('establishments.html', establishments=establishments)

if __name__ == '__main__':
    app.secret_key = 'hopmetrics-secret-key-change-in-production'
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)