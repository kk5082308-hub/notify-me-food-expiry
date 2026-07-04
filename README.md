# Notify-Me for Packaged Food

Notify-Me for Packaged Food is a smart, production-ready web application built with Python (Flask), SQLite, Bootstrap 5, and Progressive Web App (PWA) technologies. It runs completely automated expiry alert notifications via background threads and immediate triggers when you log items.

---

## Key Features

1. **Authentication**: Secure register, login, logout, and validation of phone numbers.
2. **Dashboard Charts**: Visualizations for categorizations, timeline queues, and safe vs. expired food ratios using Chart.js.
3. **Automated Expiry Checks**: Integrates APScheduler running checks every hour in the background. It finds foods expiring **TODAY** or **TOMORROW**, creates database notification records, and dispatches Twilio SMS alerts.
4. **Immediate Alerts**: Automatically triggers a Twilio SMS warning immediately after a new food item is saved if its expiration is today or tomorrow.
5. **Duplicate Prevention**: Reconciles the notification logs database to ensure the same alert is never dispatched twice.
6. **Receipt Scanning**: Integrates an EasyOCR scanning interface to extract item details from shopping bills.
7. **Barcode Scanner**: Integrates a camera scanner querying the Open Food Facts API to autofill forms.

---

## Tech Stack

* **Backend**: Python, Flask, Flask-SQLAlchemy, SQLite, Flask-Login, APScheduler, Twilio Helper
* **Frontend**: HTML5, CSS3, Bootstrap 5, Chart.js
* **Utilities**: EasyOCR, OpenCV, Pillow, requests

---

## Twilio Free Trial Configuration Instructions

Since this project runs on a Twilio Free Trial configuration for demonstration purposes:
1. **Create a Free Account**: Sign up at [Twilio](https://www.twilio.com/).
2. **Retrieve API Credentials**: Navigate to your Twilio Console Dashboard and copy:
   * **Account SID**
   * **Auth Token**
   * **Twilio Phone Number** (Assigned Sender Number)
3. **Verify Recipient Phone Number**: 
   * In the Twilio Console, search for **Verified Caller IDs**.
   * Add and verify the phone number where you will receive SMS notifications. 
   * *Twilio Free Trial ONLY allows sending SMS to verified caller phone numbers.* Replacing these credentials with a paid account enables SMS delivery to any phone number.
4. **Configure Environment Variables**:
   Set these keys in your system environment before launching the server:
   
   **On Windows (PowerShell)**:
   ```powershell
   $env:TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   $env:TWILIO_AUTH_TOKEN="your_auth_token_here"
   $env:TWILIO_PHONE_NUMBER="+1234567890"  # Your Twilio phone number
   ```
   
   **On Linux / macOS**:
   ```bash
   export TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   export TWILIO_AUTH_TOKEN="your_auth_token_here"
   export TWILIO_PHONE_NUMBER="+1234567890"
   ```

---

## Setup & Running the Server

Ensure Python is installed on your machine.

### 1. Set Up Virtual Environment

```powershell
# Create venv
py -m venv .venv

# Activate environment
.venv\Scripts\activate
```

### 2. Install Package Dependencies

```powershell
# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies from requirements.txt
pip install -r requirements.txt
```

### 3. Generate Image Assets

Draw default avatars and icon files:

```powershell
python generate_images.py
```

### 4. Run the Server

Start the Flask server:

```powershell
python app.py
```

Open [http://localhost:5000](http://localhost:5000) on your machine.
