# 📋 **Survey Builder & Response Collector (Flask + PostgreSQL)**

A lightweight, production-ready **survey creation and response collection system** built with **Flask**, **PostgreSQL**, **SQLAlchemy (ORM)**, and **SendGrid** — fully deployed on **Render**.  
Users can upload survey definition files (CSV/Excel), generate public survey links, collect responses, export them to Excel, and manage surveys via an authenticated dashboard.

---

## 🚀 **Key Features**

- **User Authentication**
  - Secure login, registration, and session management using Flask-Login.

- **Dynamic Survey Generation**
  - Upload CSV/Excel survey templates.
  - Automatically renders form fields (`text`, `date`, `checkbox`, `select`).

- **PostgreSQL Database**
  - Stores survey metadata and responses using SQLAlchemy ORM.
  - Fully compatible with Render’s managed PostgreSQL service.

- **SendGrid Email Integration**
  - Share survey links through SendGrid’s API.

- **Excel Export**
  - Export all collected responses into a clean `.xlsx` file.
  - Preserves template structure and appends new entries neatly.

- **Survey Ownership & Management**
  - Each user sees and manages only their surveys.
  - Delete surveys, uploaded files, and associated responses securely.

---

## 📦 **Tech Stack**

- **Backend:** Flask  
- **ORM:** SQLAlchemy (Object–Relational Mapper)  
- **Database:** PostgreSQL  
- **Email Service:** SendGrid API  
- **Authentication:** Flask-Login  
- **File Processing:** Pandas, OpenPyXL  
- **Hosting:** Render.com  

---
## 🌐 **Deployment**

This project is **already deployed on Render**, using:

- **Render Web Service** (Flask app)
- **Render PostgreSQL Instance**
- **Environment-based configuration for DB + SendGrid**


## ⚙️ **Local Development Setup**

### **1. Install Dependencies**
   
      ```bash
    pip install -r requirements.txt

## 2.  **Add Required Environment Variables**

DATABASE_URL=your_postgres_url

MAIL_EMAIL=your_smtp_email

MAIL_PASSWORD=your_smtp_password

SENDGRID_API_KEY=your_sendgrid_key

SENDER_EMAIL=verified_sender_email





### 🚀 Running the Application

Start the server using the main application file:

```bash
python app.py







