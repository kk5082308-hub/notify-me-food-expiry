import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from models import db, Food, Notification, User
from utils import send_twilio_sms

def check_food_expiry_job(app):
    """
    Scans the database for foods expiring TODAY or TOMORROW,
    and automatically dispatches Twilio SMS alerts.
    Prevents duplicates by searching the Notification history.
    """
    with app.app_context():
        try:
            print(f"[{datetime.datetime.now()}] Running hourly food expiry check...")
            today = datetime.date.today()
            
            # Query active foods
            active_foods = Food.query.filter_by(status='active').all()
            
            for food in active_foods:
                remaining = (food.expiry_date - today).days
                
                # We only alert automatically for TODAY (0 days) and TOMORROW (1 day)
                alert_day = None
                if remaining == 0:
                    alert_day = "TODAY"
                elif remaining == 1:
                    alert_day = "TOMORROW"
                    
                if alert_day:
                    # Check if we already sent an SMS notification for this specific food and alert level
                    existing_sms = Notification.query.filter_by(
                        user_id=food.user_id,
                        food_id=food.id,
                        notification_type='sms'
                    ).filter(Notification.message.like(f"%expires {alert_day}%")).first()
                    
                    if not existing_sms:
                        # Retrieve the owner
                        user = User.query.get(food.user_id)
                        if not user or not user.phone:
                            continue
                            
                        # Create the SMS message payload
                        title = f"🚨 Expiry Alert: {food.food_name}"
                        message_text = (
                            f"Notify-Me Reminder\n\n"
                            f"Your \"{food.food_name}\" expires {alert_day}.\n\n"
                            f"Please consume it before it expires."
                        )
                        
                        print(f"[Scheduler] Sending automatic SMS alert to {user.phone} for {food.food_name} ({alert_day})...")
                        
                        # Send SMS via Twilio
                        sms_success = send_twilio_sms(user.phone, message_text)
                        sms_status = 'sent' if sms_success else 'failed'
                        
                        # Record Notification Log in DB
                        new_notif = Notification(
                            user_id=user.id,
                            food_id=food.id,
                            title=title,
                            message=message_text,
                            notification_type='sms',
                            phone_number=user.phone,
                            status=sms_status,
                            sent_at=datetime.datetime.utcnow()
                        )
                        db.session.add(new_notif)
                        db.session.commit()
                        
            print(f"[{datetime.datetime.now()}] Hourly expiry check complete.")
        except Exception as ex:
            print(f"[Scheduler] Error running hourly check: {ex}")
        finally:
            db.session.remove()
            print("[Scheduler] Database session removed and connection released.")

def init_scheduler(app):
    """
    Initializes and starts the background scheduler running every hour.
    """
    scheduler = BackgroundScheduler()
    
    # Run once shortly after startup (5 seconds) to catch up
    scheduler.add_job(
        func=check_food_expiry_job,
        trigger='date',
        run_date=datetime.datetime.now() + datetime.timedelta(seconds=5),
        args=[app]
    )
    
    # Run hourly (interval of 1 hour)
    scheduler.add_job(
        func=check_food_expiry_job,
        trigger='interval',
        hours=1,
        args=[app]
    )
    
    scheduler.start()
    print("Scheduler initialized and started. Running hourly tasks.")
    return scheduler
