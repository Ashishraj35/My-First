# Bill Receipt Manager

This repository contains a simple web application that allows users to
capture and organise their expense receipts. The app is built with
[FastAPI](https://fastapi.tiangolo.com/) for the backend and plain HTML,
CSS and JavaScript on the frontend. There are no heavy dependencies
besides `fastapi`, `uvicorn` (for running the server) and `Pillow` for
image manipulation. A lightweight SQLite database is used to persist
users and bills.

## Features

* **User authentication** – sign up and log in with a username and
  password. Credentials are hashed before storage.
* **Receipt uploads** – authenticated users can upload images of
  receipts and enter relevant details such as amount, date, time and
  shop name. The images are stored on disk and metadata in the
  database.
* **Dashboard** – a simple dashboard shows monthly expenditure as a
  bar chart. Data updates automatically when new bills are uploaded.
* **PDF reporting** – generate a PDF containing each receipt image
  accompanied by its details for a selected month. The report can be
  downloaded and shared.

## Running the App

1. Ensure you have Python 3.8+ installed. No extra libraries are
   required beyond the ones bundled with this repository. If you want
   development reloading you may wish to install `uvicorn`:

   ```bash
   pip install uvicorn
   ```

2. Navigate to the `webapp` directory and start the server:

   ```bash
   cd webapp
   uvicorn main:app --reload
   ```

3. Open your browser to `http://localhost:8000` and you should see
   the welcome page. Sign up for an account or log in if you already
   have one.

## Notes & Limitations

* This application is a proof‑of‑concept and prioritises clarity over
  production hardening. Passwords are hashed but there is no
  password reset functionality or email verification.
* Receipt details (amount, date, time and shop) must currently be
  entered manually. Automatic OCR is outside the scope of this
  implementation but could be integrated with a library such as
  [Tesseract](https://github.com/tesseract-ocr/tesseract) or a
  third‑party API.
* PDF generation uses the Python Imaging Library. If you upload
  receipts with very high resolutions, they will be scaled down to fit
  within the PDF page dimensions.

Enjoy organising your expenses!
