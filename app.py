"""
Multi-Business-Type Store Application
A generic Flask application that supports multiple business types:
- Restaurant
- Auto Sales
- Auto Services
- Other Services
- Generic Store

HOW TO USE:
1. Run the application: python app.py
2. At the root URL, select your business type
3. Create your store or access existing stores
4. Manage your inventory/items through the admin dashboard
"""
import os
import datetime
from flask import Flask, request, render_template_string, redirect, url_for, flash, session, g, abort, Response
import json
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
from functools import wraps
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()

# --- App & DB Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a-super-secret-key-change-in-production')

# --- MongoDB Connection ---
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/?retryWrites=true&w=majority&directConnection=true')
client = MongoClient(MONGO_URI)
db = client['multi_business_db']

# --- Create Unique Indexes ---
db.stores.create_index("slug_id", unique=True)
db.users.create_index([("email", 1), ("store_id", 1)], unique=True)
db.items.create_index([("item_code", 1), ("store_id", 1)], unique=True)  # Generic collection name
db.specials.create_index([("store_id", 1), ("date_created", -1)])
db.inquiries.create_index([("store_id", 1), ("date_submitted", -1)])

# --- Business Type Configurations ---
BUSINESS_TYPES = {
    'restaurant': {
        'name': 'Restaurant',
        'item_label': 'Menu Item',
        'item_plural': 'Menu Items',
        'item_code_label': 'Item Code',
        'item_code_prefix': 'MENU',
        'section_label': 'Menu',
        'inquiry_label': 'Order/Inquiry',
        'attributes_template': [
            {'name': 'Category', 'type': 'text', 'required': True},
            {'name': 'Ingredients', 'type': 'text', 'required': False},
            {'name': 'Allergens', 'type': 'text', 'required': False},
        ],
        'status_options': ['Available', 'Sold Out'],
        'hero_text': 'Delicious Food & Great Service',
        'default_description': 'Delicious dish prepared with the finest ingredients.'
    },
    'auto-sales': {
        'name': 'Auto Sales',
        'item_label': 'Vehicle',
        'item_plural': 'Vehicles',
        'item_code_label': 'VIN/SKU',
        'item_code_prefix': 'VIN',
        'section_label': 'Inventory',
        'inquiry_label': 'Inquiry',
        'attributes_template': [
            {'name': 'Make', 'type': 'text', 'required': True},
            {'name': 'Model', 'type': 'text', 'required': True},
            {'name': 'Year', 'type': 'number', 'required': True},
            {'name': 'Mileage', 'type': 'number', 'required': False},
            {'name': 'Color', 'type': 'text', 'required': False},
            {'name': 'Condition', 'type': 'text', 'required': True},
        ],
        'status_options': ['Available', 'Pending', 'Sold'],
        'hero_text': 'Quality Vehicles at Great Prices',
        'default_description': 'Well-maintained vehicle ready for you.'
    },
    'auto-services': {
        'name': 'Auto Services',
        'item_label': 'Service',
        'item_plural': 'Services',
        'item_code_label': 'Service Code',
        'item_code_prefix': 'SRV',
        'section_label': 'Services',
        'inquiry_label': 'Appointment Request',
        'attributes_template': [
            {'name': 'Service Type', 'type': 'text', 'required': True},
            {'name': 'Duration', 'type': 'text', 'required': False},
            {'name': 'Warranty', 'type': 'text', 'required': False},
            {'name': 'Includes', 'type': 'textarea', 'required': False},
        ],
        'status_options': ['Available', 'Limited Availability'],
        'hero_text': 'Professional Auto Services',
        'default_description': 'Quality service performed by experienced technicians.'
    },
    'other-services': {
        'name': 'Other Services',
        'item_label': 'Service',
        'item_plural': 'Services',
        'item_code_label': 'Service Code',
        'item_code_prefix': 'SRV',
        'section_label': 'Services',
        'inquiry_label': 'Service Request',
        'attributes_template': [
            {'name': 'Service Type', 'type': 'text', 'required': True},
            {'name': 'Duration', 'type': 'text', 'required': False},
            {'name': 'What\'s Included', 'type': 'textarea', 'required': False},
        ],
        'status_options': ['Available', 'Limited Availability'],
        'hero_text': 'Quality Services You Can Trust',
        'default_description': 'Professional service tailored to your needs.'
    },
    'generic-store': {
        'name': 'Generic Store',
        'item_label': 'Product',
        'item_plural': 'Products',
        'item_code_label': 'SKU',
        'item_code_prefix': 'SKU',
        'section_label': 'Inventory',
        'inquiry_label': 'Inquiry',
        'attributes_template': [
            {'name': 'Category', 'type': 'text', 'required': True},
            {'name': 'Brand', 'type': 'text', 'required': False},
            {'name': 'Color', 'type': 'text', 'required': False},
            {'name': 'Size', 'type': 'text', 'required': False},
            {'name': 'Material', 'type': 'text', 'required': False},
        ],
        'status_options': ['Available', 'Pending', 'Sold'],
        'hero_text': 'Quality Products You\'ll Love',
        'default_description': 'High-quality product available now.'
    }
}

# --- HTML TEMPLATES ---

BUSINESS_SELECTION_TEMPLATE = """
<!doctype html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <title>Select Your Business Type - StoreFactory</title>
    <style>
        * { font-family: 'Poppins', sans-serif; }
        .business-card {
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border: 2px solid rgba(59, 130, 246, 0.3);
        }
        .business-card:hover {
            transform: translateY(-12px) scale(1.02);
            box-shadow: 0 25px 50px -12px rgba(59, 130, 246, 0.4);
            border-color: rgba(59, 130, 246, 0.7);
            background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
        }
        .gradient-bg {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        }
        .hero-pattern {
            background-image: radial-gradient(circle at 2px 2px, rgba(255,255,255,0.05) 1px, transparent 0);
            background-size: 40px 40px;
        }
    </style>
</head>
<body class="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 min-h-screen">
    <div class="gradient-bg hero-pattern py-20">
        <div class="container mx-auto px-6 text-center mb-16">
            <h1 class="text-6xl md:text-7xl font-extrabold text-white mb-6 drop-shadow-lg">
                Welcome to <span class="bg-gradient-to-r from-yellow-300 to-orange-300 bg-clip-text text-transparent">StoreFactory</span>
            </h1>
            <p class="text-2xl text-gray-300 max-w-3xl mx-auto mb-8 font-medium">Create your store in minutes. No coding required.</p>
            <div class="flex flex-wrap justify-center gap-4 text-white">
                <div class="flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full border border-white/20">
                    <i class="fas fa-check-circle text-yellow-300"></i>
                    <span>Easy Setup</span>
                </div>
                <div class="flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full border border-white/20">
                    <i class="fas fa-check-circle text-yellow-300"></i>
                    <span>Multiple Business Types</span>
                </div>
                <div class="flex items-center gap-2 bg-white/10 backdrop-blur-sm px-4 py-2 rounded-full border border-white/20">
                    <i class="fas fa-check-circle text-yellow-300"></i>
                    <span>Mobile Friendly</span>
                </div>
            </div>
        </div>
    </div>
    
    <div class="container mx-auto px-6 py-16 -mt-10">
        <div class="mb-12 text-center">
            <h2 class="text-4xl font-bold text-white mb-4">Choose Your Business Type</h2>
            <p class="text-lg text-gray-300 max-w-2xl mx-auto">Select the type that best matches your business to get started</p>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 max-w-6xl mx-auto mb-16">
            <a href="{{ url_for('select_business', business_type='restaurant') }}" 
               class="business-card rounded-2xl shadow-xl p-10 text-center block group">
                <div class="text-7xl mb-6 transform group-hover:scale-110 transition-transform">🍕</div>
                <h3 class="text-3xl font-bold text-white mb-3">Restaurant</h3>
                <p class="text-gray-300 mb-4">Menu items, orders, and specials</p>
                <div class="flex justify-center items-center gap-2 text-indigo-400 font-semibold mt-4">
                    <span>Get Started</span>
                    <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
                </div>
            </a>
            
            <a href="{{ url_for('select_business', business_type='auto-sales') }}" 
               class="business-card rounded-2xl shadow-xl p-10 text-center block group">
                <div class="text-7xl mb-6 transform group-hover:scale-110 transition-transform">🚗</div>
                <h3 class="text-3xl font-bold text-white mb-3">Auto Sales</h3>
                <p class="text-gray-300 mb-4">Vehicle inventory and inquiries</p>
                <div class="flex justify-center items-center gap-2 text-indigo-400 font-semibold mt-4">
                    <span>Get Started</span>
                    <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
                </div>
            </a>
            
            <a href="{{ url_for('select_business', business_type='auto-services') }}" 
               class="business-card rounded-2xl shadow-xl p-10 text-center block group">
                <div class="text-7xl mb-6 transform group-hover:scale-110 transition-transform">🔧</div>
                <h3 class="text-3xl font-bold text-white mb-3">Auto Services</h3>
                <p class="text-gray-300 mb-4">Service listings and appointments</p>
                <div class="flex justify-center items-center gap-2 text-indigo-400 font-semibold mt-4">
                    <span>Get Started</span>
                    <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
                </div>
            </a>
            
            <a href="{{ url_for('select_business', business_type='other-services') }}" 
               class="business-card rounded-2xl shadow-xl p-10 text-center block group">
                <div class="text-7xl mb-6 transform group-hover:scale-110 transition-transform">💼</div>
                <h3 class="text-3xl font-bold text-white mb-3">Other Services</h3>
                <p class="text-gray-300 mb-4">General service offerings</p>
                <div class="flex justify-center items-center gap-2 text-indigo-400 font-semibold mt-4">
                    <span>Get Started</span>
                    <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
                </div>
            </a>
            
            <a href="{{ url_for('select_business', business_type='generic-store') }}" 
               class="business-card rounded-2xl shadow-xl p-10 text-center block group">
                <div class="text-7xl mb-6 transform group-hover:scale-110 transition-transform">🏪</div>
                <h3 class="text-3xl font-bold text-white mb-3">Generic Store</h3>
                <p class="text-gray-300 mb-4">Products and inventory</p>
                <div class="flex justify-center items-center gap-2 text-indigo-400 font-semibold mt-4">
                    <span>Get Started</span>
                    <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
                </div>
            </a>
        </div>
        
        <div class="text-center bg-gray-800 border border-gray-700 rounded-2xl shadow-lg p-8 max-w-2xl mx-auto">
            <h3 class="text-2xl font-bold text-white mb-4">Already have a store?</h3>
            <p class="text-gray-300 mb-6">Browse all existing stores or access your dashboard</p>
            <a href="{{ url_for('list_stores') }}" 
               class="inline-flex items-center gap-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold py-4 px-8 rounded-xl shadow-lg transform hover:scale-105 transition-all">
                <i class="fas fa-store"></i>
                <span>View All Stores</span>
                <i class="fas fa-arrow-right"></i>
            </a>
        </div>
    </div>
</body>
</html>
"""

LAYOUT_TEMPLATE = """
<!doctype html>
<html lang="{{ store.lang or 'en' }}" class="scroll-smooth">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <title>{{ store.name }} - {{ business_config.name }}</title>
    <style>
        body { 
            font-family: 'Poppins', sans-serif;
            background-color: {{ store.theme_background or '#111827' }};
            color: {{ store.theme_text or '#f9fafb' }};
        }
        .modal {
            display: none; position: fixed; z-index: 1000; left: 0; top: 0;
            width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.6);
            animation: fadeIn 0.3s;
        }
        .modal-content {
            background-color: {{ store.theme_surface or '#1f2937' }}; 
            margin: 10% auto; padding: 2rem;
            border: 1px solid {{ store.theme_primary or '#3b82f6' }}; 
            width: 90%; max-width: 600px;
            border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.6);
            position: relative; animation: slideIn 0.3s;
            color: {{ store.theme_text or '#f9fafb' }};
        }
        .close { 
            color: {{ store.theme_text_secondary or '#d1d5db' }}; 
            float: right; font-size: 28px; font-weight: bold; cursor: pointer; 
        }
        .close:hover, .close:focus { 
            color: {{ store.theme_text or '#f9fafb' }}; 
        }
        .theme-primary { color: {{ store.theme_primary or '#3b82f6' }}; }
        .theme-primary-bg { background-color: {{ store.theme_primary or '#3b82f6' }}; }
        .theme-secondary { color: {{ store.theme_secondary or '#f59e0b' }}; }
        .theme-secondary-bg { background-color: {{ store.theme_secondary or '#f59e0b' }}; }
        .theme-surface { background-color: {{ store.theme_surface or '#1f2937' }}; }
        @keyframes fadeIn { from {opacity: 0;} to {opacity: 1;} }
        @keyframes slideIn { from {transform: translateY(-50px);} to {transform: translateY(0);} }
    </style>
</head>
<body style="background-color: {{ store.theme_background or '#111827' }}; color: {{ store.theme_text or '#f9fafb' }};">
    <header class="shadow-lg sticky top-0 z-50" style="background-color: {{ store.theme_surface or '#1f2937' }}; border-bottom: 2px solid {{ store.theme_primary or '#3b82f6' }};">
        <div class="container mx-auto px-6 py-3 flex justify-between items-center">
            <a href="{{ url_for('store_home', store_slug=store.slug_id) }}" class="flex items-center space-x-3">
                {% if store.logo_url %}<img src="{{ store.logo_url }}" alt="{{ store.name }} Logo" class="h-12">{% endif %}
                <span class="text-2xl font-bold tracking-wider">{{ store.name }}</span>
            </a>
            <nav class="hidden md:flex items-center space-x-6">
                <a href="{{ url_for('store_home', store_slug=store.slug_id) }}" 
                   style="color: {{ store.theme_text or '#f9fafb' }};" 
                   onmouseover="this.style.color='{{ store.theme_secondary or '#f59e0b' }}';" 
                   onmouseout="this.style.color='{{ store.theme_text or '#f9fafb' }}';"
                   class="transition-colors">Home</a>
                <a href="{{ url_for('store_home', store_slug=store.slug_id) }}#{{ business_config.section_label.lower().replace(' ', '-') }}" 
                   style="color: {{ store.theme_text or '#f9fafb' }};" 
                   onmouseover="this.style.color='{{ store.theme_secondary or '#f59e0b' }}';" 
                   onmouseout="this.style.color='{{ store.theme_text or '#f9fafb' }}';"
                   class="transition-colors">{{ business_config.section_label }}</a>
                <a href="{{ url_for('store_home', store_slug=store.slug_id) }}#contact" 
                   style="color: {{ store.theme_text or '#f9fafb' }};" 
                   onmouseover="this.style.color='{{ store.theme_secondary or '#f59e0b' }}';" 
                   onmouseout="this.style.color='{{ store.theme_text or '#f9fafb' }}';"
                   class="transition-colors">Contact</a>
                {% if 'user_id' in session and session.get('store_id') == store._id|string %}
                    <a href="{{ url_for('admin_dashboard', store_slug=store.slug_id) }}" 
                       style="background-color: {{ store.theme_primary or '#3b82f6' }};" 
                       onmouseover="this.style.opacity='0.9';" 
                       onmouseout="this.style.opacity='1';"
                       class="px-4 py-2 rounded-md text-white transition-opacity">Dashboard</a>
                    <a href="{{ url_for('admin_logout', store_slug=store.slug_id) }}" 
                       class="px-4 py-2 rounded-md bg-red-600 hover:bg-red-700 text-white" 
                       onclick="return confirm('Are you sure you want to logout?');">Logout</a>
                {% else %}
                    <a href="{{ url_for('admin_login', store_slug=store.slug_id) }}" 
                       style="background-color: {{ store.theme_primary or '#3b82f6' }};" 
                       onmouseover="this.style.opacity='0.9';" 
                       onmouseout="this.style.opacity='1';"
                       class="px-4 py-2 rounded-md text-white transition-opacity">Login</a>
                {% endif %}
            </nav>
            <button id="mobile-menu-button" class="md:hidden text-2xl"><i class="fas fa-bars"></i></button>
        </div>
        <div id="mobile-menu" class="hidden md:hidden bg-gray-800 border-t border-gray-700">
             <a href="{{ url_for('store_home', store_slug=store.slug_id) }}" class="block px-6 py-3 hover:bg-gray-700">Home</a>
             <a href="{{ url_for('store_home', store_slug=store.slug_id) }}#{{ business_config.section_label.lower().replace(' ', '-') }}" class="block px-6 py-3 hover:bg-gray-700">{{ business_config.section_label }}</a>
             <a href="{{ url_for('store_home', store_slug=store.slug_id) }}#contact" class="block px-6 py-3 hover:bg-gray-700">Contact</a>
             {% if 'user_id' in session and session.get('store_id') == store._id|string %}
                <a href="{{ url_for('admin_dashboard', store_slug=store.slug_id) }}" class="block px-6 py-3 bg-blue-600 hover:bg-blue-700">Dashboard</a>
                <a href="{{ url_for('admin_logout', store_slug=store.slug_id) }}" class="block px-6 py-3 bg-red-600 hover:bg-red-700" onclick="return confirm('Are you sure you want to logout?');">Logout</a>
             {% else %}
                <a href="{{ url_for('admin_login', store_slug=store.slug_id) }}" class="block px-6 py-3 bg-indigo-600 hover:bg-indigo-700">Login</a>
             {% endif %}
        </div>
    </header>
    <main>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            <div class="container mx-auto px-6 mt-4">
              {% for category, message in messages %}
              <div class="p-4 mb-4 text-sm rounded-lg {{ 'bg-green-900 text-green-200 border border-green-700' if category == 'success' else 'bg-red-900 text-red-200 border border-red-700' }}" role="alert">
                <span class="font-medium">{{ category|title }}!</span> {{ message }}
              </div>
              {% endfor %}
            </div>
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer style="background-color: {{ store.theme_surface or '#1f2937' }}; color: {{ store.theme_text or '#f9fafb' }};" class="mt-12 py-10">
        <div class="container mx-auto px-6 text-center">
            {% if store.logo_url %}<img src="{{ store.logo_url }}" alt="Logo" class="h-16 mx-auto mb-4">{% endif %}
            <p>© {{ now.year }} {{ store.name }}. Todos los derechos reservados.</p>
            <p class="text-sm text-gray-400 mt-2">Powered by StoreFactory</p>
        </div>
    </footer>
    <script>
        document.getElementById('mobile-menu-button')?.addEventListener('click', () => {
            document.getElementById('mobile-menu')?.classList.toggle('hidden');
        });
    </script>
</body>
</html>
"""

