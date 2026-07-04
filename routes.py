import os
import re
import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import requests

from models import db, User, Food, Notification
from utils import lookup_barcode, parse_receipt, send_twilio_sms
from config import Config

main_bp = Blueprint('main', __name__)

# Helper to check allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_phone_number(phone):
    """
    Validates phone number format.
    Requires a country code prefix (e.g., +91 for India, +1 for US)
    followed by exactly 10 subscriber digits.
    """
    # Remove spacing and formatting dashes
    phone = phone.replace(" ", "").replace("-", "")
    
    # Must start with '+' followed by 11 to 14 digits total
    if not re.match(r'^\+[1-9]\d{10,14}$', phone):
        return False
        
    # Enforce exactly 10 subscriber digits for India (+91)
    if phone.startswith('+91'):
        return len(phone) == 13  # + (1) + 91 (2) + 10 digits = 13 characters
        
    # Enforce exactly 10 subscriber digits for US/Canada (+1)
    if phone.startswith('+1'):
        return len(phone) == 12  # + (1) + 1 (1) + 10 digits = 12 characters
        
    return True

# ----------------------------------------------------
# PWA Static Assets Helper Routes
# ----------------------------------------------------
@main_bp.route('/manifest.json')
def manifest():
    return current_app.send_static_file('manifest.json')

# ----------------------------------------------------
# Web App Landing Page
# ----------------------------------------------------
@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('landing.html')

# ----------------------------------------------------
# Authentication routes
# ----------------------------------------------------
@main_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone').strip()
        password = request.form.get('password')
        
        # Phone Validation
        if not validate_phone_number(phone):
            flash('Invalid phone number. Must use E.164 format starting with + and country code (e.g. +919876543210).', 'error')
            return redirect(url_for('main.register'))
            
        # Check if email already registered
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered.', 'error')
            return redirect(url_for('main.register'))
            
        hashed_password = generate_password_hash(password, method='scrypt')
        
        new_user = User(
            name=name,
            email=email,
            phone=phone,
            password=hashed_password
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Trigger an initial welcome notification
        welcome_notif = Notification(
            user_id=new_user.id,
            title="👋 Welcome to Notify-Me!",
            message="Thank you for registering. Start logging packaged foods and configure Twilio environment variables to receive SMS alerts.",
            notification_type='system',
            status='sent'
        )
        db.session.add(welcome_notif)
        db.session.commit()
        
        flash('Account created successfully! Please login.', 'success')
        return redirect(url_for('main.login'))
        
    return render_template('register.html')

@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password, password):
            flash('Invalid email or password. Please try again.', 'error')
            return redirect(url_for('main.login'))
            
        login_user(user, remember=remember)
        flash(f'Welcome back, {user.name}!', 'success')
        return redirect(url_for('main.dashboard'))
        
    return render_template('login.html')

@main_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('main.index'))

# ----------------------------------------------------
# Dashboard & Charts View
# ----------------------------------------------------
@main_bp.route('/dashboard')
@login_required
def dashboard():
    today = datetime.date.today()
    
    # Base stats query
    foods_query = Food.query.filter_by(user_id=current_user.id)
    active_foods = foods_query.filter_by(status='active').all()
    
    # Statistics calculations
    total_active = len(active_foods)
    expired_count = sum(1 for f in active_foods if f.remaining_days < 0)
    today_count = sum(1 for f in active_foods if f.remaining_days == 0)
    tomorrow_count = sum(1 for f in active_foods if f.remaining_days == 1)
    
    # Expiring this week: remaining days between 0 and 7 inclusive
    this_week_count = sum(1 for f in active_foods if 0 <= f.remaining_days <= 7)
    # Safe count: remaining days > 7
    safe_count = sum(1 for f in active_foods if f.remaining_days > 7)
    
    consumed_count = foods_query.filter_by(status='consumed').count()
    wasted_count = foods_query.filter_by(status='wasted').count()
    
    # Unread notifications (System notifications)
    unread_notifs = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    
    # Recent SMS History (latest 5 alerts)
    recent_sms = Notification.query.filter_by(
        user_id=current_user.id, 
        notification_type='sms'
    ).order_by(Notification.sent_at.desc()).limit(5).all()
    
    # Urgent alerts (expires in <= 3 days)
    urgent_foods = [f for f in active_foods if f.remaining_days <= 3]
    # Sort urgent items so expired/today appear first
    urgent_foods = sorted(urgent_foods, key=lambda x: x.remaining_days)[:6]
    
    # Charts calculations:
    # 1. Foods by Category
    categories_dict = {}
    for f in active_foods:
        categories_dict[f.category] = categories_dict.get(f.category, 0) + 1
        
    # 2. Expiry status counts
    status_dict = {
        'Active': total_active,
        'Consumed': consumed_count,
        'Expired/Wasted': wasted_count + expired_count
    }
    
    # 3. Expiry Timeline (grouped by upcoming days)
    timeline_dict = {
        'Expired': expired_count,
        'Today': today_count,
        'Tomorrow': tomorrow_count,
        '2-3 Days': sum(1 for f in active_foods if 2 <= f.remaining_days <= 3),
        '4-7 Days': sum(1 for f in active_foods if 4 <= f.remaining_days <= 7),
        '8+ Days': sum(1 for f in active_foods if f.remaining_days > 7)
    }
    
    stats = {
        'total': total_active + consumed_count + wasted_count,
        'today': today_count,
        'tomorrow': tomorrow_count,
        'this_week': this_week_count,
        'expired': expired_count,
        'safe': safe_count,
        'consumed': consumed_count,
        'unread_notifications': unread_notifs
    }
    
    charts = {
        'categories': categories_dict,
        'status': status_dict,
        'timeline': timeline_dict
    }

    return render_template(
        'dashboard.html',
        stats=stats,
        urgent_foods=urgent_foods,
        charts=charts,
        recent_sms=recent_sms
    )

