import os
import json
import re
import tempfile
import io
from datetime import datetime

from fastapi import FastAPI, UploadFile, File
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, text
from sqlalchemy.orm import declarative_base, sessionmaker
from pydantic import BaseModel
from PIL import Image
import fitz  # PyMuPDF
import pytesseract
from groq import Groq
from dotenv import load_dotenv
from dateutil import parser

# ----------------------------
# Basic Setup
# ----------------------------

load_dotenv()

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# This tells Python to go look INSIDE your .env file for the real address
DATABASE_URL = os.getenv("DATABASE_URL")

# Safety check: if .env is missing, it will use the local sqlite
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./database.db"

#DATABASE_URL = "sqlite:///./database.db"
# Create a test script or update your .env file
#DATABASE_URL = "mysql+pymysql://admin:YOUR_PASSWORD@YOUR_ENDPOINT:3306/invoicedata"
#engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ----------------------------
# Database Model
# ----------------------------

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    vendor = Column(String(255), nullable=False)
    invoice_number = Column(String(255), nullable=False, unique=True)
    invoice_date = Column(Date)
    total_amount = Column(Float)
    gst = Column(Float)

Base.metadata.create_all(bind=engine)

class Question(BaseModel):
    question: str

def seed_demo_invoice():
    db = SessionLocal()
    try:
        existing = db.query(Invoice).first()
        if not existing:

            invoices = [
                Invoice(
                    vendor="Zylker Technologies",
                    invoice_number="INV-1001",
                    invoice_date=datetime.strptime("2025-01-10", "%Y-%m-%d").date(),
                    total_amount=12000,
                    gst=2160
                ),
                Invoice(
                    vendor="Acme Corp",
                    invoice_number="INV-1002",
                    invoice_date=datetime.strptime("2025-02-05", "%Y-%m-%d").date(),
                    total_amount=18500,
                    gst=3330
                ),
                Invoice(
                    vendor="Demo Vendor Pvt Ltd",
                    invoice_number="INV-1003",
                    invoice_date=datetime.strptime("2025-03-01", "%Y-%m-%d").date(),
                    total_amount=9500,
                    gst=1710
                )
            ]

            db.add_all(invoices)
            db.commit()

    finally:
        db.close()

seed_demo_invoice()

# ----------------------------
# OCR & Extraction Logic
# ----------------------------

def extract_text_from_pdf(file_bytes):
    text_content = ""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        pdf_path = tmp.name

    doc = fitz.open(pdf_path)
    for page in doc:
        text_content += page.get_text()

    if not text_content.strip():
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            text_content += pytesseract.image_to_string(img)

    doc.close()
    return text_content

def extract_invoice_with_llm(text_input):
    system_prompt = "You are a JSON API. Return ONLY valid JSON. No talk, no markdown."
    user_prompt = f"""
    Extract invoice data:
    {{
      "vendor": "string",
      "invoice_number": "string",
      "invoice_date": "YYYY-MM-DD",
      "total_amount": number,
      "gst": number
    }}
    Text: {text_input}
    """
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
    )
    content = response.choices[0].message.content.strip()
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match: raise Exception("No JSON found")
    return json.loads(match.group(0))

# ----------------------------
# Endpoints
# ----------------------------

@app.post("/upload/")
def upload_invoice(file: UploadFile = File(...)):
    db = SessionLocal()
    try:
        file_bytes = file.file.read()
        text_data = extract_text_from_pdf(file_bytes)
        data = extract_invoice_with_llm(text_data)

        try:
            invoice_date = parser.parse(data.get("invoice_date", "")).date()
        except:
            invoice_date = None

        invoice_number = data.get("invoice_number")
        if not invoice_number:
            return {"message": "Invoice number not found"}

        existing = db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
        if existing:
            return {"message": "Invoice already exists"}

        invoice = Invoice(
            vendor=data.get("vendor"),
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            total_amount=float(data.get("total_amount", 0)),
            gst=float(data.get("gst", 0)),
        )
        db.add(invoice)
        db.commit()
        return {"message": "Invoice saved successfully"}
    except Exception as e:
        return {"message": f"Error: {str(e)}"}
    finally:
        db.close()

@app.get("/invoices/")
def get_invoices():
    db = SessionLocal()
    # Fetch invoices sorted by date
    invoices = db.query(Invoice).order_by(Invoice.invoice_date.desc()).all()
    
    # Explicitly defining the order and names of columns
    result = []
    for idx, inv in enumerate(invoices, start=1):
        result.append({
            "S.No": idx,
            "Invoice ID": inv.invoice_number,
            "Vendor Name": inv.vendor,
            "Date": inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else "N/A",
            "Total Amount": inv.total_amount,
            "GST": inv.gst
        })
    
    db.close()
    return result

@app.post("/ask/")
def ask_question(data: Question):
    db = SessionLocal()
    
  # 1. SQL Generation with Safety Guardrails
    sql_prompt = f"""
    You are a SQLite SQL expert. Generate a SQL query to answer the user's question.
    Table: 'invoices'
    Columns: id, vendor, invoice_number, invoice_date, total_amount, gst

    Rules:
    - Return ONLY SQL. No explanation.
    - Only SELECT queries allowed.
    - For highest values use: ORDER BY total_amount DESC LIMIT 1
    - For totals use: SUM(total_amount)
    - For year filtering use: strftime('%Y', invoice_date)
    - For month filtering use: strftime('%m', invoice_date)
    
    Question: {data.question}
    """
    try:
        # Generate SQL
        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": sql_prompt}],
            temperature=0
        )
        raw_sql = res.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
        
        # Security check: Block destructive commands
        if any(cmd in raw_sql.upper() for cmd in ["DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE"]):
            return {"answer": "I am only authorized to read data, not modify it."}

        # 2. Execute SQL
        result = db.execute(text(raw_sql))
        rows = result.mappings().all()
        
        # 3. Format Answer with LLM
        format_prompt = f"""
        User Question: {data.question}
        Database Result: {list(rows)}
        
        Provide a concise, professional answer based ONLY on the data above. 
        If no data matches, say no records were found.
        """
        
        answer_res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": format_prompt}],
            temperature=0
        )
        
        return {"answer": answer_res.choices[0].message.content}

    except Exception as e:
        return {"answer": f"Processing error: {str(e)}"}
    finally:
        db.close()
