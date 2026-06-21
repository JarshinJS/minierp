# Shiv Furniture Works ERP

A comprehensive Enterprise Resource Planning (ERP) system tailored for Shiv Furniture Works. Built with modern web technologies to handle all aspects of furniture manufacturing, inventory, sales, procurement, and more.

## Tech Stack

- **Backend:** Python, Django
- **Frontend:** HTMX, Alpine.js, Tailwind CSS (Vanilla CSS, compiled)
- **Database:** SQLite (default)
- **AI Integration:** Ollama (for ERP Voice Assistant)

## Features

- **Dashboard Control Center:** Real-time enterprise overview, status alerts, and KPI charts.
- **User Management:** Role-based access control with predefined roles like Admin, Sales, Purchase, Inventory Manager, Accountant, etc.
- **Product Catalog:** Manage furniture items, SKUs, HS codes, and pricing.
- **Inventory Tracking:** Real-time stock levels, warehouse management, and stock movement history.
- **Sales & Purchasing:** Complete lifecycle for sales orders and purchase orders.
- **Manufacturing:** Manage manufacturing orders (MO), BOMs, and production tracking.
- **Procurement & Delivery:** Streamlined procurement workflows and delivery notes generation.
- **Foreign Trade:** Export/Import order management including standard Incoterms 2020.
- **Blockchain Integration:** Tracking mechanisms for logistics and supply chain transparency.
- **Audit Logs:** System-wide activity tracking for accountability.
- **ERP Voice Assistant:** An AI-powered voice assistant (using Ollama) to navigate, query, and command the ERP hands-free.

## Prerequisites

- Python 3.11+
- Node.js (for Tailwind CSS)
- [Ollama](https://ollama.com/) (Required for the Voice Assistant feature)

## Setup Instructions

### 1. Python Environment

```bash
python -m venv .venv
source .venv/Scripts/activate  # On Windows use: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Frontend Assets

```bash
npm install
npm run build:css
```

### 3. Database Migration & Setup

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Running the Development Server

You can run both the Django server and the Tailwind CSS watcher concurrently:

```bash
npm run dev
```
*(Alternatively, run `python manage.py runserver` and `npm run watch:css` in separate terminals).*

### 5. Running Ollama for Voice Assistant
To use the ERP Voice Assistant, ensure you have Ollama installed and running locally with the required models.
```bash
ollama serve
ollama run llama3  # or whichever model you have configured
```

## Note
This project relies on `requests` for the Ollama integration. Ensure your `.venv` is properly configured.
