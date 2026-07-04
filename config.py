import os
import json

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'notify_me_packaged_food_secret_key_12345')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "database.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload configurations
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload size
    
    # Push Notifications (VAPID) settings
    VAPID_KEYS_FILE = os.path.join(BASE_DIR, 'vapid_keys.json')
    VAPID_CLAIM_EMAIL = os.environ.get('VAPID_CLAIM_EMAIL', 'mailto:admin@notifyme.local')
    
    # Twilio Configuration (Demo Free Trial Mode)
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')
    
    @classmethod
    def init_app(cls, app):
        # Create upload folder if not exists
        os.makedirs(cls.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(cls.UPLOAD_FOLDER, 'profile_pics'), exist_ok=True)
        os.makedirs(os.path.join(cls.UPLOAD_FOLDER, 'foods'), exist_ok=True)
        
        # Ensure VAPID keys exist
        cls.load_or_generate_vapid_keys()

    @classmethod
    def load_or_generate_vapid_keys(cls):
        """Loads VAPID keys from file or generates them if not present."""
        if os.path.exists(cls.VAPID_KEYS_FILE):
            try:
                with open(cls.VAPID_KEYS_FILE, 'r') as f:
                    keys = json.load(f)
                    cls.VAPID_PUBLIC_KEY = keys.get('public_key')
                    cls.VAPID_PRIVATE_KEY = keys.get('private_key')
                    return
            except Exception as e:
                print(f"Error loading VAPID keys: {e}. Re-generating...")
        
        # Generate new VAPID keys dynamically using pywebpush Vapid class
        try:
            from pywebpush import Vapid
            import base64
            from cryptography.hazmat.primitives import serialization
            
            v = Vapid()
            v.generate_keys()
            
            # Private key in base64url format string (32 raw bytes)
            priv_val = v._private_key.private_numbers().private_value
            priv_bytes = priv_val.to_bytes(32, 'big')
            cls.VAPID_PRIVATE_KEY = base64.urlsafe_b64encode(priv_bytes).decode('utf-8')
            
            # Public key in uncompressed Base64url format string
            pub_bytes = v._public_key.public_bytes(
                serialization.Encoding.X962,
                serialization.PublicFormat.UncompressedPoint
            )
            cls.VAPID_PUBLIC_KEY = base64.urlsafe_b64encode(pub_bytes).decode('utf-8')
            
            with open(cls.VAPID_KEYS_FILE, 'w') as f:
                json.dump({
                    'public_key': cls.VAPID_PUBLIC_KEY,
                    'private_key': cls.VAPID_PRIVATE_KEY
                }, f)
            print("Successfully generated and saved new VAPID keypair.")
        except Exception as e:
            print(f"Could not generate VAPID keys dynamically ({e}). Using temporary static keypair.")
            # Standard valid uncompressed public key fallback if generation fails
            cls.VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', 'BDq8yZ3V6tYkI_R-o0H6i5z1wG1Z065t4v7yU42cR9nZ4N-R8y4z2wG1Z065t4v7yU42cR9nZ4N-R8y4z2w')
            cls.VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
