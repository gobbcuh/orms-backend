# ORMS Backend API

A Flask-based backend API for an Outpatient Record Management System (ORMS) with MySQL database integration.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Database Setup](#database-setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [API Endpoints](#api-endpoints)
- [Testing](#testing)
- [Project Structure](#project-structure)

## Prerequisites

Before setting up this project, ensure you have the following installed:

- **Python 3.8+** - [Download Python](https://www.python.org/downloads/)
- **MySQL Server** - [Download MySQL](https://dev.mysql.com/downloads/mysql/)
- **pip** - Python package manager (comes with Python)
- **Git** (optional) - For version control

## Installation

### 1. Clone the Repository (if using Git)

```bash
git clone <repository-url>
cd orms-backend
```

### 2. Create a Virtual Environment

**On Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Database Setup

### 1. Start MySQL Server

Ensure your MySQL server is running on your local machine.

### 2. Create the Database

Run the schema file to create the database and tables:

```bash
mysql -u root -p < database/schema.sql
```

Or manually in MySQL:
```bash
mysql -u root -p
```

Then execute:
```sql
source database/schema.sql;
```

### 3. (Optional) Import Sample Data

If you have CSV files to import:

```bash
python database/import_csv.py
```

## Configuration

### 1. Create Environment File

Create a `.env` file in the root directory of the project:

```bash
# On Windows
type nul > .env

# On macOS/Linux
touch .env
```

### 2. Configure Environment Variables

Add the following variables to your `.env` file:

```env
# Flask Configuration
SECRET_KEY=your-secret-key-here
FLASK_DEBUG=True
FLASK_ENV=development

# Database Configuration
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your-mysql-password
DB_NAME=orms_db
DB_CHARSET=utf8mb4

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key-here
JWT_EXPIRATION_HOURS=24

# CORS Configuration
CORS_ORIGINS=http://localhost:8080

# Server Configuration
PORT=5000
```

**Important:** 
- Replace `your-mysql-password` with your actual MySQL root password
- Generate secure random strings for `SECRET_KEY` and `JWT_SECRET_KEY` in production
- Adjust `CORS_ORIGINS` to match your frontend URL

### Example for generating secure keys (Python):

```python
import secrets
print(secrets.token_hex(32))
```

## Running the Application

### 1. Activate Virtual Environment (if not already active)

**On Windows:**
```bash
venv\Scripts\activate
```

**On macOS/Linux:**
```bash
source venv/bin/activate
```

### 2. Start the Flask Server

```bash
python app.py
```

The server will start on `http://localhost:5000` (or the port specified in your `.env` file).

You should see output similar to:
```
======================================================================
ORMS Backend API Server
======================================================================
- Running on: http://localhost:5000
- CORS enabled for: http://localhost:8080
- Environment: development
======================================================================
```

### 3. Verify the Server is Running

Open your browser or use curl to test the health endpoint:

```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "running",
  "database": "connected",
  "message": "ORMS Backend API is running"
}
```

## API Endpoints

The API provides the following main endpoints:

- **Health Check:** `GET /api/health` - Check server and database status
- **Authentication:** `/api/auth/*` - User authentication endpoints
- **Patients:** `/api/patients/*` - Patient management endpoints
- **Billing:** `/api/billing/*` - Billing and payment endpoints
- **Reference:** `/api/reference/*` - Reference data endpoints

For detailed API documentation, refer to the individual route files in the `routes/` directory.

## Testing

Run the test suite:

```bash
# Test authentication functionality
python test_auth.py

# Test formatters
python test_formatters.py
```

## Project Structure

```
orms-backend/
│
├── app.py                  # Application entry point
├── config.py               # Configuration and database manager
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
│
├── database/
│   ├── schema.sql         # Database schema
│   └── import_csv.py      # CSV import utility
│
├── routes/                # API route blueprints
│   ├── __init__.py
│   ├── auth.py           # Authentication routes
│   ├── billing.py        # Billing routes
│   ├── patients.py       # Patient management routes
│   └── reference.py      # Reference data routes
│
├── utils/                 # Utility modules
│   ├── __init__.py
│   ├── auth.py           # Authentication utilities
│   └── formatters.py     # Data formatting utilities
│
├── models/                # Data models
│
└── test_*.py             # Test files
```

## Troubleshooting

### Database Connection Issues

If you encounter database connection errors:

1. Verify MySQL is running:
   ```bash
   # On Windows
   net start MySQL80
   
   # Check status
   mysqladmin -u root -p status
   ```

2. Check your database credentials in `.env` file
3. Ensure the database `orms_db` exists:
   ```bash
   mysql -u root -p -e "SHOW DATABASES;"
   ```

### Port Already in Use

If port 5000 is already in use, change the `PORT` value in your `.env` file:

```env
PORT=5001
```

### Import Errors

If you get import errors, ensure:
1. Virtual environment is activated
2. All dependencies are installed: `pip install -r requirements.txt`
3. You're in the correct directory

### CORS Errors

If you encounter CORS errors from your frontend:
1. Ensure `CORS_ORIGINS` in `.env` matches your frontend URL
2. Multiple origins can be comma-separated: `http://localhost:8080,http://localhost:3000`

## Development

### Adding New Dependencies

When adding new Python packages:

```bash
pip install package-name
pip freeze > requirements.txt
```

### Database Migrations

To modify the database schema:
1. Edit `database/schema.sql`
2. Drop and recreate the database (development only):
   ```bash
   mysql -u root -p < database/schema.sql
   ```

**Note:** In production, use proper migration tools like Alembic.

## Contributing

1. Create a new branch for your feature
2. Make your changes
3. Test thoroughly
4. Submit a pull request

## Support

For issues and questions, please [create an issue](link-to-issues) in the repository.
