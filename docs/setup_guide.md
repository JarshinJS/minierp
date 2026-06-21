# Setup & Installation Guide

This guide will walk you through the process of setting up the Mini ERP System for development.

## Prerequisites

Ensure you have the following installed on your system:
- **Python 3.11+**
- **Node.js** (for building Tailwind CSS)
- **Git**
- **Ollama** (Required for the Voice Assistant feature)

## 1. Clone the Repository

```bash
git clone https://github.com/JarshinJS/minierp.git
cd minierp
```

## 2. Python Environment Setup

It's highly recommended to use a virtual environment.

```bash
# Create the virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 3. Frontend Assets Setup

The project uses Tailwind CSS. You need to install the Node modules and compile the CSS.

```bash
# Install Node dependencies
npm install

# Build the CSS for the first time
npm run build:css
```

## 4. Database Setup

Apply the Django migrations to set up the SQLite database schema and create a superuser for admin access.

```bash
python manage.py migrate
python manage.py createsuperuser
```
Follow the prompts to set an email and password for the superuser.

## 5. Running the Application

For active development, you will typically want to run the Django server and the Tailwind CSS watcher simultaneously.

**Option A: Using the NPM script (Runs concurrently)**
```bash
npm run dev
```

**Option B: Separate terminals**
Terminal 1:
```bash
python manage.py runserver
```
Terminal 2:
```bash
npm run watch:css
```

The application will be accessible at `http://127.0.0.1:8000/`.

## 6. Setting up Ollama (Voice Assistant)

To utilize the ERP Voice Assistant, you must have Ollama running locally.

1. Download and install [Ollama](https://ollama.com/).
2. Start the Ollama server:
   ```bash
   ollama serve
   ```
3. Pull and run the desired model (the default model used in `core/api_views.py` is `llama3.1`, but you can update the code to use another model like `llama3`):
   ```bash
   ollama run llama3.1
   ```

*Note: The Django application communicates with Ollama via `requests` at `http://localhost:11434`.*