# ----------------------------------------------------
# Food Inventory CRUD Routes
# ----------------------------------------------------
@main_bp.route('/foods')
@login_required
def foods():
    search = request.args.get('search', '')
    status = request.args.get('status', 'all')
    category = request.args.get('category', 'all')
    sort = request.args.get('sort', 'expiry_asc')
    
    query = Food.query.filter_by(user_id=current_user.id)
    
    # Text Search (name, brand, store)
    if search:
        query = query.filter(
            (Food.food_name.like(f'%{search}%')) | 
            (Food.brand.like(f'%{search}%')) |
            (Food.store.like(f'%{search}%'))
        )
        
    # Expiry Status Filter
    today = datetime.date.today()
    if status == 'consumed':
        query = query.filter_by(status='consumed')
    elif status == 'expired':
        query = query.filter_by(status='active').filter(Food.expiry_date < today)
    elif status == 'soon':
        # Expiring within 7 days
        query = query.filter_by(status='active').filter(Food.expiry_date >= today, Food.expiry_date <= today + datetime.timedelta(days=7))
    elif status == 'safe':
        query = query.filter_by(status='active').filter(Food.expiry_date > today + datetime.timedelta(days=7))
    else:
        # 'all' active foods + expired
        query = query.filter(Food.status.in_(['active', 'wasted']))
        
    # Category Filter
    if category != 'all' and category:
        query = query.filter_by(category=category)
        
    # Sorting options
    if sort == 'expiry_desc':
        query = query.order_by(Food.expiry_date.desc())
    elif sort == 'newest':
        query = query.order_by(Food.created_at.desc())
    elif sort == 'oldest':
        query = query.order_by(Food.created_at.asc())
    elif sort == 'name_asc':
        query = query.order_by(Food.food_name.asc())
    else: # default: expiry_asc
        query = query.order_by(Food.expiry_date.asc())
        
    food_items = query.all()
    
    # Get all categories logged by user to dynamically populate filter dropdown
    user_categories = db.session.query(Food.category).filter_by(user_id=current_user.id).distinct().all()
    categories_list = [c[0] for c in user_categories]
    
    return render_template('foods.html', foods=food_items, categories=categories_list)

