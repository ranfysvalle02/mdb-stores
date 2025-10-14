"""
A complete, single-file Flask application boilerplate for a simple inventory-based website.

HOW TO USE:
1.  Prerequisites:
    - Python 3
    - A running MongoDB instance
    - Run: pip install Flask pymongo

2.  Customize the Store:
    - Change the `STORE_SLUG_ID` variable below to a unique identifier for your store (e.g., 'janes-bookstore').
    - Edit the `seed_database()` function with your store's name, details, product attributes, and initial inventory.

3.  Run the Application:
    - From your terminal, run: python app.py
    - The first time you run it, it will populate the database with your store's information.
    - Open your browser and go to http://127.0.0.1:5000

4.  Log In and Manage:
    - Go to http://127.0.0.1:5000/admin/login
    - Use the email and password you set in the `seed_database()` function (default is owner@example.com / password123).
"""
import datetime
from flask import Flask, request, render_template_string, redirect, url_for, flash, session, g, abort
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson.errors import InvalidId
from functools import wraps
from pymongo.errors import DuplicateKeyError

# --- App & DB Configuration ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'a-truly-generic-single-store-secret-key'

# --- (STEP 1) CONFIGURE YOUR STORE'S UNIQUE ID ---
# Change this to a unique, URL-friendly identifier for your store.
STORE_SLUG_ID = 'my-awesome-store'

# --- MongoDB Connection ---
client = MongoClient('mongodb://localhost:27017/?retryWrites=true&w=majority&directConnection=true')
db = client['single_store_db'] # You can rename this database if you wish.

# --- Create Unique Indexes for Collections ---
# These ensure data integrity, e.g., no two products can have the same SKU.
db.stores.create_index("slug_id", unique=True)
db.users.create_index([("email", 1), ("store_id", 1)], unique=True)
db.products.create_index([("sku", 1), ("store_id", 1)], unique=True)


# --- HTML TEMPLATES ---

# Base layout
LAYOUT_TEMPLATE = """
<!doctype html>
<html lang="{{ store.lang or 'en' }}" class="scroll-smooth">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <script src="https://cdn.tailwindcss.com"></script>
    <title>{{ store.name }}</title>
</head>
<body class="bg-gray-200 text-gray-900 flex flex-col min-h-screen">
    <nav class="bg-gray-800 text-white shadow-lg sticky top-0 z-50">
        <div class="container mx-auto px-6 py-3 flex justify-between items-center">
            <a href="{{ url_for('home') }}" class="flex items-center space-x-3">
                {% if store.logo_url %}<img src="{{ store.logo_url }}" alt="{{ store.name }} Logo" class="h-12">{% endif %}
                <span class="text-2xl font-bold text-white tracking-wider">{{ store.name }}</span>
            </a>
            <div class="flex items-center space-x-4">
                {% if store.lang == 'es' %}
                    <a href="#specials" class="px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Ofertas</a>
                    <a href="#inventory" class="px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Inventario</a>
                    <a href="#about" class="px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Sobre Nosotros</a>
                {% else %}
                    <a href="#specials" class="px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Specials</a>
                    <a href="#inventory" class="px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700">Inventory</a>
                    <a href="#about" class="px-4 py-2 rounded-md text-sm font-medium hover:bg-gray-700">About Us</a>
                {% endif %}
                {% if 'user_id' in session and session.get('store_id') == store._id|string %}
                    <a href="{{ url_for('dashboard') }}" class="px-4 py-2 rounded-md text-sm font-medium bg-blue-600 hover:bg-blue-700">Dashboard</a>
                    <a href="{{ url_for('logout') }}" class="px-4 py-2 rounded-md text-sm font-medium bg-red-600 hover:red-bg-700">Logout</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <main class="container mx-auto mt-8 p-6 flex-grow">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}{% for category, message in messages %}
            <div class="p-4 mb-4 text-sm rounded-lg {{ 'bg-green-100 text-green-800' if category == 'success' else 'bg-red-100 text-red-800' }}" role="alert">
                <span class="font-medium">{{ category.title() }}!</span> {{ message }}
            </div>
            {% endfor %}{% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="bg-gray-800 text-white mt-12 py-8">
        <div class="container mx-auto px-6 text-center">
            <p class="font-bold text-lg">{{ store.name }}</p>
            <p class="text-gray-400 mt-2">{{ store.address }}</p>
            <p class="text-gray-400 mt-1"><strong>{% if store.lang == 'es' %}Horarios{% else %}Hours{% endif %}:</strong> {{ store.hours }}</p>
            <p class="text-gray-300 mt-4 text-sm">© {{ now.year }} {{ store.name }}. {% if store.lang == 'es' %}Todos los derechos reservados.{% else %}All Rights Reserved.{% endif %}</p>
        </div>
    </footer>
</body>
</html>
"""

