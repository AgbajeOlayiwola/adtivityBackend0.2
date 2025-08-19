# init_db.py
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
from app.database import engine
from app.models import Base

Base.metadata.create_all(bind=engine)
