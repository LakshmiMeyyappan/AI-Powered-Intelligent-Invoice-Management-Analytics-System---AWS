FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Create startup script
RUN printf '#!/bin/bash\n\
echo "Starting FastAPI server..."\n\
uvicorn main:app --host 0.0.0.0 --port 8000 &\n\
echo "Waiting for API to start..."\n\
sleep 5\n\
echo "Starting Streamlit..."\n\
streamlit run dashboard.py --server.port 8501 --server.address 0.0.0.0\n\
' > start.sh && chmod +x start.sh

# Start container
CMD ["./start.sh"]
