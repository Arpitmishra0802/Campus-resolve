# Campus Resolve — Smart Complaint & Grievance Management System

Campus Resolve is a full-stack college complaint and grievance management web application. It connects students and campus management through an intuitive, institutional user interface (designed with Google Stitch) backed by a secure Python Flask backend, SQLite database, and an AI/ML text classification module.

Students can submit infrastructure, IT, and facility issues with descriptions and photo evidence, obtain unique ticket IDs, receive real-time AI category suggestions, and track the chronological resolution timeline. Campus administrators can inspect complaints, triage priorities, change lifecycle stages, add remarks, and mark tickets as resolved or closed.

---

## 🚀 Key Features

### 1. UI & Visual Design (Preserving Google Stitch)
- **Design System Fidelity:** Faithful implementation of the Stitch design system tokens (`#f8f9ff` surface, `#0051d5` primary blue, `#0b1c30` slate headers, `#ba1a1a` alerts, `#10b981` success).
- **Responsive Layout:** Adaptive desktop top navigation and desktop sidebars paired with mobile bottom tabs.
- **7 Implemented Screens:**
  1. **Landing Page (`/`):** Hero showcase, campus SLA indicators, and portal navigation.
  2. **Login Page (`/login`):** Unified role-detecting authentication interface with demo credentials guide.
  3. **Student Registration Page (`/register`):** Student account creation with server-side validation.
  4. **Student Dashboard (`/dashboard`):** Real database triage summary counters, filtered ticket list, and empty state.
  5. **New Complaint Page (`/complaints/new`):** Description input with AI category suggestion, manual selection, and safe photo upload preview.
  6. **Complaint Details & Tracking Page (`/complaints/<ticket_id>`):** Student tracking view with photo evidence and chronological audit timeline.
  7. **Management Portal (`/management`):** Command center, live triage counters, multi-criteria filtering, ticket management drawer with priority/status updates and broadcast remarks.

### 2. Role-Based Authentication & Security
- **Two Roles:** `student` and `management`.
- **Password Security:** Salted password hashing via Werkzeug (`generate_password_hash` & `check_password_hash`).
- **Authorization Boundaries:** Server-side decorators (`@login_required`, `@student_required`, `@management_required`).
- **Data Isolation:** Students can only view their own tickets; management accounts have access to the campus queue.
- **CSRF Protection:** Cryptographic session-bound CSRF token validation on all state-changing requests.
- **Safe File Uploads:** Strict file extension validation (`.jpg`, `.jpeg`, `.png`, `.webp`), MIME type verification, size limit (5 MB), and UUID-prefixed safe filenames.

### 3. AI/ML Category Classifier
- **Technology:** TF-IDF Vectorization + Multinomial Naive Bayes with Laplace smoothing ($\alpha=0.1$).
- **Dataset:** 116 realistic campus grievance records across 6 categories:
  - `Electrical` (fans, wiring, tube lights, ACs, circuit breakers)
  - `Cleaning` (garbage bins, restrooms, dust, spills, cafeteria sanitation)
  - `Internet` (campus Wi-Fi, LAN switches, routers, portals)
  - `Classroom Equipment` (projectors, audio speakers, podiums, whiteboards)
  - `Plumbing` (water taps, flush valves, leaks, water coolers)
  - `Other` (campus security, parking gates, noise, animal control)
- **Live Auto-Suggestion:** Interactive suggestion box that predicts category as the student writes their description.
- **Student Choice:** Allows student to keep the AI suggestion or choose manually.
- **Graceful Fallback:** If description is too short or model is unavailable, gracefully falls back to manual selection without error.

---

## 📁 Project Structure

