import os
from flask import Flask
from flask_login import LoginManager

from config import Config
from models import db, User
from routes import main_bp
from scheduler import init_scheduler

def create_app():
    """Application factory for Flask configuration."""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize Configuration hooks
    Config.init_app(app)
    
    # Initialize SQLAlchemy database
    db.init_app(app)
    
    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = 'main.login'
    login_manager.login_message_category = 'info'
    login_manager.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
        
    # Register blueprints
    app.register_blueprint(main_bp)
    
    # Database table creations and migrations
    with app.app_context():
        try:
            from sqlalchemy import text
            # Inspect table columns in SQLite
            res = db.session.execute(text("PRAGMA table_info(notifications)")).fetchall()
            cols = [col[1] for col in res]
            if len(cols) > 0 and 'notification_type' not in cols:
                db.session.execute(text("DROP TABLE notifications"))
                db.session.commit()
                print("Successfully dropped old notifications table for restructuring.")
        except Exception as e:
            print(f"Error during notifications table drop check: {e}")
            db.session.rollback()

        # Recreate tables (creates new notifications layout if dropped)
        db.create_all()
        
    # Start APScheduler inside App Context (prevent double start in debug reload)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        init_scheduler(app)
        
    return app

if __name__ == '__main__':
    app = create_app()
    # Run server on all interfaces (necessary for testing PWA on phone via local Wi-Fi IP)
    app.run(host='0.0.0.0', port=5000, debug=True)