# Home page
HOME_TEMPLATE = """
{% extends "layout" %}
{% block content %}
<section id="specials" class="pt-4 mb-16">
    <div class="bg-white p-8 rounded-lg shadow-xl">
        <div class="text-center mb-10">
            <h1 class="text-4xl font-extrabold mb-2 text-gray-800">{% if store.lang == 'es' %}Últimas Ofertas y Noticias{% else %}Latest Deals & News{% endif %}</h1>
            <p class="text-gray-600">{% if store.lang == 'es' %}¡Vea nuestras ofertas actuales!{% else %}Check out our current specials!{% endif %}</p>
        </div>
        <div class="space-y-8">
            {% for special in specials %}
            <div class="flex flex-col md:flex-row gap-6 items-center {% if not loop.last %}border-b pb-8{% endif %}">
                {% if special.image_url %}<div class="md:w-1/3 flex-shrink-0"><img src="{{ special.image_url }}" alt="{{ special.title }}" class="w-full h-48 object-cover rounded-lg shadow-md"></div>{% endif %}
                <div class="{% if special.image_url %}md:w-2/3{% else %}w-full{% endif %}">
                    <h2 class="text-2xl font-bold text-gray-800">{{ special.title }}</h2>
                    <p class="text-sm text-gray-500 mb-3">{{ special.date_created.strftime('%B %d, %Y') }}</p>
                    <p class="text-gray-700 whitespace-pre-wrap">{{ special.content }}</p>
                </div>
            </div>
            {% else %}
            <p class="col-span-full text-center text-gray-500">{% if store.lang == 'es' %}No hay ofertas especiales disponibles en este momento.{% else %}No specials are available at the moment.{% endif %}</p>
            {% endfor %}
        </div>
    </div>
</section>

<section id="inventory" class="pt-4">
    <div class="bg-white p-8 rounded-lg shadow-xl">
        <div class="text-center mb-10">
            <h1 class="text-4xl font-extrabold mb-2 text-gray-800">{% if store.lang == 'es' %}Nuestro Inventario{% else %}Our Inventory{% endif %}</h1>
            <p class="text-gray-600">{{ store.tagline }}</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {% for product in products %}
            <div class="border rounded-lg overflow-hidden shadow-lg transition-transform transform hover:-translate-y-2 hover:shadow-2xl">
                <a href="{{ url_for('product_details', product_id=product._id) }}"><img src="{{ product.image_url or 'https://placehold.co/600x400/cccccc/ffffff?text=Image+Not+Available' }}" alt="Image of {{ product.name }}" class="w-full h-56 object-cover"></a>
                <div class="p-6">
                    <h2 class="text-2xl font-bold text-gray-800">{{ product.name }}</h2>
                    <p class="text-xl font-semibold text-green-600 mt-2">${{ "%.2f"|format(product.price) }}</p>
                    {% set first_attr_key = product.attributes.keys()|first %}{% if first_attr_key %}<p class="text-gray-500 text-sm mt-1"><strong>{{ first_attr_key }}:</strong> {{ product.attributes[first_attr_key] }}</p>{% endif %}
                    <a href="{{ url_for('product_details', product_id=product._id) }}" class="mt-4 inline-block w-full text-center bg-gray-800 hover:bg-green-600 hover:text-white text-white font-bold py-2 px-4 rounded-md transition-colors">{% if store.lang == 'es' %}Ver Detalles{% else %}View Details{% endif %}</a>
                </div>
            </div>
            {% else %}
            <p class="col-span-full text-center text-gray-500">{% if store.lang == 'es' %}No hay productos disponibles actualmente.{% else %}No products are currently available.{% endif %}</p>
            {% endfor %}
        </div>
    </div>
</section>

<section id="about" class="mt-16 pt-4">
    <div class="bg-white p-8 rounded-lg shadow-xl">
        <div class="text-center"><h2 class="text-3xl font-extrabold text-gray-800 mb-4">{% if store.lang == 'es' %}Sobre Nosotros{% else %}About Us{% endif %}</h2></div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-12 items-center mt-6">
            <div class="text-gray-700 leading-relaxed text-center md:text-left">
                <h3 class="text-2xl font-bold text-gray-900 mb-2">{{ store.name }}</h3>
                <p class="whitespace-pre-wrap">{{ store.about_text }}</p>
            </div>
            <div class="text-center md:text-left">
                <h3 class="text-2xl font-bold text-gray-900 mb-2">{% if store.lang == 'es' %}Visítanos{% else %}Visit Us{% endif %}</h3>
                <p>{{ store.address }}</p>
                <p class="mt-4"><strong>{% if store.lang == 'es' %}Horarios{% else %}Hours{% endif %}:</strong><br>{{ store.hours }}</p>
            </div>
        </div>
    </div>
</section>

{% if store.google_maps_embed_html %}
<section id="location" class="mt-16">
    <div class="bg-white rounded-lg shadow-xl overflow-hidden">
        {{ store.google_maps_embed_html | safe }}
    </div>
</section>
{% endif %}
{% endblock %}
"""