HOME_TEMPLATE = """
{% extends "layout" %}
{% block content %}
<section id="hero" class="h-screen bg-cover bg-center bg-fixed flex items-center justify-center text-white" style="background-image: linear-gradient(rgba(0,0,0,0.6), rgba(0,0,0,0.6)), url('{{ store.hero_image_url or 'https://images.pexels.com/photos/376464/pexels-photo-376464.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2' }}');">
    <div class="text-center px-4">
        <h1 class="text-4xl md:text-6xl font-extrabold drop-shadow-lg">{{ store.tagline or business_config.hero_text }}</h1>
        <p class="text-lg md:text-xl mt-4 max-w-2xl mx-auto drop-shadow-md">{{ store.about_text or 'Welcome to our store' }}</p>
    </div>
</section>

<section id="{{ business_config.section_label.lower().replace(' ', '-') }}" class="py-16 bg-gray-800">
    <div class="container mx-auto px-6 text-center">
        <h2 class="text-4xl font-extrabold mb-4 text-white">{{ business_config.section_label }}</h2>
        <p class="text-gray-300 mb-10 max-w-2xl mx-auto">{{ store.inventory_description or 'Browse our selection below' }}</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
            {% for item in items %}
            <div class="bg-gray-700 border border-gray-600 rounded-lg overflow-hidden shadow-lg transition-transform transform hover:-translate-y-2 hover:shadow-2xl flex flex-col">
                <a href="{{ url_for('item_details', store_slug=store.slug_id, item_id=item._id) }}">
                    <img src="{{ item.image_url or 'https://placehold.co/600x400/cccccc/ffffff?text=' + business_config.item_label }}" alt="{{ item.name }}" class="w-full h-56 object-cover">
                </a>
                <div class="p-6 flex-grow flex flex-col">
                    <h3 class="text-2xl font-bold text-white">{{ item.name }}</h3>
                    <p class="text-xl font-semibold text-green-400 mt-2">${{ "%.2f"|format(item.price) }}</p>
                    {% if item.status %}<p class="text-sm mt-2"><span class="px-2 py-1 rounded {{ 'bg-green-900 text-green-200 border border-green-700' if item.status == 'Available' else 'bg-red-900 text-red-200 border border-red-700' }}">{{ item.status }}</span></p>{% endif %}
                    <div class="mt-auto pt-4">
                        <a href="{{ url_for('item_details', store_slug=store.slug_id, item_id=item._id) }}" class="inline-block w-full text-center bg-gray-800 hover:bg-yellow-500 hover:text-gray-900 border border-gray-600 hover:border-yellow-500 text-white font-bold py-2 px-4 rounded-md transition-colors">View Details</a>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="col-span-full text-center text-gray-400 py-12">
                <p>No {{ business_config.item_plural.lower() }} available at this time.</p>
            </div>
            {% endfor %}
        </div>
    </div>
</section>

{% if store.specials and store.specials|length > 0 %}
<section id="specials" class="py-16 bg-gray-800 border-t border-gray-700">
    <div class="container mx-auto px-6 text-center">
        <h2 class="text-4xl font-extrabold mb-10 text-white">Specials & Announcements</h2>
        <div class="space-y-6 max-w-3xl mx-auto">
            {% for special in store.specials[:3] %}
            <div class="bg-gray-700 border border-gray-600 p-6 rounded-lg shadow-md">
                <h3 class="text-2xl font-bold mb-2 text-white">{{ special.title }}</h3>
                <p class="text-gray-300 whitespace-pre-wrap">{{ special.content }}</p>
            </div>
            {% endfor %}
        </div>
    </div>
</section>
{% endif %}

<section id="contact" class="py-16 bg-gray-900">
    <div class="container mx-auto px-6">
        <h2 class="text-4xl font-extrabold text-center mb-10 text-white">Visit Us</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-12">
            <div class="bg-gray-800 border border-gray-700 p-8 rounded-lg shadow-lg">
                <div class="space-y-6 text-lg text-gray-200">
                    {% if store.address %}<div class="flex items-center gap-4"><i class="fas fa-map-marker-alt text-yellow-500 text-2xl w-8 text-center"></i><span>{{ store.address }}</span></div>{% endif %}
                    {% if store.hours %}<div class="flex items-center gap-4"><i class="fas fa-clock text-yellow-500 text-2xl w-8 text-center"></i><span>{{ store.hours | replace('\\n', '<br>') | safe }}</span></div>{% endif %}
                    {% if store.phone %}<div class="flex items-center gap-4"><i class="fas fa-phone text-yellow-500 text-2xl w-8 text-center"></i><a href="tel:{{ store.phone }}" class="hover:underline text-yellow-400">{{ store.phone_display or store.phone }}</a></div>{% endif %}
                </div>
                {% if store.socials %}
                <div class="mt-8 pt-6 border-t border-gray-600 flex justify-center space-x-6">
                    {% for social in store.socials %}
                    <a href="{{ social.url }}" target="_blank" rel="noopener noreferrer" class="text-gray-400 hover:text-yellow-500 text-3xl transition-transform transform hover:scale-110"><i class="fab fa-{{ social.icon }}"></i></a>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% if store.google_maps_embed_html %}
            <div class="rounded-lg shadow-lg overflow-hidden">
                {{ store.google_maps_embed_html | safe }}
            </div>
            {% endif %}
        </div>
    </div>
</section>
{% endblock %}
"""

ITEM_DETAILS_TEMPLATE = """
{% extends "layout" %}
{% block content %}
<div class="container mx-auto mt-10 px-4">
<div class="bg-gray-800 border border-gray-700 p-6 sm:p-8 rounded-lg shadow-xl max-w-4xl mx-auto">
    <a href="{{ url_for('store_home', store_slug=store.slug_id) }}#{{ business_config.section_label.lower().replace(' ', '-') }}" class="text-yellow-400 font-semibold hover:underline mb-6 inline-block">← Back to {{ business_config.section_label }}</a>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div><img src="{{ item.image_url or 'https://placehold.co/600x400/cccccc/ffffff?text=Image+Not+Available' }}" alt="{{ item.name }}" class="w-full h-auto object-cover rounded-lg shadow-md"></div>
        <div>
            <h1 class="text-3xl md:text-4xl font-extrabold text-white">{{ item.name }}</h1>
            <p class="text-3xl font-bold text-green-400 mt-4">${{ "%.2f"|format(item.price) }}</p>
            {% if item.status %}<p class="mt-2"><span class="px-3 py-1 rounded-full {{ 'bg-green-900 text-green-200 border border-green-700' if item.status == 'Available' else 'bg-red-900 text-red-200 border border-red-700' }}">{{ item.status }}</span></p>{% endif %}
            <div class="mt-6 border-t border-gray-600 pt-6">
                <h2 class="text-xl font-semibold mb-3 text-white">Description</h2>
                <p class="text-gray-300 whitespace-pre-wrap">{{ item.description or business_config.default_description }}</p>
            </div>
            <div class="mt-6 border-t border-gray-600 pt-6">
                 <h2 class="text-xl font-semibold mb-3 text-white">Details</h2>
                 <ul class="space-y-2 text-gray-300">
                     <li><strong class="text-white">{{ business_config.item_code_label }}:</strong> {{ item.item_code }}</li>
                     {% for key, value in item.attributes.items() %}
                     <li><strong class="text-white">{{ key }}:</strong> {{ value }}</li>
                     {% endfor %}
                 </ul>
            </div>
            
            <div id="contact-form" class="mt-8 border-t border-gray-600 pt-8 bg-gray-700 border border-gray-600 p-6 rounded-lg shadow-inner">
                <h2 class="text-2xl font-bold text-white mb-4">Have a Question?</h2>
                <form action="{{ url_for('submit_inquiry', store_slug=store.slug_id, item_id=item._id) }}" method="post" class="space-y-4">
                    <div>
                        <label for="customer_name" class="block text-sm font-medium text-gray-300">Your Name</label>
                        <input type="text" name="customer_name" id="customer_name" class="mt-1 block w-full px-3 py-2 bg-gray-800 border border-gray-600 text-white rounded-md shadow-sm focus:ring-yellow-500 focus:border-yellow-500" required>
                    </div>
                    <div>
                        <label for="customer_contact" class="block text-sm font-medium text-gray-300">Phone or Email</label>
                        <input type="text" name="customer_contact" id="customer_contact" class="mt-1 block w-full px-3 py-2 bg-gray-800 border border-gray-600 text-white rounded-md shadow-sm focus:ring-yellow-500 focus:border-yellow-500" required>
                    </div>
                    <div>
                        <label for="message" class="block text-sm font-medium text-gray-300">Message (Optional)</label>
                        <textarea name="message" id="message" rows="3" class="mt-1 block w-full px-3 py-2 bg-gray-800 border border-gray-600 text-white rounded-md shadow-sm focus:ring-yellow-500 focus:border-yellow-500" placeholder="Your message here..."></textarea>
                    </div>
                    <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-gray-900 bg-yellow-500 hover:bg-yellow-600">Submit Inquiry</button>
                </form>
            </div>
        </div>
    </div>
</div>
</div>
{% endblock %}
"""

# --- Admin Templates ---
DASHBOARD_TEMPLATE = """
{% extends "layout" %}
{% block content %}
<div class="container mx-auto px-4 mt-8 pb-12">
    <div class="flex flex-col sm:flex-row justify-between sm:items-center gap-4 mb-8">
        <div>
            <h1 class="text-4xl md:text-5xl font-extrabold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent mb-2">
                ✨ Admin Dashboard
            </h1>
            <p class="text-gray-300">Manage your store, items, and orders</p>
        </div>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div class="bg-gradient-to-br from-blue-500 to-cyan-500 rounded-2xl shadow-xl p-6 transform hover:scale-105 transition-all">
            <div class="flex items-center justify-between mb-4">
                <i class="fas fa-box text-3xl text-white opacity-80"></i>
                <span class="text-4xl font-bold text-white">{{ items_count or 0 }}</span>
            </div>
            <h3 class="text-lg font-semibold text-white">{{ business_config.item_plural }}</h3>
        </div>
        <div class="bg-gradient-to-br from-green-500 to-emerald-500 rounded-2xl shadow-xl p-6 transform hover:scale-105 transition-all">
            <div class="flex items-center justify-between mb-4">
                <i class="fas fa-star text-3xl text-white opacity-80"></i>
                <span class="text-4xl font-bold text-white">{{ specials_count or 0 }}</span>
            </div>
            <h3 class="text-lg font-semibold text-white">Specials</h3>
        </div>
        <div class="bg-gradient-to-br from-yellow-500 to-orange-500 rounded-2xl shadow-xl p-6 transform hover:scale-105 transition-all">
            <div class="flex items-center justify-between mb-4">
                <i class="fas fa-inbox text-3xl text-white opacity-80"></i>
                <span class="text-4xl font-bold text-white">{{ inquiries_count or 0 }}</span>
            </div>
            <h3 class="text-lg font-semibold text-white">{{ business_config.inquiry_label }}s</h3>
        </div>
        <div class="bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl shadow-xl p-6 transform hover:scale-105 transition-all">
            <div class="flex items-center justify-between mb-4">
                <i class="fas fa-palette text-3xl text-white opacity-80"></i>
                <span class="text-2xl font-bold text-white">Theme</span>
            </div>
            <h3 class="text-lg font-semibold text-white">Customize</h3>
        </div>
    </div>

    <!-- Quick Actions -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <a href="{{ url_for('admin_list_items', store_slug=store.slug_id) }}" 
           class="bg-gradient-to-br from-gray-800 to-gray-900 border-2 border-gray-700 rounded-2xl shadow-xl p-8 hover:shadow-2xl hover:border-blue-500 transform hover:scale-105 transition-all group">
            <div class="w-14 h-14 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center text-white text-2xl mb-4 shadow-lg group-hover:scale-110 transition-transform">
                <i class="fas fa-box"></i>
            </div>
            <h2 class="text-2xl font-bold mb-3 text-white">{{ business_config.section_label }}</h2>
            <p class="text-gray-300 mb-4">Manage your {{ business_config.item_plural.lower() }}</p>
            <div class="flex items-center gap-2 text-blue-400 font-semibold">
                <span>Manage</span>
                <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
            </div>
        </a>

        <a href="{{ url_for('admin_list_specials', store_slug=store.slug_id) }}" 
           class="bg-gradient-to-br from-gray-800 to-gray-900 border-2 border-gray-700 rounded-2xl shadow-xl p-8 hover:shadow-2xl hover:border-green-500 transform hover:scale-105 transition-all group">
            <div class="w-14 h-14 bg-gradient-to-br from-green-500 to-emerald-500 rounded-xl flex items-center justify-center text-white text-2xl mb-4 shadow-lg group-hover:scale-110 transition-transform">
                <i class="fas fa-star"></i>
            </div>
            <h2 class="text-2xl font-bold mb-3 text-white">Specials</h2>
            <p class="text-gray-300 mb-4">Create or update specials and announcements</p>
            <div class="flex items-center gap-2 text-green-400 font-semibold">
                <span>Manage</span>
                <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
            </div>
        </a>

        <a href="{{ url_for('admin_list_inquiries', store_slug=store.slug_id) }}" 
           class="bg-gradient-to-br from-gray-800 to-gray-900 border-2 border-gray-700 rounded-2xl shadow-xl p-8 hover:shadow-2xl hover:border-yellow-500 transform hover:scale-105 transition-all group">
            <div class="w-14 h-14 bg-gradient-to-br from-yellow-500 to-orange-500 rounded-xl flex items-center justify-center text-white text-2xl mb-4 shadow-lg group-hover:scale-110 transition-transform">
                <i class="fas fa-inbox"></i>
            </div>
            <h2 class="text-2xl font-bold mb-3 text-white">{{ business_config.inquiry_label }}s</h2>
            <p class="text-gray-300 mb-4">Review customer {{ business_config.inquiry_label.lower() }}s</p>
            <div class="flex items-center gap-2 text-yellow-400 font-semibold">
                <span>View</span>
                <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
            </div>
        </a>

        <a href="{{ url_for('admin_store_settings', store_slug=store.slug_id) }}" 
           class="bg-gradient-to-br from-gray-800 to-gray-900 border-2 border-gray-700 rounded-2xl shadow-xl p-8 hover:shadow-2xl hover:border-purple-500 transform hover:scale-105 transition-all group">
            <div class="w-14 h-14 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center text-white text-2xl mb-4 shadow-lg group-hover:scale-110 transition-transform">
                <i class="fas fa-palette"></i>
            </div>
            <h2 class="text-2xl font-bold mb-3 text-white">Settings</h2>
            <p class="text-gray-300 mb-4">Customize theme, logo, and branding</p>
            <div class="flex items-center gap-2 text-purple-400 font-semibold">
                <span>Customize</span>
                <i class="fas fa-arrow-right transform group-hover:translate-x-2 transition-transform"></i>
            </div>
        </a>
    </div>

    <!-- Store Management -->
    <div class="bg-gradient-to-br from-red-900/30 to-orange-900/30 border-2 border-red-500/30 rounded-2xl shadow-xl p-8 mb-8">
        <div class="flex items-center justify-between mb-6">
            <div>
                <h2 class="text-3xl font-bold text-white flex items-center gap-3">
                    <i class="fas fa-cog text-red-400"></i>
                    Store Management
                </h2>
                <p class="text-gray-300 mt-2">Factory controls for your store</p>
            </div>
        </div>
        <div class="space-y-4">
            <div class="bg-gray-900/50 border border-gray-700 rounded-lg p-6">
                <h3 class="text-xl font-bold text-white mb-3 flex items-center gap-2">
                    <i class="fas fa-redo text-orange-400"></i>
                    Reset Store Data
                </h3>
                <p class="text-gray-300 mb-4">Clear all store data (items, specials, inquiries) and reseed from defaults. This will restore your store to its initial state.</p>
                <form action="{{ url_for('admin_reset_store', store_slug=store.slug_id) }}" method="post" 
                      onsubmit="return confirm('⚠️ WARNING: This will delete ALL items, specials, and inquiries! This action cannot be undone. Continue?');">
                    <button type="submit" 
                            class="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-red-600 to-orange-600 hover:from-red-700 hover:to-orange-700 text-white font-bold rounded-xl shadow-lg transform hover:scale-105 transition-all">
                        <i class="fas fa-trash-alt"></i>
                        <span>Reset Store Data</span>
                    </button>
                </form>
                <p class="text-xs text-gray-400 mt-3">💡 Your store settings and admin account will be preserved.</p>
            </div>
        </div>
    </div>

    <!-- Recent Activity -->
    <div class="bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 rounded-2xl shadow-xl p-8">
        <h2 class="text-3xl font-bold mb-6 text-white flex items-center gap-3">
            <i class="fas fa-clock text-yellow-400"></i>
            Recent Activity
        </h2>
        <div class="space-y-4">
            <p class="text-gray-300">Recent inquiries and updates will appear here</p>
        </div>
    </div>
</div>
{% endblock %}
"""

