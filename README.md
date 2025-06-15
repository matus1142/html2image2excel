


### 🗂️ Folder Structure

```
html2image2excel/
│
├── frontend/
│   ├── html2image2excel_frontend.html
│   └── Dockerfile
│
├── backend/
│   ├── html2image2excel_backend.py
│   └── requirements.txt
│   └── services.py
│
└── docker-compose.yml
```

---

## 🔧 1. Backend (Flask API)

**📄 `backend/html2image2excel_backend.py`**

```python
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)

# Code for the API endpoints

if __name__ == '__main__':
    # Run with threading enabled
    app.run(
        debug=False,  # Disabled for production
        host='0.0.0.0',
        port=5000,
        threaded=True,  # Enable threading
        request_handler=ThreadedWSGIRequestHandler
    )
```

**📄 `backend/requirements.txt`**

```
flask-cors==4.0.0
beautifulsoup4==4.12.2
pandas==2.1.1
openpyxl==3.1.2
lxml==4.9.3
pillow==11.2.1
playwright==1.52.0
```
```bash
cd backend
pip install -r requirements.txt
python html2image2excel_backend.py
```
---

## 🌐 2. Frontend (Static HTML)

**📄 `frontend/html2image2excel_frontend.html`**

```html
<!DOCTYPE html>
<html>
<head>
  <title>Frontend</title>
</head>
<body>
  <h1>Frontend Page</h1>
    <!-- Your HTML content goes here -->
  <script>
    // Your JavaScript code goes here
  </script>
</body>
</html>
```

**📄 `frontend/Dockerfile`**

```Dockerfile
FROM nginx:alpine

COPY html2image2excel_frontend.html /usr/share/nginx/html/index.html
```

---

## ⚙️ 3. Compose File (`podman-compose.yml`)

```yaml
version: '3'
services:
  frontend:
    build: ./frontend
    ports:
      - "8080:80"
```

---

## 🛠️ 4. Build and Run

Make sure you're in the `podman-app` directory:

```bash
# Build containers
podman-compose -f docker-compose.yml build

# Run containers
podman-compose -f docker-compose.yml up
```

---

## ✅ Access

* Frontend: [http://localhost:8080](http://localhost:8080)
* Backend API: [http://localhost:5000/health](http://localhost:5000/health)

---