# Product details page
PRODUCT_DETAILS_TEMPLATE = """
{% extends "layout" %}
{% block content %}
<div class="bg-white p-8 rounded-lg shadow-xl">
    <a href="{{ url_for('home') }}#inventory" class="text-green-600 font-semibold hover:underline mb-6 inline-block">← {% if store.lang == 'es' %}Volver al Inventario{% else %}Back to Inventory{% endif %}</a>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div><img src="{{ product.image_url or 'https://placehold.co/600x400/cccccc/ffffff?text=Image+Not+Available' }}" alt="Image of {{ product.name }}" class="w-full h-auto object-cover rounded-lg shadow-md"></div>
        <div>
            <h1 class="text-4xl font-extrabold text-gray-800">{{ product.name }}</h1>
            <p class="text-3xl font-bold text-green-600 mt-4">${{ "%.2f"|format(product.price) }}</p>
            <div class="mt-6 border-t pt-6">
                <h2 class="text-xl font-semibold mb-3">{% if store.lang == 'es' %}Detalles del Producto{% else %}Product Details{% endif %}</h2>
                <ul class="space-y-2 text-gray-700">
                    <li><strong>SKU:</strong> {{ product.sku }}</li>
                    {% for key, value in product.attributes.items() %}
                    <li><strong>{{ key }}:</strong> {{ value }}</li>
                    {% endfor %}
                    <li><strong>{% if store.lang == 'es' %}Estado{% else %}Status{% endif %}:</strong> <span class="font-semibold px-2 py-1 rounded-full {{ 'bg-green-100 text-green-800' if product.status == 'Available' else 'bg-red-100 text-red-800' }}">{{ product.status }}</span></li>
                </ul>
            </div>
            <div class="mt-6 border-t pt-6">
                 <h2 class="text-xl font-semibold mb-3">{% if store.lang == 'es' %}Descripción{% else %}Description{% endif %}</h2>
                 <p class="text-gray-600 whitespace-pre-wrap">{{ product.description or 'No description provided.' }}</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
"""

