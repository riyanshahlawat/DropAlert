from flask import Flask, render_template, request, redirect, url_for, flash
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for flash messages

# In-memory store for tracking jobs
tracking_jobs = []

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

CHECK_INTERVAL = 6 * 60 * 60  # 6 hours in seconds

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

def send_email(product_name, price, url, to_email, from_email, from_password):
    subject = f'Price Drop Alert: {product_name} now at ₹{price}'
    body = f'The price for "{product_name}" has dropped to ₹{price} on Amazon!\n\nCheck it out here: {url}'
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

def check_all_prices():
    print('Running scheduled price check for all tracked products...')
    to_remove = []
    from_email = os.environ.get('EMAIL')
    from_password = os.environ.get('EMAIL_PASSWORD')
    if not from_email or not from_password:
        print('WARNING: EMAIL or EMAIL_PASSWORD environment variable not set!')
        return
    for job in tracking_jobs:
        url = job['url']
        target_price = job['target_price']
        user_email = job['user_email']
        product_name, price = get_price_and_name(url)
        print(f'Checked {product_name}: {price}')
        if price is not None and price <= target_price:
            send_email(product_name, price, url, user_email, from_email, from_password)
            to_remove.append(job)
    # Remove jobs that have been alerted
    for job in to_remove:
        tracking_jobs.remove(job)

# Set up APScheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_all_prices, trigger="interval", seconds=CHECK_INTERVAL)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/track', methods=['POST'])
def track():
    url = request.form['url']
    target_price = float(request.form['target_price'])
    user_email = request.form['email']
    # Add to tracking jobs
    tracking_jobs.append({
        'url': url,
        'target_price': target_price,
        'user_email': user_email
    })
    flash('Tracking started! You will get an email if the price drops.')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 