ITEM_DASHBOARD_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="container mx-auto px-4 mt-8"><div class="flex flex-col sm:flex-row justify-between sm:items-center gap-4 mb-6"><h1 class="text-3xl md:text-4xl font-extrabold text-white">Manage {{ business_config.section_label }}</h1><div class="flex-shrink-0"><a href="{{ url_for('admin_dashboard', store_slug=store.slug_id) }}" class="text-gray-300 hover:underline mr-4">← Back</a><a href="{{ url_for('admin_add_item', store_slug=store.slug_id) }}" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md shadow-lg">+ Add {{ business_config.item_label }}</a></div></div><div class="bg-gray-800 border border-gray-700 p-2 sm:p-8 rounded-lg shadow-xl"><div class="hidden md:block overflow-x-auto"><table class="w-full text-left"><thead><tr class="bg-gray-700 border-b-2 border-gray-600"><th class="p-4 text-white">Name</th><th class="p-4 text-white">{{ business_config.item_code_label }}</th><th class="p-4 text-white">Price</th><th class="p-4 text-white">Status</th><th class="p-4 text-center text-white">Actions</th></tr></thead><tbody>{% for item in items %}<tr class="border-b border-gray-600 hover:bg-gray-700"><td class="p-4 font-medium text-white">{{ item.name }}</td><td class="p-4 text-gray-300">{{ item.item_code }}</td><td class="p-4 text-gray-300">${{ "%.2f"|format(item.price) }}</td><td class="p-4"><span class="px-2 py-1 rounded {{ 'bg-green-900 text-green-200 border border-green-700' if item.status == 'Available' else 'bg-red-900 text-red-200 border border-red-700' }}">{{ item.status or 'Available' }}</span></td><td class="p-4 text-center space-x-2"><a href="{{ url_for('admin_edit_item', store_slug=store.slug_id, item_id=item._id) }}" class="text-blue-400 hover:underline">Edit</a><form action="{{ url_for('admin_delete_item', store_slug=store.slug_id, item_id=item._id) }}" method="post" class="inline" onsubmit="return confirm('Delete this item permanently?');"><button type="submit" class="text-red-400 hover:underline">Delete</button></form></td></tr>{% else %}<tr><td colspan="5" class="text-center p-6 text-gray-400">No items. Add one to get started!</td></tr>{% endfor %}</tbody></table></div><div class="md:hidden space-y-4">{% for item in items %}<div class="border border-gray-600 rounded-lg p-4 bg-gray-700"><h3 class="font-bold text-lg text-white">{{ item.name }}</h3><p class="text-sm text-gray-300">{{ item.item_code }} - ${{ "%.2f"|format(item.price) }}</p><div class="mt-4 pt-3 border-t border-gray-600 flex justify-end items-center gap-4"><a href="{{ url_for('admin_edit_item', store_slug=store.slug_id, item_id=item._id) }}" class="text-sm text-blue-400 hover:underline">Edit</a><form action="{{ url_for('admin_delete_item', store_slug=store.slug_id, item_id=item._id) }}" method="post" class="inline" onsubmit="return confirm('Delete this item permanently?');"><button type="submit" class="text-sm text-red-400 hover:underline">Delete</button></form></div></div>{% else %}<p class="text-center p-6 text-gray-400">No items.</p>{% endfor %}</div></div></div>{% endblock %}"""

ITEM_FORM_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="container mx-auto px-4 mt-8"><div class="max-w-2xl mx-auto bg-gray-800 border border-gray-700 p-8 rounded-lg shadow-xl"><h1 class="text-3xl font-bold mb-6 text-white">{{ 'Edit' if item else 'Add New' }} {{ business_config.item_label }}</h1><form method="post" class="space-y-6"><div><label for="name" class="block text-sm font-medium text-gray-300">Name</label><input type="text" name="name" value="{{ item.name or '' }}" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" required></div><div class="grid grid-cols-1 md:grid-cols-2 gap-6"><div><label for="item_code" class="block text-sm font-medium text-gray-300">{{ business_config.item_code_label }} (Unique)</label><input type="text" name="item_code" value="{{ item.item_code or '' }}" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" required></div><div><label for="price" class="block text-sm font-medium text-gray-300">Price ($)</label><input type="number" step="0.01" name="price" value="{{ item.price or '' }}" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" required></div></div>{% if business_config.status_options %}<div><label for="status" class="block text-sm font-medium text-gray-300">Status</label><select name="status" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500">{% for status in business_config.status_options %}<option value="{{ status }}" {{ 'selected' if item and item.status == status else '' }}>{{ status }}</option>{% endfor %}</select></div>{% endif %}<div>{% for attr in business_config.attributes_template %}<div class="mt-4"><label for="attr_{{ attr.name }}" class="block text-sm font-medium text-gray-300">{{ attr.name }}</label>{% if attr.type == 'textarea' %}<textarea name="attr_{{ attr.name }}" rows="3" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" {% if attr.required %}required{% endif %}>{{ item.attributes.get(attr.name, '') if item else '' }}</textarea>{% else %}<input type="{{ attr.type }}" name="attr_{{ attr.name }}" value="{{ item.attributes.get(attr.name, '') if item else '' }}" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" {% if attr.required %}required{% endif %}></div>{% endif %}{% endfor %}</div><div><label for="image_url" class="block text-sm font-medium text-gray-300">Image URL</label><input type="url" name="image_url" value="{{ item.image_url or '' if item else '' }}" placeholder="https://..." class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500"></div><div><label for="description" class="block text-sm font-medium text-gray-300">Description</label><textarea name="description" rows="4" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500">{{ item.description or '' if item else '' }}</textarea></div><div class="flex items-center justify-end gap-4 pt-4 border-t border-gray-600"><a href="{{ url_for('admin_list_items', store_slug=store.slug_id) }}" class="text-gray-300 hover:underline">Cancel</a><button type="submit" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md">{{ 'Save Changes' if item else 'Add ' + business_config.item_label }}</button></div></form></div></div>{% endblock %}"""

SPECIALS_DASHBOARD_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="container mx-auto px-4 mt-8"><div class="flex flex-col sm:flex-row justify-between sm:items-center gap-4 mb-6"><h1 class="text-3xl md:text-4xl font-extrabold text-white">Specials & Announcements</h1><div class="flex-shrink-0"><a href="{{ url_for('admin_dashboard', store_slug=store.slug_id) }}" class="text-gray-300 hover:underline mr-4">← Back</a><a href="{{ url_for('admin_add_special', store_slug=store.slug_id) }}" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md shadow-lg">+ Add Special</a></div></div><div class="bg-gray-800 border border-gray-700 p-6 sm:p-8 rounded-lg shadow-xl"><div class="space-y-6">{% for special in specials %}<div class="flex flex-col sm:flex-row items-start gap-4 {% if not loop.last %}border-b border-gray-600 pb-6{% endif %}"><div class="flex-grow"><h2 class="text-xl font-bold text-white">{{ special.title }}</h2><p class="text-sm text-gray-400">{{ special.date_created.strftime('%B %d, %Y') }}</p><p class="text-gray-300 mt-2 whitespace-pre-wrap">{{ special.content }}</p></div><div class="flex-shrink-0 flex items-center gap-4 mt-2 sm:mt-0"><a href="{{ url_for('admin_edit_special', store_slug=store.slug_id, special_id=special._id) }}" class="text-blue-400 hover:underline">Edit</a><form action="{{ url_for('admin_delete_special', store_slug=store.slug_id, special_id=special._id) }}" method="post" onsubmit="return confirm('Delete this special?');"><button type="submit" class="text-red-400 hover:underline">Delete</button></form></div></div>{% else %}<p class="text-center text-gray-400">No specials. Add one to get started!</p>{% endfor %}</div></div></div>{% endblock %}"""

SPECIAL_FORM_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="container mx-auto px-4 mt-8"><div class="max-w-2xl mx-auto bg-gray-800 border border-gray-700 p-8 rounded-lg shadow-xl"><h1 class="text-3xl font-bold mb-6 text-white">{{ 'Edit' if special else 'Add New' }} Special</h1><form method="post" class="space-y-6"><div><label for="title" class="block text-sm font-medium text-gray-300">Title</label><input type="text" name="title" value="{{ special.title or '' if special else '' }}" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" required></div><div><label for="content" class="block text-sm font-medium text-gray-300">Content</label><textarea name="content" rows="6" class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" required>{{ special.content or '' if special else '' }}</textarea></div><div class="flex items-center justify-end gap-4 pt-4 border-t border-gray-600"><a href="{{ url_for('admin_list_specials', store_slug=store.slug_id) }}" class="text-gray-300 hover:underline">Cancel</a><button type="submit" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md">{{ 'Save Changes' if special else 'Create Special' }}</button></div></form></div></div>{% endblock %}"""

LOGIN_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="container mx-auto px-4 mt-16"><div class="max-w-md mx-auto bg-gray-800 border border-gray-700 p-8 rounded-lg shadow-xl"><h1 class="text-3xl font-bold mb-6 text-center text-white">Login for {{ store.name }}</h1>{% if demo_credentials %}<div class="mb-6 p-4 bg-yellow-900/30 border border-yellow-700 rounded-lg"><h3 class="text-lg font-bold text-yellow-400 mb-2 flex items-center gap-2"><i class="fas fa-info-circle"></i> Demo Store Credentials</h3><p class="text-sm text-yellow-200 mb-3">This is a demo store. Use these credentials to login:</p><div class="bg-gray-900 border border-gray-700 rounded p-3 space-y-2"><div><span class="text-gray-400 text-sm">Email:</span> <code class="text-yellow-300 font-mono">{{ demo_credentials.email }}</code></div><div><span class="text-gray-400 text-sm">Password:</span> <code class="text-yellow-300 font-mono">{{ demo_credentials.password }}</code></div></div><p class="text-xs text-yellow-300 mt-3 italic">These are demo credentials for testing purposes only.</p></div>{% endif %}<form method="post" class="space-y-4"><div><label for="email" class="block text-sm font-medium text-gray-300">Email</label><input type="email" name="email" id="email" {% if demo_credentials %}value="{{ demo_credentials.email }}"{% endif %} class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" required></div><div><label for="password" class="block text-sm font-medium text-gray-300">Password</label><input type="password" name="password" id="password" {% if demo_credentials %}value="{{ demo_credentials.password }}"{% endif %} class="mt-1 block w-full px-3 py-2 bg-gray-700 border border-gray-600 text-white rounded-md focus:ring-yellow-500 focus:border-yellow-500" required></div><button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-700 hover:bg-yellow-500 hover:text-gray-900 transition-colors">Sign In</button></form></div></div>{% endblock %}"""

INQUIRIES_DASHBOARD_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="container mx-auto px-4 mt-8"><div class="flex flex-col sm:flex-row justify-between sm:items-center gap-4 mb-6"><h1 class="text-3xl md:text-4xl font-extrabold text-white">{{ business_config.inquiry_label }}s</h1><a href="{{ url_for('admin_dashboard', store_slug=store.slug_id) }}" class="text-gray-300 hover:underline flex-shrink-0">← Back</a></div><div class="bg-gray-800 border border-gray-700 p-4 sm:p-8 rounded-lg shadow-xl"><div class="space-y-6">{% for inquiry in inquiries %}<div class="border border-gray-600 rounded-lg p-4 bg-gray-700 flex flex-col md:flex-row gap-4 justify-between {% if inquiry.status == 'New' %}border-l-4 border-yellow-400{% endif %}"><div class="flex-grow"><div><span class="text-xs text-gray-400">{{ inquiry.date_submitted.strftime('%b %d, %Y %I:%M %p') }} UTC</span></div><p class="font-bold text-lg mt-1 text-white">{{ inquiry.customer_name }} - <span class="font-normal text-gray-300">{{ inquiry.customer_contact }}</span></p><p class="mt-2 text-gray-200 bg-gray-800 border border-gray-600 p-3 rounded-md shadow-inner">"{{ inquiry.message or 'No message provided.' }}"</p><p class="mt-3 text-sm text-gray-300">Inquiry for: <a href="{{ url_for('item_details', store_slug=store.slug_id, item_id=inquiry.item_id) }}" target="_blank" class="text-blue-400 hover:underline">{{ inquiry.item_name }}</a></p></div><div class="flex-shrink-0 flex items-center md:items-start gap-4 self-end md:self-center"><form action="{{ url_for('admin_delete_inquiry', store_slug=store.slug_id, inquiry_id=inquiry._id) }}" method="post" onsubmit="return confirm('Delete this inquiry permanently?');"><button type="submit" class="text-red-400 hover:underline font-semibold">Delete</button></form></div></div>{% else %}<p class="text-center p-6 text-gray-400">No inquiries yet.</p>{% endfor %}</div></div></div>{% endblock %}"""

STORE_SELECTION_TEMPLATE = """
<!doctype html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <title>Select or Create Store - {{ business_type_name }}</title>
    <style>
        * { font-family: 'Poppins', sans-serif; }
        .store-card {
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        }
        .store-card:hover {
            transform: translateY(-8px) scale(1.02);
            box-shadow: 0 20px 40px -12px rgba(59, 130, 246, 0.4);
            border-color: #3b82f6;
            background: linear-gradient(135deg, #334155 0%, #1e293b 100%);
        }
        .form-section {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        }
        input:focus, textarea:focus, select:focus {
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.3);
        }
    </style>
</head>
<body class="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 min-h-screen">
    <div class="container mx-auto px-6 py-12">
        <div class="text-center mb-12">
            <a href="{{ url_for('create_store_flow') }}" class="inline-flex items-center gap-2 mb-6 text-indigo-400 hover:text-indigo-300 font-semibold transition-colors">
                <i class="fas fa-arrow-left"></i> 
                <span>Back to Create Store</span>
            </a>
            <h1 class="text-5xl md:text-6xl font-extrabold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent mb-4">
                {{ business_type_name }}
            </h1>
            <p class="text-xl text-gray-300 max-w-2xl mx-auto font-medium">Select an existing store or create a new one to get started</p>
        </div>
        
        <div class="max-w-7xl mx-auto">
            <div class="form-section rounded-2xl shadow-2xl p-8 md:p-12 mb-10 border border-gray-700">
                <div class="flex items-center gap-4 mb-8">
                    <div class="w-12 h-12 bg-gradient-to-br from-green-400 to-green-600 rounded-xl flex items-center justify-center text-white text-xl shadow-lg">
                        <i class="fas fa-plus"></i>
                    </div>
                    <div>
                        <h2 class="text-3xl font-bold text-white">Create New Store</h2>
                        <p class="text-gray-300">Fill out the form below to set up your store</p>
                    </div>
                </div>
                
                <form id="create-store-form" method="post" action="{{ url_for('create_store', business_type=business_type) }}" class="space-y-8">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div class="space-y-2">
                            <label for="name" class="block text-sm font-semibold text-gray-300">
                                Store Name <span class="text-red-400">*</span>
                            </label>
                            <input type="text" name="name" id="name" required 
                                   class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                                   placeholder="My Awesome {{ business_type_name }}"
                                   value="">
                            <p class="text-xs text-gray-400 mt-1">💡 Start typing and the URL slug will auto-generate!</p>
                        </div>
                        <div class="space-y-2">
                            <label for="slug_id" class="block text-sm font-semibold text-gray-300">
                                URL Slug <span class="text-red-400">*</span>
                                <button type="button" id="generate-slug" class="ml-2 text-xs text-indigo-400 hover:text-indigo-300">
                                    <i class="fas fa-magic"></i> Auto-Generate
                                </button>
                            </label>
                            <input type="text" name="slug_id" id="slug_id" required 
                                   class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                                   placeholder="my-awesome-store" pattern="[a-z0-9-]+" title="Only lowercase letters, numbers, and hyphens">
                            <p class="text-xs text-gray-400 mt-1 flex items-center gap-1">
                                <i class="fas fa-info-circle"></i>
                                Your store URL: <code class="bg-gray-700 px-1 rounded">/your-slug-here</code>
                            </p>
                        </div>
                    </div>
                    
                    <div class="bg-blue-900/20 border border-blue-500/30 rounded-xl p-4 mb-4">
                        <p class="text-sm text-blue-300 flex items-center gap-2">
                            <i class="fas fa-lightbulb"></i>
                            <strong>Quick Tip:</strong> Fill in the store name first - we'll help you with the rest!
                        </p>
                    </div>
                    
                    <div class="space-y-2">
                        <label for="tagline" class="block text-sm font-semibold text-gray-300">
                            Tagline 
                            <span class="text-xs text-gray-400 font-normal">(Optional - appears on homepage)</span>
                        </label>
                        <input type="text" name="tagline" id="tagline" 
                               class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                               placeholder="{% if business_type == 'restaurant' %}Delicious Food & Great Service{% elif business_type == 'auto-sales' %}Quality Vehicles at Great Prices{% elif business_type == 'auto-services' %}Professional Auto Services You Can Trust{% else %}Quality Products You'll Love{% endif %}">
                    </div>
                    
                    <div class="space-y-2">
                        <label for="about_text" class="block text-sm font-semibold text-gray-300">
                            About Your Store
                            <span class="text-xs text-gray-400 font-normal">(Optional)</span>
                        </label>
                        <textarea name="about_text" id="about_text" rows="4" 
                                  class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all resize-none"
                                  placeholder="{% if business_type == 'restaurant' %}We serve delicious meals made with fresh, locally-sourced ingredients.{% elif business_type == 'auto-sales' %}We specialize in quality pre-owned vehicles with full inspection and warranty options.{% elif business_type == 'auto-services' %}Full-service auto repair and maintenance with certified technicians.{% else %}A wide variety of quality products for all your needs.{% endif %}"></textarea>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div class="space-y-2">
                            <label for="address" class="block text-sm font-semibold text-gray-300">
                                Address
                                <span class="text-xs text-gray-400 font-normal">(Optional)</span>
                            </label>
                            <input type="text" name="address" id="address" 
                                   class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                                   placeholder="123 Main St, City, State 12345">
                        </div>
                        <div class="space-y-2">
                            <label for="phone" class="block text-sm font-semibold text-gray-300">
                                Phone
                                <span class="text-xs text-gray-400 font-normal">(Optional)</span>
                            </label>
                            <input type="tel" name="phone" id="phone" 
                                   class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                                   placeholder="(555) 123-4567">
                        </div>
                    </div>
                    
                    <div class="space-y-2">
                        <label for="hours" class="block text-sm font-semibold text-gray-300">
                            Business Hours
                            <span class="text-xs text-gray-400 font-normal">(Optional)</span>
                        </label>
                        <textarea name="hours" id="hours" rows="3" 
                                  class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all resize-none"
                                  placeholder="Monday-Friday: 9am-5pm&#10;Saturday: 10am-3pm&#10;Sunday: Closed"></textarea>
                        <p class="text-xs text-gray-400 mt-1">💡 Press Enter for new lines</p>
                    </div>
                    
                    <div class="border-t-2 border-gray-600 pt-8">
                        <h3 class="text-lg font-bold text-white mb-6 flex items-center gap-2">
                            <i class="fas fa-user-shield text-indigo-400"></i>
                            Admin Account Setup
                        </h3>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div class="space-y-2">
                                <label for="email" class="block text-sm font-semibold text-gray-300">Admin Email <span class="text-red-400">*</span></label>
                                <input type="email" name="email" id="email" required 
                                       class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                                       placeholder="owner@example.com">
                                <p class="text-xs text-gray-400 mt-1">Used for admin dashboard login</p>
                            </div>
                            <div class="space-y-2">
                                <label for="password" class="block text-sm font-semibold text-gray-300">Admin Password <span class="text-red-400">*</span></label>
                                <input type="password" name="password" id="password" required 
                                       class="w-full px-4 py-3 bg-gray-800 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                                       placeholder="Choose a strong password">
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex items-center justify-end gap-4 pt-6 border-t-2 border-gray-600">
                        <a href="{{ url_for('create_store_flow') }}" class="px-6 py-3 text-gray-300 hover:text-gray-100 font-semibold transition-colors">
                            Cancel
                        </a>
                        <button type="submit" class="inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold rounded-xl shadow-xl transform hover:scale-105 transition-all">
                            <i class="fas fa-magic"></i>
                            <span>✨ Create Store</span>
                            <i class="fas fa-arrow-right"></i>
                        </button>
                    </div>
                </form>
            </div>
            
            <script>
                // Auto-generate slug from store name
                const nameInput = document.getElementById('name');
                const slugInput = document.getElementById('slug_id');
                const generateSlugBtn = document.getElementById('generate-slug');
                
                function generateSlug(text) {
                    return text.toLowerCase()
                        .trim()
                        .replace(/[^\w\s-]/g, '') // Remove special chars
                        .replace(/[\s_-]+/g, '-')  // Replace spaces/underscores with hyphens
                        .replace(/^-+|-+$/g, '');   // Remove leading/trailing hyphens
                }
                
                // Auto-generate slug as user types
                nameInput.addEventListener('input', function() {
                    if (nameInput.value && !slugInput.value) {
                        slugInput.value = generateSlug(nameInput.value);
                    }
                });
                
                // Manual generate button
                generateSlugBtn.addEventListener('click', function() {
                    if (nameInput.value) {
                        slugInput.value = generateSlug(nameInput.value);
                        slugInput.focus();
                    } else {
                        alert('Please enter a store name first!');
                        nameInput.focus();
                    }
                });
                
                // Add visual feedback
                slugInput.addEventListener('input', function() {
                    if (slugInput.value && /^[a-z0-9-]+$/.test(slugInput.value)) {
                        slugInput.classList.remove('border-red-500');
                        slugInput.classList.add('border-green-500');
                    } else {
                        slugInput.classList.remove('border-green-500');
                        slugInput.classList.add('border-red-500');
                    }
                });
                
                // Focus on name input when page loads
                window.addEventListener('load', function() {
                    nameInput.focus();
                });
            </script>
            
            {% if existing_stores|length > 0 %}
            <div class="bg-gray-800 border border-gray-700 rounded-2xl shadow-2xl p-8 md:p-12">
                <div class="flex items-center gap-4 mb-8">
                    <div class="w-12 h-12 bg-gradient-to-br from-blue-400 to-blue-600 rounded-xl flex items-center justify-center text-white text-xl shadow-lg">
                        <i class="fas fa-store"></i>
                    </div>
                    <div>
                        <h2 class="text-3xl font-bold text-white">Existing Stores</h2>
                        <p class="text-gray-300">Click on any store to visit it</p>
                    </div>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {% for store in existing_stores %}
                    <a href="{{ url_for('store_home', store_slug=store.slug_id) }}" 
                       class="store-card rounded-xl shadow-lg p-6 block border-2 border-gray-600 hover:border-indigo-400 group">
                        <div class="flex items-start justify-between mb-4">
                            <h3 class="text-2xl font-bold text-white group-hover:text-indigo-400 transition-colors">{{ store.name }}</h3>
                            <i class="fas fa-arrow-right text-gray-400 group-hover:text-indigo-400 transform group-hover:translate-x-1 transition-all"></i>
                        </div>
                        <p class="text-sm text-gray-300 mb-4 font-medium">{{ store.tagline or 'No tagline set' }}</p>
                        {% if store.address %}
                        <p class="text-xs text-gray-400 mb-2 flex items-center gap-2">
                            <i class="fas fa-map-marker-alt text-indigo-400"></i>
                            <span>{{ store.address[:40] }}{% if store.address|length > 40 %}...{% endif %}</span>
                        </p>
                        {% endif %}
                        <div class="mt-4 pt-4 border-t border-gray-600">
                            <span class="text-sm text-indigo-400 font-semibold">Visit Store →</span>
                        </div>
                    </a>
                    {% endfor %}
                </div>
            </div>
            {% else %}
            <div class="bg-gray-800 border border-gray-700 rounded-2xl shadow-xl p-12 text-center">
                <i class="fas fa-store text-6xl text-gray-500 mb-4"></i>
                <h3 class="text-2xl font-bold text-white mb-2">No Stores Yet</h3>
                <p class="text-gray-300">Be the first to create a {{ business_type_name }} store!</p>
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

STORE_LIST_TEMPLATE = """
<!doctype html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <title>Browse Stores - StoreFactory</title>
    <style>
        * { font-family: 'Poppins', sans-serif; }
    </style>
