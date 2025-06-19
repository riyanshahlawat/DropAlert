from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flash messages and sessions

# In-memory store for tracking jobs
tracking_jobs = []

DB_PATH = 'price_history.db'

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS tracked_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                target_price REAL NOT NULL,
                status TEXT DEFAULT 'tracking',
                product_name TEXT,
                last_price REAL,
                created_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                date TEXT NOT NULL,
                price REAL NOT NULL,
                user_id INTEGER,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        conn.commit()

init_db()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

CHECK_INTERVAL = 6 * 60 * 60  # 6 hours in seconds

AFFILIATE_TAG = 'dropalert-21'

# --- Scraping and Email Logic ---
def get_price_and_name(url):
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.content, 'html.parser')
    # Product name
    title = soup.find(id='productTitle')
    product_name = title.get_text(strip=True) if title else 'Unknown Product'
    # Product price
    price_tag = soup.find('span', {'class': 'a-price-whole'})
    if not price_tag:
        price_tag = soup.find('span', {'id': 'priceblock_ourprice'})
    if not price_tag:
        price_tag = soup.find('span', {'id': 'priceblock_dealprice'})
    if price_tag:
        price_str = price_tag.get_text().replace(',', '').replace('₹', '').strip()
        try:
            price = float(price_str.split()[0])
        except Exception:
            price = None
    else:
        price = None
    return product_name, price

def make_affiliate_link(url):
    if 'amazon.' not in url:
        return url
    if '?tag=' in url or '&tag=' in url:
        return url  # Already has a tag
    if '?' in url:
        return url + f'&tag={AFFILIATE_TAG}'
    else:
        return url + f'?tag={AFFILIATE_TAG}'

def send_email(product_name, price, url, to_email, from_email, from_password):
    affiliate_url = make_affiliate_link(url)
    subject = f'Price Drop Alert: {product_name} now at ₹{price}'
    body = f'The price for "{product_name}" has dropped to ₹{price} on Amazon!\n\nCheck it out here: {affiliate_url}'
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(from_email, from_password)
            server.sendmail(from_email, to_email, msg.as_string())
        print('Email sent!')
    except Exception as e:
        print('Failed to send email:', e)

def log_price(url, price, user_id=None):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('INSERT INTO price_history (url, date, price, user_id) VALUES (?, ?, ?, ?)',
                  (url, datetime.utcnow().strftime('%Y-%m-%d'), price, user_id))
        conn.commit()

def check_all_prices():
    print('Running scheduled price check for all tracked products...')
    from_email = os.environ.get('EMAIL')
    from_password = os.environ.get('EMAIL_PASSWORD')
    if not from_email or not from_password:
        print('WARNING: EMAIL or EMAIL_PASSWORD environment variable not set!')
        return
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''SELECT id, user_id, url, target_price, status FROM tracked_products WHERE status = 'tracking' ''')
        jobs = c.fetchall()
    for job in jobs:
        pid, user_id, url, target_price, status = job
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('SELECT email FROM users WHERE id = ?', (user_id,))
            user_row = c.fetchone()
            user_email = user_row[0] if user_row else None
        product_name, price = get_price_and_name(url)
        print(f'Checked {product_name}: {price}')
        if price is not None:
            log_price(url, price, user_id)
            # Update last_price and product_name
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute('''UPDATE tracked_products SET last_price = ?, product_name = ? WHERE id = ?''', (price, product_name, pid))
                conn.commit()
        if price is not None and price <= target_price and status == 'tracking':
            send_email(product_name, price, url, user_email, from_email, from_password)
            # Mark as alerted
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute('''UPDATE tracked_products SET status = 'alerted' WHERE id = ?''', (pid,))
                conn.commit()

# Set up APScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_all_prices, trigger="interval", seconds=CHECK_INTERVAL)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# --- User Auth Logic ---
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM users WHERE email = ?', (email,))
            if c.fetchone():
                flash('Email already registered.')
                return redirect(url_for('signup'))
            password_hash = generate_password_hash(password)
            c.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)', (email, password_hash))
            conn.commit()
        flash('Signup successful! Please log in.')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('SELECT id, password_hash FROM users WHERE email = ?', (email,))
            user = c.fetchone()
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['user_email'] = email
                flash('Logged in successfully!')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.')
                return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.')
    return redirect(url_for('login'))

@app.route('/')
def index():
    user_id = session.get('user_id')
    return render_template('index.html', user_id=user_id, user_email=session.get('user_email'))

@app.route('/track', methods=['POST'])
def track():
    if 'user_id' not in session:
        flash('Please log in to track products.')
        return redirect(url_for('login'))
    url = request.form['url']
    target_price = float(request.form['target_price'])
    user_id = session['user_id']
    # Scrape product name and current price
    product_name, last_price = get_price_and_name(url)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''INSERT INTO tracked_products (user_id, url, target_price, product_name, last_price, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))''',
                  (user_id, url, target_price, product_name, last_price))
        conn.commit()
    flash('Product added for tracking!')
    return redirect(url_for('dashboard'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        flash('Please log in to view price history.')
        return redirect(url_for('login'))
    url = request.args.get('url')
    if not url:
        return 'Missing url parameter', 400
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('SELECT date, price FROM price_history WHERE url = ? AND user_id = ? ORDER BY date', (url, session['user_id']))
        data = c.fetchall()
    dates = [row[0] for row in data]
    prices = [row[1] for row in data]
    return render_template('history.html', url=url, dates=dates, prices=prices)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access your dashboard.')
        return redirect(url_for('login'))
    user_id = session['user_id']
    # Add product form submission
    if request.method == 'POST':
        url = request.form['url']
        target_price = float(request.form['target_price'])
        # Scrape product name and current price
        product_name, last_price = get_price_and_name(url)
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''INSERT INTO tracked_products (user_id, url, target_price, product_name, last_price, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))''',
                      (user_id, url, target_price, product_name, last_price))
            conn.commit()
        flash('Product added for tracking!')
        return redirect(url_for('dashboard'))
    # List all tracked products for this user
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''SELECT id, url, target_price, status, product_name, last_price FROM tracked_products WHERE user_id = ?''', (user_id,))
        products = c.fetchall()
    # For each product, get analytics from price_history
    analytics = {}
    for p in products:
        pid, url, target_price, status, product_name, last_price = p
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute('''SELECT MIN(price), MAX(price), AVG(price) FROM price_history WHERE url = ? AND user_id = ?''', (url, user_id))
            min_price, max_price, avg_price = c.fetchone()
        analytics[pid] = {
            'min': min_price,
            'max': max_price,
            'avg': avg_price,
            'current': last_price
        }
    return render_template('dashboard.html', products=products, analytics=analytics, user_email=session.get('user_email'))

@app.route('/remove_product/<int:product_id>', methods=['POST'])
def remove_product(product_id):
    if 'user_id' not in session:
        flash('Please log in.')
        return redirect(url_for('login'))
    user_id = session['user_id']
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('DELETE FROM tracked_products WHERE id = ? AND user_id = ?', (product_id, user_id))
        conn.commit()
    flash('Product removed from tracking.')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 