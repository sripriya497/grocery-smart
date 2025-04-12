from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

# Blueprint for authentication routes
auth = Blueprint('auth', __name__)
bcrypt = Bcrypt()

# Database connection function
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306))
        )
        print("✅ Successfully connected to MySQL database!")
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

# User Registration (Signup)
@auth.route('/signup', methods=['POST'])
def signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    conn = get_db_connection()

    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (email, password) VALUES (%s, %s);", (email, hashed_password))
        user_id = cur.lastrowid
        conn.commit()
        cur.close()

        return jsonify({"message": "User registered successfully!", "user_id": user_id}), 201

    except mysql.connector.IntegrityError as e:
        conn.rollback()
        print("❌ Integrity Error:", e)
        return jsonify({"error": "User already exists"}), 409

    except Exception as e:
        conn.rollback()
        print("❌ Signup error:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()

# User Login
@auth.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db_connection()

    if not conn:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cur = conn.cursor()
        cur.execute("SELECT id, password FROM users WHERE email = %s;", (email,))
        user = cur.fetchone()
        cur.close()

        if not user:
            return jsonify({"error": "Invalid email or password"}), 401

        user_id, hashed_password = user

        if not bcrypt.check_password_hash(hashed_password, password):
            return jsonify({"error": "Invalid email or password"}), 401

        access_token = create_access_token(identity=email)
        return jsonify({
            "message": "Login successful!",
            "token": access_token,
            "email": email,  # ✅ Add this
            "user_id": user_id  # ✅ Optional: You can also send user_id if you want to use it later
        }), 200

    except Exception as e:
        print("❌ Login error:", e)
        return jsonify({"error": str(e)}), 500

    finally:
        conn.close()

# Protected Route (for testing JWT)
@auth.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user = get_jwt_identity()
    return jsonify({"message": f"Welcome {current_user}!"})
