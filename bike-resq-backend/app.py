
import os
import uuid
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
    jwt_required,
    get_jwt_identity,
    get_csrf_token
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ---------------- CONFIGURATION ----------------

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///bike_resq.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

secure_cookie = os.getenv("COOKIE_SECURE", "false").lower() == "true"

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_TOKEN_LOCATION"] = ["cookies"]
app.config["JWT_COOKIE_SECURE"] = secure_cookie
app.config["JWT_COOKIE_SAMESITE"] = "None" if secure_cookie else "Lax"
app.config["JWT_COOKIE_CSRF_PROTECT"] = True
app.config["JWT_COOKIE_CSRF_METHODS"] = ["POST", "PUT", "PATCH", "DELETE"]
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 60 * 60 * 8
app.config["JWT_ACCESS_CSRF_HEADER_NAME"] = "X-CSRF-TOKEN"

db = SQLAlchemy(app)
jwt = JWTManager(app)

origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGIN",
        "https://rushikeshjadhav7575.github.io"
    ).split(",")
    if origin.strip()
]

CORS(
    app,
    origins=origins,
    supports_credentials=True,
    allow_headers=["Content-Type", "X-CSRF-TOKEN"],
    methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
)

# ---------------- DATABASE MODELS ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="customer")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_code = db.Column(
        db.String(30), unique=True, nullable=False
    )

    customer_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )

    partner_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )

    service = db.Column(db.String(100), nullable=False)
    bike = db.Column(db.String(100))
    problem = db.Column(db.Text)

    location_text = db.Column(db.String(255))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)

    status = db.Column(db.String(30), default="pending")

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    customer = db.relationship(
        "User", foreign_keys=[customer_id]
    )
    partner = db.relationship(
        "User", foreign_keys=[partner_id]
    )


class PartnerLocation(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    partner_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), unique=True,
        nullable=False
    )

    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)

    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


# ---------------- HELPERS ----------------

def response(message, status=200, **extra):
    return jsonify({"message": message, **extra}), status


def current_user():
    return db.session.get(
        User, int(get_jwt_identity())
    )


def role_required(*roles):
    def decorator(function):
        @wraps(function)
        @jwt_required()
        def wrapper(*args, **kwargs):
            user = current_user()

            if not user or user.role not in roles:
                return response("Access denied.", 403)

            return function(*args, **kwargs)
        return wrapper
    return decorator


def booking_data(booking, show_private=False):
    data = {
        "id": booking.id,
        "booking_code": booking.booking_code,
        "service": booking.service,
        "bike": booking.bike,
        "status": booking.status,
        "created_at": booking.created_at.isoformat()
    }

    if show_private:
        data.update({
            "problem": booking.problem,
            "location_text": booking.location_text,
            "latitude": booking.latitude,
            "longitude": booking.longitude,
            "customer": booking.customer.name,
            "phone": booking.customer.phone
        })

    return data


# ---------------- CUSTOMER REGISTRATION ----------------

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))

    if not all([name, email, phone, password]):
        return response("All fields are required.", 400)

    if len(name) > 100 or len(email) > 150:
        return response("Input is too long.", 400)

    if len(password) < 10:
        return response("Password must contain at least 10 characters.", 400)

    if len(phone) != 10 or not phone.isdigit():
        return response("Enter a valid 10-digit phone number.", 400)

    if User.query.filter_by(email=email).first():
        return response("Email is already registered.", 409)

    user = User(
        name=name,
        email=email,
        phone=phone,
        password=generate_password_hash(password),
        role="customer"
    )

    db.session.add(user)
    db.session.commit()

    return response("Registration successful.", 201)


# ---------------- LOGIN ----------------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(
        user.password, password
    ):
        return response("Invalid email or password.", 401)

    token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role}
    )

    csrf_token = get_csrf_token(token)

    result = jsonify({
        "message": "Login successful.",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        },
        "csrf_token": csrf_token
    })

    set_access_cookies(result, token)
    return result


