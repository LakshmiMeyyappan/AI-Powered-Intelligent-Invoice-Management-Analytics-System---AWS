FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

RUN echo '#!/bin/bash\n\
echo "Starting FastAPI..."\n\
uvicorn main:app --host 0.0.0.0 --port 8000 &\n\
sleep 5\n\
echo "Starting Streamlit..."\n\
streamlit run dashboard.py --server.port 10000 --server.address 0.0.0.0 --server.headless true\n\
' > start.sh && chmod +x start.sh

CMD ["./start.sh"]
