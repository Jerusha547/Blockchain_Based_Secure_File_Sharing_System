# """
# Secure File Sharing - Main Flask Application (Token-based auth)
# """

# from flask import Flask
# from flask_cors import CORS
# from flask_mail import Mail
# from database.db import init_db
# from routes.auth_routes import auth_bp
# from routes.file_routes import file_bp

# app = Flask(__name__)
# app.secret_key = "super-secret-key-change-in-production"

# # ── Email Configuration ───────────────────────────────────────
# app.config["MAIL_SERVER"]         = "smtp.gmail.com"
# app.config["MAIL_PORT"]           = 587
# app.config["MAIL_USE_TLS"]        = True
# app.config["MAIL_USERNAME"]       = "marthajerushamarumudi7@gmail.com"
# app.config["MAIL_PASSWORD"]       = "lgwk rtnc jyzu dnym"
# app.config["MAIL_DEFAULT_SENDER"] = "marthajerushamarumudi7@gmail.com"
# # ─────────────────────────────────────────────────────────────

# CORS(app)

# # Create Mail instance here and pass it to auth_routes
# mail = Mail(app)

# # Give auth_routes access to the mail instance
# from routes import auth_routes
# auth_routes.mail = mail

# app.register_blueprint(auth_bp, url_prefix="/auth")
# app.register_blueprint(file_bp, url_prefix="/files")

# with app.app_context():
#     init_db()

# @app.route("/")
# def index():
#     return {"message": "Secure File Sharing API is running ✅"}

# if __name__ == "__main__":
#     app.run(debug=True, port=5000)



import os
from flask import Flask
from flask_cors import CORS
from flask_mail import Mail
from database.db import init_db
from routes.auth_routes import auth_bp
from routes.file_routes import file_bp

app = Flask(__name__, static_folder="../frontend", static_url_path="/")
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key")

# ── Email Configuration ───────────────────────────────────────
app.config["MAIL_SERVER"]         = "smtp.gmail.com"
app.config["MAIL_PORT"]           = 587
app.config["MAIL_USE_TLS"]        = True
app.config["MAIL_USE_SSL"]        = False
app.config["MAIL_USERNAME"]       = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"]       = os.environ.get("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME")
# ─────────────────────────────────────────────────────────────

CORS(app)

mail = Mail(app)

from routes import auth_routes
auth_routes.mail = mail

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(file_bp, url_prefix="/files")

with app.app_context():
    init_db()

# ── Serve frontend ────────────────────────────────────────────
@app.route("/")
def index():
    return app.send_static_file("login.html")

@app.route("/<path:path>")
def static_files(path):
    return app.send_static_file(path)
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)