</head>
<body class="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 min-h-screen">
    <div class="container mx-auto px-6 py-16">
        <div class="text-center mb-12">
            <h1 class="text-5xl md:text-6xl font-extrabold text-white mb-4">
                Welcome to <span class="bg-gradient-to-r from-yellow-300 to-orange-300 bg-clip-text text-transparent">StoreFactory</span>
            </h1>
            <p class="text-xl text-gray-300 max-w-2xl mx-auto mb-8">Browse all stores or create your own</p>
            <a href="{{ url_for('create_store_flow') }}" 
               class="inline-flex items-center gap-3 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold py-4 px-8 rounded-xl shadow-lg transform hover:scale-105 transition-all">
                <i class="fas fa-plus-circle"></i>
                <span>Create New Store</span>
            </a>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            {% for store in stores %}
            <a href="{{ url_for('store_home', store_slug=store.slug_id) }}" 
               class="bg-gray-800 border border-gray-700 rounded-xl shadow-lg p-6 hover:shadow-xl hover:border-indigo-500 transition-all transform hover:-translate-y-1">
                <h2 class="text-2xl font-bold mb-2 text-white">{{ store.name }}</h2>
                <p class="text-gray-300 mb-2">{{ BUSINESS_TYPES[store.business_type]['name'] if store.business_type in BUSINESS_TYPES else 'Store' }}</p>
                {% if store.tagline %}
                <p class="text-sm text-gray-400 mb-2 italic">"{{ store.tagline }}"</p>
                {% endif %}
                <p class="text-sm text-gray-400 mt-2">{{ store.address or 'No address' }}</p>
                <div class="mt-4 pt-3 border-t border-gray-700">
                    <span class="text-sm text-indigo-400 font-semibold">Visit Store →</span>
                </div>
            </a>
            {% else %}
            <div class="col-span-full text-center py-12">
                <i class="fas fa-store text-6xl text-gray-600 mb-4"></i>
                <p class="text-xl text-gray-400 mb-4">No stores found.</p>
                <a href="{{ url_for('create_store_flow') }}" class="text-indigo-400 hover:text-indigo-300 font-semibold">Create the first store →</a>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""

# --- Helper Functions & Decorators ---
def render_page(template_string, **context):
    """Renders a page by injecting content into the base layout."""
    context['now'] = datetime.datetime.utcnow()
    context['store'] = g.store
    context['business_config'] = BUSINESS_TYPES.get(g.store.get('business_type', 'generic-store'), BUSINESS_TYPES['generic-store'])
    
    # Fetch specials
    if g.store:
        context['specials'] = list(db.specials.find({"store_id": g.store['_id']}).sort("date_created", -1))
    
    if '{% extends "layout" %}' in template_string:
        content_block = template_string.split('{% extends "layout" %}', 1)[-1]
    else:
        content_block = template_string
    
    full_html = LAYOUT_TEMPLATE.replace("{% block content %}{% endblock %}", content_block)
    return render_template_string(full_html, **context)

def owner_required(f):
    """Decorator to ensure a route is accessed only by the logged-in store owner."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.store:
            abort(404)
        if ('user_id' not in session or 'store_id' not in session or
            session['store_id'] != str(g.store['_id'])):
            flash('You must be logged in as the owner to view this page.', 'error')
            return redirect(url_for('admin_login', store_slug=g.store['slug_id']))
        return f(*args, **kwargs)
    return decorated_function

# --- Global & Pre-Request Logic ---
@app.before_request
def load_store():
    """Load the store object from the database before each request (if store_slug is provided)."""
    store_slug = request.view_args.get('store_slug') if request.view_args else None
    if store_slug:
        g.store = db.stores.find_one({"slug_id": store_slug})
        if not g.store:
            abort(404, description=f"Store with slug '{store_slug}' not found.")

# --- Root Routes ---
@app.route('/')
def home():
    """Default to browse stores page."""
    return redirect(url_for('list_stores'))

@app.route('/create')
def create_store_flow():
    """Business type selection page for creating a new store."""
    return render_template_string(BUSINESS_SELECTION_TEMPLATE)

@app.route('/select/<business_type>')
def select_business(business_type):
    """Show store selection/creation page for a business type."""
    if business_type not in BUSINESS_TYPES:
        flash('Invalid business type selected.', 'error')
        return redirect(url_for('create_store_flow'))
    
    # Get existing stores for this business type
    existing_stores = list(db.stores.find({"business_type": business_type}).sort("name", 1))
    
    business_config = BUSINESS_TYPES[business_type]
    return render_template_string(
        STORE_SELECTION_TEMPLATE,
        business_type=business_type,
        business_type_name=business_config['name'],
        existing_stores=existing_stores,
        BUSINESS_TYPES=BUSINESS_TYPES
    )

def seed_default_data(store_id, business_type):
    """Seed default demo items and specials for a new store."""
    business_config = BUSINESS_TYPES.get(business_type, BUSINESS_TYPES['generic-store'])
    now = datetime.datetime.utcnow()
    
    # Default items based on business type
    default_items = []
    if business_type == 'restaurant':
        default_items = [
            {
                "name": "Classic Burger",
                "item_code": f"{business_config['item_code_prefix']}-001",
                "price": 12.99,
                "description": "Juicy beef patty with fresh lettuce, tomato, and our special sauce on a toasted bun.",
                "status": "Available",
                "attributes": {"Category": "Main Course", "Ingredients": "Beef, Lettuce, Tomato, Cheese", "Allergens": "Gluten, Dairy"},
                "image_url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Margherita Pizza",
                "item_code": f"{business_config['item_code_prefix']}-002",
                "price": 15.99,
                "description": "Traditional Italian pizza with fresh mozzarella, basil, and tomato sauce.",
                "status": "Available",
                "attributes": {"Category": "Main Course", "Ingredients": "Dough, Mozzarella, Basil, Tomato Sauce", "Allergens": "Gluten, Dairy"},
                "image_url": "https://images.unsplash.com/photo-1574071318508-1cdbab80d002?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Caesar Salad",
                "item_code": f"{business_config['item_code_prefix']}-003",
                "price": 9.99,
                "description": "Fresh romaine lettuce with Caesar dressing, parmesan cheese, and croutons.",
                "status": "Available",
                "attributes": {"Category": "Salad", "Ingredients": "Romaine, Caesar Dressing, Parmesan, Croutons", "Allergens": "Dairy, Gluten"},
                "image_url": "https://images.unsplash.com/photo-1546793665-c74683f339c1?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Chocolate Lava Cake",
                "item_code": f"{business_config['item_code_prefix']}-004",
                "price": 7.99,
                "description": "Warm chocolate cake with a molten center, served with vanilla ice cream.",
                "status": "Available",
                "attributes": {"Category": "Dessert", "Ingredients": "Chocolate, Flour, Eggs, Butter", "Allergens": "Gluten, Dairy, Eggs"},
                "image_url": "https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Fresh Lemonade",
                "item_code": f"{business_config['item_code_prefix']}-005",
                "price": 4.99,
                "description": "Refreshing homemade lemonade made with fresh lemons.",
                "status": "Available",
                "attributes": {"Category": "Beverage", "Ingredients": "Lemons, Sugar, Water", "Allergens": "None"},
                "image_url": "https://images.unsplash.com/photo-1523677011783-c91d1bbe2dcf?w=800",
                "store_id": store_id,
                "date_added": now
            }
        ]
    elif business_type == 'auto-sales':
        default_items = [
            {
                "name": "2020 Honda Accord",
                "item_code": f"{business_config['item_code_prefix']}-001",
                "price": 24999.00,
                "description": "Well-maintained sedan with low mileage and excellent fuel economy.",
                "status": "Available",
                "attributes": {"Make": "Honda", "Model": "Accord", "Year": "2020", "Mileage": "35000", "Color": "Silver", "Condition": "Excellent"},
                "image_url": "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "2019 Toyota Camry",
                "item_code": f"{business_config['item_code_prefix']}-002",
                "price": 22999.00,
                "description": "Reliable and spacious family sedan with great safety features.",
                "status": "Available",
                "attributes": {"Make": "Toyota", "Model": "Camry", "Year": "2019", "Mileage": "42000", "Color": "White", "Condition": "Very Good"},
                "image_url": "https://images.unsplash.com/photo-1617486496723-e46bd3c9bd9d?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "2021 Ford F-150",
                "item_code": f"{business_config['item_code_prefix']}-003",
                "price": 35999.00,
                "description": "Powerful pickup truck perfect for work or adventure.",
                "status": "Available",
                "attributes": {"Make": "Ford", "Model": "F-150", "Year": "2021", "Mileage": "28000", "Color": "Black", "Condition": "Excellent"},
                "image_url": "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=800",
                "store_id": store_id,
                "date_added": now
            }
        ]
    elif business_type == 'auto-services':
        default_items = [
            {
                "name": "Full Service Oil Change",
                "item_code": f"{business_config['item_code_prefix']}-001",
                "price": 49.99,
                "description": "Complete oil change service with premium oil and filter replacement.",
                "status": "Available",
                "attributes": {"Service Type": "Maintenance", "Duration": "30 minutes", "Warranty": "3 months", "Includes": "Oil change, filter replacement, fluid check"},
                "image_url": "https://images.unsplash.com/photo-1581092160562-40aa08e78837?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Brake Inspection & Service",
                "item_code": f"{business_config['item_code_prefix']}-002",
                "price": 89.99,
                "description": "Comprehensive brake inspection and necessary adjustments or repairs.",
                "status": "Available",
                "attributes": {"Service Type": "Repair", "Duration": "1-2 hours", "Warranty": "6 months", "Includes": "Inspection, adjustment, pad replacement if needed"},
                "image_url": "https://images.unsplash.com/photo-1486262715619-67b85e0b08d3?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Engine Diagnostic",
                "item_code": f"{business_config['item_code_prefix']}-003",
                "price": 79.99,
                "description": "Complete engine diagnostic scan to identify any issues.",
                "status": "Available",
                "attributes": {"Service Type": "Diagnostic", "Duration": "1 hour", "Warranty": "N/A", "Includes": "Computer scan, report, recommendations"},
                "image_url": "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?w=800",
                "store_id": store_id,
                "date_added": now
            }
        ]
    elif business_type == 'other-services':
        default_items = [
            {
                "name": "Basic Consultation",
                "item_code": f"{business_config['item_code_prefix']}-001",
                "price": 99.00,
                "description": "One-on-one consultation to discuss your needs and provide recommendations.",
                "status": "Available",
                "attributes": {"Service Type": "Consultation", "Duration": "1 hour", "What's Included": "Initial meeting, needs assessment, recommendations"},
                "image_url": "https://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Standard Service Package",
                "item_code": f"{business_config['item_code_prefix']}-002",
                "price": 299.00,
                "description": "Comprehensive service package tailored to your requirements.",
                "status": "Available",
                "attributes": {"Service Type": "Package", "Duration": "2-3 hours", "What's Included": "Full service, follow-up, support"},
                "image_url": "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Premium Service",
                "item_code": f"{business_config['item_code_prefix']}-003",
                "price": 499.00,
                "description": "Premium service with extended support and priority handling.",
                "status": "Available",
                "attributes": {"Service Type": "Premium", "Duration": "4-6 hours", "What's Included": "Premium service, priority support, extended warranty"},
                "image_url": "https://images.unsplash.com/photo-1552664730-d307ca884978?w=800",
                "store_id": store_id,
                "date_added": now
            }
        ]
    else:  # generic-store
        default_items = [
            {
                "name": "Premium Product",
                "item_code": f"{business_config['item_code_prefix']}-001",
                "price": 49.99,
                "description": "High-quality product with excellent value.",
                "status": "Available",
                "attributes": {"Category": "General", "Brand": "Premium", "Color": "Black", "Size": "Standard", "Material": "Quality"},
                "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Deluxe Edition",
                "item_code": f"{business_config['item_code_prefix']}-002",
                "price": 79.99,
                "description": "Upgraded version with additional features.",
                "status": "Available",
                "attributes": {"Category": "Premium", "Brand": "Deluxe", "Color": "Silver", "Size": "Large", "Material": "Premium"},
                "image_url": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=800",
                "store_id": store_id,
                "date_added": now
            },
            {
                "name": "Standard Option",
                "item_code": f"{business_config['item_code_prefix']}-003",
                "price": 29.99,
                "description": "Great value option for everyday use.",
                "status": "Available",
                "attributes": {"Category": "Standard", "Brand": "Standard", "Color": "Blue", "Size": "Medium", "Material": "Standard"},
                "image_url": "https://images.unsplash.com/photo-1468495244123-6c6c332eeece?w=800",
                "store_id": store_id,
                "date_added": now
            }
        ]
    
    # Default specials for all business types
    default_specials = [
        {
            "title": "Grand Opening Special!",
            "content": "Welcome to our store! Check out our amazing selection and get started today. We're excited to serve you!",
            "store_id": store_id,
            "date_created": now
        },
        {
            "title": "New Customer Discount",
            "content": "New customers get 10% off their first order! Mention this special when placing your order.",
            "store_id": store_id,
            "date_created": now
        }
    ]
    
    # Insert items
    if default_items:
        db.items.insert_many(default_items)
    
    # Insert specials
    if default_specials:
        db.specials.insert_many(default_specials)

@app.route('/create/<business_type>', methods=['POST'])
def create_store(business_type):
    """Handle store creation."""
    if business_type not in BUSINESS_TYPES:
        flash('Invalid business type selected.', 'error')
        return redirect(url_for('create_store_flow'))
    
    form = request.form
    
    # Generate slug_id if not provided
    slug_id = form.get('slug_id', '').strip().lower()
    if not slug_id:
        # Auto-generate from name
        slug_id = form.get('name', '').lower().replace(' ', '-')
        slug_id = ''.join(c for c in slug_id if c.isalnum() or c == '-')
    
    # Validate slug_id
    if not slug_id or not all(c.isalnum() or c == '-' for c in slug_id):
        flash('Invalid URL slug. Use only lowercase letters, numbers, and hyphens.', 'error')
        return redirect(url_for('select_business', business_type=business_type))
    
    # Check if slug_id already exists
    if db.stores.find_one({"slug_id": slug_id}):
        flash(f'A store with URL slug "{slug_id}" already exists. Please choose a different one.', 'error')
        return redirect(url_for('select_business', business_type=business_type))
    
    # Create store with theme defaults
    store_data = {
        "name": form.get('name'),
        "slug_id": slug_id,
        "business_type": business_type,
        "tagline": form.get('tagline'),
        "about_text": form.get('about_text'),
        "address": form.get('address'),
        "phone": form.get('phone'),
        "phone_display": form.get('phone'),
        "hours": form.get('hours'),
        "lang": "en",
        "hero_image_url": None,
        "logo_url": None,
        "gallery_image_1_url": None,
        "gallery_image_2_url": None,
        "menu_image_url": None,
        "google_maps_embed_html": None,
        "inventory_description": None,
        "socials": [],
        # Theme defaults
        "theme_primary": form.get('theme_primary', '#3b82f6'),
        "theme_secondary": form.get('theme_secondary', '#f59e0b'),
        "theme_background": form.get('theme_background', '#111827'),
        "theme_surface": form.get('theme_surface', '#1f2937'),
        "theme_text": form.get('theme_text', '#f9fafb'),
        "theme_text_secondary": form.get('theme_text_secondary', '#d1d5db'),
        "date_created": datetime.datetime.utcnow()
    }
    
    try:
        store_id = db.stores.insert_one(store_data).inserted_id
        
        # Create admin user
        db.users.insert_one({
            "email": form.get('email'),
            "password": form.get('password'),  # In production, hash this!
            "role": "owner",
            "store_id": store_id,
            "date_created": datetime.datetime.utcnow()
        })
        
        # Seed default demo data
        seed_default_data(store_id, business_type)
        
        flash(f'Store "{store_data["name"]}" created successfully with demo data!', 'success')
        return redirect(url_for('download_store', store_slug=slug_id))
    except DuplicateKeyError:
        flash(f'A store with URL slug "{slug_id}" already exists. Please choose a different one.', 'error')
        return redirect(url_for('select_business', business_type=business_type))

DOWNLOAD_STORE_TEMPLATE = """
<!doctype html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <title>Download {{ store.name }} - StoreFactory</title>
    <style>
        * { font-family: 'Poppins', sans-serif; }
    </style>
