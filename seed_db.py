# seed_db.py
from pymongo import MongoClient
import datetime

# --- Configuration ---
# Connect to your local MongoDB instance
client = MongoClient('mongodb://localhost:27017/')
db = client['storefront_db'] # Use a specific database name

def seed_database():
    """
    Wipes and seeds the database with initial sample data.
    """
    print("Connecting to the database...")

    # --- Clear Existing Data ---
    # This ensures a clean slate every time the seed script is run.
    print("Clearing existing collections...")
    db.users.drop()
    db.businesses.drop()
    db.products.drop()
    db.inventory.drop()
    db.sales.drop()
    print("Collections cleared.")

    # --- Seed Users ---
    # In a real app, passwords MUST be hashed. Storing plaintext is for demo purposes only.
    print("Seeding users...")
    users = [
        {"username": "owner", "password": "password", "role": "owner"},
        {"username": "buyer", "password": "password", "role": "buyer"}
    ]
    user_results = db.users.insert_many(users)
    owner_id = user_results.inserted_ids[0]
    print(f"Inserted {len(user_results.inserted_ids)} users.")

    # --- Seed Businesses ---
    print("Seeding businesses...")
    business1_id = db.businesses.insert_one({
        "name": "FitZone Gym",
        "business_type": "gym",
        "owner_id": owner_id
    }).inserted_id

    business2_id = db.businesses.insert_one({
        "name": "Prestige Autos",
        "business_type": "car_dealership",
        "owner_id": owner_id
    }).inserted_id
    print("Inserted businesses.")

    # --- Seed Products ---
    # We link products to businesses using their newly generated _id
    print("Seeding products...")
    product1_id = db.products.insert_one({
        "name": "Vanilla Protein Shake", "description": "25g of whey protein",
        "price": 5.99, "sku": "G-SHK-01", "business_id": business1_id,
        "image_url": "https://images.pexels.com/photos/3837781/pexels-photo-3837781.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1"
    }).inserted_id

    product2_id = db.products.insert_one({
        "name": "Pre-Workout Boost", "description": "Energy and focus blend",
        "price": 3.50, "sku": "G-PRE-01", "business_id": business1_id,
        "image_url": ""
    }).inserted_id

    product3_id = db.products.insert_one({
        "name": "2023 Sedan", "description": "Reliable family car, low mileage",
        "price": 25000.00, "sku": "C-SED-23", "business_id": business2_id,
        "image_url": "https://images.pexels.com/photos/170811/pexels-photo-170811.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1"
    }).inserted_id

    product4_id = db.products.insert_one({
        "name": "2024 SUV", "description": "Spacious 7-seater with modern tech",
        "price": 38000.00, "sku": "C-SUV-24", "business_id": business2_id,
        "image_url": "https://images.pexels.com/photos/3764984/pexels-photo-3764984.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1"
    }).inserted_id
    print("Inserted products.")

    # --- Seed Inventory ---
    # Link inventory to products using their _id
    print("Seeding inventory...")
    inventory_data = [
        {"product_id": product1_id, "quantity": 48},
        {"product_id": product2_id, "quantity": 30},
        {"product_id": product3_id, "quantity": 5},
        {"product_id": product4_id, "quantity": 3}
    ]
    db.inventory.insert_many(inventory_data)
    print("Inserted inventory records.")

    # --- Seed Sales ---
    print("Seeding sales...")
    db.sales.insert_one({
        "product_id": product1_id,
        "quantity_sold": 2,
        "total_price": 11.98,
        "sale_date": datetime.datetime.utcnow()
    })
    print("Inserted sales records.")

    print("\nDatabase seeding complete! ✅")


if __name__ == '__main__':
    seed_database()
