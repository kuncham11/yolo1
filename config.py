import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "crowdguard_ai_secret_fallback_key_2026")
    DEBUG = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", 5000))
    DEMO_MODE = os.getenv("DEMO_MODE", "True").lower() in ("true", "1", "yes")

    # Database
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "crowdguard_ai")

    # Models
    PERSON_MODEL_PATH = os.getenv("PERSON_MODEL_PATH", "models/person/yolo11n.pt")
    WEAPON_MODEL_PATH = os.getenv("WEAPON_MODEL_PATH", "models/weapon/weapon_detector.pt")
    VIOLENCE_MODEL_PATH = os.getenv("VIOLENCE_MODEL_PATH", "models/violence/action_model.pt")
    FACE_MODEL_PATH = os.getenv("FACE_MODEL_PATH", "models/face/best.pt")

    # Risk Scoring Weights (0-100 scale)
    WEIGHT_WEAPON = 50
    WEIGHT_VIOLENCE = 40
    WEIGHT_RESTRICTED_ENTRY = 25
    WEIGHT_ABNORMAL_MOVEMENT = 20
    WEIGHT_HIGH_DENSITY = 15
    WEIGHT_RUNNING = 10
    WEIGHT_LOITERING = 5

    # Density Thresholds
    DENSITY_NORMAL_MAX = int(os.getenv("CROWD_DENSITY_NORMAL", 10))
    DENSITY_MODERATE_MAX = int(os.getenv("CROWD_DENSITY_MODERATE", 20))

    # Alert Cooldown (seconds)
    ALERT_COOLDOWN_SEC = 30