@app.route("/api/logout", methods=["POST"])
@jwt_required()
def logout():
    result = jsonify({"message": "Logged out successfully."})
    unset_jwt_cookies(result)
    return result


@app.route("/api/me", methods=["GET"])
@jwt_required()
def me():
    user = current_user()

    if not user:
        return response("User not found.", 404)

    return jsonify({
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role
    })


# ---------------- CUSTOMER BOOKINGS ----------------

@app.route("/api/bookings", methods=["POST"])
@role_required("customer")
def create_booking():
    user = current_user()
    data = request.get_json(silent=True) or {}

    service = str(data.get("service", "")).strip()
    bike = str(data.get("bike", "")).strip()
    problem = str(data.get("problem", "")).strip()
    location_text = str(data.get("location_text", "")).strip()

    allowed_services = [
        "Petrol Delivery",
        "Diesel Delivery",
        "Flat Tyre",
        "Battery Assistance",
        "Bike Breakdown"
    ]

    if service not in allowed_services:
        return response("Invalid service.", 400)

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    try:
        if latitude is not None:
            latitude = float(latitude)
        if longitude is not None:
            longitude = float(longitude)
    except (TypeError, ValueError):
        return response("Invalid GPS coordinates.", 400)

    if (latitude is None) != (longitude is None):
        return response("Both GPS coordinates are required.", 400)

    if latitude is not None:
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            return response("GPS coordinates are out of range.", 400)

    booking = Booking(
        booking_code="BR-" + uuid.uuid4().hex[:10].upper(),
        customer_id=user.id,
        service=service,
        bike=bike[:100],
        problem=problem[:1000],
        location_text=location_text[:255],
        latitude=latitude,
        longitude=longitude,
        status="pending"
    )

    db.session.add(booking)
    db.session.commit()

    return response(
        "Booking created successfully.",
        201,
        booking=booking_data(booking, True)
    )


@app.route("/api/bookings/my", methods=["GET"])
@role_required("customer")
def my_bookings():
    user = current_user()

    bookings = Booking.query.filter_by(
        customer_id=user.id
    ).order_by(Booking.id.desc()).all()

    return jsonify([
        booking_data(item, True) for item in bookings
    ])


# ---------------- PARTNER DASHBOARD ----------------

@app.route("/api/partner/bookings", methods=["GET"])
@role_required("partner")
def partner_bookings():
    user = current_user()

    pending = Booking.query.filter_by(
        status="pending",
        partner_id=None
    ).order_by(Booking.id.desc()).all()

    assigned = Booking.query.filter_by(
        partner_id=user.id
    ).order_by(Booking.id.desc()).all()

    result = []

    for booking in pending:
        result.append({
            "id": booking.id,
            "booking_code": booking.booking_code,
            "service": booking.service,
            "status": booking.status,
            "created_at": booking.created_at.isoformat()
        })

    for booking in assigned:
        result.append(
            booking_data(booking, True)
        )

    return jsonify(result)


@app.route("/api/partner/bookings/<int:booking_id>/accept",
           methods=["POST"])
@role_required("partner")
def accept_booking(booking_id):
    user = current_user()

    booking = Booking.query.filter_by(
        id=booking_id,
        status="pending",
        partner_id=None
    ).first()

    if not booking:
        return response("Booking is no longer available.", 409)

    booking.partner_id = user.id
    booking.status = "accepted"

    db.session.commit()

    return response(
        "Booking accepted.",
        booking=booking_data(booking, True)
    )


@app.route("/api/partner/bookings/<int:booking_id>/status",
           methods=["PATCH"])
@role_required("partner")
def update_booking_status(booking_id):
    user = current_user()
    data = request.get_json(silent=True) or {}

    status = data.get("status")

    allowed = {
        "accepted": ["en_route"],
        "en_route": ["completed"]
    }

    booking = Booking.query.filter_by(
        id=booking_id,
        partner_id=user.id
    ).first()

    if not booking:
        return response("Booking not found.", 404)

    if status not in allowed.get(booking.status, []):
        return response("Invalid status transition.", 400)

    booking.status = status
    db.session.commit()

    return response("Booking status updated.")


