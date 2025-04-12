from flask import Flask, request, jsonify
import os
from flask_cors import CORS # type: ignore
import mysql.connector
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
from datetime import datetime, timezone
from supabase import create_client
from werkzeug.utils import secure_filename
import time
import logging
import traceback
import requests
from math import radians, sin, cos, sqrt, atan2
from auth import auth

logging.basicConfig(level=logging.DEBUG)

load_dotenv()

app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv("JWT_SECRET_KEY", "your_jwt_secret_key")
jwt = JWTManager(app)

CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True, allow_headers=["Content-Type"])

@app.after_request
def add_cors_headers(response):
    """ Ensure CORS headers are applied to every response """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

def get_db_connection():

    try:
        conn = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306))
        )
        print("Successfully connected to the database!")
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

app.register_blueprint(auth)


#  Get list of all stores
@app.route('/stores', methods=['GET'])
def get_stores():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "Database connection failed"}), 500
        
    cur = conn.cursor()
    cur.execute("SELECT * FROM stores ORDER BY id;")
    stores = [{"id": row[0], "name": row[1], "zip_code": row[2]} for row in cur.fetchall()]
    cur.close()
    conn.close()
    
    return jsonify(stores)

# Get store details, products, and flyers
@app.route('/store/<int:store_id>', methods=['GET'])
def get_store_data(store_id):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Fetch store details
        cur.execute("SELECT name FROM stores WHERE id = %s", (store_id,))
        store = cur.fetchone()

        if not store:
            return jsonify({"error": "Store not found"}), 404

        store_name = store[0]

        # Fetch products from this store (including quantity)
        cur.execute("SELECT name, price, quantity FROM products WHERE store_id = %s", (store_id,))
        products = [{"name": row[0], "price": row[1], "quantity": row[2]} for row in cur.fetchall()]

        # Fetch flyers for this store
        cur.execute("SELECT image_url FROM flyers WHERE store_id = %s", (store_id,))
        flyers = [{"image_url": row[0].replace("//", "/")} for row in cur.fetchall()]  # List of flyer image URLs

        return jsonify({
            "name": store_name,
            "products": products,
            "flyers": flyers  # Added flyers
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()
   
#Upload product data (Crowdsourced)
@app.route('/upload_product', methods=['POST'])
def upload_product():
    data = request.json
    name, store_id, price, quantity = data.get("name"), data.get("store_id"), data.get("price"), data.get("quantity")

    if not all([name, store_id, price, quantity]):
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Check if the store exists
        cur.execute("SELECT id FROM stores WHERE id = %s;", (store_id,))
        if cur.fetchone() is None:
            return jsonify({"error": "Store ID does not exist"}), 400

        # Check if the product with exact same name and quantity exists for this store
        cur.execute("""
            SELECT id FROM products 
            WHERE name = %s AND store_id = %s AND quantity = %s;
        """, (name, store_id, quantity))
        existing_product = cur.fetchone()

        if existing_product:
            # Update existing product only if name and quantity match exactly
            cur.execute("""
                UPDATE products 
                SET price = %s 
                WHERE id = %s
                RETURNING id;
            """, (price, existing_product[0]))
            product_id = existing_product[0]
            message = "Product price updated successfully"
        else:
            # Insert new product if no exact match found
            cur.execute("""
                INSERT INTO products (name, store_id, price, quantity) 
                VALUES (%s, %s, %s, %s) 
                RETURNING id;
            """, (name, store_id, price, quantity))
            product_id = cur.fetchone()[0]
            message = "New product added successfully"

        conn.commit()
        return jsonify({"message": message, "product_id": product_id}), 201

    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()
        conn.close()

#Upload flyer image
@app.route('/upload_flyer', methods=['POST'])
def upload_flyer():
    logging.debug(f"Request received: {request.form}, Files: {request.files}")
    if 'file' not in request.files or 'store_id' not in request.form:
        return jsonify({"error": "Missing required fields"}), 400

    file = request.files['file']
    store_id = request.form['store_id']

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Secure the filename and generate a unique name
    filename = secure_filename(f"{int(time.time())}_{file.filename}")
    print(f"File to be uploaded: {filename}")
    # Upload to Supabase Storage
    try:
        # Verify if Supabase Upload is Working
        # Convert file to binary before sending to Supabase
        file_data = file.read()  

        response = supabase.storage.from_("flyers").upload(
            f"{filename}",  # File path in storage
            file_data,  # Binary content
            file_options={"content-type": file.content_type}  # Ensure correct MIME type
        )

        image_url = f"{SUPABASE_URL}/storage/v1/object/public/flyers/{filename}"
        print(f"Image URL: {image_url}")
        updated_at = datetime.now(timezone.utc)

        # Insert flyer details into the database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO flyers (store_id, image_url, uploaded_at) 
            VALUES (%s, %s, %s) RETURNING id;
        """, (store_id, image_url, updated_at))
        
        flyer_id = cur.fetchone()
        if not flyer_id:
            print("Database insertion failed!")
        else:
            print(f"Flyer inserted with ID: {flyer_id[0]}")
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "message": "Flyer uploaded successfully", 
            "flyer_id": flyer_id[0], 
            "store_id": store_id, 
            "image_url": image_url, 
            "updated_at": updated_at
        }), 201

    except Exception as e:
        print("Upload error:", str(e))
        traceback.print_exc()  # Prints full error traceback
        return jsonify({"error": str(e)}), 500

# Function to get ZIP code coordinates
def get_zip_coordinates(zip_code):
    try:
        # Using the free ZIP code API
        response = requests.get(f"https://api.zippopotam.us/us/{zip_code}")
        if response.status_code == 200:
            data = response.json()
            return {
                "lat": float(data["places"][0]["latitude"]),
                "lng": float(data["places"][0]["longitude"])
            }
        return None
    except Exception as e:
        print(f"Error getting coordinates for ZIP code: {e}")
        return None

# Calculate distance between two ZIP codes using Haversine formula
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 3959.87433  # Earth's radius in miles

    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    distance = R * c
    
    return round(distance, 2)

# Get stores sorted by distance from user's ZIP code
@app.route('/stores/by-distance/<user_zip>', methods=['GET'])
def get_stores_by_distance(user_zip):
    try:
        # Get user's coordinates
        user_coords = get_zip_coordinates(user_zip)
        if not user_coords:
            return jsonify({"error": "Invalid ZIP code"}), 400

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get all stores
        cur.execute("SELECT id, name, zip_code FROM stores")
        stores = cur.fetchall()
        
        # Calculate distances and sort stores
        stores_with_distance = []
        for store in stores:
            store_id, store_name, store_zip = store
            store_coords = get_zip_coordinates(store_zip)
            
            if store_coords:
                distance = calculate_distance(
                    user_coords["lat"], user_coords["lng"],
                    store_coords["lat"], store_coords["lng"]
                )
                
                stores_with_distance.append({
                    "id": store_id,
                    "name": store_name,
                    "zip_code": store_zip,
                    "distance": distance
                })
        
        # Sort stores by distance
        stores_with_distance.sort(key=lambda x: x["distance"])
        
        cur.close()
        conn.close()
        
        return jsonify(stores_with_distance)
    
    except Exception as e:
        print(f"Error in get_stores_by_distance: {e}")
        return jsonify({"error": str(e)}), 500

# Modified compare_prices endpoint to include distance information
@app.route('/api/compare-prices', methods=['POST'])
def compare_prices():
    try:
        data = request.get_json()
        print("Received request data:", data)  # Debug log
        
        items = data.get('items', [])
        user_zip = data.get('userZip')
        
        print(f"Processing items: {items}, user_zip: {user_zip}")  # Debug log
        
        if not items:
            return jsonify({"error": "No items provided"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
            
        cur = conn.cursor()
        
        # Create a placeholder string for the SQL IN clause
        items_placeholder = ','.join(['%s'] * len(items))
        
        query = f"""
            SELECT p.name, s.name as store_name, p.price, s.zip_code
            FROM products p
            JOIN stores s ON p.store_id = s.id
            WHERE LOWER(p.name) IN ({items_placeholder})
            ORDER BY p.name, p.price ASC
        """
        
        # Convert items to lowercase for case-insensitive comparison
        query_params = tuple(item.lower() for item in items)
        print(f"Executing query with params: {query_params}")  # Debug log
        
        cur.execute(query, query_params)
        data = cur.fetchall()
        print(f"Query returned {len(data)} rows")  # Debug log
        
        cur.close()
        conn.close()

        # Process data into best price format with actual savings calculation
        comparisons = {}
        total_best_price = 0
        
        # Get user coordinates if ZIP provided
        user_coords = get_zip_coordinates(user_zip) if user_zip else None
        
        # First pass to find the price range for each product
        for product_name, store_name, price, store_zip in data:
            store_distance = None
            if user_coords and store_zip:
                store_coords = get_zip_coordinates(store_zip)
                if store_coords:
                    store_distance = calculate_distance(
                        user_coords["lat"], user_coords["lng"],
                        store_coords["lat"], store_coords["lng"]
                    )

            if product_name not in comparisons:
                comparisons[product_name] = {
                    "bestStore": store_name,
                    "bestPrice": float(price),  # Convert to float
                    "worstPrice": float(price),  # Convert to float
                    "bestStoreDistance": store_distance,
                    "allPrices": [(store_name, float(price), store_distance)]  # Convert to float
                }
            else:
                comparisons[product_name]["allPrices"].append((store_name, float(price), store_distance))
                if price < comparisons[product_name]["bestPrice"]:
                    comparisons[product_name]["bestPrice"] = float(price)
                    comparisons[product_name]["bestStore"] = store_name
                    comparisons[product_name]["bestStoreDistance"] = store_distance
                if price > comparisons[product_name]["worstPrice"]:
                    comparisons[product_name]["worstPrice"] = float(price)

        # Calculate savings and format response
        result = []
        for product_name, data in comparisons.items():
            savings = data["worstPrice"] - data["bestPrice"]
            total_best_price += data["bestPrice"]
            
            result.append({
                "product": product_name,
                "bestStore": data["bestStore"],
                "bestPrice": data["bestPrice"],
                "bestStoreDistance": data["bestStoreDistance"],
                "savings": round(savings, 2),
                "allPrices": data["allPrices"]
            })

        response_data = {
            "items": result,
            "totalBestPrice": round(total_best_price, 2)
        }
        print("Sending response:", response_data)  # Debug log
        return jsonify(response_data)

    except Exception as e:
        print(f"Error in compare_prices: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

def optimize_shopping_stops(items, user_zip):
    try:
        print(f"Optimizing shopping stops for items: {items}")
        print(f"User ZIP: {user_zip}")
        
        if not items:
            return {"error": "No items provided"}, 400
            
        if not user_zip:
            return {"error": "ZIP code is required for optimization"}, 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get coordinates for user's ZIP code
        user_coords = get_zip_coordinates(user_zip)
        if not user_coords:
            return {"error": "Invalid ZIP code"}, 400

        # Get prices for all items at all stores
        placeholders = ','.join(['%s'] * len(items))
        query = f"""
            SELECT p.store_id, p.name as product_name, p.price, s.name as store_name, s.zip_code
            FROM products p
            JOIN stores s ON p.store_id = s.id
            WHERE LOWER(p.name) IN ({placeholders})
        """
        print(f"Executing query: {query}")
        print(f"With parameters: {[item.lower() for item in items]}")
        
        cursor.execute(query, [item.lower() for item in items])
        prices = cursor.fetchall()
        print(f"Found {len(prices)} price entries")

        if not prices:
            return {"error": "No items found in any stores"}, 404

        # Group prices by store
        store_prices = {}
        for price in prices:
            store_id = price[0]
            if store_id not in store_prices:
                store_prices[store_id] = {
                    'name': price[3],
                    'zip_code': price[4],
                    'items': {}
                }
            store_prices[store_id]['items'][price[1]] = float(price[2])  # Convert price to float

        print(f"Found {len(store_prices)} stores with items")
        for store_id, store_data in store_prices.items():
            print(f"Store {store_data['name']} has {len(store_data['items'])} items")

        # Calculate distances from user's location to each store
        for store_id, store_data in store_prices.items():
            store_coords = get_zip_coordinates(store_data['zip_code'])
            if store_coords:
                store_data['distance'] = calculate_distance(
                    user_coords["lat"], user_coords["lng"],
                    store_coords["lat"], store_coords["lng"]
                )
            else:
                store_data['distance'] = float('inf')

        # Strategy 1: Price-optimized (best price for each item)
        price_optimized = find_price_optimized_stops(store_prices, items)
        print("Price optimized result:", price_optimized)
        
        # Strategy 2: Distance-optimized (closest stores first)
        distance_optimized = find_distance_optimized_stops(store_prices, items)
        print("Distance optimized result:", distance_optimized)
        
        # Strategy 3: Convenience-optimized (minimum stops)
        convenience_optimized = find_optimal_stops(store_prices, items)
        print("Convenience optimized result:", convenience_optimized)

        # Format response with all three strategies
        response = {
            "price_optimized": {
                "stores": price_optimized["stores"],
                "total_cost": float(price_optimized["total_cost"]),  # Ensure it's a number
                "total_distance": float(price_optimized["total_distance"]),  # Ensure it's a number
                "item_breakdown": price_optimized["item_breakdown"]
            },
            "distance_optimized": {
                "stores": distance_optimized["stores"],
                "total_cost": float(distance_optimized["total_cost"]),  # Ensure it's a number
                "total_distance": float(distance_optimized["total_distance"]),  # Ensure it's a number
                "item_breakdown": distance_optimized["item_breakdown"]
            },
            "convenience_optimized": {
                "stores": convenience_optimized["stores"],
                "total_cost": float(convenience_optimized["total_cost"]),  # Ensure it's a number
                "total_distance": float(convenience_optimized["total_distance"]),  # Ensure it's a number
                "item_breakdown": convenience_optimized["item_breakdown"]
            }
        }

        print("Final optimization response:", response)
        return response

    except Exception as e:
        print(f"Error in optimize_shopping_stops: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return {"error": str(e)}, 500
    finally:
        if 'conn' in locals():
            conn.close()

def find_price_optimized_stops(store_prices, items):
    """Find the best price for each item, regardless of store."""
    result = {
        "stores": [],
        "total_cost": 0,
        "total_distance": 0,
        "item_breakdown": {}
    }
    
    print(f"Finding price-optimized stops for items: {items}")
    print(f"Available stores: {[store_data['name'] for store_data in store_prices.values()]}")
    
    # Find best price for each item
    for item in items:
        best_price = float('inf')
        best_store = None
        
        for store_id, store_data in store_prices.items():
            # Create case-insensitive mapping of items
            store_items = {k.lower(): (k, v) for k, v in store_data['items'].items()}
            if item.lower() in store_items:
                original_name, price = store_items[item.lower()]
                if price < best_price:
                    best_price = price
                    best_store = store_id
        
        if best_store is not None:
            if best_store not in result["stores"]:
                result["stores"].append(best_store)
            result["total_cost"] += best_price
            result["item_breakdown"][item] = {
                "store": store_prices[best_store]["name"],
                "price": best_price
            }
            print(f"Found {item} at {store_prices[best_store]['name']} for ${best_price}")
    
    # Calculate total distance
    for store_id in result["stores"]:
        result["total_distance"] += store_prices[store_id]["distance"]
    
    print(f"Price-optimized result: {result}")
    return result

def find_distance_optimized_stops(store_prices, items):
    """Find stores to visit based on distance, getting items from closest stores first."""
    result = {
        "stores": [],
        "total_cost": 0,
        "total_distance": 0,
        "item_breakdown": {}
    }
    
    print(f"Finding distance-optimized stops for items: {items}")
    
    # Sort stores by distance
    sorted_stores = sorted(
        store_prices.items(),
        key=lambda x: x[1]['distance']
    )
    
    remaining_items = set(items)
    print(f"Remaining items: {remaining_items}")
    
    # Try to get items from closest stores first
    for store_id, store_data in sorted_stores:
        if not remaining_items:
            break
            
        # Create case-insensitive mapping of items
        store_items = {k.lower(): (k, v) for k, v in store_data['items'].items()}
        available_items = {item for item in remaining_items if item.lower() in store_items}
        
        if available_items:
            result["stores"].append(store_id)
            result["total_distance"] += store_data["distance"]
            
            for item in available_items:
                original_name, price = store_items[item.lower()]
                result["total_cost"] += price
                result["item_breakdown"][item] = {
                    "store": store_data["name"],
                    "price": price
                }
                print(f"Found {item} at {store_data['name']} for ${price}")
            
            remaining_items -= available_items
    
    print(f"Distance-optimized result: {result}")
    return result

def find_optimal_stops(store_prices, items):
    """Find the minimum number of stores to visit."""
    result = {
        "stores": [],
        "total_cost": 0,
        "total_distance": 0,
        "item_breakdown": {}
    }
    
    print(f"Finding convenience-optimized stops for items: {items}")
    
    # First, find stores that have the most items
    store_coverage = {}
    for store_id, store_data in store_prices.items():
        # Create case-insensitive mapping of items
        store_items = {k.lower(): (k, v) for k, v in store_data['items'].items()}
        coverage = len({item for item in items if item.lower() in store_items})
        if coverage > 0:
            store_coverage[store_id] = coverage
    
    print(f"Store coverage: {store_coverage}")
    
    # Sort stores by coverage (descending) and then by distance
    sorted_stores = sorted(
        store_coverage.items(),
        key=lambda x: (-x[1], store_prices[x[0]]['distance'])
    )
    
    remaining_items = set(items)
    print(f"Remaining items: {remaining_items}")
    
    # Try to get items from stores with the most coverage first
    for store_id, _ in sorted_stores:
        if not remaining_items:
            break
            
        store_data = store_prices[store_id]
        # Create case-insensitive mapping of items
        store_items = {k.lower(): (k, v) for k, v in store_data['items'].items()}
        available_items = {item for item in remaining_items if item.lower() in store_items}
        
        if available_items:
            result["stores"].append(store_id)
            result["total_distance"] += store_data["distance"]
            
            for item in available_items:
                original_name, price = store_items[item.lower()]
                result["total_cost"] += price
                result["item_breakdown"][item] = {
                    "store": store_data["name"],
                    "price": price
                }
                print(f"Found {item} at {store_data['name']} for ${price}")
            
            remaining_items -= available_items
    
    print(f"Convenience-optimized result: {result}")
    return result

@app.route('/api/optimize-stops', methods=['POST'])
def optimize_stops():
    data = request.get_json()
    items = data.get('items', [])
    user_zip = data.get('userZip')
    
    result = optimize_shopping_stops(items, user_zip)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)

@app.route('/')
def home():
    return jsonify({"message": "Grocery Smart API is running!"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
