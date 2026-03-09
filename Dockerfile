# Use the official Python 3.14 slim image
FROM python:3.14-slim

# Install Tesseract and modern OpenGL dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files (ignoring venv via .dockerignore)
COPY . .

# Expose ports
EXPOSE 8000
EXPOSE 8501

# Start script
RUN echo '#!/bin/bash\n\
uvicorn main:app --host 0.0.0.0 --port 8000 &\n\
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0\n\
' > start.sh && chmod +x start.sh

CMD ["./start.sh"]