@main_bp.route('/foods/add', methods=['GET', 'POST'])
@login_required
def add_food():
    if request.method == 'POST':
        food_name = request.form.get('food_name')
        brand = request.form.get('brand')
        category = request.form.get('category')
        quantity = request.form.get('quantity')
        manufacture_date_str = request.form.get('manufacture_date')
        expiry_date_str = request.form.get('expiry_date')
        store = request.form.get('store')
        barcode = request.form.get('barcode')
        notes = request.form.get('notes')
        
        # Parsing optional dates
        mfg_date = None
        if manufacture_date_str:
            mfg_date = datetime.datetime.strptime(manufacture_date_str, '%Y-%m-%d').date()
            
        expiry_date = datetime.datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        
        # Image Upload
        image_filename = None
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_name = f"{current_user.id}_{int(datetime.datetime.now().timestamp())}_{filename}"
            save_path = os.path.join(Config.UPLOAD_FOLDER, 'foods', unique_name)
            file.save(save_path)
            image_filename = unique_name
        elif request.form.get('image_url_hidden'):
            # Fetch from Open Food Facts image URL and save locally
            try:
                img_url = request.form.get('image_url_hidden')
                response = requests.get(img_url, timeout=5)
                if response.status_code == 200:
                    ext = img_url.split('.')[-1].split('?')[0]
                    if ext not in ALLOWED_EXTENSIONS:
                        ext = 'jpg'
                    unique_name = f"{current_user.id}_{int(datetime.datetime.now().timestamp())}_off.{ext}"
                    save_path = os.path.join(Config.UPLOAD_FOLDER, 'foods', unique_name)
                    with open(save_path, 'wb') as f:
                        f.write(response.content)
                    image_filename = unique_name
            except Exception as e:
                print(f"Failed to download image from Open Food Facts: {e}")
                
        new_food = Food(
            user_id=current_user.id,
            food_name=food_name,
            brand=brand,
            category=category,
            quantity=quantity,
            manufacture_date=mfg_date,
            expiry_date=expiry_date,
            store=store,
            barcode=barcode,
            notes=notes,
            image=image_filename
        )
        
        db.session.add(new_food)
        db.session.commit()
        
        flash(f'"{food_name}" successfully added to your inventory.', 'success')
        
        # ----------------------------------------------------
        # IMMEDIATE NOTIFICATION CHECK (TODAY or TOMORROW Expiries)
        # ----------------------------------------------------
        remaining = new_food.remaining_days
        alert_day = None
        if remaining == 0:
            alert_day = "TODAY"
        elif remaining == 1:
            alert_day = "TOMORROW"
            
        if alert_day:
            title = f"🚨 Expiry Alert: {new_food.food_name}"
            message_text = (
                f"Notify-Me Reminder\n\n"
                f"Your \"{new_food.food_name}\" expires {alert_day}.\n\n"
                f"Please consume it before it expires."
            )
            
            print(f"[Immediate Alert] Sending SMS to {current_user.phone} for {new_food.food_name} ({alert_day})...")
            
            # Send Twilio SMS immediately
            sms_success = send_twilio_sms(current_user.phone, message_text)
            sms_status = 'sent' if sms_success else 'failed'
            
            # Record Notification History in DB
            new_notif = Notification(
                user_id=current_user.id,
                food_id=new_food.id,
                title=title,
                message=message_text,
                notification_type='sms',
                phone_number=current_user.phone,
                status=sms_status,
                sent_at=datetime.datetime.utcnow()
            )
            db.session.add(new_notif)
            db.session.commit()
            
            if sms_success:
                flash(f"Immediate SMS alert successfully dispatched to {current_user.phone}!", "info")
            else:
                flash("Failed to send immediate SMS alert. Verify Twilio environment configurations.", "warning")
                
        return redirect(url_for('main.foods'))
        
    return render_template('add_food.html', is_edit=False)

@main_bp.route('/foods/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_food(id):
    food = Food.query.get_or_404(id)
    if food.user_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.foods'))
        
    if request.method == 'POST':
        food.food_name = request.form.get('food_name')
        food.brand = request.form.get('brand')
        food.category = request.form.get('category')
        food.quantity = request.form.get('quantity')
        food.store = request.form.get('store')
        food.barcode = request.form.get('barcode')
        food.notes = request.form.get('notes')
        food.status = request.form.get('status', 'active')
        
        mfg_date_str = request.form.get('manufacture_date')
        if mfg_date_str:
            food.manufacture_date = datetime.datetime.strptime(mfg_date_str, '%Y-%m-%d').date()
        else:
            food.manufacture_date = None
            
        expiry_date_str = request.form.get('expiry_date')
        food.expiry_date = datetime.datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        
        # New Image Upload
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_name = f"{current_user.id}_{int(datetime.datetime.now().timestamp())}_{filename}"
            save_path = os.path.join(Config.UPLOAD_FOLDER, 'foods', unique_name)
            file.save(save_path)
            # Delete old image if it exists
            if food.image:
                try:
                    old_path = os.path.join(Config.UPLOAD_FOLDER, 'foods', food.image)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception as e:
                    print(e)
            food.image = unique_name
            
        db.session.commit()
        flash(f'"{food.food_name}" details updated successfully.', 'success')
        return redirect(url_for('main.foods'))
        
    return render_template('add_food.html', food=food, is_edit=True)

@main_bp.route('/foods/delete/<int:id>', methods=['POST'])
@login_required
def delete_food(id):
    food = Food.query.get_or_404(id)
    if food.user_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.foods'))
        
    food_name = food.food_name
    # Delete associated file
    if food.image:
        try:
            file_path = os.path.join(Config.UPLOAD_FOLDER, 'foods', food.image)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(e)
            
    db.session.delete(food)
    db.session.commit()
    flash(f'"{food_name}" has been deleted.', 'info')
    return redirect(url_for('main.foods'))

@main_bp.route('/foods/consume/<int:id>', methods=['POST'])
@login_required
def consume_food(id):
    food = Food.query.get_or_404(id)
    if food.user_id != current_user.id:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('main.foods'))
        
    food.status = 'consumed'
    db.session.commit()
    
    # Log notification of consumption
    notif = Notification(
        user_id=current_user.id,
        food_id=food.id,
        title="🥳 Food Consumed!",
        message=f'Great job! You consumed your "{food.food_name}" and prevented household food waste.',
        notification_type='system',
        status='sent'
    )
    db.session.add(notif)
    db.session.commit()
    
    flash(f'Woohoo! "{food.food_name}" marked as consumed. Thank you for reducing waste!', 'success')
    return redirect(request.referrer or url_for('main.dashboard'))