# Admin templates (kept in English for simplicity)
DASHBOARD_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="flex justify-between items-center mb-6"><h1 class="text-4xl font-extrabold text-gray-800">Main Dashboard</h1></div><div class="grid grid-cols-1 md:grid-cols-2 gap-8"><div class="bg-white p-6 rounded-lg shadow-xl"><h2 class="text-2xl font-bold mb-4">Inventory Management</h2><p class="text-gray-600 mb-4">Add, edit, or remove products from your store's inventory.</p><a href="{{ url_for('list_products') }}" class="bg-blue-500 hover:bg-blue-600 text-white font-bold py-2 px-4 rounded-md">Manage Products</a></div><div class="bg-white p-6 rounded-lg shadow-xl"><h2 class="text-2xl font-bold mb-4">Specials & Announcements</h2><p class="text-gray-600 mb-4">Create or update posts for your customers to see on the homepage.</p><a href="{{ url_for('list_specials') }}" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md">Manage Specials</a></div></div>{% endblock %}"""
PRODUCT_DASHBOARD_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="flex justify-between items-center mb-6"><h1 class="text-4xl font-extrabold text-gray-800">Inventory Dashboard</h1><div><a href="{{ url_for('dashboard') }}" class="text-gray-600 hover:underline mr-4">← Back to Main Dashboard</a><a href="{{ url_for('add_product') }}" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md shadow-lg">+ Add New Product</a></div></div><div class="bg-white p-8 rounded-lg shadow-xl overflow-x-auto"><table class="w-full text-left"><thead class="bg-gray-50 border-b-2 border-gray-200"><tr><th class="p-4">Product Name</th><th class="p-4">SKU</th><th class="p-4">Price</th><th class="p-4">Status</th><th class="p-4 text-center">Actions</th></tr></thead><tbody>{% for product in products %}<tr class="border-b hover:bg-gray-50"><td class="p-4 font-medium">{{ product.name }}</td><td class="p-4 text-gray-600">{{ product.sku }}</td><td class="p-4 text-gray-600">${{ "%.2f"|format(product.price) }}</td><td class="p-4"><span class="font-semibold px-2 py-1 text-xs rounded-full {{ 'bg-green-100 text-green-800' if product.status == 'Available' else 'bg-red-100 text-red-800' }}">{{ product.status }}</span></td><td class="p-4 text-center space-x-2"><a href="{{ url_for('edit_product', product_id=product._id) }}" class="text-blue-600 hover:underline">Edit</a><form action="{{ url_for('mark_as_sold', product_id=product._id) }}" method="post" class="inline"><button type="submit" class="text-green-600 hover:underline">Mark Sold</button></form><form action="{{ url_for('delete_product', product_id=product._id) }}" method="post" class="inline" onsubmit="return confirm('Delete this product permanently?');"><button type="submit" class="text-red-600 hover:underline">Delete</button></form></td></tr>{% else %}<tr><td colspan="5" class="text-center p-6 text-gray-500">No products found. Add one to get started!</td></tr>{% endfor %}</tbody></table></div>{% endblock %}"""
PRODUCT_FORM_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="max-w-2xl mx-auto bg-white p-8 rounded-lg shadow-xl"><h1 class="text-3xl font-bold mb-6 text-gray-800">{{ 'Edit Product' if product else 'Add New Product' }}</h1><form method="post" class="space-y-6"><div class="p-4 bg-gray-50 rounded-lg"><h2 class="text-lg font-semibold text-gray-700 mb-2">Core Details</h2><div><label for="name" class="block text-sm font-medium text-gray-700">Product Name</label><input type="text" name="name" value="{{ product.name or '' }}" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" required></div><div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-4"><div><label for="sku" class="block text-sm font-medium text-gray-700">SKU (Unique ID)</label><input type="text" name="sku" value="{{ product.sku or '' }}" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" required></div><div><label for="price" class="block text-sm font-medium text-gray-700">Price ($)</label><input type="number" step="0.01" name="price" value="{{ product.price or '' }}" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" required></div></div></div><div class="p-4 bg-gray-50 rounded-lg"><h2 class="text-lg font-semibold text-gray-700 mb-2">Custom Attributes</h2>{% for attr in store.product_attributes_template %}<div class="mt-4"><label for="attr_{{ attr.name }}" class="block text-sm font-medium text-gray-700">{{ attr.name }}</label>{% if attr.type == 'textarea' %}<textarea name="attr_{{ attr.name }}" rows="3" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md">{{ product.attributes.get(attr.name, '') }}</textarea>{% else %}<input type="{{ attr.type }}" name="attr_{{ attr.name }}" value="{{ product.attributes.get(attr.name, '') }}" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" {% if attr.required %}required{% endif %}>{% endif %}</div>{% endfor %}</div><div class="p-4 bg-gray-50 rounded-lg"><h2 class="text-lg font-semibold text-gray-700 mb-2">Additional Information</h2><div class="mt-4"><label for="image_url" class="block text-sm font-medium text-gray-700">Image URL</label><input type="url" name="image_url" value="{{ product.image_url or '' }}" placeholder="https://..." class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"></div><div class="mt-4"><label for="description" class="block text-sm font-medium text-gray-700">Description</label><textarea name="description" rows="4" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md">{{ product.description or '' }}</textarea></div></div><div class="flex items-center justify-end gap-4 pt-4 border-t"><a href="{{ url_for('list_products') }}" class="text-gray-600 hover:underline">Cancel</a><button type="submit" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md">{{ 'Save Changes' if product else 'Add Product' }}</button></div></form></div>{% endblock %}"""
SPECIALS_DASHBOARD_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="flex justify-between items-center mb-6"><h1 class="text-4xl font-extrabold text-gray-800">Specials & Announcements</h1><div><a href="{{ url_for('dashboard') }}" class="text-gray-600 hover:underline mr-4">← Back to Main Dashboard</a><a href="{{ url_for('add_special') }}" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md shadow-lg">+ Add New Special</a></div></div><div class="bg-white p-8 rounded-lg shadow-xl">{% for special in specials %}<div class="flex items-start gap-4 {% if not loop.last %}border-b pb-4 mb-4{% endif %}">{% if special.image_url %}<img src="{{ special.image_url }}" class="w-24 h-24 object-cover rounded-md">{% endif %}<div class="flex-grow"><h2 class="text-xl font-bold">{{ special.title }}</h2><p class="text-sm text-gray-500">{{ special.date_created.strftime('%B %d, %Y') }}</p><p class="text-gray-600 mt-2">{{ special.content|truncate(150) }}</p></div><div class="flex-shrink-0 flex flex-col space-y-2"><a href="{{ url_for('edit_special', special_id=special._id) }}" class="text-blue-600 hover:underline">Edit</a><form action="{{ url_for('delete_special', special_id=special._id) }}" method="post" onsubmit="return confirm('Delete this special?');"><button type="submit" class="text-red-600 hover:underline">Delete</button></form></div></div>{% else %}<p class="text-center text-gray-500">No specials found. Add one to get started!</p>{% endfor %}</div>{% endblock %}"""
SPECIAL_FORM_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="max-w-2xl mx-auto bg-white p-8 rounded-lg shadow-xl"><h1 class="text-3xl font-bold mb-6 text-gray-800">{{ 'Edit Special' if special else 'Add New Special' }}</h1><form method="post" class="space-y-6"><div><label for="title" class="block text-sm font-medium text-gray-700">Title</label><input type="text" name="title" value="{{ special.title or '' }}" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" required></div><div><label for="content" class="block text-sm font-medium text-gray-700">Content</label><textarea name="content" rows="6" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" required>{{ special.content or '' }}</textarea></div><div><label for="image_url" class="block text-sm font-medium text-gray-700">Image URL (Optional)</label><input type="url" name="image_url" value="{{ special.image_url or '' }}" placeholder="https://..." class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md"></div><div class="flex items-center justify-end gap-4 pt-4 border-t"><a href="{{ url_for('list_specials') }}" class="text-gray-600 hover:underline">Cancel</a><button type="submit" class="bg-green-500 hover:bg-green-600 text-white font-bold py-2 px-4 rounded-md">{{ 'Save Changes' if special else 'Create Special' }}</button></div></form></div>{% endblock %}"""
LOGIN_TEMPLATE = """{% extends "layout" %}{% block content %}<div class="max-w-md mx-auto bg-white p-8 mt-10 rounded-lg shadow-xl"><h1 class="text-3xl font-bold mb-6 text-center text-gray-800">Owner Login for {{ store.name }}</h1><form method="post" class="space-y-4"><div><label for="email" class="block text-sm font-medium text-gray-700">Email</label><input type="email" name="email" id="email" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" required></div><div><label for="password" class="block text-sm font-medium text-gray-700">Password</label><input type="password" name="password" id="password" class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md" required></div><button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-gray-800 hover:bg-green-600">Sign In</button></form></div>{% endblock %}"""

