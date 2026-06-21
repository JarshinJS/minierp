# Architecture Overview

This document provides a high-level overview of the Mini ERP System's architecture, including its tech stack, components, and directory structure.

## Tech Stack

The application is built using a modern, lightweight, and reactive tech stack:

- **Backend Framework:** Django (Python)
  - Provides the robust ORM, routing, authentication, and admin interface.
- **Frontend Interaction:** HTMX + Alpine.js
  - **HTMX:** Used for sending AJAX requests directly from HTML attributes, updating portions of the DOM without full page reloads.
  - **Alpine.js:** Used for lightweight client-side interactions (modals, dropdowns, simple state toggles) without the overhead of a large JS framework.
- **Styling:** Tailwind CSS
  - Utility-first CSS framework for rapid and responsive UI development.
- **Database:** SQLite (Development)
  - Default database for ease of setup. Can be easily swapped out to PostgreSQL in production.
- **AI Integration:** Ollama
  - Used locally to run the `llama3.1` model (or similar) to power the **Voice Assistant**.
- **Background Jobs (Optional but recommended):** Celery + Redis
  - For asynchronous tasks (e.g., generating reports, sending notifications).

## System Components

1. **Web Server / WSGI:** Django's built-in server (development) or Gunicorn/Uvicorn (production).
2. **Database:** Stores all relational data across the 14 ERP modules (Products, Orders, Inventory, etc.).
3. **AI Service:** The Ollama service runs locally on port `11434` and provides an API for natural language understanding. The `core/api_views.py` communicates with this service.

## Key Design Patterns

- **Fat Models, Skinny Views:** Business logic is primarily kept in models or dedicated `services.py` / `selectors.py` files to keep Django views clean.
- **Modular Apps:** The system is divided into highly cohesive apps (e.g., `sales`, `inventory`, `manufacturing`) inside the `apps/` directory to maintain separation of concerns.
- **Event-Driven UI:** Using HTMX, the UI updates reactively based on user actions without needing complex REST APIs for every interaction.