# ---------------- PARTNER GPS ----------------

@app.route("/api/partner/location", methods=["POST"])
@role_required("partner")
def update_partner_location():
    user = current_user()
    data = request.get_json(silent=True) or {}

    try:
        lat = float(data.get("latitude"))
        lng = float(data.get("longitude"))
    except (TypeError, ValueError):
        return response("Valid coordinates are required.", 400)

    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return response("Coordinates out of range.", 400)

    active = Booking.query.filter(
        Booking.partner_id == user.id,
        Booking.status.in_(["accepted", "en_route"])
    ).first()

    if not active:
        return response("No active assigned booking.", 403)

    location = PartnerLocation.query.filter_by(
        partner_id=user.id
    ).first()

    if location is None:
        location = PartnerLocation(
            partner_id=user.id,
            latitude=lat,
            longitude=lng
        )
        db.session.add(location)
    else:
        location.latitude = lat
        location.longitude = lng
        location.updated_at = datetime.now(timezone.utc)

    db.session.commit()

    return response("Location updated.")


# ---------------- CUSTOMER TRACKING ----------------

@app.route("/api/bookings/<int:booking_id>/tracking",
           methods=["GET"])
@role_required("customer")
def customer_tracking(booking_id):
    user = current_user()

    booking = Booking.query.filter_by(
        id=booking_id,
        customer_id=user.id
    ).first()

    if not booking:
        return response("Booking not found.", 404)

    result = {
        "booking_code": booking.booking_code,
        "status": booking.status,
        "partner_location": None
    }

    if booking.partner_id:
        location = PartnerLocation.query.filter_by(
            partner_id=booking.partner_id
        ).first()

        if location:
            result["partner_location"] = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "updated_at": location.updated_at.isoformat()
            }

    return jsonify(result)


# ---------------- ADMIN ----------------

@app.route("/api/admin/partners", methods=["POST"])
@role_required("admin")
def create_partner():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    password = str(data.get("password", ""))

    if not all([name, email, phone, password]):
        return response("All fields are required.", 400)

    if len(password) < 10:
        return response("Password must be at least 10 characters.", 400)

    if len(phone) != 10 or not phone.isdigit():
        return response("Invalid phone number.", 400)

    if User.query.filter_by(email=email).first():
        return response("Email already exists.", 409)

    partner = User(
        name=name,
        email=email,
        phone=phone,
        password=generate_password_hash(password),
        role="partner"
    )

    db.session.add(partner)
    db.session.commit()

    return response("Partner account created.", 201)


@app.route("/api/admin/bookings", methods=["GET"])
@role_required("admin")
def admin_bookings():
    bookings = Booking.query.order_by(
        Booking.id.desc()
    ).all()

    return jsonify([
        {
            **booking_data(item, True),
            "partner": item.partner.name if item.partner else None
        }
        for item in bookings
    ])


# ---------------- HEALTH CHECK ----------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "service": "BIKE RESQ API",
        "time": datetime.now(timezone.utc).isoformat()
    })


# ---------------- DATABASE INITIALIZATION ----------------

def initialize_database():
    with app.app_context():
        db.create_all()

        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")

        if admin_email and admin_password:
            admin = User.query.filter_by(
                email=admin_email.lower()
            ).first()

            if not admin:
                admin = User(
                    name=os.getenv("ADMIN_NAME", "BIKE RESQ Admin"),
                    email=admin_email.lower(),
                    phone="0000000000",
                    password=generate_password_hash(admin_password),
                    role="admin"
                )
                db.session.add(admin)
                db.session.commit()


if __name__ == "__main__":
    if not app.config["SECRET_KEY"] or not app.config["JWT_SECRET_KEY"]:
        raise RuntimeError("Set SECRET_KEY and JWT_SECRET_KEY in .env")

    initialize_database()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