# --- Helper Functions & Decorators ---
def render_page(template_string, **context):
    """Renders a page by injecting its content into the base layout."""
    context['now'] = datetime.datetime.utcnow()
    context['store'] = g.store
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
        if not g.store: abort(404)
        if ('user_id' not in session or 'store_id' not in session or 
            session['store_id'] != str(g.store['_id'])):
            flash('You must be logged in as the owner to view this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- (STEP 2) SEEDING FUNCTION: CUSTOMIZE YOUR STORE'S DATA HERE ---
def seed_database():
    """
    Populates the database with the store's initial data if it doesn't exist.
    THIS IS THE PRIMARY AREA TO CUSTOMIZE FOR YOUR STORE.
    """
    if not db.stores.find_one({"slug_id": STORE_SLUG_ID}):
        print(f"Store '{STORE_SLUG_ID}' not found. Seeding database...")
        
        # --- Store Information ---
        store_data = {
            "name": "My Awesome Store",
            "slug_id": STORE_SLUG_ID,
            "lang": "en", # 'en' for English, 'es' for Spanish
            "logo_url": None, # e.g., "https://i.imgur.com/your-logo.png"
            "address": "123 Main Street, Anytown, USA 12345",
            "google_maps_embed_html": None, # Paste your full Google Maps iframe code here
            "hours": "Monday to Friday: 9am - 5pm\nSaturday: 10am - 3pm",
            "tagline": "Your one-stop shop for amazing things.",
            "about_text": "Welcome to our store! We are passionate about providing the highest quality products and the best customer service. Our journey started in a small garage and has grown into what it is today, all thanks to customers like you.",
            
            # --- Define Custom Product Fields for the Admin Form ---
            "product_attributes_template": [
                {"name": "Color", "type": "text", "required": True},
                {"name": "Size", "type": "text", "required": False},
                {"name": "Material", "type": "text", "required": False},
                {"name": "Specifications", "type": "textarea", "required": False}
            ]
        }
        store_id = db.stores.insert_one(store_data).inserted_id

        # --- Store Owner Login ---
        db.users.insert_one({
            "email": "owner@example.com", 
            "password": "password123", 
            "role": "owner", 
            "store_id": store_id
        })

        # --- Initial Product Inventory ---
        db.products.insert_many([
            {
                "name": "Deluxe Widget",
                "sku": "WIDGET-001",
                "price": 19.99,
                "description": "A high-quality widget designed for excellence. Features a durable chassis and a sleek, modern design.",
                "image_url": "https://placehold.co/600x400/2d3748/ffffff?text=Deluxe+Widget",
                "status": "Available",
                "store_id": store_id,
                "date_added": datetime.datetime.utcnow(),
                "attributes": {"Color": "Red", "Size": "Large", "Material": "Stainless Steel", "Specifications": "- 5.5 inch display\n- 12-hour battery life"}
            },
            {
                "name": "Standard Gadget",
                "sku": "GADGET-A5",
                "price": 9.95,
                "description": "A reliable and affordable gadget for everyday use. Perfect for simple tasks.",
                "image_url": "https://placehold.co/600x400/4a5568/ffffff?text=Standard+Gadget",
                "status": "Available",
                "store_id": store_id,
                "date_added": datetime.datetime.utcnow(),
                "attributes": {"Color": "Blue", "Size": "Medium", "Material": "Plastic"}
            }
        ])

        # --- Initial Specials/Announcements ---
        db.specials.insert_one({
            "title": "Grand Opening Sale!",
            "content": "To celebrate our grand opening, get 10% off all items this week! Come visit us at our new location on Main Street.",
            "image_url": "https://placehold.co/800x400/a0aec0/ffffff?text=Grand+Opening!",
            "date_created": datetime.datetime.utcnow(),
            "store_id": store_id
        })
        print("Database seeding complete.")

# --- Global & Pre-Request Logic ---
@app.before_request
def load_store():
    """Load the store object from the database before each request."""
    g.store = db.stores.find_one({"slug_id": STORE_SLUG_ID})
    if not g.store:
        abort(500, description=f"Store with slug_id '{STORE_SLUG_ID}' not found in the database. Please run the seed function.")

# --- Public Store Routes ---
@app.route('/')
def home():
    """Display the store's homepage."""
    products = list(db.products.find({"status": "Available", "store_id": g.store['_id']}).sort("date_added", -1))
    specials = list(db.specials.find({"store_id": g.store['_id']}).sort("date_created", -1))
    return render_page(HOME_TEMPLATE, products=products, specials=specials)

@app.route('/product/<string:product_id>')
def product_details(product_id):
    """Display details for a single product."""
    try:
        product = db.products.find_one({"_id": ObjectId(product_id), "store_id": g.store['_id']})
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('home'))
        return render_page(PRODUCT_DETAILS_TEMPLATE, product=product)
    except InvalidId:
        flash('Invalid product ID.', 'error')
        return redirect(url_for('home'))