</head>
<body class="bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 min-h-screen">
    <div class="container mx-auto px-6 py-16">
        <div class="max-w-4xl mx-auto">
            <div class="text-center mb-12">
                <div class="inline-flex items-center justify-center w-20 h-20 bg-green-500 rounded-full mb-6">
                    <i class="fas fa-check text-white text-4xl"></i>
                </div>
                <h1 class="text-5xl md:text-6xl font-extrabold text-white mb-4">
                    Store Created Successfully!
                </h1>
                <p class="text-xl text-gray-300 max-w-2xl mx-auto mb-8">
                    Your store "<strong class="text-white">{{ store.name }}</strong>" is ready. Download it as a standalone Flask application.
                </p>
            </div>
            
            <div class="bg-gray-800 border border-gray-700 rounded-2xl shadow-2xl p-8 md:p-12 mb-8">
                <h2 class="text-3xl font-bold text-white mb-6 flex items-center gap-3">
                    <i class="fas fa-download text-indigo-400"></i>
                    Download Your Store
                </h2>
                <p class="text-gray-300 mb-6">
                    Download your store as a standalone Flask application. This includes all your store data and can be run independently.
                </p>
                <div class="flex flex-col sm:flex-row gap-4 mb-6">
                    <a href="{{ url_for('download_store_file', store_slug=store.slug_id) }}" 
                       class="inline-flex items-center justify-center gap-3 px-8 py-4 bg-gradient-to-r from-green-500 to-green-600 hover:from-green-600 hover:to-green-700 text-white font-bold rounded-xl shadow-xl transform hover:scale-105 transition-all">
                        <i class="fas fa-download"></i>
                        <span>Download main.py</span>
                    </a>
                    <a href="{{ url_for('store_home', store_slug=store.slug_id) }}" 
                       class="inline-flex items-center justify-center gap-3 px-8 py-4 bg-gray-700 hover:bg-gray-600 text-white font-bold rounded-xl shadow-lg transition-all">
                        <i class="fas fa-store"></i>
                        <span>Visit Store</span>
                    </a>
                    <a href="{{ url_for('admin_login', store_slug=store.slug_id) }}" 
                       class="inline-flex items-center justify-center gap-3 px-8 py-4 bg-indigo-600 hover:bg-indigo-700 text-white font-bold rounded-xl shadow-lg transition-all">
                        <i class="fas fa-sign-in-alt"></i>
                        <span>Admin Login</span>
                    </a>
                </div>
                
                <div class="bg-gray-900 border border-gray-600 rounded-lg p-6 mt-6">
                    <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
                        <i class="fas fa-info-circle text-yellow-400"></i>
                        How to Use Your Downloaded Store
                    </h3>
                    <ol class="space-y-3 text-gray-300 list-decimal list-inside">
                        <li>Download the <code class="bg-gray-800 px-2 py-1 rounded text-white">main.py</code> file</li>
                        <li>Create a virtual environment: <code class="bg-gray-800 px-2 py-1 rounded text-white">python -m venv venv</code></li>
                        <li>Activate it: <code class="bg-gray-800 px-2 py-1 rounded text-white">source venv/bin/activate</code> (Linux/Mac) or <code class="bg-gray-800 px-2 py-1 rounded text-white">venv\\Scripts\\activate</code> (Windows)</li>
                        <li>Install dependencies: <code class="bg-gray-800 px-2 py-1 rounded text-white">pip install flask pymongo python-dotenv</code></li>
                        <li>Run the app: <code class="bg-gray-800 px-2 py-1 rounded text-white">python main.py</code></li>
                    </ol>
                </div>
            </div>
            
            <div class="text-center">
                <a href="{{ url_for('list_stores') }}" class="text-indigo-400 hover:text-indigo-300 font-semibold">
                    ← Back to Browse Stores
                </a>
            </div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/stores')
def list_stores():
    """List all stores, optionally filtered by business type."""
    business_type = request.args.get('business_type')
    query = {}
    if business_type and business_type in BUSINESS_TYPES:
        query['business_type'] = business_type
    
    stores = list(db.stores.find(query).sort("name", 1))
    return render_template_string(STORE_LIST_TEMPLATE, stores=stores, BUSINESS_TYPES=BUSINESS_TYPES)

# --- Store Routes ---
@app.route('/<store_slug>')
def store_home(store_slug):
    """Display the store's homepage."""
    items = list(db.items.find({"store_id": g.store['_id'], "status": {"$ne": "Sold"}}).sort("date_added", -1).limit(12))
    
    # Get specials for the store
    specials = list(db.specials.find({"store_id": g.store['_id']}).sort("date_created", -1).limit(3))
    if specials:
        g.store['specials'] = specials
    
    return render_page(HOME_TEMPLATE, items=items)

@app.route('/<store_slug>/item/<string:item_id>')
def item_details(store_slug, item_id):
    """Display details for a single item."""
    try:
        item = db.items.find_one({"_id": ObjectId(item_id), "store_id": g.store['_id']})
        if not item:
            flash('Item not found.', 'error')
            return redirect(url_for('store_home', store_slug=store_slug))
        return render_page(ITEM_DETAILS_TEMPLATE, item=item)
    except InvalidId:
        flash('Invalid item ID.', 'error')
        return redirect(url_for('store_home', store_slug=store_slug))

@app.route('/<store_slug>/inquire/<string:item_id>', methods=['POST'])
def submit_inquiry(store_slug, item_id):
    """Handle the submission of a new customer inquiry."""
    try:
        item = db.items.find_one({"_id": ObjectId(item_id), "store_id": g.store['_id']})
        if not item:
            flash('Could not submit inquiry: Item not found.', 'error')
            return redirect(url_for('store_home', store_slug=store_slug))
        
        form = request.form
        new_inquiry = {
            "item_id": item['_id'],
            "item_name": item['name'],
            "customer_name": form.get('customer_name'),
            "customer_contact": form.get('customer_contact'),
            "message": form.get('message'),
            "date_submitted": datetime.datetime.utcnow(),
            "store_id": g.store['_id'],
            "status": "New"
        }
        db.inquiries.insert_one(new_inquiry)
        flash('Thank you! We have received your inquiry and will contact you soon.', 'success')
        return redirect(url_for('item_details', store_slug=store_slug, item_id=item_id))
    except InvalidId:
        flash('Invalid item ID.', 'error')
        return redirect(url_for('store_home', store_slug=store_slug))

@app.route('/<store_slug>/download')
def download_store(store_slug):
    """Display download store page."""
    return render_template_string(DOWNLOAD_STORE_TEMPLATE, store=g.store)

