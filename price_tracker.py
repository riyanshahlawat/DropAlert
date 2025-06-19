import requests
from bs4 import BeautifulSoup
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
URL = 'https://www.amazon.in/dp/B0CHYQ7J7W/'
TARGET_PRICE = 1500
EMAIL = 'your_email@gmail.com'
EMAIL_PASSWORD = 'your_app_password'
TO_EMAIL = 'receiver_email@gmail.com'
CHECK_INTERVAL = 6 * 60 * 60  # 6 hours in seconds

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

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

def send_email(product_name, price, url):
    subject = f'Price Drop Alert: {product_name} now at ₹{price}'
    body = f'The price for "{product_name}" has dropped to ₹{price} on Amazon!\n\nCheck it out here: {url}'
    msg = MIMEMultipart()
    msg['From'] = EMAIL
    msg['To'] = TO_EMAIL
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL, EMAIL_PASSWORD)
            server.sendmail(EMAIL, TO_EMAIL, msg.as_string())
        print('Email sent!')
    except Exception as e:
        print('Failed to send email:', e)

def main():
    while True:
        print('Checking price...')
        product_name, price = get_price_and_name(URL)
        print(f'Product: {product_name}\nCurrent Price: {price}')
        if price is not None and price <= TARGET_PRICE:
            send_email(product_name, price, URL)
        else:
            print('No alert sent.')
        print(f'Waiting {CHECK_INTERVAL/3600} hours for next check...')
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main() 