# --- Admin Routes ---
@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    """Handle store owner login."""
    if request.method == 'POST':
        user = db.users.find_one({
            "email": request.form.get('email'), 
            "password": request.form.get('password'), 
            "store_id": g.store['_id']
        })
        if user:
            session['user_id'] = str(user['_id'])
            session['store_id'] = str(user['store_id'])
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.', 'error')
    return render_page(LOGIN_TEMPLATE)

@app.route('/admin/logout')
def logout():
    """Log the user out."""
    session.clear()
    flash('You have been successfully logged out.', 'success')
    return redirect(url_for('home'))

@app.route('/admin/dashboard')
@owner_required
def dashboard():
    """Display the main admin dashboard."""
    return render_page(DASHBOARD_TEMPLATE)

# Admin Product Routes
@app.route('/admin/products')
@owner_required
def list_products():
    """List all products."""
    products = list(db.products.find({"store_id": g.store['_id']}).sort([("status", 1), ("name", 1)]))
    return render_page(PRODUCT_DASHBOARD_TEMPLATE, products=products)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@owner_required
def add_product():
    """Handle adding a new product."""
    if request.method == 'POST':
        form = request.form
        attributes = {attr['name']: form.get(f"attr_{attr['name']}") for attr in g.store['product_attributes_template']}
        new_product = {
            "name": form.get('name'), "sku": form.get('sku').upper(), "price": form.get('price', type=float),
            "image_url": form.get('image_url') or None, "description": form.get('description'),
            "status": "Available", "store_id": g.store['_id'], "date_added": datetime.datetime.utcnow(),
            "attributes": attributes
        }
        try:
            db.products.insert_one(new_product)
            flash(f"Product '{new_product['name']}' added successfully!", 'success')
            return redirect(url_for('list_products'))
        except DuplicateKeyError:
            flash(f"Error: A product with SKU '{new_product['sku']}' already exists.", 'error')
            return render_page(PRODUCT_FORM_TEMPLATE, product=new_product)
    return render_page(PRODUCT_FORM_TEMPLATE, product=None)

