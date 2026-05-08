# NuroTrack Setup

## 1. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux

## 2. Install dependencies
pip install -r requirements.txt

## 3. Firebase setup (optional)
- Go to Firebase Console → Project Settings → Service Accounts
- Click "Generate new private key" → save as firebase/serviceAccountKey.json

## 4. Open frontend
- Open frontend/index.html in your browser

## 5. Run backend
cd backend
python main.py

## API Endpoints (once running)
http://localhost:5050/api/today
http://localhost:5050/api/sessions
http://localhost:5050/api/weekly
http://localhost:5050/api/hourly