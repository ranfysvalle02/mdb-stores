# StoreFactory 🏭

A multi-business-type store application built with Flask and MongoDB. StoreFactory allows you to quickly create and manage online stores for different business types with a beautiful, customizable interface.

## Features

- 🎯 **Multiple Business Types**: Support for Restaurants, Auto Sales, Auto Services, Other Services, and Generic Stores
- 🎨 **Customizable Themes**: Full control over colors, branding, and styling
- 📱 **Mobile Responsive**: Beautiful UI built with Tailwind CSS that works on all devices
- 🔐 **Admin Dashboard**: Comprehensive admin panel for managing inventory, specials, and inquiries
- 📦 **Item Management**: Easy-to-use system for adding, editing, and organizing items/menu/products
- 🎯 **Inquiry System**: Built-in contact/inquiry forms for customer interactions
- 🎪 **Specials & Announcements**: Create and manage special offers and announcements
- 🚀 **Standalone Export**: Generate standalone Flask applications for individual stores
- 🌐 **Multi-Store Support**: Host multiple stores from a single application instance

## Supported Business Types

1. **Restaurant** - Menu items, orders, and specials
2. **Auto Sales** - Vehicle inventory and inquiries
3. **Auto Services** - Service listings and appointments
4. **Other Services** - General service offerings
5. **Generic Store** - Products and inventory

## Requirements

- Python 3.7+
- MongoDB (local or remote)
- pip (Python package manager)

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd mdb-stores
   ```

2. **Install dependencies**:
   ```bash
   pip install flask pymongo python-dotenv
   ```

3. **Start MongoDB Atlas Local** (for local development):
   ```bash
   docker run -p 27017:27017 mongodb/mongodb-atlas-local
   ```

4. **Set up environment variables**:
   Create a `.env` file in the root directory:
   ```env
   SECRET_KEY=your-secret-key-here
   MONGO_URI=mongodb://localhost:27017/?retryWrites=true&w=majority&directConnection=true
   ```
   
   **Note**: For local development, use the MongoDB Atlas Local container above. When deploying to production, simply update `MONGO_URI` in your `.env` file with your production MongoDB connection string:
   ```env
   MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/?retryWrites=true&w=majority
   ```

5. **Run the application**:
   ```bash
   python app.py
   ```

6. **Access the application**:
   Open your browser and navigate to `http://localhost:5000`

## Usage

### Creating a Store

1. Visit the home page (`http://localhost:5000`)
2. Select your business type from the available options
3. Fill out the store creation form with:
   - Store name
   - Store slug (URL-friendly identifier)
   - Admin email and password
   - Store details (address, hours, contact info)
   - Theme colors and branding

4. Once created, you'll be redirected to your store's admin dashboard

### Managing Your Store

#### Admin Dashboard
- Access via: `http://localhost:5000/<store-slug>/admin/dashboard`
- View store statistics and quick actions
- Navigate to different management sections

#### Items Management
- **Add Items**: Create new items/products/menu items with custom attributes
- **Edit Items**: Update existing items, prices, descriptions, and images
- **Delete Items**: Remove items from your inventory
- **Item Attributes**: Each business type has specific attributes (e.g., vehicles have Make, Model, Year; menu items have Category, Ingredients)

#### Specials & Announcements
- Create promotional offers and announcements
- Display featured content on your store frontend
- Manage active specials

#### Inquiries Management
- View and manage customer inquiries/orders/requests
- Delete processed inquiries
- Track customer contact information

#### Store Settings
- Update store information (name, description, contact details)
- Customize theme colors (primary, secondary, background, text)
- Upload logo and hero images
- Modify business hours and location details

### Store Frontend

Each store has a public-facing website accessible at:
```
http://localhost:5000/<store-slug>
```

The frontend includes:
- Hero section with customizable imagery
- Item/product/menu listing
- Item detail pages with inquiry forms
- Contact information section
- Specials and announcements display

### Export Standalone Application

You can export your store as a standalone Flask application:
1. Navigate to: `http://localhost:5000/<store-slug>/download/main.py`
2. Download the generated `main.py` file
3. Run it independently with its own MongoDB database

## Project Structure

```
mdb-stores/
├── app.py              # Main Flask application
├── README.md           # This file
├── LICENSE             # AGPL-3.0 License
├── .env               # Environment variables (create this)
└── static/
    └── img/
        └── logo.png   # Static assets
```

## Dependencies

- **Flask**: Web framework
- **pymongo**: MongoDB driver for Python
- **python-dotenv**: Environment variable management
- **bson**: MongoDB ObjectId handling

## Database Schema

The application uses MongoDB with the following collections:

- **stores**: Store information and settings
- **users**: Admin user accounts (per store)
- **items**: Products/menu items/services/inventory
- **specials**: Special offers and announcements
- **inquiries**: Customer inquiries and contact forms

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | `a-super-secret-key-change-in-production` |
| `MONGO_URI` | MongoDB connection string | `mongodb://localhost:27017/...` |

### Business Type Configuration

Each business type has its own configuration including:
- Item labels (e.g., "Menu Item", "Vehicle", "Service")
- Item code prefixes (e.g., "MENU", "VIN", "SRV")
- Custom attributes template
- Status options
- Default descriptions

## Security Considerations

- ⚠️ **Change the default SECRET_KEY** in production
- ⚠️ **Use strong MongoDB credentials** and restrict network access
- ⚠️ **Enable HTTPS** in production
- ⚠️ **Set up proper firewall rules** for your MongoDB instance
- ⚠️ **Regular backups** of your MongoDB database

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPL-3.0). See the [LICENSE](LICENSE) file for details.

## Support

For issues, questions, or contributions, please open an issue on the GitHub repository.

## Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- Styled with [Tailwind CSS](https://tailwindcss.com/)
- Icons by [Font Awesome](https://fontawesome.com/)
- Database: [MongoDB](https://www.mongodb.com/)

---

**Note**: This application is designed for rapid prototyping and small-to-medium scale deployments. For production use, consider implementing additional security measures, caching, rate limiting, and monitoring.