@app.route('/admin/product/edit/<string:product_id>', methods=['GET', 'POST'])
@owner_required
def edit_product(product_id):
    """Handle editing an existing product."""
    try:
        product = db.products.find_one({"_id": ObjectId(product_id), "store_id": g.store['_id']})
        if not product: return redirect(url_for('list_products'))
        if request.method == 'POST':
            form = request.form
            attributes = {attr['name']: form.get(f"attr_{attr['name']}") for attr in g.store['product_attributes_template']}
            update_data = {
                "name": form.get('name'), "sku": form.get('sku').upper(), "price": form.get('price', type=float),
                "image_url": form.get('image_url') or None, "description": form.get('description'), 
                "attributes": attributes
            }
            try:
                db.products.update_one({"_id": ObjectId(product_id)}, {"$set": update_data})
                flash('Product updated successfully!', 'success')
                return redirect(url_for('list_products'))
            except DuplicateKeyError:
                flash(f"Error: A product with SKU '{update_data['sku']}' already exists.", 'error')
                product.update(update_data)
                return render_page(PRODUCT_FORM_TEMPLATE, product=product)
        return render_page(PRODUCT_FORM_TEMPLATE, product=product)
    except InvalidId:
        return redirect(url_for('list_products'))

@app.route('/admin/product/sell/<string:product_id>', methods=['POST'])
@owner_required
def mark_as_sold(product_id):
    """Mark a product as Sold."""
    try:
        db.products.update_one({"_id": ObjectId(product_id), "store_id": g.store['_id']}, {"$set": {"status": "Sold"}})
    except InvalidId: pass
    return redirect(url_for('list_products'))

