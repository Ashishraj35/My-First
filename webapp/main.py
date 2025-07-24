"""
FastAPI-based web application for managing bill receipts.

This application provides simple user authentication (sign up and log in),
allowing users to upload images of their receipts along with basic metadata
(amount, date, time and shop name). All information is persisted in a
SQLite database. Users can view aggregated monthly spending through a
dashboard and generate a PDF report of their receipts for a given month.

The PDF generation does not rely on external libraries like ReportLab.
Instead, it uses Pillow (PIL) to assemble each bill onto its own A4-sized
page and then writes the collection of images out as a single PDF file.

This file is intentionally self contained: running `python main.py` will
start the server. A default SQLite database and data directories will be
created automatically on first run.

Usage:

    uvicorn main:app --reload

After the server is running, open `http://localhost:8000` in a browser.
You'll be presented with a simple interface for signing up and logging in.
"""

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont

# Initialise FastAPI app
app = FastAPI(title="Bill Receipt Manager")


def get_db() -> sqlite3.Connection:
    """Return a connection to the SQLite database with row factory set."""
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the necessary tables and directories if they don't already exist."""
    os.makedirs("user_data/images", exist_ok=True)
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    # Create users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            token TEXT NOT NULL
        )
        """
    )
    # Create bills table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            amount REAL NOT NULL,
            bill_date TEXT NOT NULL,
            bill_time TEXT NOT NULL,
            shop TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )
    conn.commit()
    conn.close()


# Initialise database on import
init_db()


def get_current_user_id(token: str) -> int:
    """Return the user ID associated with a given token or raise if invalid."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE token = ?", (token,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    return row[0]


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the main application HTML page."""
    index_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# Mount static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


class AuthRequest(BaseModel):
    """Schema for sign up and login requests."""
    username: str
    password: str


@app.post("/api/signup")
async def signup(auth: AuthRequest) -> Dict[str, str]:
    """
    Register a new user. Creates a hashed password and assigns a token.
    Returns the token so the client can authenticate future requests.
    """
    conn = get_db()
    cur = conn.cursor()
    # Check for existing user
    cur.execute("SELECT id FROM users WHERE username = ?", (auth.username,))
    if cur.fetchone() is not None:
        conn.close()
        raise HTTPException(status_code=400, detail="Username is already taken")
    password_hash = hashlib.sha256(auth.password.encode("utf-8")).hexdigest()
    token = secrets.token_hex(16)
    cur.execute(
        "INSERT INTO users (username, password_hash, token) VALUES (?, ?, ?)",
        (auth.username, password_hash, token),
    )
    conn.commit()
    conn.close()
    return {"token": token}


@app.post("/api/login")
async def login(auth: AuthRequest) -> Dict[str, str]:
    """
    Authenticate a user and return their token. If credentials are invalid an error is raised.
    """
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT password_hash, token FROM users WHERE username = ?", (auth.username,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    stored_hash, token = row
    if hashlib.sha256(auth.password.encode("utf-8")).hexdigest() != stored_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": token}


class UploadRequest(BaseModel):
    token: str
    filename: str
    image: str  # base64-encoded image string (data without prefix)
    amount: float
    bill_date: str
    bill_time: str
    shop: str


@app.post("/api/upload_bill")
async def upload_bill(req: UploadRequest) -> Dict[str, str]:
    """
    Upload a bill image with associated metadata. The image is supplied as
    a base64 encoded string within a JSON payload to avoid the need for
    multipart form parsing. The image is stored on disk and metadata
    persisted in the database.
    """
    user_id = get_current_user_id(req.token)
    # Ensure directory exists
    os.makedirs("user_data/images", exist_ok=True)
    # Unique filename to avoid collisions while preserving original name
    unique_name = f"{datetime.utcnow().timestamp():.0f}_{req.filename}"
    save_path = os.path.join("user_data/images", unique_name)
    # Decode base64 image
    import base64
    try:
        image_data = base64.b64decode(req.image)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image data")
    with open(save_path, "wb") as out_file:
        out_file.write(image_data)
    # Persist metadata
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO bills (user_id, filename, amount, bill_date, bill_time, shop, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            unique_name,
            req.amount,
            req.bill_date,
            req.bill_time,
            req.shop,
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    return {"status": "success"}


@app.get("/api/stats")
async def stats(token: str) -> Dict[str, Dict[str, float]]:
    """
    Return aggregated monthly spending for the authenticated user. The return
    format is a mapping from ``YYYY-MM`` strings to total amount values.
    """
    user_id = get_current_user_id(token)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT bill_date, amount FROM bills WHERE user_id = ? ORDER BY bill_date",
        (user_id,),
    )
    monthly_totals: Dict[str, float] = {}
    for bill_date, amount in cur.fetchall():
        month = bill_date[:7]  # Extract YYYY-MM
        monthly_totals[month] = monthly_totals.get(month, 0.0) + float(amount)
    conn.close()
    return {"stats": monthly_totals}


@app.get("/api/monthly_report/{year_month}")
async def monthly_report(year_month: str, token: str) -> FileResponse:
    """
    Generate a PDF containing each bill for the given month for the authenticated user.

    Each page of the PDF contains the image of the bill along with its
    associated metadata (shop, amount, date and time). If no bills exist for
    the requested month, a one-page PDF with a message will be returned.
    """
    user_id = get_current_user_id(token)
    # Fetch bills for the month
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT filename, amount, bill_date, bill_time, shop
        FROM bills
        WHERE user_id = ? AND bill_date LIKE ?
        ORDER BY bill_date
        """,
        (user_id, f"{year_month}%"),
    )
    bills = cur.fetchall()
    conn.close()
    # Create pages
    pages = []
    for bill in bills:
        # A4 page in points at 72 DPI (approx 595x842)
        page = Image.new("RGB", (595, 842), "white")
        draw = ImageDraw.Draw(page)
        # Draw metadata text
        text = (
            f"Shop: {bill['shop']}\n"
            f"Amount: {bill['amount']}\n"
            f"Date: {bill['bill_date']} {bill['bill_time']}"
        )
        # Basic font – fallback to default PIL font
        font = None
        # Draw text at top left
        draw.multiline_text((20, 20), text, fill="black", font=font, spacing=4)
        # Load and resize image
        image_path = os.path.join("user_data/images", bill["filename"])
        try:
            bill_img = Image.open(image_path).convert("RGB")
        except Exception:
            bill_img = Image.new("RGB", (200, 200), "gray")
        # Resize preserving aspect ratio
        max_width, max_height = 555, 600
        bill_img.thumbnail((max_width, max_height))
        # Paste below the text
        page.paste(bill_img, (20, 150))
        pages.append(page)
    if not pages:
        # Add a blank page with message
        page = Image.new("RGB", (595, 842), "white")
        draw = ImageDraw.Draw(page)
        draw.text((20, 400), "No bills found for this month.", fill="black")
        pages.append(page)
    # Save PDF to disk in user_data directory
    report_path = os.path.join("user_data", f"report_{user_id}_{year_month}.pdf")
    pages[0].save(report_path, save_all=True, append_images=pages[1:])
    filename = f"report_{year_month}.pdf"
    return FileResponse(path=report_path, filename=filename, media_type="application/pdf")
