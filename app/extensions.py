from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_compress import Compress

db = SQLAlchemy()

compress = Compress()

migrate = Migrate()

csrf = CSRFProtect()