@app.route('/admin/product/delete/<string:product_id>', methods=['POST'])
@owner_required
def delete_product(product_id):
    """Permanently delete a product."""
    try:
        db.products.delete_one({"_id": ObjectId(product_id), "store_id": g.store['_id']})
    except InvalidId: pass
    return redirect(url_for('list_products'))

# Admin Specials Routes
@app.route('/admin/specials')
@owner_required
def list_specials():
    """List all specials/announcements."""
    specials = list(db.specials.find({"store_id": g.store['_id']}).sort("date_created", -1))
    return render_page(SPECIALS_DASHBOARD_TEMPLATE, specials=specials)

@app.route('/admin/specials/add', methods=['GET', 'POST'])
@owner_required
def add_special():
    """Handle adding a new special."""
    if request.method == 'POST':
        form = request.form
        db.specials.insert_one({
            "title": form.get('title'), "content": form.get('content'), 
            "image_url": form.get('image_url') or None,
            "date_created": datetime.datetime.utcnow(), "store_id": g.store['_id']
        })
        flash('New special created!', 'success')
        return redirect(url_for('list_specials'))
    return render_page(SPECIAL_FORM_TEMPLATE, special=None)

@app.route('/admin/specials/edit/<string:special_id>', methods=['GET', 'POST'])
@owner_required
def edit_special(special_id):
    """Handle editing an existing special."""
    try:
        special = db.specials.find_one({"_id": ObjectId(special_id), "store_id": g.store['_id']})
        if not special: return redirect(url_for('list_specials'))
        if request.method == 'POST':
            form = request.form
            db.specials.update_one({"_id": ObjectId(special_id)}, {"$set": {
                "title": form.get('title'), "content": form.get('content'), 
                "image_url": form.get('image_url') or None
            }})
            flash('Special updated!', 'success')
            return redirect(url_for('list_specials'))
        return render_page(SPECIAL_FORM_TEMPLATE, special=special)
    except InvalidId:
        return redirect(url_for('list_specials'))

@app.route('/admin/specials/delete/<string:special_id>', methods=['POST'])
@owner_required
def delete_special(special_id):
    """Permanently delete a special."""
    try:
        db.specials.delete_one({"_id": ObjectId(special_id), "store_id": g.store['_id']})
    except InvalidId: pass
    return redirect(url_for('list_specials'))


if __name__ == '__main__':
    with app.app_context():
        seed_database()
    app.run(debug=True, port=5000)
