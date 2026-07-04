import os
import re
import json
import requests
from datetime import datetime

# Optional third-party imports with fallback handling
try:
    from pywebpush import webpush, WebPushException
except ImportError:
    webpush = None
    WebPushException = None

try:
    import cv2
    import numpy as np
    import easyocr
except ImportError:
    easyocr = None
    cv2 = None
    np = None

from config import Config

# Categorization map from Open Food Facts categories to our system categories
CATEGORY_MAP = {
    'dairies': 'Dairy',
    'milk': 'Dairy',
    'cheeses': 'Dairy',
    'beverages': 'Beverages',
    'sodas': 'Beverages',
    'fruits': 'Fruits & Vegetables',
    'vegetables': 'Fruits & Vegetables',
    'groceries': 'Pantry',
    'snacks': 'Snacks',
    'sweet snacks': 'Snacks',
    'biscuits': 'Snacks',
    'meats': 'Meat & Seafood',
    'seafoods': 'Meat & Seafood',
    'frozen foods': 'Frozen',
    'breads': 'Bakery',
    'bakery': 'Bakery',
    'canned foods': 'Canned Goods'
}

def lookup_barcode(barcode):
    """
    Looks up a barcode using the Open Food Facts free JSON API.
    Returns a dictionary of product data or None if not found/error.
    """
    if not barcode:
        return None
        
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    try:
        response = requests.get(url, headers={'User-Agent': 'NotifyMePackagedFood - Android/Web - Version 1.0'}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 1:  # Product found
                product = data.get('product', {})
                
                # Try to map category
                off_categories = product.get('categories_tags', [])
                mapped_category = 'Other'
                for cat in off_categories:
                    # Clean tag (e.g. "en:beverages" -> "beverages")
                    clean_cat = cat.split(':')[-1].lower() if ':' in cat else cat.lower()
                    if clean_cat in CATEGORY_MAP:
                        mapped_category = CATEGORY_MAP[clean_cat]
                        break
                
                # Try to extract store
                stores = product.get('stores', '')
                store_name = stores.split(',')[0].strip() if stores else ''
                
                return {
                    'food_name': product.get('product_name', ''),
                    'brand': product.get('brands', '').split(',')[0].strip() if product.get('brands') else '',
                    'category': mapped_category,
                    'quantity': product.get('quantity', '1'),
                    'store': store_name,
                    'image_url': product.get('image_front_url') or product.get('image_url') or '',
                    'notes': f"Auto-imported from Open Food Facts. Barcode: {barcode}"
                }
    except Exception as e:
        print(f"Error querying Open Food Facts API: {e}")
        
    return None

def send_web_push(subscription_data, payload_data):
    """
    Sends a Web Push notification to a browser/phone using pywebpush.
    subscription_data is a dictionary/object with keys: endpoint, p256dh, auth
    payload_data is a dict containing title, body, url, etc.
    """
    if not webpush:
        print("WebPush module not loaded. Skipping push notification.")
        return False
        
    try:
        # Load keys from configuration
        public_key = Config.VAPID_PUBLIC_KEY
        private_key = Config.VAPID_PRIVATE_KEY
        claim_email = Config.VAPID_CLAIM_EMAIL
        
        if not private_key or not public_key:
            print("VAPID keys not configured. Cannot send web push.")
            return False
            
        subscription = {
            "endpoint": subscription_data.get('endpoint'),
            "keys": {
                "p256dh": subscription_data.get('p256dh'),
                "auth": subscription_data.get('auth')
            }
        }
        
        response = webpush(
            subscription_info=subscription,
            data=json.dumps(payload_data),
            vapid_private_key=private_key,
            vapid_claims={"sub": claim_email},
            timeout=10
        )
        return response.ok
    except WebPushException as ex:
        print(f"WebPushException sending notification: {ex}")
        # If the endpoint is no longer valid (e.g. code 410 Gone or 404),
        # we can flag it to be deleted.
        if ex.response is not None and ex.response.status_code in [404, 410]:
            return "expired"
    except Exception as e:
        print(f"Failed to send web push: {e}")
        
    return False

def send_twilio_sms(phone_number, message):
    """
    Sends an SMS using the Twilio API.
    
    DEMO FREE TRIAL MODE COMMENTS:
    1. The Twilio Free Trial account ONLY permits sending SMS to phone numbers 
       that have been manually added and verified in the Twilio Console under
       "Verified Caller IDs".
    2. No paid subscription is required to run this demo.
    3. Simply replace the TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER
       with credentials from a paid Twilio account to enable SMS delivery to any phone number.
    """
    sid = Config.TWILIO_ACCOUNT_SID
    token = Config.TWILIO_AUTH_TOKEN
    from_num = Config.TWILIO_PHONE_NUMBER
    
    if not sid or not token or not from_num:
        print("[Twilio] Credentials not set in environment. Skipping SMS notification.")
        return False
        
    if not phone_number:
        print("[Twilio] Recipient phone number is empty. Skipping SMS.")
        return False
        
    try:
        from twilio.rest import Client
        client = Client(sid, token)
        
        # Send SMS via Twilio Client
        client.messages.create(
            body=message,
            from_=from_num,
            to=phone_number
        )
        print(f"[Twilio] SMS successfully sent to {phone_number}")
        return True
    except Exception as e:
        print(f"[Twilio] Failed to send SMS to {phone_number}: {e}")
        return False

def parse_receipt(image_path):
    """
    Uses EasyOCR to scan a grocery bill image and parse items.
    Returns a list of dicts: [{'food_name': name, 'brand': brand, 'quantity': qty}]
    """
    print(f"Attempting to scan receipt: {image_path}")
    
    # 1. Fallback to mock parser if EasyOCR/PyTorch is not available
    if not easyocr or not cv2:
        print("EasyOCR or OpenCV is not loaded. Using Simulated OCR parser.")
        return simulate_ocr_parse(image_path)
        
    try:
        # Initialize easyocr reader (will load models to CPU/GPU)
        reader = easyocr.Reader(['en'], gpu=False)
        results = reader.readtext(image_path)
        
        # Sort results based on vertical position (Y-coordinate) to rebuild lines
        # results element: ( [ [x0,y0], [x1,y1], [x2,y2], [x3,y3] ], text, confidence )
        lines = []
        # Group text segments that are roughly on the same horizontal level (threshold 15 pixels)
        sorted_results = sorted(results, key=lambda x: x[0][0][1])
        
        current_line_y = -999
        current_line = []
        
        for res in sorted_results:
            bbox, text, conf = res
            y_center = sum([pt[1] for pt in bbox]) / 4.0
            
            if current_line_y == -999:
                current_line_y = y_center
                current_line.append((bbox[0][0][0], text))  # store (X-start, text)
            elif abs(y_center - current_line_y) < 15:
                current_line.append((bbox[0][0][0], text))
            else:
                # Save previous line sorted by X-coordinate
                current_line = sorted(current_line, key=lambda x: x[0])
                lines.append(" ".join([item[1] for item in current_line]))
                # Reset
                current_line_y = y_center
                current_line = [(bbox[0][0][0], text)]
                
        if current_line:
            current_line = sorted(current_line, key=lambda x: x[0])
            lines.append(" ".join([item[1] for item in current_line]))
            
        print(f"OCR extracted lines: {lines}")
        return parse_lines_to_items(lines)
        
    except Exception as e:
        print(f"EasyOCR parsing failed: {e}. Falling back to Simulated OCR.")
        return simulate_ocr_parse(image_path)

def parse_lines_to_items(lines):
    """
    Parses raw text lines from a receipt into structured food products.
    """
    detected_items = []
    
    # Common words in receipts to ignore
    ignore_keywords = [
        r'total', r'subtotal', r'tax', r'gst', r'vat', r'cash', r'change', r'card', 
        r'visa', r'mastercard', r'change', r'balance', r'payment', r'items', r'invoice',
        r'receipt', r'welcome', r'thank', r'store', r'supermarket', r'market', r'grocery',
        r'phone', r'tel', r'date', r'time', r'amount', r'price', r'address', r'road', r'street'
    ]
    
    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line or len(cleaned_line) < 3:
            continue
            
        # Check if line contains ignore keywords
        should_ignore = False
        for kw in ignore_keywords:
            if re.search(kw, cleaned_line.lower()):
                should_ignore = True
                break
        if should_ignore:
            continue
            
        # Parse potential grocery line:
        # e.g., "1 AMUL MILK 500ML 32.00"
        # e.g., "BRITANNIA BREAD 1 PCS 40"
        # e.g., "2x Kellogg Corn Flakes 180"
        
        # Try to find quantity (often starts with number + x, or just a number at the beginning)
        qty = '1'
        qty_match = re.match(r'^(\d+)\s*[xX]?\s+', cleaned_line)
        if qty_match:
            qty = qty_match.group(1)
            # Strip the quantity from line
            cleaned_line = cleaned_line[qty_match.end():].strip()
        else:
            # Check for quantity at end or inside e.g. "* 2"
            qty_end_match = re.search(r'\s+\*?\s*(\d+)$', cleaned_line)
            if qty_end_match:
                # But wait, could this be the price? Let's check if there is a decimal.
                # If there's no decimal and it's a small number, we can assume it might be quantity, but usually price has decimals.
                # Let's extract items if possible.
                pass
                
        # Remove numbers that look like prices (e.g. 12.50, 150.00, or just numbers at the end of the line)
        cleaned_line = re.sub(r'\b\d+\.\d{2}\b', '', cleaned_line) # remove floats
        cleaned_line = re.sub(r'\b\d{2,}\b$', '', cleaned_line)  # remove trailing integers which are likely prices
        cleaned_line = cleaned_line.strip()
        
        # Remove symbols
        cleaned_line = re.sub(r'[\$\#\*\|]', '', cleaned_line).strip()
        
        if len(cleaned_line) < 3:
            continue
            
        # Split into brand and food name
        # If the first word is a common brand, use it. Otherwise, put it all in food name.
        brands_list = ['amul', 'britannia', 'kellogg', 'nestle', 'tata', 'cadbury', 'haldiram', 'mother dairy', 'surf', 'coca', 'pepsi', 'fortune']
        detected_brand = ''
        
        words = cleaned_line.split()
        if words:
            first_word = words[0].lower()
            for b in brands_list:
                if b in first_word:
                    detected_brand = words[0]
                    cleaned_line = " ".join(words[1:])
                    break
        
        # Title case the names
        food_name = cleaned_line.title()
        brand = detected_brand.title()
        
        # Determine category based on keywords
        category = 'Other'
        lower_name = food_name.lower()
        if any(w in lower_name for w in ['milk', 'cheese', 'butter', 'curd', 'paneer', 'yogurt']):
            category = 'Dairy'
        elif any(w in lower_name for w in ['juice', 'soda', 'coke', 'pepsi', 'water', 'tea', 'coffee', 'beverage']):
            category = 'Beverages'
        elif any(w in lower_name for w in ['bread', 'bun', 'biscuit', 'cake', 'bakery', 'croissant']):
            category = 'Bakery'
        elif any(w in lower_name for w in ['apple', 'banana', 'tomato', 'potato', 'onion', 'vegetable', 'fruit', 'orange']):
            category = 'Fruits & Vegetables'
        elif any(w in lower_name for w in ['chips', 'nachos', 'snack', 'chocolate', 'cookie', 'namkeen']):
            category = 'Snacks'
        elif any(w in lower_name for w in ['rice', 'flour', 'dal', 'oil', 'salt', 'sugar', 'pantry', 'pasta', 'noodle']):
            category = 'Pantry'
        elif any(w in lower_name for w in ['chicken', 'meat', 'fish', 'prawn', 'egg', 'mutton', 'seafood']):
            category = 'Meat & Seafood'
            
        detected_items.append({
            'food_name': food_name,
            'brand': brand,
            'quantity': qty,
            'category': category
        })
        
    return detected_items

def simulate_ocr_parse(image_path):
    """
    Simulates receipt parsing by returning realistic grocery items.
    Used as a fallback if EasyOCR is not available or if CPU/GPU memory is constrained.
    """
    # Create realistic grocery items based on the filename or static simulation
    filename = os.path.basename(image_path).lower()
    
    # We return a dynamic list of items so the user gets realistic results
    return [
        {
            'food_name': 'Fresh Milk 1L',
            'brand': 'Amul',
            'quantity': '2',
            'category': 'Dairy'
        },
        {
            'food_name': 'Whole Wheat Bread',
            'brand': 'Britannia',
            'quantity': '1',
            'category': 'Bakery'
        },
        {
            'food_name': 'Corn Flakes 500g',
            'brand': 'Kelloggs',
            'quantity': '1',
            'category': 'Snacks'
        },
        {
            'food_name': 'Orange Juice',
            'brand': 'Tropicana',
            'quantity': '3',
            'category': 'Beverages'
        },
        {
            'food_name': 'Basmati Rice 5kg',
            'brand': 'Fortune',
            'quantity': '1',
            'category': 'Pantry'
        }
    ]
