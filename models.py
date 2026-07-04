from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)  # Phone is now required for SMS alerts
    password = db.Column(db.String(200), nullable=False)
    profile_image = db.Column(db.String(200), nullable=True, default='default.jpg')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    foods = db.relationship('Food', backref='owner', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    subscriptions = db.relationship('PushSubscription', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'

class Food(db.Model):
    __tablename__ = 'foods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    food_name = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(50), nullable=False, default='Other')
    manufacture_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=False)
    quantity = db.Column(db.String(50), nullable=False, default='1')
    store = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)
    barcode = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='active')  # active, consumed, wasted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    notifications = db.relationship('Notification', backref='food', lazy=True, cascade='all, delete-orphan')

    @property
    def remaining_days(self):
        """Returns the number of days remaining until expiration (can be negative for expired items)."""
        delta = self.expiry_date - datetime.utcnow().date()
        return delta.days

    @property
    def status_level(self):
        """Returns status levels: red (expired), orange (<=3 days), yellow (<=7 days), green (>7 days)."""
        days = self.remaining_days
        if self.status != 'active':
            return 'safe' if self.status == 'consumed' else 'expired'
        
        if days < 0:
            return 'red'
        elif days <= 3:
            return 'orange'
        elif days <= 7:
            return 'yellow'
        else:
            return 'green'

    @property
    def status_label(self):
        """Returns the formatted remaining time label."""
        days = self.remaining_days
        if days == 0:
            return "Expires Today"
        elif days == 1:
            return "Tomorrow"
        elif days > 1:
            return f"{days} Days Left"
        elif days == -1:
            return "Expired Yesterday"
        else:
            return f"Expired {abs(days)} Days Ago"

    def __repr__(self):
        return f'<Food {self.food_name}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    food_id = db.Column(db.Integer, db.ForeignKey('foods.id', ondelete='CASCADE'), nullable=True)
    title = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(20), nullable=False, default='system')  # 'system', 'sms'
    phone_number = db.Column(db.String(30), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='sent')  # 'sent', 'failed'
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Notification {self.title}>'

class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False, unique=True)
    p256dh = db.Column(db.String(250), nullable=False)
    auth = db.Column(db.String(250), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PushSubscription {self.endpoint[:30]}...>'
