# BSU Research Dashboard - Docker image
# Build from project root: docker build -t bsu-research .
# Run: docker run -p 5000:5000 -e SCOPUS_API_KEY=your_key bsu-research

FROM python:3.11-slim

WORKDIR /app

# Copy backend (HTML, CSS, JS, img are in backend/ or backend/img/)
COPY backend/requirements.txt backend/
COPY backend/ ./backend/
COPY img/ ./img/

WORKDIR /app/backend

RUN pip install --no-cache-dir -r requirements.txt

# Default port
ENV PORT=5000

EXPOSE 5000

# Run with Gunicorn; static files are served from parent dir
CMD gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 app:app
