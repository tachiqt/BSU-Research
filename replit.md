# BSU Research Dashboard

## Overview
A research dashboard for Batangas State University that displays publications and faculty research data fetched from the Scopus API.

## Project Architecture
- **Frontend**: Static HTML/CSS/JS files served by Flask (index.html, publications.html, faculty.html)
- **Backend**: Python Flask API (backend/app.py) serving both API endpoints and static files
- **Database**: SQLite (faculty.db) for faculty data storage

## Tech Stack
- Python 3.11
- Flask with Flask-CORS
- Gunicorn (production server)
- Pandas/OpenPyXL for data processing
- Scopus API integration

## Key Files
- `backend/app.py` - Main Flask application with API routes and static file serving
- `backend/scopus.py` - Scopus API integration
- `backend/database.py` - SQLite database operations
- `backend/faculty_reader.py` - Faculty data processing
- `index.html`, `publications.html`, `faculty.html` - Frontend pages
- `script.js`, `faculty.js` - Frontend JavaScript
- `style.css` - Styling

## Running the Project
The application runs on port 5000 with Flask serving both the API and static files.

## Environment Variables
- `SCOPUS_API_KEY` - Required for Scopus API access (get from https://dev.elsevier.com/)
- `FLASK_ENV` - Set to 'production' for production mode

## Recent Changes
- 2026-01-29: Initial Replit setup and deployment configuration
