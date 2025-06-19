# DropAlert

**DropAlert** is a modern web app that tracks Amazon India product prices and sends you an email alert when the price drops below your target. It features a beautiful glassmorphism UI and supports Amazon affiliate links for monetization.

---

## Features
- Track any Amazon India product by URL
- Get notified by email when the price drops below your target
- Modern, mobile-friendly UI (Apple-style glassmorphism)
- Monetize with Amazon affiliate links

---

## How It Works
1. **Enter the product URL, your target price, and your email** on the DropAlert homepage.
2. **DropAlert stores your request** and checks the product price every 6 hours.
3. **If the price drops below your target,** you receive an email alert with an affiliate link to the product.

---

## Quick Start (Local)

### 1. Clone the repo
```bash
git clone https://github.com/riyanshahlawat/DropAlert.git
cd DropAlert
```

### 2. Install dependencies
```bash
python -m pip install -r requirements.txt
```

### 3. Set environment variables
Create a `.env` file or set these in your environment:
- `EMAIL` = your Gmail address (for sending alerts)
- `EMAIL_PASSWORD` = your Gmail app password (not your regular password)

On Windows (PowerShell):
```powershell
$env:EMAIL="your_email@gmail.com"
$env:EMAIL_PASSWORD="your_app_password"
```

### 4. Run the app
```bash
python app.py
```
Visit [http://localhost:5000](http://localhost:5000) in your browser.

---

## Deploy on Render.com
1. **Push your code to GitHub.**
2. **Create a new Web Service** on [Render.com](https://render.com/):
   - Build command: `pip install -r requirements.txt`
   - Start command: `python app.py`
   - Set environment variables `EMAIL` and `EMAIL_PASSWORD` in the Render dashboard.
3. **Your app will be live at a public URL!**

---

## Amazon Affiliate Links
- All alert emails include your Amazon affiliate tag (set in the code as `dropalert-21`).
- You earn a commission if users buy through your links.
- You can update the affiliate tag in `app.py`.

---

## Customization
- **UI:** Edit `templates/index.html` for branding or layout changes.
- **Check Interval:** Change `CHECK_INTERVAL` in `app.py` (default: every 6 hours).
- **Add More Stores:** Extend the backend to support Flipkart or other e-commerce sites.

---

## License
MIT 