```
MY PROJECT/
├── stitch_original/         # Untouched original Stitch design assets (code.html, DESIGN.md, screen.png)
├── static/
│   ├── img/                 # Application SVG logos and visual assets
│   └── uploads/             # Safely validated and stored complaint evidence photos
├── templates/
│   ├── base.html            # Shared layout with Stitch design tokens, header, bottom nav, CSRF
│   ├── landing.html         # Screen 1: Landing Page
│   ├── login.html           # Screen 2: Login Page
│   ├── register.html        # Screen 3: Student Registration Page
│   ├── student_dashboard.html # Screen 4: Student Dashboard
│   ├── new_complaint.html   # Screen 5: New Complaint Page with AI Predictor
│   ├── complaint_detail.html # Screen 6: Complaint Tracking & Audit Timeline
│   └── management_portal.html # Screen 7: Management Command Center
├── ai_model/
│   ├── dataset.json         # Labeled campus grievance dataset (116 records)
│   ├── train_model.py       # ML training and evaluation script (TF-IDF + Naive Bayes)
│   ├── classifier.py        # Reusable category predictor with graceful fallback
│   └── trained_model.json   # Serialized model parameters and vocabulary (622 tokens)
├── app.py                   # Main Flask application entry point, routing, API endpoints
├── auth.py                  # Authentication routes, password hashing, role-based decorators
├── models.py                # SQLite schema creation, database helper functions
├── seed_data.py             # Database initialization and demo data seeding
├── test_app.py              # Automated test suite covering all 17 criteria
├── requirements.txt         # Project dependencies
├── .env.example             # Environment configuration example
├── .gitignore               # Git ignore configuration
└── README.md                # Documentation and running instructions
```

---

## 🛠️ Setup & Running Instructions (Beginner-Friendly)

### Step 1: Open Terminal / PowerShell
Open your terminal in the project directory:
```bash
cd "c:\Users\Arpit Mishra\OneDrive\Desktop\MY PROJECT"
```

### Step 2: Set Up Virtual Environment (Already Configured)
To activate the existing virtual environment:
- On Windows (PowerShell):
  ```powershell
  .\.venv\bin\Activate.ps1
  ```
- Or on Windows (Command Prompt):
  ```cmd
  .venv\bin\activate.bat
  ```

### Step 3: Install Dependencies
```bash
.venv\bin\pip install -r requirements.txt
```

### Step 4: (Optional) Re-train the AI Classifier
To re-train the AI model on the dataset and view the evaluation metrics:
```bash
.venv\bin\python ai_model\train_model.py
```

### Step 5: (Optional) Re-seed the Database
To initialize SQLite tables and load sample grievances:
```bash
.venv\bin\python seed_data.py
```

### Step 6: Start the Application
Run the Flask server:
```bash
.venv\bin\python app.py
```

### Step 7: Open in Your Browser
Open your favorite web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🔑 Demo Login Accounts

| Role | Email | Password | Access |
|---|---|---|---|
| **Management** | `admin@campus.edu` | `Admin@123` | Full Queue Triage, Priority & Status Management, Remarks Broadcast |
| **Demo Student** | `student@campus.edu` | `Student@123` | Student Dashboard, Submit Complaint, AI Categorization, Track Tickets |
| **Alex Morgan** | `alex@college.edu` | `Student@123` | Student Dashboard, Has photo evidence ticket `#CR-2026-1042` |
| **Priyah Sharma** | `priyah@college.edu` | `Student@123` | Student Dashboard, Ticket `#CR-2026-1041` (Critical Wi-Fi Outage) |
| **David Chen** | `david@college.edu` | `Student@123` | Student Dashboard, Ticket `#CR-2026-1039` (Resolved Plumbing Leak) |

You can also click **"Register"** on the website to create a brand new student account!

---

## 🧪 Running the Automated Test Suite

To run the full automated test suite verifying all 17 core requirements:
```bash
.venv\bin\python -m unittest test_app.py
```

Expected Output:
```
.................
----------------------------------------------------------------------
Ran 17 tests in 6.471s

OK
```

All 17 verification points pass cleanly, confirming role security, input validation, AI inference accuracy, and SQLite data persistence.

