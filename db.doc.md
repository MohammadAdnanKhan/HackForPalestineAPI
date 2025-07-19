# 📘 `db.doc.md` — Using SQLite with Flask and SQLAlchemy

This document provides a guide to integrating and using an SQLite database in a Flask application via SQLAlchemy ORM.

---

## 🔧 Setup & Configuration

1. **Import required modules**:

   ```python
   from flask_sqlalchemy import SQLAlchemy
   from flask import Flask
   from flask_cors import CORS
   import os
   ```

2. **Initialize Flask app and configure SQLite URI**:

   ```python
   app = Flask(__name__)
   CORS(app)  # Allow Cross-Origin Requests

   # Use environment variable or fallback to SQLite database
   app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DB_URI') or 'sqlite:///hack4pal.db'
   app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

   db = SQLAlchemy(app)
   ```

---

## 🧱 Defining Models (Tables)

Models define the structure of your database tables using Python classes.

Example model:

```python
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    
    field1 = db.Column(db.Text, nullable=True)
    field2 = db.Column(db.Text, nullable=True)
    field3 = db.Column(db.Text, nullable=True)
    field4 = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<UserSubmission {self.name}, {self.category}>"
```

---

## 🗂️ Creating the Database

Ensure the database and its tables are initialized before using them.

```python
with app.app_context():
    db.create_all()  # Creates tables based on the models
```

*Optional*: To reset the DB during development, you can drop all tables first:

```python
db.drop_all()
db.create_all()
```

---

## ➕ Adding Data

To add a new entry to the database:

```python
new_feedback = Feedback(
    name="Jane Doe",
    email="jane@example.com",
    category="Usability",
    field1="Easy to navigate",
    field2="Nice layout",
)

db.session.add(new_feedback)
db.session.commit()
```

---

## 📤 Querying Data

Example: Get all feedback entries

```python
all_feedback = Feedback.query.all()
```

Example: Filter by category

```python
usability_feedback = Feedback.query.filter_by(category='Usability').all()
```

---

## ✏️ Updating Records

```python
entry = Feedback.query.get(1)
entry.field1 = "Updated response"
db.session.commit()
```

---

## ❌ Deleting Records

```python
entry = Feedback.query.get(1)
db.session.delete(entry)
db.session.commit()
```

---

## 💾 Database File

* The SQLite database file is created at the project root (or wherever `sqlite:///hack4pal.db` points).
* You can inspect it using tools like:

  * **DB Browser for SQLite**
  * **sqlite3 CLI**

---

## 📌 Tips

* Always use `with app.app_context():` when running DB operations outside request context (e.g., CLI scripts).
* For production, consider switching to PostgreSQL or MySQL for scalability.

---
Note: this info is AI generated, please verify before using it.