@app.route('/<store_slug>/download/main.py')
def download_store_file(store_slug):
    """Generate and download standalone Flask main.py for the store."""
    # Get all store data
    store = g.store
    business_config = BUSINESS_TYPES.get(store.get('business_type', 'generic-store'), BUSINESS_TYPES['generic-store'])
    
    # Get store items
    items = list(db.items.find({"store_id": store['_id']}))
    for item in items:
        if '_id' in item:
            item['_id'] = str(item['_id'])
        if 'store_id' in item:
            item['store_id'] = str(item['store_id'])
        if 'date_added' in item and isinstance(item['date_added'], datetime.datetime):
            item['date_added'] = item['date_added'].isoformat()
    
    # Get specials
    specials = list(db.specials.find({"store_id": store['_id']}))
    for special in specials:
        if '_id' in special:
            special['_id'] = str(special['_id'])
        if 'store_id' in special:
            special['store_id'] = str(special['store_id'])
        if 'date_created' in special and isinstance(special['date_created'], datetime.datetime):
            special['date_created'] = special['date_created'].isoformat()
    
    # Get admin user
    user = db.users.find_one({"store_id": store['_id']})
    if not user:
        flash('Admin user not found for this store.', 'error')
        return redirect(url_for('store_home', store_slug=store_slug))
    
    # Convert store to JSON-safe format
    store_data = dict(store)
    if '_id' in store_data:
        store_data['_id'] = str(store_data['_id'])
    if 'date_created' in store_data and isinstance(store_data['date_created'], datetime.datetime):
        store_data['date_created'] = store_data['date_created'].isoformat()
    
    # Helper function to escape template strings for embedding in Python code
    def escape_template(template_str):
        """Escape a template string for embedding in Python triple-quoted string."""
        # Replace triple quotes to avoid conflicts
        result = template_str.replace('"""', '\\"\\"\\"')
        # Replace newlines
        result = result.replace('\n', '\\n')
        result = result.replace('\r', '')
        return result
    
    # Helper function to convert multi-store URLs to standalone format
    def convert_to_standalone_urls(template_str):
        """Convert URL references from multi-store format to standalone format."""
        import re
        result = template_str
        
        # Replace store_home with home (all variations)
        patterns = [
            (r"url_for\(['\"]store_home['\"],\s*store_slug=store\.slug_id\)", "url_for('home')"),
            (r"url_for\(['\"]store_home['\"],\s*store_slug=store_slug\)", "url_for('home')"),
            (r"url_for\(['\"]store_home['\"]\)", "url_for('home')"),
            # Handle with hash fragments
            (r"url_for\(['\"]store_home['\"],\s*store_slug=store\.slug_id\)#", "url_for('home')#"),
            (r"url_for\(['\"]store_home['\"],\s*store_slug=store_slug\)#", "url_for('home')#"),
        ]
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        # Replace item_details and remove store_slug parameter
        result = re.sub(r"url_for\(['\"]item_details['\"],\s*store_slug=store\.slug_id,\s*item_id=", "url_for('item_details', item_id=", result)
        result = re.sub(r"url_for\(['\"]item_details['\"],\s*store_slug=store_slug,\s*item_id=", "url_for('item_details', item_id=", result)
        
        # Replace admin routes - more comprehensive pattern matching
        admin_routes = ['admin_login', 'admin_logout', 'admin_dashboard', 'admin_list_items', 
                       'admin_add_item', 'admin_edit_item', 'admin_delete_item', 'admin_list_specials',
                       'admin_add_special', 'admin_edit_special', 'admin_delete_special',
                       'admin_list_inquiries', 'admin_delete_inquiry', 'admin_store_settings']
        
        for route in admin_routes:
            # Pattern 1: url_for('route', store_slug=store.slug_id)
            result = re.sub(rf"url_for\(['\"]{re.escape(route)}['\"],\s*store_slug=store\.slug_id\)", f"url_for('{route}')", result)
            # Pattern 2: url_for('route', store_slug=store_slug)
            result = re.sub(rf"url_for\(['\"]{re.escape(route)}['\"],\s*store_slug=store_slug\)", f"url_for('{route}')", result)
            # Pattern 3: url_for('route', store_slug=store.slug_id, other_param=...)
            result = re.sub(rf"url_for\(['\"]{re.escape(route)}['\"],\s*store_slug=store\.slug_id,\s*", f"url_for('{route}', ", result)
            result = re.sub(rf"url_for\(['\"]{re.escape(route)}['\"],\s*store_slug=store_slug,\s*", f"url_for('{route}', ", result)
            # Pattern 4: url_for('route', other_param=..., store_slug=store.slug_id)
            result = re.sub(rf",\s*store_slug=store\.slug_id", "", result)
            result = re.sub(rf",\s*store_slug=store_slug", "", result)
        
        return result
    
    # Pre-process templates for embedding - convert URLs first, then escape
    layout_template_standalone = convert_to_standalone_urls(LAYOUT_TEMPLATE)
    home_template_standalone = convert_to_standalone_urls(HOME_TEMPLATE)
    item_details_template_standalone = convert_to_standalone_urls(ITEM_DETAILS_TEMPLATE)
    login_template_standalone = convert_to_standalone_urls(LOGIN_TEMPLATE)
    dashboard_template_standalone = convert_to_standalone_urls(DASHBOARD_TEMPLATE)
    item_dashboard_template_standalone = convert_to_standalone_urls(ITEM_DASHBOARD_TEMPLATE)
    item_form_template_standalone = convert_to_standalone_urls(ITEM_FORM_TEMPLATE)
    specials_dashboard_template_standalone = convert_to_standalone_urls(SPECIALS_DASHBOARD_TEMPLATE)
    special_form_template_standalone = convert_to_standalone_urls(SPECIAL_FORM_TEMPLATE)
    inquiries_dashboard_template_standalone = convert_to_standalone_urls(INQUIRIES_DASHBOARD_TEMPLATE)
    
    # Escape templates for embedding
    layout_template_escaped = escape_template(layout_template_standalone)
    home_template_escaped = escape_template(home_template_standalone)
    item_details_template_escaped = escape_template(item_details_template_standalone)
    login_template_escaped = escape_template(login_template_standalone)
    dashboard_template_escaped = escape_template(dashboard_template_standalone)
    item_dashboard_template_escaped = escape_template(item_dashboard_template_standalone)
    item_form_template_escaped = escape_template(item_form_template_standalone)
    specials_dashboard_template_escaped = escape_template(specials_dashboard_template_standalone)
    special_form_template_escaped = escape_template(special_form_template_standalone)
    inquiries_dashboard_template_escaped = escape_template(inquiries_dashboard_template_standalone)
    
    # Generate standalone Flask app code
    secret_key_default = os.getenv("SECRET_KEY", "a-super-secret-key-change-in-production")
    store_name = store['name']
    store_slug = store["slug_id"]
    
    # Convert to JSON then replace JSON values with Python equivalents
    def json_to_python(json_str):
        """Convert JSON to Python-compatible format."""
        # Replace null with None
        result = json_str.replace(': null', ': None').replace(', null', ', None').replace('null', 'None')
        # Replace true with True
        result = result.replace(': true', ': True').replace(', true', ', True').replace('true', 'True')
        # Replace false with False
        result = result.replace(': false', ': False').replace(', false', ', False').replace('false', 'False')
        return result
    
    store_json = json_to_python(json.dumps(store_data, indent=2))
    business_config_json = json_to_python(json.dumps(business_config, indent=2))
    items_json = json_to_python(json.dumps(items, indent=8))
    specials_json = json_to_python(json.dumps(specials, indent=8))
    
    user_email = user['email']
    user_password = user['password']
    
    standalone_code = f'''"""
Standalone Flask Application for {store_name}
Generated by StoreFactory
"""
import os
import datetime
from flask import Flask, request, render_template_string, redirect, url_for, flash, session, g, abort
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
from functools import wraps
from pymongo.errors import DuplicateKeyError
from dotenv import load_dotenv

load_dotenv()

# --- App & DB Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '{secret_key_default}')

# --- MongoDB Connection ---
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/?retryWrites=true&w=majority&directConnection=true')
client = MongoClient(MONGO_URI)
db = client['{store_slug}_store_db']

# --- Create Collections & Indexes ---
if 'stores' not in db.list_collection_names():
    db.stores.create_index("slug_id", unique=True)
if 'users' not in db.list_collection_names():
    db.users.create_index([("email", 1), ("store_id", 1)], unique=True)
if 'items' not in db.list_collection_names():
    db.items.create_index([("item_code", 1), ("store_id", 1)], unique=True)
if 'specials' not in db.list_collection_names():
    db.specials.create_index([("store_id", 1), ("date_created", -1)])
if 'inquiries' not in db.list_collection_names():
    db.inquiries.create_index([("store_id", 1), ("date_submitted", -1)])

# --- Store Data ---
STORE_DATA = {store_json}

# --- Business Type Config ---
BUSINESS_CONFIG = {business_config_json}

# Initialize store and user data
def initialize_store():
    """Initialize store and admin user in database."""
    print("\\n" + "="*60)
    print("🏭 StoreFactory - Initializing Store...")
    print("="*60)
    
    existing_store = db.stores.find_one({{"slug_id": "{store_slug}"}})
    if not existing_store:
        print("📦 Seeding store data...")
        store_doc = {store_json}
        store_doc['_id'] = ObjectId(store_doc['_id'])
        store_doc['date_created'] = datetime.datetime.fromisoformat(store_doc['date_created'])
        store_id = db.stores.insert_one(store_doc).inserted_id
        print(f"   ✓ Store '{store_name}' created!")
        
        # Create admin user
        user_doc = {{
            "email": "{user_email}",
            "password": "{user_password}",
            "role": "owner",
            "store_id": store_id,
            "date_created": datetime.datetime.utcnow()
        }}
        db.users.insert_one(user_doc)
        print(f"   ✓ Admin user created: {user_email}")
        
        # Insert items
        items_data = {items_json}
        items_count = len(items_data)
        for item in items_data:
            item['_id'] = ObjectId(item['_id'])
            item['store_id'] = ObjectId(item['store_id'])
            if 'date_added' in item:
                item['date_added'] = datetime.datetime.fromisoformat(item['date_added'])
            db.items.insert_one(item)
        if items_count > 0:
            print(f"   ✓ {{items_count}} items seeded!")
        
        # Insert specials
        specials_data = {specials_json}
        specials_count = len(specials_data)
        for special in specials_data:
            special['_id'] = ObjectId(special['_id'])
            special['store_id'] = ObjectId(special['store_id'])
            if 'date_created' in special:
                special['date_created'] = datetime.datetime.fromisoformat(special['date_created'])
            db.specials.insert_one(special)
        if specials_count > 0:
            print(f"   ✓ {{specials_count}} specials seeded!")
        
        print("\\n✨ Store ready! Visit http://localhost:5000")
        print(f"   Admin Login: {user_email}")
        print("="*60 + "\\n")
        return store_id
    else:
        store_id = existing_store['_id']
        print(f"✓ Store already exists: '{store_name}'")
        
        # Check if user exists, create if not
        existing_user = db.users.find_one({{"store_id": store_id}})
        if not existing_user:
            print("📦 Creating admin user...")
            user_doc = {{
                "email": "{user_email}",
                "password": "{user_password}",
                "role": "owner",
                "store_id": store_id,
                "date_created": datetime.datetime.utcnow()
            }}
            db.users.insert_one(user_doc)
            print(f"   ✓ Admin user created: {user_email}")
        
        # Check if items exist, seed if not
        existing_items_count = db.items.count_documents({{"store_id": store_id}})
        if existing_items_count == 0:
            print("📦 Seeding items...")
            items_data = {items_json}
            items_count = len(items_data)
            print(f"   📊 Found {{items_count}} items in data to seed...")
            items_seeded = 0
            for item in items_data:
                try:
                    # Create a copy to avoid modifying the original
                    item_copy = dict(item)
                    # Generate new ObjectId instead of using the old one
                    item_copy['_id'] = ObjectId()
                    item_copy['store_id'] = ObjectId(store_id)
                    if 'date_added' in item_copy and isinstance(item_copy.get('date_added'), str):
                        item_copy['date_added'] = datetime.datetime.fromisoformat(item_copy['date_added'])
                    elif 'date_added' not in item_copy:
                        item_copy['date_added'] = datetime.datetime.utcnow()
                    db.items.insert_one(item_copy)
                    items_seeded += 1
                except Exception as e:
                    print(f"   ⚠️ Error seeding item: {{e}}")
                    continue
            if items_seeded > 0:
                print(f"   ✓ {{items_seeded}} items seeded!")
            elif items_count == 0:
                print(f"   ⚠️ No items to seed (items_json is empty)")
        else:
            print(f"   ✓ {{existing_items_count}} items already exist")
        
        # Check if specials exist, seed if not
        existing_specials_count = db.specials.count_documents({{"store_id": store_id}})
        if existing_specials_count == 0:
            print("📦 Seeding specials...")
            specials_data = {specials_json}
            specials_count = len(specials_data)
            print(f"   📊 Found {{specials_count}} specials in data to seed...")
            specials_seeded = 0
            for special in specials_data:
                try:
                    # Create a copy to avoid modifying the original
                    special_copy = dict(special)
                    # Generate new ObjectId instead of using the old one
                    special_copy['_id'] = ObjectId()
                    special_copy['store_id'] = ObjectId(store_id)
                    if 'date_created' in special_copy and isinstance(special_copy.get('date_created'), str):
                        special_copy['date_created'] = datetime.datetime.fromisoformat(special_copy['date_created'])
                    elif 'date_created' not in special_copy:
                        special_copy['date_created'] = datetime.datetime.utcnow()
                    db.specials.insert_one(special_copy)
                    specials_seeded += 1
                except Exception as e:
                    print(f"   ⚠️ Error seeding special: {{e}}")
                    continue
            if specials_seeded > 0:
                print(f"   ✓ {{specials_seeded}} specials seeded!")
            elif specials_count == 0:
                print(f"   ⚠️ No specials to seed (specials_json is empty)")
        else:
            print(f"   ✓ {{existing_specials_count}} specials already exist")
        
        print(f"\\n✨ Store ready! Visit http://localhost:5000")
        print(f"   Admin Login: {user_email}")
        print("="*60 + "\\n")
        return store_id

# --- HTML Templates (same as original) ---
LAYOUT_TEMPLATE = """{layout_template_escaped}"""

HOME_TEMPLATE = """{home_template_escaped}"""

ITEM_DETAILS_TEMPLATE = """{item_details_template_escaped}"""

LOGIN_TEMPLATE = """{login_template_escaped}"""

DASHBOARD_TEMPLATE = """{dashboard_template_escaped}"""

ITEM_DASHBOARD_TEMPLATE = """{item_dashboard_template_escaped}"""

ITEM_FORM_TEMPLATE = """{item_form_template_escaped}"""

SPECIALS_DASHBOARD_TEMPLATE = """{specials_dashboard_template_escaped}"""

SPECIAL_FORM_TEMPLATE = """{special_form_template_escaped}"""

INQUIRIES_DASHBOARD_TEMPLATE = """{inquiries_dashboard_template_escaped}"""

# --- Helper Functions ---
def render_page(template_string, **context):
    """Renders a page by injecting content into the base layout."""
    context['now'] = datetime.datetime.utcnow()
    context['store'] = g.store
    context['business_config'] = BUSINESS_CONFIG
    
    if g.store:
        context['specials'] = list(db.specials.find({{"store_id": g.store['_id']}}).sort("date_created", -1))
    
    if '{{% extends "layout" %}}' in template_string:
        content_block = template_string.split('{{% extends "layout" %}}', 1)[-1]
    else:
        content_block = template_string
    
    full_html = LAYOUT_TEMPLATE.replace("{{% block content %}}{{% endblock %}}", content_block)
    return render_template_string(full_html, **context)

def owner_required(f):
    """Decorator to ensure a route is accessed only by the logged-in store owner."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.store:
            abort(404)
        if ('user_id' not in session or 'store_id' not in session or
            session['store_id'] != str(g.store['_id'])):
            flash('You must be logged in as the owner to view this page.', 'error')
            return redirect(url_for('admin_login', store_slug=g.store['slug_id']))
        return f(*args, **kwargs)
    return decorated_function

# --- Global & Pre-Request Logic ---
@app.before_request
def load_store():
    """Load the store object from the database before each request."""
    g.store = db.stores.find_one({{"slug_id": "{store['slug_id']}"}})
    if not g.store:
        abort(404, description=f"Store not found.")

# --- Routes ---
@app.route('/')
def home():
    """Display the store's homepage."""
    items = list(db.items.find({{"store_id": g.store['_id'], "status": {{"$ne": "Sold"}}}}).sort("date_added", -1).limit(12))
    specials = list(db.specials.find({{"store_id": g.store['_id']}}).sort("date_created", -1).limit(3))
    if specials:
        g.store['specials'] = specials
    return render_page(HOME_TEMPLATE, items=items)

@app.route('/item/<string:item_id>')
def item_details(item_id):
    """Display details for a single item."""
    try:
        item = db.items.find_one({{"_id": ObjectId(item_id), "store_id": g.store['_id']}})
        if not item:
            flash('Item not found.', 'error')
            return redirect(url_for('home'))
        return render_page(ITEM_DETAILS_TEMPLATE, item=item)
    except InvalidId:
        flash('Invalid item ID.', 'error')
        return redirect(url_for('home'))

@app.route('/inquire/<string:item_id>', methods=['POST'])
def submit_inquiry(item_id):
    """Handle the submission of a new customer inquiry."""
    try:
        item = db.items.find_one({{"_id": ObjectId(item_id), "store_id": g.store['_id']}})
        if not item:
            flash('Could not submit inquiry: Item not found.', 'error')
            return redirect(url_for('home'))
        
        form = request.form
        new_inquiry = {{
            "item_id": item['_id'],
            "item_name": item['name'],
            "customer_name": form.get('customer_name'),
            "customer_contact": form.get('customer_contact'),
            "message": form.get('message'),
            "date_submitted": datetime.datetime.utcnow(),
            "store_id": g.store['_id'],
            "status": "New"
        }}
        db.inquiries.insert_one(new_inquiry)
        flash('Thank you! We have received your inquiry and will contact you soon.', 'success')
        return redirect(url_for('item_details', item_id=item_id))
    except InvalidId:
        flash('Invalid item ID.', 'error')
        return redirect(url_for('home'))

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Handle store owner login."""
    if request.method == 'POST':
        user = db.users.find_one({{
            "email": request.form.get('email'),
            "password": request.form.get('password'),
            "store_id": g.store['_id']
        }})
        if user:
            session['user_id'] = str(user['_id'])
            session['store_id'] = str(user['store_id'])
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    return render_page(LOGIN_TEMPLATE)

@app.route('/admin/logout')
def admin_logout():
    """Log the user out."""
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/admin/dashboard')
@owner_required
def admin_dashboard():
    """Display the admin dashboard."""
    return render_page(DASHBOARD_TEMPLATE)

@app.route('/admin/items')
@owner_required
def admin_list_items():
    """List all items."""
    items = list(db.items.find({{"store_id": g.store['_id']}}).sort("name", 1))
    return render_page(ITEM_DASHBOARD_TEMPLATE, items=items)

@app.route('/admin/item/add', methods=['GET', 'POST'])
@owner_required
def admin_add_item():
    """Handle adding a new item."""
    if request.method == 'POST':
        form = request.form
        attributes = {{attr['name']: form.get(f"attr_{{attr['name']}}") for attr in BUSINESS_CONFIG['attributes_template']}}
        new_item = {{
            "name": form.get('name'),
            "item_code": form.get('item_code').upper(),
            "price": float(form.get('price')),
            "image_url": form.get('image_url') or None,
            "description": form.get('description'),
            "status": form.get('status') or BUSINESS_CONFIG['status_options'][0] if BUSINESS_CONFIG['status_options'] else None,
            "store_id": g.store['_id'],
            "date_added": datetime.datetime.utcnow(),
            "attributes": attributes
        }}
        try:
            db.items.insert_one(new_item)
            flash(f"{{BUSINESS_CONFIG['item_label']}} '{{new_item['name']}}' added successfully!", 'success')
            return redirect(url_for('admin_list_items'))
        except DuplicateKeyError:
            flash(f"Error: An item with {{BUSINESS_CONFIG['item_code_label']}} '{{new_item['item_code']}}' already exists.", 'error')
            return render_page(ITEM_FORM_TEMPLATE, item=new_item)
    return render_page(ITEM_FORM_TEMPLATE, item=None)

@app.route('/admin/item/edit/<string:item_id>', methods=['GET', 'POST'])
@owner_required
def admin_edit_item(item_id):
    """Handle editing an existing item."""
    try:
        item = db.items.find_one({{"_id": ObjectId(item_id), "store_id": g.store['_id']}})
        if not item:
            return redirect(url_for('admin_list_items'))
        
        if request.method == 'POST':
            form = request.form
            attributes = {{attr['name']: form.get(f"attr_{{attr['name']}}") for attr in BUSINESS_CONFIG['attributes_template']}}
            update_data = {{
                "name": form.get('name'),
                "item_code": form.get('item_code').upper(),
                "price": float(form.get('price')),
                "image_url": form.get('image_url') or None,
                "description": form.get('description'),
                "status": form.get('status') or BUSINESS_CONFIG['status_options'][0] if BUSINESS_CONFIG['status_options'] else None,
                "attributes": attributes
            }}
            try:
                db.items.update_one({{"_id": ObjectId(item_id)}}, {{"$set": update_data}})
                flash(f'{{BUSINESS_CONFIG["item_label"]}} updated successfully!', 'success')
                return redirect(url_for('admin_list_items'))
            except DuplicateKeyError:
                flash(f"Error: An item with {{BUSINESS_CONFIG['item_code_label']}} '{{update_data['item_code']}}' already exists.", 'error')
                item.update(update_data)
                return render_page(ITEM_FORM_TEMPLATE, item=item)
        return render_page(ITEM_FORM_TEMPLATE, item=item)
    except InvalidId:
        return redirect(url_for('admin_list_items'))

@app.route('/admin/item/delete/<string:item_id>', methods=['POST'])
@owner_required
def admin_delete_item(item_id):
    """Permanently delete an item."""
    try:
        db.items.delete_one({{"_id": ObjectId(item_id), "store_id": g.store['_id']}})
    except InvalidId:
        pass
    return redirect(url_for('admin_list_items'))

@app.route('/admin/specials')
@owner_required
def admin_list_specials():
    """List all specials."""
    specials = list(db.specials.find({{"store_id": g.store['_id']}}).sort("date_created", -1))
    return render_page(SPECIALS_DASHBOARD_TEMPLATE, specials=specials)

@app.route('/admin/special/add', methods=['GET', 'POST'])
@owner_required
def admin_add_special():
    """Handle adding a new special."""
    if request.method == 'POST':
        form = request.form
        db.specials.insert_one({{
            "title": form.get('title'),
            "content": form.get('content'),
            "date_created": datetime.datetime.utcnow(),
            "store_id": g.store['_id']
        }})
        flash('New special created!', 'success')
        return redirect(url_for('admin_list_specials'))
    return render_page(SPECIAL_FORM_TEMPLATE, special=None)

@app.route('/admin/special/edit/<string:special_id>', methods=['GET', 'POST'])
@owner_required
def admin_edit_special(special_id):
    """Handle editing an existing special."""
    try:
        special = db.specials.find_one({{"_id": ObjectId(special_id), "store_id": g.store['_id']}})
        if not special:
            return redirect(url_for('admin_list_specials'))
        
        if request.method == 'POST':
            form = request.form
            db.specials.update_one(
                {{"_id": ObjectId(special_id)}},
                {{"$set": {{"title": form.get('title'), "content": form.get('content')}}}}
            )
            flash('Special updated!', 'success')
            return redirect(url_for('admin_list_specials'))
        return render_page(SPECIAL_FORM_TEMPLATE, special=special)
    except InvalidId:
        return redirect(url_for('admin_list_specials'))

@app.route('/admin/special/delete/<string:special_id>', methods=['POST'])
@owner_required
def admin_delete_special(special_id):
    """Permanently delete a special."""
    try:
        db.specials.delete_one({{"_id": ObjectId(special_id), "store_id": g.store['_id']}})
    except InvalidId:
        pass
    return redirect(url_for('admin_list_specials'))

@app.route('/admin/inquiries')
@owner_required
def admin_list_inquiries():
    """List all inquiries."""
    inquiries = list(db.inquiries.find({{"store_id": g.store['_id']}}).sort("date_submitted", -1))
    return render_page(INQUIRIES_DASHBOARD_TEMPLATE, inquiries=inquiries)

@app.route('/admin/inquiry/delete/<string:inquiry_id>', methods=['POST'])
@owner_required
def admin_delete_inquiry(inquiry_id):
    """Permanently delete an inquiry."""
    try:
        db.inquiries.delete_one({{"_id": ObjectId(inquiry_id), "store_id": g.store['_id']}})
        flash('Inquiry deleted successfully.', 'success')
    except InvalidId:
        flash('Invalid inquiry ID.', 'error')
    return redirect(url_for('admin_list_inquiries'))

@app.route('/admin/reset', methods=['POST'])
@owner_required
def admin_reset_store():
    """Reset store data - clear items, specials, inquiries and reseed."""
    store_id = g.store['_id']
    
    # Delete all items, specials, and inquiries
    items_deleted = db.items.delete_many({{"store_id": store_id}}).deleted_count
    specials_deleted = db.specials.delete_many({{"store_id": store_id}}).deleted_count
    inquiries_deleted = db.inquiries.delete_many({{"store_id": store_id}}).deleted_count
    
    # Reseed items and specials with fresh IDs
    items_data = {items_json}
    items_reseeded = 0
    for item in items_data:
        # Generate new ObjectId for reseeded items
        item['_id'] = ObjectId()
        item['store_id'] = store_id
        item['date_added'] = datetime.datetime.utcnow()
        # Remove old date_added if present
        if 'date_added' in item and isinstance(item.get('date_added'), str):
            pass  # Already handled
        db.items.insert_one(item)
        items_reseeded += 1
    
    specials_data = {specials_json}
    specials_reseeded = 0
    for special in specials_data:
        # Generate new ObjectId for reseeded specials
        special['_id'] = ObjectId()
        special['store_id'] = store_id
        special['date_created'] = datetime.datetime.utcnow()
        # Remove old date_created if present
        if 'date_created' in special and isinstance(special.get('date_created'), str):
            pass  # Already handled
        db.specials.insert_one(special)
        specials_reseeded += 1
    
    flash(f'✨ Store reset! Deleted {{items_deleted}} items, {{specials_deleted}} specials, {{inquiries_deleted}} inquiries. Reseeded {{items_reseeded}} items and {{specials_reseeded}} specials.', 'success')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    print("\\n🚀 Starting StoreFactory standalone application...")
    with app.app_context():
        initialize_store()
    print("🌐 Server starting on http://localhost:5000\\n")
    app.run(debug=True, port=5000, host='0.0.0.0')
'''
    
    return Response(
        standalone_code,
        mimetype='text/plain',
        headers={
            'Content-Disposition': f'attachment; filename=main.py'
        }
    )

# --- Admin Routes ---
@app.route('/<store_slug>/admin/login', methods=['GET', 'POST'])
def admin_login(store_slug):
    """Handle store owner login."""
    # Demo store credentials mapping
    demo_credentials_map = {
        'country-pizza': {'email': 'owner@country-pizza.com', 'password': 'password123'},
        'premium-auto-sales': {'email': 'owner@premiumauto.com', 'password': 'demo123'},
        'quick-fix-auto': {'email': 'owner@quickfix.com', 'password': 'demo123'},
        'pro-services-hub': {'email': 'owner@proservices.com', 'password': 'demo123'},
        'general-store-demo': {'email': 'owner@generalstore.com', 'password': 'demo123'}
    }
    
    if request.method == 'POST':
        user = db.users.find_one({
            "email": request.form.get('email'),
            "password": request.form.get('password'),
            "store_id": g.store['_id']
        })
        if user:
            session['user_id'] = str(user['_id'])
            session['store_id'] = str(user['store_id'])
            return redirect(url_for('admin_dashboard', store_slug=store_slug))
        else:
            flash('Invalid email or password for this store.', 'error')
    
    # Check if this is a demo store and provide credentials
    demo_credentials = demo_credentials_map.get(store_slug)
    return render_page(LOGIN_TEMPLATE, demo_credentials=demo_credentials)

