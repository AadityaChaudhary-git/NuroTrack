# NuroTrack

AI-powered productivity monitoring system using Machine Learning.

NuroTrack tracks user activity in real time, analyzes productivity behavior, and predicts a smart productivity score called **NuroScore** using a Machine Learning model.

---

# Features

- Real-time window/activity tracking
- Productivity classification
- ML-based NuroScore prediction
- Daily and hourly productivity reports
- Interactive dashboard
- Firebase Authentication
- Task management system
- Live charts and analytics

---

# Tech Stack

## Backend
- Python
- Flask
- SQLite
- Firebase Admin SDK

## Frontend
- HTML
- CSS
- JavaScript
- Chart.js

## Machine Learning
- Scikit-learn
- Gradient Boosting Regressor
- NumPy
- Pandas

---

# Project Structure

```text
NuroTrack/
│
├── backend/
│   ├── main.py
│   ├── api.py
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── firebase.py
│   ├── ml.py
│   ├── stats.py
│   └── tracker.py
│
├── frontend/
│   ├── index.html
│   └── styles.css
│
├── firebase/
│   └── serviceAccountKey.json
│
├── requirements.txt
├── README.md
└── .gitignore