# ----------------------------------------------------
# Notification Logs History
# ----------------------------------------------------
@main_bp.route('/notifications')
@login_required
def notifications():
    user_notifs = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.sent_at.desc()).all()
    return render_template('notifications.html', notifications=user_notifs)

@main_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def read_all_notifications():
    unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).all()
    for notif in unread:
        notif.is_read = True
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('main.notifications'))

# ----------------------------------------------------
# Profile Customizations
# ----------------------------------------------------
@main_bp.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

@main_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    name = request.form.get('name')
    phone = request.form.get('phone').strip()
    
    # Phone Validation
    if not validate_phone_number(phone):
        flash('Invalid phone number. Must use E.164 format starting with + and country code (e.g. +919876543210).', 'error')
        return redirect(url_for('main.profile'))
        
    current_user.name = name
    current_user.phone = phone
    
    # Profile Pic upload
    file = request.files.get('profile_pic')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_name = f"{current_user.id}_{int(datetime.datetime.now().timestamp())}_{filename}"
        save_path = os.path.join(Config.UPLOAD_FOLDER, 'profile_pics', unique_name)
        file.save(save_path)
        
        # Delete old profile pic (unless default)
        if current_user.profile_image and current_user.profile_image != 'default.jpg':
            try:
                old_path = os.path.join(Config.UPLOAD_FOLDER, 'profile_pics', current_user.profile_image)
                if os.path.exists(old_path):
                    os.remove(old_path)
            except Exception as e:
                print(e)
                
        current_user.profile_image = unique_name
        
    db.session.commit()
    flash('Profile details updated successfully.', 'success')
    return redirect(url_for('main.profile'))

@main_bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    current_pass = request.form.get('current_password')
    new_pass = request.form.get('new_password')
    
    if not check_password_hash(current_user.password, current_pass):
        flash('Incorrect current password.', 'error')
        return redirect(url_for('main.profile'))
        
    current_user.password = generate_password_hash(new_pass, method='scrypt')
    db.session.commit()
    flash('Password changed successfully.', 'success')
    return redirect(url_for('main.profile'))

# ----------------------------------------------------
# API ENDPOINTS
# ----------------------------------------------------
@main_bp.route('/api/barcode/<barcode>')
def api_barcode_lookup(barcode):
    """API endpoint to query Open Food Facts barcode data."""
    product_data = lookup_barcode(barcode)
    if product_data:
        return jsonify({'success': True, 'product': product_data})
    return jsonify({'success': False, 'message': 'Product not found'}), 404

@main_bp.route('/api/ocr', methods=['POST'])
@login_required
def api_ocr_scan():
    """API endpoint running EasyOCR on grocery bill uploads."""
    if 'receipt' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        
    file = request.files['receipt']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        temp_path = os.path.join(Config.UPLOAD_FOLDER, f"temp_ocr_{filename}")
        file.save(temp_path)
        
        try:
            detected_items = parse_receipt(temp_path)
            # Remove temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({'success': True, 'items': detected_items})
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({'success': False, 'error': str(e)}), 500
            
    return jsonify({'success': False, 'error': 'Invalid file type'}), 400