@app.route('/<store_slug>/admin/logout')
def admin_logout(store_slug):
    """Log the user out."""
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('store_home', store_slug=store_slug))

@app.route('/<store_slug>/admin/dashboard')
@owner_required
def admin_dashboard(store_slug):
    """Display the admin dashboard with stats."""
    items_count = db.items.count_documents({"store_id": g.store['_id']})
    specials_count = db.specials.count_documents({"store_id": g.store['_id']})
    inquiries_count = db.inquiries.count_documents({"store_id": g.store['_id']})
    
    return render_page(DASHBOARD_TEMPLATE, 
                       items_count=items_count,
                       specials_count=specials_count,
                       inquiries_count=inquiries_count)

# Admin Item Routes
@app.route('/<store_slug>/admin/items')
@owner_required
def admin_list_items(store_slug):
    """List all items."""
    items = list(db.items.find({"store_id": g.store['_id']}).sort("name", 1))
    return render_page(ITEM_DASHBOARD_TEMPLATE, items=items)

@app.route('/<store_slug>/admin/item/add', methods=['GET', 'POST'])
@owner_required
def admin_add_item(store_slug):
    """Handle adding a new item."""
    business_config = BUSINESS_TYPES.get(g.store.get('business_type', 'generic-store'), BUSINESS_TYPES['generic-store'])
    
    if request.method == 'POST':
        form = request.form
        attributes = {attr['name']: form.get(f"attr_{attr['name']}") for attr in business_config['attributes_template']}
        new_item = {
            "name": form.get('name'),
            "item_code": form.get('item_code').upper(),
            "price": float(form.get('price')),
            "image_url": form.get('image_url') or None,
            "description": form.get('description'),
            "status": form.get('status') or business_config['status_options'][0] if business_config['status_options'] else None,
            "store_id": g.store['_id'],
            "date_added": datetime.datetime.utcnow(),
            "attributes": attributes
        }
        try:
            db.items.insert_one(new_item)
            flash(f"{business_config['item_label']} '{new_item['name']}' added successfully!", 'success')
            return redirect(url_for('admin_list_items', store_slug=store_slug))
        except DuplicateKeyError:
            flash(f"Error: An item with {business_config['item_code_label']} '{new_item['item_code']}' already exists.", 'error')
            return render_page(ITEM_FORM_TEMPLATE, item=new_item)
    return render_page(ITEM_FORM_TEMPLATE, item=None)

@app.route('/<store_slug>/admin/item/edit/<string:item_id>', methods=['GET', 'POST'])
@owner_required
def admin_edit_item(store_slug, item_id):
    """Handle editing an existing item."""
    business_config = BUSINESS_TYPES.get(g.store.get('business_type', 'generic-store'), BUSINESS_TYPES['generic-store'])
    
    try:
        item = db.items.find_one({"_id": ObjectId(item_id), "store_id": g.store['_id']})
        if not item:
            return redirect(url_for('admin_list_items', store_slug=store_slug))
        
        if request.method == 'POST':
            form = request.form
            attributes = {attr['name']: form.get(f"attr_{attr['name']}") for attr in business_config['attributes_template']}
            update_data = {
                "name": form.get('name'),
                "item_code": form.get('item_code').upper(),
                "price": float(form.get('price')),
                "image_url": form.get('image_url') or None,
                "description": form.get('description'),
                "status": form.get('status') or business_config['status_options'][0] if business_config['status_options'] else None,
                "attributes": attributes
            }
            try:
                db.items.update_one({"_id": ObjectId(item_id)}, {"$set": update_data})
                flash(f'{business_config["item_label"]} updated successfully!', 'success')
                return redirect(url_for('admin_list_items', store_slug=store_slug))
            except DuplicateKeyError:
                flash(f"Error: An item with {business_config['item_code_label']} '{update_data['item_code']}' already exists.", 'error')
                item.update(update_data)
                return render_page(ITEM_FORM_TEMPLATE, item=item)
        return render_page(ITEM_FORM_TEMPLATE, item=item)
    except InvalidId:
        return redirect(url_for('admin_list_items', store_slug=store_slug))

@app.route('/<store_slug>/admin/item/delete/<string:item_id>', methods=['POST'])
@owner_required
def admin_delete_item(store_slug, item_id):
    """Permanently delete an item."""
    try:
        db.items.delete_one({"_id": ObjectId(item_id), "store_id": g.store['_id']})
    except InvalidId:
        pass
    return redirect(url_for('admin_list_items', store_slug=store_slug))

# Admin Specials Routes
@app.route('/<store_slug>/admin/specials')
@owner_required
def admin_list_specials(store_slug):
    """List all specials."""
    specials = list(db.specials.find({"store_id": g.store['_id']}).sort("date_created", -1))
    return render_page(SPECIALS_DASHBOARD_TEMPLATE, specials=specials)

@app.route('/<store_slug>/admin/special/add', methods=['GET', 'POST'])
@owner_required
def admin_add_special(store_slug):
    """Handle adding a new special."""
    if request.method == 'POST':
        form = request.form
        db.specials.insert_one({
            "title": form.get('title'),
            "content": form.get('content'),
            "date_created": datetime.datetime.utcnow(),
            "store_id": g.store['_id']
        })
        flash('New special created!', 'success')
        return redirect(url_for('admin_list_specials', store_slug=store_slug))
    return render_page(SPECIAL_FORM_TEMPLATE, special=None)

@app.route('/<store_slug>/admin/special/edit/<string:special_id>', methods=['GET', 'POST'])
@owner_required
def admin_edit_special(store_slug, special_id):
    """Handle editing an existing special."""
    try:
        special = db.specials.find_one({"_id": ObjectId(special_id), "store_id": g.store['_id']})
        if not special:
            return redirect(url_for('admin_list_specials', store_slug=store_slug))
        
        if request.method == 'POST':
            form = request.form
            db.specials.update_one(
                {"_id": ObjectId(special_id)},
                {"$set": {"title": form.get('title'), "content": form.get('content')}}
            )
            flash('Special updated!', 'success')
            return redirect(url_for('admin_list_specials', store_slug=store_slug))
        return render_page(SPECIAL_FORM_TEMPLATE, special=special)
    except InvalidId:
        return redirect(url_for('admin_list_specials', store_slug=store_slug))

@app.route('/<store_slug>/admin/special/delete/<string:special_id>', methods=['POST'])
@owner_required
def admin_delete_special(store_slug, special_id):
    """Permanently delete a special."""
    try:
        db.specials.delete_one({"_id": ObjectId(special_id), "store_id": g.store['_id']})
    except InvalidId:
        pass
    return redirect(url_for('admin_list_specials', store_slug=store_slug))

# Admin Inquiries Routes
@app.route('/<store_slug>/admin/inquiries')
@owner_required
def admin_list_inquiries(store_slug):
    """List all inquiries."""
    inquiries = list(db.inquiries.find({"store_id": g.store['_id']}).sort("date_submitted", -1))
    return render_page(INQUIRIES_DASHBOARD_TEMPLATE, inquiries=inquiries)

@app.route('/<store_slug>/admin/inquiry/delete/<string:inquiry_id>', methods=['POST'])
@owner_required
def admin_delete_inquiry(store_slug, inquiry_id):
    """Permanently delete an inquiry."""
    try:
        db.inquiries.delete_one({"_id": ObjectId(inquiry_id), "store_id": g.store['_id']})
        flash('Inquiry deleted successfully.', 'success')
    except InvalidId:
        flash('Invalid inquiry ID.', 'error')
    return redirect(url_for('admin_list_inquiries', store_slug=store_slug))

@app.route('/<store_slug>/admin/reset', methods=['POST'])
@owner_required
def admin_reset_store(store_slug):
    """Reset store data - clear items, specials, inquiries and reseed from defaults."""
    store_id = g.store['_id']
    
    # Delete all items, specials, and inquiries
    items_deleted = db.items.delete_many({"store_id": store_id}).deleted_count
    specials_deleted = db.specials.delete_many({"store_id": store_id}).deleted_count
    inquiries_deleted = db.inquiries.delete_many({"store_id": store_id}).deleted_count
    
    # Reseed from stored data if available (for standalone stores, this happens via initialize_store)
    # For multi-store version, just delete and let user know
    flash(f'✨ Store reset complete! Deleted {items_deleted} items, {specials_deleted} specials, and {inquiries_deleted} inquiries. You can now add new items and specials!', 'success')
    return redirect(url_for('admin_dashboard', store_slug=store_slug))

# Store Settings Routes
STORE_SETTINGS_TEMPLATE = """
{% extends "layout" %}
{% block content %}
<div class="container mx-auto px-4 mt-8 pb-12">
    <div class="flex flex-col sm:flex-row justify-between sm:items-center gap-4 mb-8">
        <div>
            <h1 class="text-4xl md:text-5xl font-extrabold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent mb-2">
                ✨ Store Customization
            </h1>
            <p class="text-gray-300">Make your store truly yours with custom themes and branding</p>
        </div>
        <a href="{{ url_for('admin_dashboard', store_slug=store.slug_id) }}" 
           class="inline-flex items-center gap-2 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
            <i class="fas fa-arrow-left"></i>
            <span>Back to Dashboard</span>
        </a>
    </div>

    <form method="post" id="store-settings-form" class="space-y-8">
        <!-- Logo Section -->
        <div class="bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 rounded-2xl shadow-2xl p-8 hover:shadow-3xl transition-all">
            <div class="flex items-center gap-4 mb-6">
                <div class="w-14 h-14 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center text-white text-2xl shadow-lg">
                    <i class="fas fa-image"></i>
                </div>
                <div>
                    <h2 class="text-3xl font-bold text-white">Logo & Branding</h2>
                    <p class="text-gray-400">Upload your logo and brand images</p>
                </div>
            </div>
            
            <div class="space-y-6">
                <div>
                    <label for="logo_url" class="block text-sm font-semibold text-gray-200 mb-2">
                        Logo URL <span class="text-yellow-400">*</span>
                    </label>
                    <p class="text-xs text-gray-400 mb-3">Enter the full URL to your logo (https://example.com/logo.png or /static/img/logo.png)</p>
                    <input type="url" name="logo_url" id="logo_url" 
                           value="{{ store.logo_url or '' }}" 
                           placeholder="https://example.com/logo.png"
                           class="w-full px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500 transition-all">
                    {% if store.logo_url %}
                    <div class="mt-4 p-4 bg-gray-900 border-2 border-gray-700 rounded-xl">
                        <p class="text-sm text-gray-300 mb-3 font-semibold">Current Logo Preview:</p>
                        <img src="{{ store.logo_url }}" alt="Current Logo" 
                             class="h-24 object-contain mx-auto rounded-lg shadow-lg" 
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                        <p class="text-sm text-red-400 hidden text-center">❌ Logo failed to load. Please check the URL.</p>
                    </div>
                    {% endif %}
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div>
                        <label for="hero_image_url" class="block text-sm font-semibold text-gray-200 mb-2">Hero Background Image</label>
                        <input type="url" name="hero_image_url" id="hero_image_url" 
                               value="{{ store.hero_image_url or '' }}" 
                               placeholder="https://..."
                               class="w-full px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500 transition-all">
                    </div>
                    <div>
                        <label for="gallery_image_1_url" class="block text-sm font-semibold text-gray-200 mb-2">Gallery Image 1</label>
                        <input type="url" name="gallery_image_1_url" id="gallery_image_1_url" 
                               value="{{ store.gallery_image_1_url or '' }}" 
                               placeholder="https://..."
                               class="w-full px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500 transition-all">
                    </div>
                    <div>
                        <label for="gallery_image_2_url" class="block text-sm font-semibold text-gray-200 mb-2">Gallery Image 2</label>
                        <input type="url" name="gallery_image_2_url" id="gallery_image_2_url" 
                               value="{{ store.gallery_image_2_url or '' }}" 
                               placeholder="https://..."
                               class="w-full px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500 transition-all">
                    </div>
                </div>
            </div>
        </div>

        <!-- Theme Colors Section -->
        <div class="bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 rounded-2xl shadow-2xl p-8 hover:shadow-3xl transition-all">
            <div class="flex items-center gap-4 mb-6">
                <div class="w-14 h-14 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center text-white text-2xl shadow-lg">
                    <i class="fas fa-palette"></i>
                </div>
                <div>
                    <h2 class="text-3xl font-bold text-white">Theme Colors</h2>
                    <p class="text-gray-400">Customize your store's color scheme</p>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <div>
                    <label for="theme_primary" class="block text-sm font-semibold text-gray-200 mb-2">
                        Primary Color
                        <span class="text-gray-400 text-xs">(Buttons, Links)</span>
                    </label>
                    <div class="flex items-center gap-3">
                        <input type="color" name="theme_primary" id="theme_primary" 
                               value="{{ store.theme_primary or '#3b82f6' }}"
                               class="w-16 h-16 rounded-lg cursor-pointer border-2 border-gray-600">
                        <input type="text" name="theme_primary_hex" id="theme_primary_hex"
                               value="{{ store.theme_primary or '#3b82f6' }}"
                               pattern="^#[0-9A-Fa-f]{6}$"
                               class="flex-1 px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500">
                    </div>
                </div>

                <div>
                    <label for="theme_secondary" class="block text-sm font-semibold text-gray-200 mb-2">
                        Secondary Color
                        <span class="text-gray-400 text-xs">(Accents, Highlights)</span>
                    </label>
                    <div class="flex items-center gap-3">
                        <input type="color" name="theme_secondary" id="theme_secondary" 
                               value="{{ store.theme_secondary or '#f59e0b' }}"
                               class="w-16 h-16 rounded-lg cursor-pointer border-2 border-gray-600">
                        <input type="text" name="theme_secondary_hex" id="theme_secondary_hex"
                               value="{{ store.theme_secondary or '#f59e0b' }}"
                               pattern="^#[0-9A-Fa-f]{6}$"
                               class="flex-1 px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500">
                    </div>
                </div>

                <div>
                    <label for="theme_background" class="block text-sm font-semibold text-gray-200 mb-2">
                        Background Color
                        <span class="text-gray-400 text-xs">(Main Background)</span>
                    </label>
                    <div class="flex items-center gap-3">
                        <input type="color" name="theme_background" id="theme_background" 
                               value="{{ store.theme_background or '#111827' }}"
                               class="w-16 h-16 rounded-lg cursor-pointer border-2 border-gray-600">
                        <input type="text" name="theme_background_hex" id="theme_background_hex"
                               value="{{ store.theme_background or '#111827' }}"
                               pattern="^#[0-9A-Fa-f]{6}$"
                               class="flex-1 px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500">
                    </div>
                </div>

                <div>
                    <label for="theme_surface" class="block text-sm font-semibold text-gray-200 mb-2">
                        Surface Color
                        <span class="text-gray-400 text-xs">(Cards, Panels)</span>
                    </label>
                    <div class="flex items-center gap-3">
                        <input type="color" name="theme_surface" id="theme_surface" 
                               value="{{ store.theme_surface or '#1f2937' }}"
                               class="w-16 h-16 rounded-lg cursor-pointer border-2 border-gray-600">
                        <input type="text" name="theme_surface_hex" id="theme_surface_hex"
                               value="{{ store.theme_surface or '#1f2937' }}"
                               pattern="^#[0-9A-Fa-f]{6}$"
                               class="flex-1 px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500">
                    </div>
                </div>

                <div>
                    <label for="theme_text" class="block text-sm font-semibold text-gray-200 mb-2">
                        Text Color
                        <span class="text-gray-400 text-xs">(Primary Text)</span>
                    </label>
                    <div class="flex items-center gap-3">
                        <input type="color" name="theme_text" id="theme_text" 
                               value="{{ store.theme_text or '#f9fafb' }}"
                               class="w-16 h-16 rounded-lg cursor-pointer border-2 border-gray-600">
                        <input type="text" name="theme_text_hex" id="theme_text_hex"
                               value="{{ store.theme_text or '#f9fafb' }}"
                               pattern="^#[0-9A-Fa-f]{6}$"
                               class="flex-1 px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500">
                    </div>
                </div>

                <div>
                    <label for="theme_text_secondary" class="block text-sm font-semibold text-gray-200 mb-2">
                        Secondary Text
                        <span class="text-gray-400 text-xs">(Muted Text)</span>
                    </label>
                    <div class="flex items-center gap-3">
                        <input type="color" name="theme_text_secondary" id="theme_text_secondary" 
                               value="{{ store.theme_text_secondary or '#d1d5db' }}"
                               class="w-16 h-16 rounded-lg cursor-pointer border-2 border-gray-600">
                        <input type="text" name="theme_text_secondary_hex" id="theme_text_secondary_hex"
                               value="{{ store.theme_text_secondary or '#d1d5db' }}"
                               pattern="^#[0-9A-Fa-f]{6}$"
                               class="flex-1 px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500">
                    </div>
                </div>
            </div>

            <!-- Theme Preview -->
            <div class="mt-8 p-6 bg-gray-900 border-2 border-gray-700 rounded-xl">
                <p class="text-sm font-semibold text-gray-300 mb-4">Live Preview:</p>
                <div class="grid grid-cols-3 gap-4">
                    <div class="p-4 rounded-lg text-center shadow-lg" style="background-color: {{ store.theme_primary or '#3b82f6' }}; color: white;">
                        Primary
                    </div>
                    <div class="p-4 rounded-lg text-center shadow-lg" style="background-color: {{ store.theme_secondary or '#f59e0b' }}; color: white;">
                        Secondary
                    </div>
                    <div class="p-4 rounded-lg text-center shadow-lg" style="background-color: {{ store.theme_surface or '#1f2937' }}; color: {{ store.theme_text or '#f9fafb' }};">
                        Surface
                    </div>
                </div>
            </div>
        </div>

        <!-- Additional Settings -->
        <div class="bg-gradient-to-br from-gray-800 to-gray-900 border border-gray-700 rounded-2xl shadow-2xl p-8 hover:shadow-3xl transition-all">
            <div class="flex items-center gap-4 mb-6">
                <div class="w-14 h-14 bg-gradient-to-br from-green-500 to-emerald-500 rounded-xl flex items-center justify-center text-white text-2xl shadow-lg">
                    <i class="fas fa-cog"></i>
                </div>
                <div>
                    <h2 class="text-3xl font-bold text-white">Additional Settings</h2>
                    <p class="text-gray-400">Fine-tune your store experience</p>
                </div>
            </div>

            <div class="space-y-6">
                <div>
                    <label for="menu_image_url" class="block text-sm font-semibold text-gray-200 mb-2">Menu Image URL</label>
                    <input type="url" name="menu_image_url" id="menu_image_url" 
                           value="{{ store.menu_image_url or '' }}" 
                           placeholder="https://example.com/menu.png"
                           class="w-full px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500">
                </div>

                <div>
                    <label for="google_maps_embed_html" class="block text-sm font-semibold text-gray-200 mb-2">Google Maps Embed HTML</label>
                    <textarea name="google_maps_embed_html" id="google_maps_embed_html" rows="4"
                              class="w-full px-4 py-3 bg-gray-700 border-2 border-gray-600 text-white rounded-xl focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500 font-mono text-sm"
                              placeholder="<iframe src='https://www.google.com/maps/embed?...'></iframe>">{{ store.google_maps_embed_html or '' }}</textarea>
                    <p class="text-xs text-gray-400 mt-2">Paste the embed HTML from Google Maps</p>
                </div>
            </div>
        </div>

        <!-- Save Button -->
        <div class="flex items-center justify-end gap-4 pt-6">
            <a href="{{ url_for('admin_dashboard', store_slug=store.slug_id) }}" 
               class="px-6 py-3 text-gray-300 hover:text-white font-semibold transition-colors">
                Cancel
            </a>
            <button type="submit" 
                    class="inline-flex items-center gap-3 px-8 py-4 bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white font-bold rounded-xl shadow-xl transform hover:scale-105 transition-all">
                <i class="fas fa-save"></i>
                <span>Save All Changes</span>
                <i class="fas fa-magic"></i>
            </button>
        </div>
    </form>
</div>

<script>
    // Sync color picker with hex input
    document.querySelectorAll('input[type="color"]').forEach(colorPicker => {
        const hexInput = document.getElementById(colorPicker.id + '_hex');
        if (hexInput) {
            colorPicker.addEventListener('input', (e) => {
                hexInput.value = e.target.value;
            });
            hexInput.addEventListener('input', (e) => {
                if (/^#[0-9A-Fa-f]{6}$/.test(e.target.value)) {
                    colorPicker.value = e.target.value;
                }
            });
        }
    });

    // Live preview update
    const form = document.getElementById('store-settings-form');
    form.addEventListener('input', () => {
        // Could add live preview updates here
    });
</script>
{% endblock %}
"""

