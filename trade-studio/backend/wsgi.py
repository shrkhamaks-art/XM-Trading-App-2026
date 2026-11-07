import os
from server import create_app

app = create_app(os.getenv("DB_PATH", "/data/trade-studio.sqlite"), os.environ["OTP_SECRET"].encode())