@app.route('/<store_slug>/admin/settings', methods=['GET', 'POST'])
@owner_required
def admin_store_settings(store_slug):
    """Handle store settings management, including logo, images, and theme customization."""
    if request.method == 'POST':
        form = request.form
        
        # Prepare update data
        update_data = {}
        
        # Logo and images
        logo_url = form.get('logo_url', '').strip()
        update_data['logo_url'] = logo_url if logo_url else None
        
        update_data['hero_image_url'] = form.get('hero_image_url', '').strip() or None
        update_data['gallery_image_1_url'] = form.get('gallery_image_1_url', '').strip() or None
        update_data['gallery_image_2_url'] = form.get('gallery_image_2_url', '').strip() or None
        update_data['menu_image_url'] = form.get('menu_image_url', '').strip() or None
        update_data['google_maps_embed_html'] = form.get('google_maps_embed_html', '').strip() or None
        
        # Theme colors - use hex input if available, otherwise color picker
        update_data['theme_primary'] = form.get('theme_primary_hex', form.get('theme_primary', '#3b82f6')).strip()
        update_data['theme_secondary'] = form.get('theme_secondary_hex', form.get('theme_secondary', '#f59e0b')).strip()
        update_data['theme_background'] = form.get('theme_background_hex', form.get('theme_background', '#111827')).strip()
        update_data['theme_surface'] = form.get('theme_surface_hex', form.get('theme_surface', '#1f2937')).strip()
        update_data['theme_text'] = form.get('theme_text_hex', form.get('theme_text', '#f9fafb')).strip()
        update_data['theme_text_secondary'] = form.get('theme_text_secondary_hex', form.get('theme_text_secondary', '#d1d5db')).strip()
        
        # Update store
        db.stores.update_one(
            {"_id": g.store['_id']},
            {"$set": update_data}
        )
        
        # Refresh g.store
        g.store = db.stores.find_one({"slug_id": store_slug})
        
        flash('✨ Store settings updated successfully! Your theme changes are now live!', 'success')
        return redirect(url_for('admin_store_settings', store_slug=store_slug))
    
    return render_page(STORE_SETTINGS_TEMPLATE)

# --- Auto-Seeding Function ---
def seed_database():
    """Auto-seed database with example stores for each business type if they don't exist."""
    print("Checking for demo stores...")
    
    demo_stores = [
        {
            'business_type': 'restaurant',
            'name': 'Country Pizza',
            'slug_id': 'country-pizza',
            'tagline': 'Más de 40 años brindándoles servicio en Aguadilla',
            'about_text': 'Cocina, barra y billares... todo en un solo lugar.',
            'address': 'Carr. 110 Km 9, Bo. Maleza, Aguadilla, PR',
            'phone': '17878914860',
            'phone_display': '(787) 891-4860',
            'hours': 'Abierto todos los días: 4pm – 12am\nAlmuerzo: 11am – 2pm',
            'hero_image_url': 'https://images.pexels.com/photos/376464/pexels-photo-376464.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
            'gallery_image_1_url': 'https://images.pexels.com/photos/1267320/pexels-photo-1267320.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
            'gallery_image_2_url': 'https://images.pexels.com/photos/4057755/pexels-photo-4057755.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
            'menu_image_url': 'https://i.imgur.com/8aJ4z2Y.png',
            'google_maps_embed_html': '<iframe src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d15134.149722116716!2d-67.12504398730123!3d18.50460047092597!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x8c029616f8e64d75%3A0x7356a68ba6d44dca!2sCountry%20Pizza!5e0!3m2!1sen!2sus!4v1750828525017!5m2!1sen!2sus" width="100%" height="100%" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>',
            'socials': [
                {'name': 'Facebook', 'icon': 'facebook-f', 'url': 'https://www.facebook.com/CountryPizzaa'},
                {'name': 'Instagram', 'icon': 'instagram', 'url': 'https://www.instagram.com/countrypizzapr'},
                {'name': 'WhatsApp', 'icon': 'whatsapp', 'url': 'https://wa.me/17878914860'}
            ],
            'items': [
                {'name': 'Pizza de Pepperoni', 'price': 12.50, 'item_code': 'MENU001', 'description': 'Clásica pizza de pepperoni con queso mozzarella', 'image_url': 'https://images.pexels.com/photos/1146760/pexels-photo-1146760.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2', 'attributes': {'Category': 'Pizzas', 'Ingredients': 'Pepperoni, Queso Mozzarella, Salsa de Tomate'}},
                {'name': 'Surtido Criollo', 'price': 18.00, 'item_code': 'MENU002', 'description': 'Variedad de platos criollos tradicionales', 'image_url': 'https://images.pexels.com/photos/2338407/pexels-photo-2338407.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2', 'attributes': {'Category': 'Aperitivos', 'Ingredients': 'Carne, Pollo, Tostones'}},
                {'name': 'Mofongo con Carne Frita', 'price': 15.75, 'item_code': 'MENU003', 'description': 'Mofongo tradicional con carne frita jugosa', 'image_url': 'https://images.pexels.com/photos/593006/pexels-photo-593006.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2', 'attributes': {'Category': 'Platos Principales', 'Ingredients': 'Plátano, Carne Frita, Ajo'}},
                {'name': 'Alitas de Pollo (BBQ o Picantes)', 'price': 9.95, 'item_code': 'MENU004', 'description': 'Alitas crujientes con salsa BBQ o picante', 'image_url': 'https://images.pexels.com/photos/2338407/pexels-photo-2338407.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2', 'attributes': {'Category': 'Aperitivos', 'Ingredients': 'Alitas de Pollo, Salsa BBQ'}},
                {'name': 'Churrasco con Tostones', 'price': 19.50, 'item_code': 'MENU005', 'description': 'Churrasco jugoso servido con tostones', 'image_url': 'https://images.pexels.com/photos/3186654/pexels-photo-3186654.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2', 'attributes': {'Category': 'Platos Principales', 'Ingredients': 'Churrasco, Tostones'}},
                {'name': 'Hamburguesa Clásica', 'price': 11.25, 'item_code': 'MENU006', 'description': 'Hamburguesa clásica con todos los acompañamientos', 'image_url': 'https://images.pexels.com/photos/1639557/pexels-photo-1639557.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2', 'attributes': {'Category': 'Platos Principales', 'Ingredients': 'Carne, Queso, Vegetales'}},
            ],
            'specials': [
                {'title': 'Happy Hour: Cervezas Locales', 'content': '🍺 Disfruta de 2x1 en todas las cervezas locales. Válido de 5pm a 7pm.'},
                {'title': 'Happy Hour: Combo Pizza', 'content': '🍕 Combo de Pizza personal + Cerveza por solo $9.99.'},
                {'title': 'Happy Hour: Billar Gratis', 'content': '🎱 Juega billar GRATIS con tu primera ronda de bebidas.'},
            ],
            'owner_email': 'owner@country-pizza.com',
            'owner_password': 'password123'
        },
        {
            'business_type': 'auto-sales',
            'name': 'Premium Auto Sales',
            'slug_id': 'premium-auto-sales',
            'tagline': 'Quality Vehicles at Great Prices',
            'about_text': 'We specialize in quality pre-owned vehicles with full inspection and warranty options.',
            'address': '456 Auto Boulevard, Car City, CA 90210',
            'phone': '15551234567',
            'phone_display': '(555) 123-4567',
            'hours': 'Monday-Saturday: 9am-7pm\nSunday: 11am-5pm',
            'hero_image_url': 'https://images.pexels.com/photos/116675/pexels-photo-116675.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
            'items': [
                {'name': '2020 Toyota Camry', 'price': 18900.00, 'item_code': 'VIN001', 'description': 'Well-maintained sedan with low mileage', 'status': 'Available', 'attributes': {'Make': 'Toyota', 'Model': 'Camry', 'Year': '2020', 'Mileage': '25000', 'Color': 'Silver', 'Condition': 'Excellent'}},
                {'name': '2019 Honda CR-V', 'price': 22900.00, 'item_code': 'VIN002', 'description': 'Spacious SUV perfect for families', 'status': 'Available', 'attributes': {'Make': 'Honda', 'Model': 'CR-V', 'Year': '2019', 'Mileage': '32000', 'Color': 'Black', 'Condition': 'Very Good'}},
                {'name': '2021 Ford F-150', 'price': 32900.00, 'item_code': 'VIN003', 'description': 'Powerful truck ready for work or play', 'status': 'Pending', 'attributes': {'Make': 'Ford', 'Model': 'F-150', 'Year': '2021', 'Mileage': '18000', 'Color': 'Blue', 'Condition': 'Excellent'}},
            ],
            'specials': [
                {'title': 'Spring Sale', 'content': '💰 0% APR financing available on select vehicles this month!'},
            ],
            'owner_email': 'owner@premiumauto.com',
            'owner_password': 'demo123'
        },
        {
            'business_type': 'auto-services',
            'name': 'Quick Fix Auto Service',
            'slug_id': 'quick-fix-auto',
            'tagline': 'Professional Auto Services You Can Trust',
            'about_text': 'Full-service auto repair and maintenance with certified technicians.',
            'address': '789 Service Road, Repair Town, TX 75001',
            'phone': '15559876543',
            'phone_display': '(555) 987-6543',
            'hours': 'Monday-Friday: 8am-6pm\nSaturday: 9am-4pm',
            'hero_image_url': 'https://images.pexels.com/photos/13065693/pexels-photo-13065693.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
            'items': [
                {'name': 'Oil Change Service', 'price': 39.99, 'item_code': 'SRV001', 'description': 'Full synthetic oil change with filter replacement', 'status': 'Available', 'attributes': {'Service Type': 'Maintenance', 'Duration': '30 minutes', 'Warranty': '3 months'}},
                {'name': 'Brake Inspection & Service', 'price': 89.99, 'item_code': 'SRV002', 'description': 'Complete brake system inspection and pad replacement', 'status': 'Available', 'attributes': {'Service Type': 'Repair', 'Duration': '1-2 hours', 'Warranty': '12 months'}},
                {'name': 'Tire Rotation & Balance', 'price': 49.99, 'item_code': 'SRV003', 'description': 'Professional tire rotation and wheel balancing', 'status': 'Available', 'attributes': {'Service Type': 'Maintenance', 'Duration': '45 minutes', 'Warranty': '6 months'}},
            ],
            'specials': [
                {'title': 'New Customer Special', 'content': '🔧 $10 off your first service! Mention this ad.'},
            ],
            'owner_email': 'owner@quickfix.com',
            'owner_password': 'demo123'
        },
        {
            'business_type': 'other-services',
            'name': 'Pro Services Hub',
            'slug_id': 'pro-services-hub',
            'tagline': 'Quality Services You Can Trust',
            'about_text': 'Professional services for home and business needs.',
            'address': '321 Service Center Drive, Business City, NY 10001',
            'phone': '15558889999',
            'phone_display': '(555) 888-9999',
            'hours': 'Monday-Friday: 9am-6pm\nBy Appointment',
            'hero_image_url': 'https://images.pexels.com/photos/3184465/pexels-photo-3184465.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
            'items': [
                {'name': 'Home Cleaning Service', 'price': 120.00, 'item_code': 'SRV101', 'description': 'Professional deep cleaning for your home', 'status': 'Available', 'attributes': {'Service Type': 'Cleaning', 'Duration': '2-4 hours', "What's Included": 'Kitchen, Bathrooms, Living Areas'}},
                {'name': 'Consulting Session', 'price': 150.00, 'item_code': 'SRV102', 'description': 'One-on-one business consulting', 'status': 'Available', 'attributes': {'Service Type': 'Consulting', 'Duration': '1 hour', "What's Included": 'Strategy Session & Action Plan'}},
            ],
            'specials': [],
            'owner_email': 'owner@proservices.com',
            'owner_password': 'demo123'
        },
        {
            'business_type': 'generic-store',
            'name': 'General Store Demo',
            'slug_id': 'general-store-demo',
            'tagline': 'Quality Products You\'ll Love',
            'about_text': 'A wide variety of quality products for all your needs.',
            'address': '999 Store Street, Shopping Mall, FL 33101',
            'phone': '15557778888',
            'phone_display': '(555) 777-8888',
            'hours': 'Monday-Saturday: 10am-8pm\nSunday: 12pm-6pm',
            'hero_image_url': 'https://images.pexels.com/photos/3962285/pexels-photo-3962285.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=2',
            'items': [
                {'name': 'Premium Widget', 'price': 29.99, 'item_code': 'SKU001', 'description': 'High-quality widget for everyday use', 'status': 'Available', 'attributes': {'Category': 'Electronics', 'Brand': 'WidgetPro', 'Color': 'Black'}},
                {'name': 'Deluxe Gadget', 'price': 49.99, 'item_code': 'SKU002', 'description': 'Advanced gadget with multiple features', 'status': 'Available', 'attributes': {'Category': 'Electronics', 'Brand': 'GadgetMaster', 'Color': 'Silver'}},
            ],
            'specials': [
                {'title': 'Grand Opening Sale', 'content': '🎉 20% off all items this week!'},
            ],
            'owner_email': 'owner@generalstore.com',
            'owner_password': 'demo123'
        }
    ]
    
    created_count = 0
    for demo in demo_stores:
        # Check if store already exists
        existing_store = db.stores.find_one({"slug_id": demo['slug_id']})
        if existing_store:
            print(f"  ✓ Store '{demo['slug_id']}' already exists, skipping...")
            continue
        
        print(f"  Creating demo store: {demo['name']}...")
        
        # Create store
        store_data = {
            "name": demo['name'],
            "slug_id": demo['slug_id'],
            "business_type": demo['business_type'],
            "tagline": demo['tagline'],
            "about_text": demo['about_text'],
            "address": demo['address'],
            "phone": demo['phone'],
            "phone_display": demo['phone_display'],
            "hours": demo['hours'],
            "lang": "es" if demo['slug_id'] == 'country-pizza' else "en",
            "hero_image_url": demo['hero_image_url'],
            "logo_url": '/static/img/logo.png' if demo['slug_id'] == 'country-pizza' else None,
            "gallery_image_1_url": demo.get('gallery_image_1_url'),
            "gallery_image_2_url": demo.get('gallery_image_2_url'),
            "menu_image_url": demo.get('menu_image_url'),
            "google_maps_embed_html": demo.get('google_maps_embed_html'),
            "inventory_description": None,
            "socials": demo.get('socials', []),
            # Theme defaults
            "theme_primary": demo.get('theme_primary', '#3b82f6'),
            "theme_secondary": demo.get('theme_secondary', '#f59e0b'),
            "theme_background": demo.get('theme_background', '#111827'),
            "theme_surface": demo.get('theme_surface', '#1f2937'),
            "theme_text": demo.get('theme_text', '#f9fafb'),
            "theme_text_secondary": demo.get('theme_text_secondary', '#d1d5db'),
            "date_created": datetime.datetime.utcnow()
        }
        
        store_id = db.stores.insert_one(store_data).inserted_id
        
        # Create admin user
        db.users.insert_one({
            "email": demo['owner_email'],
            "password": demo['owner_password'],  # In production, hash this!
            "role": "owner",
            "store_id": store_id,
            "date_created": datetime.datetime.utcnow()
        })
        
        # Create items
        business_config = BUSINESS_TYPES[demo['business_type']]
        for item_data in demo['items']:
            item = {
                "name": item_data['name'],
                "item_code": item_data['item_code'],
                "price": item_data['price'],
                "description": item_data.get('description', business_config['default_description']),
                "image_url": item_data.get('image_url'),
                "status": item_data.get('status', business_config['status_options'][0] if business_config['status_options'] else None),
                "store_id": store_id,
                "date_added": datetime.datetime.utcnow(),
                "attributes": item_data.get('attributes', {})
            }
            db.items.insert_one(item)
        
        # Create specials
        for special_data in demo.get('specials', []):
            db.specials.insert_one({
                "title": special_data['title'],
                "content": special_data['content'],
                "date_created": datetime.datetime.utcnow(),
                "store_id": store_id
            })
        
        created_count += 1
        print(f"    ✓ Created store with {len(demo['items'])} items and {len(demo.get('specials', []))} specials")
    
    if created_count > 0:
        print(f"\n✅ Successfully created {created_count} demo store(s)!")
        print("   You can now access them from the business type selection page.")
    else:
        print("\n✅ All demo stores already exist.")

if __name__ == '__main__':
    with app.app_context():
        seed_database()
    app.run(debug=True, port=5000)
