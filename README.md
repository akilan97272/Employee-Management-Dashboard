﻿# Attendance Management System

A comprehensive **RFID-based attendance tracking system** built with **FastAPI**, **MariaDB**, and **Tailwind CSS**. This application allows organizations to monitor employee attendance in real-time, manage user roles, and generate reports.

---


##  Table of Contents

* [Features](#features)
* [Tech Stack](#tech-stack)
* [Prerequisites](#prerequisites)
* [Installation](#installation)
* [Running the Application](#running-the-application-development)
* [Usage](#usage)

  * [Login and Navigation](#login-and-navigation)
  * [Admin Functions](#admin-functions)
  * [RFID Integration (ESP32/Microcontroller)](#rfid-integration-esp32microcontroller)
* [API Endpoints](#api-endpoints)
* [Project Environment & Security](#project-environment-security)
* [Database Schema](#database-schema)
* [Hosting on Your IP / Network Access](#hosting-on-your-ip--network-access)
* [Configuration & Environment Variables](#configuration--environment-variables)
* [Security Notes](#security-notes)
* [Troubleshooting](#troubleshooting)
* [Contributing](#contributing)
* [Support](#support)

---

## Features

* **User Authentication**: Role-based access control (Super Admin, Admin, Employee).
* **RFID Integration**: Real-time attendance recording using RFID tags sent from an ESP32 or similar microcontroller.
* **Dashboards**:

  * **Employee Dashboard**: View personal attendance details.
  * **Admin Dashboard**: Manage employees, view attendance summaries, handle unknown RFIDs.
  * **Super Admin Dashboard**: Oversee admins and manage system-wide settings.
* **Attendance Tracking**: Record entry/exit times, calculate duration, track occupancy by blocks.
* **Employee Management**: Add, remove, update employee info.
* **Reporting**: Filter attendance by department, employee, or date.
* **Unknown RFID Detection**: Log and alert on unrecognized RFID tags.

##  Tech Stack

* **Backend**: FastAPI (Python)
* **Database**: MariaDB
* **Frontend**: HTML + Tailwind CSS
* **Auth**: Session-based with bcrypt password hashing
* **Hardware**: ESP32 / microcontroller for RFID reading

---

##  Prerequisites

* Python 3.8+
* `pip` (Python package manager)
* Git (optional, for cloning)
* Node.js 18+ (required for `gltf-transform`)

### 3D Model Pipeline (One-Time Setup)

1. Install `gltf-transform` CLI:

```bash
npm install -g @gltf-transform/cli
```

2. Install backend dependencies:

```bash
pip install -r requirements.txt
```

3. Configure `.env` for AWS/CDN:

```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION= ....
S3_BUCKET= ....
CLOUDFRONT_DOMAIN= ....
```

4. AWS resources:

- Create S3 bucket (model storage)
- Create CloudFront distribution with S3 origin
- Use CloudFront URL for serving models

Current production flow:

`Upload GLB -> Draco compression -> S3 upload -> CloudFront URL -> MariaDB metadata`

### Where Each Thing Lives

- GLB files: **Amazon S3**
- Fast delivery: **Amazon CloudFront**
- Links + metadata: **MariaDB**
- Compression: **Backend server**

### Package Summary

Node side:
- `gltf-transform`

Python backend:
- `boto3`
- `python-dotenv`
- `pymysql`

### Golden Rules

- Always store **CloudFront URL** in DB
- Never store S3 URL in DB
- Never store GLB binaries inside MariaDB

---



**Security Notes:**
- Never commit your `.env` file or secrets to source control.
- Always use strong, unique values for `SECRET_KEY` and `ADMIN_PASSWORD`.
- For production, run the app with HTTPS enabled (see instructions above).
- To enable HTTPS, provide valid SSL certificate and key files:
  - `--ssl-keyfile=path/to/key.pem`
  - `--ssl-certfile=path/to/cert.pem`
- If using SMTP for email, set the SMTP variables as shown above.

**Error Handling:**
- The app will raise an error if `DATABASE_URL` is missing from your `.env` file.

**Logging:**
- Request duration and errors are logged for debugging and monitoring.

---

##  Installation

1. **Create a virtual environment**

```bash
conda create --name AttendanceSystem python=3.11
conda activate AttendanceSystem
``` 
**Without conda:**
```bash
#on windows
python -m venv AttendanceSystem
AttendanceSystem\Scripts\activate

#on Linux / MacOS
python3 -m venv AttendanceSystem
source AttendanceSystem/bin/activate
```

2. **Clone or download the project:**

```bash
git clone <repository-url>
cd attendance_system
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
```

4. **Create a `.env` file or export environment variables if you want to override defaults (see Configuration section).**
```env
DATABASE_URL=" <-- your database url --> "
```
---

## Running the Application

Development (hot reload, slower):

```bash
uvicorn app.main:app --reload --http httptools
```

Production-fast (Linux/macOS, no reload, multiple workers):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --http httptools
```

Alternative fast server (Hypercorn):

```bash
hypercorn app.main:app --config hypercorn.toml
```

Windows note: Uvicorn multi-worker mode can fail on Windows (WinError 10022). Use --workers 1 with Uvicorn, or use Hypercorn.

Windows PowerShell production profile (recommended for stability):

```powershell
$env:APP_PROFILE="production"
$env:AUTO_SCHEMA_SYNC_ON_STARTUP="false"
$env:RUNTIME_SCHEMA_GUARD_ENABLED="false"
$env:AUTO_TABLE_HEALTH_REPAIR="false"
$env:ENABLE_GZIP="true"
$env:GZIP_MIN_SIZE="1024"
$env:STATIC_ASSET_CACHE_SECONDS="604800"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --http httptools
```

PowerShell with Hypercorn:

```powershell
$env:APP_PROFILE="production"
$env:AUTO_SCHEMA_SYNC_ON_STARTUP="false"
$env:RUNTIME_SCHEMA_GUARD_ENABLED="false"
$env:AUTO_TABLE_HEALTH_REPAIR="false"
$env:ENABLE_GZIP="true"
$env:GZIP_MIN_SIZE="1024"
$env:STATIC_ASSET_CACHE_SECONDS="604800"
hypercorn app.main:app --config hypercorn.toml
```

Open your browser: `http://127.0.0.1:8000`

HTTPS (SSL/TLS):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --ssl-keyfile=path/to/ssl/key.pem \
  --ssl-certfile=path/to/ssl/cert.pem
```

Replace `path/to/ssl/key.pem` and `path/to/ssl/cert.pem` with real file paths.

---

##  Usage

### Login and Navigation

* Visit the root URL (`/`) to access the login page.
* Enter credentials appropriate to the role (Employee, Admin).
* Use the navigation links to move between dashboards.

### Admin Functions

* **Add Employee**: Provide `name`, `email`, `rfid_tag`, `role`, and `department`.
* **Remove Employee**: Select employee to remove (may require Super Admin approval depending on settings).
* **View Attendance**: Check current occupancy per block or view detailed summaries.
* **Handle Unknown RFIDs**: Review and resolve logged unrecognized tags.
* **Live Block Level Monitoring**: Block visualization is enabled based on the number of blockes and the number of persons in it.

### RFID Integration (ESP32/Microcontroller)

Configure your ESP device to send POST requests to the attendance API endpoint when a tag is scanned.

**Sample JSON payload**:

```json
{
  "rfid_tag": "0123456789AB",
  "area": "Area 1",
  "slot_no": "Building 1",
  "building_name": "Building 1",
  "building_id": "R2566"
}
```

**Endpoint**: `POST /api/attendance`

* The backend will match `rfid_tag` with a user in the `users` table and create or update an `attendance` record (entry/exit/duration).
* Use **Slot No / Building Name** (`slot_no` or `building_name`) for room mapping.
* If `rfid_tag` is unknown, it will be logged in the `unknown_rfids` table for review.

---

## API Endpoints

**Authentication**

* `GET /` - Login page
* `POST /login` - Authenticate user
* `GET /logout` - Logout user

**Dashboards**

* `GET /employee` - Employee dashboard
* `GET /admin` - Admin dashboard

**Admin Operations**

* `POST /admin/add_employee` - Add new employee
* `POST /admin/remove_employee` - Remove employee
* `GET /admin/employee_details` - Get employee profile

**API (for devices / integrations)**

* `POST /api/attendance` - Record RFID attendance
* `GET /api/block_persons` - Get persons in a specific block

---

##  Database Schema

This project uses **SQLAlchemy ORM** with a relational database.
Below is an overview of the core tables and their relationships.



##  users

Stores employee and system user information.

| Column          | Type                    | Description                          |
| --------------- | ----------------------- | ------------------------------------ |
| id              | Integer (PK)            | Internal user ID                     |
| employee_id     | String (60)             | Unique employee identifier           |
| name            | String                  | Employee full name                   |
| email           | String                  | Unique email address                 |
| rfid_tag        | String                  | RFID card/tag                        |
| role            | String                  | User role (Admin, Employee, Manager) |
| department      | String                  | Department name                      |
| password_hash   | String                  | bcrypt hashed password               |
| is_active       | Boolean                 | Account status                       |
| hourly_rate     | Float                   | Hourly wage                          |
| allowances      | Float                   | Extra allowances                     |
| deductions      | Float                   | Salary deductions                    |
| can_manage      | Boolean                 | Manager permission                   |
| current_team_id | Integer (FK â†’ teams.id) | Assigned team                        |
| active_leader   | Boolean                 | Leader status                        |



##  attendance

Tracks daily attendance using RFID.

| Column        | Type                            | Description        |
| ------------- | ------------------------------- | ------------------ |
| id            | Integer (PK)                    | Attendance ID      |
| employee_id   | String (FK â†’ users.employee_id) | Employee reference |
| date          | Date                            | Attendance date    |
| entry_time    | DateTime                        | Entry timestamp    |
| exit_time     | DateTime                        | Exit timestamp     |
| duration      | Float                           | Working hours      |
| status        | String                          | PRESENT / ABSENT   |
| location_name | String                          | Location           |
| room_no       | String                          | Room number        |

 **Relationship**:

* One user â†’ many attendance records



##  removed_employees

Keeps history of removed employees.

| Column      | Type         | Description       |
| ----------- | ------------ | ----------------- |
| id          | Integer (PK) | Record ID         |
| employee_id | String       | Employee ID       |
| name        | String       | Name              |
| email       | String       | Email             |
| rfid_tag    | String       | RFID              |
| role        | String       | Role              |
| department  | String       | Department        |
| removed_at  | DateTime     | Removal timestamp |



##  unknown_rfids

Logs unauthorized or unknown RFID scans.

| Column    | Type         | Description   |
| --------- | ------------ | ------------- |
| id        | Integer (PK) | Record ID     |
| rfid_tag  | String       | Unknown RFID  |
| location  | String       | Scan location |
| timestamp | DateTime     | Scan time     |



## rooms

Stores physical room details.

| Column        | Type         | Description          |
| ------------- | ------------ | -------------------- |
| id            | Integer (PK) | Room ID              |
| room_id       | String       | Unique room code     |
| room_no       | String       | Room number          |
| location_name | String       | Location             |
| description   | String       | Optional description |



## departments

Organization departments.

| Column      | Type         | Description     |
| ----------- | ------------ | --------------- |
| id          | Integer (PK) | Department ID   |
| name        | String       | Department name |
| description | String       | Optional info   |



## tasks

Task management for employees.

| Column      | Type         | Description         |
| ----------- | ------------ | ------------------- |
| id          | Integer (PK) | Task ID             |
| user_id     | String       | Assigned employee   |
| title       | String       | Task title          |
| description | Text         | Task details        |
| status      | String       | pending / completed |
| priority    | String       | low / medium / high |
| due_date    | DateTime     | Deadline            |
| created_at  | DateTime     | Created timestamp   |



## leave_requests

Employee leave management.

| Column      | Type                            | Description                   |
| ----------- | ------------------------------- | ----------------------------- |
| id          | Integer (PK)                    | Request ID                    |
| employee_id | String (FK â†’ users.employee_id) | Employee                      |
| start_date  | Date                            | Leave start                   |
| end_date    | Date                            | Leave end                     |
| reason      | String                          | Leave reason                  |
| status      | String                          | Pending / Approved / Rejected |



## teams

Team and leadership structure.

| Column     | Type                    | Description       |
| ---------- | ----------------------- | ----------------- |
| id         | Integer (PK)            | Team ID           |
| name       | String                  | Team name         |
| department | String                  | Department        |
| leader_id  | Integer (FK â†’ users.id) | Team leader       |
| created_at | DateTime                | Created timestamp |

**Relationships**:

* One team â†’ many users
* One team â†’ one leader



## Entity Relationship Overview

```
User â”€â”€â”€< Attendance
User â”€â”€â”€< LeaveRequest
User â”€â”€â”€< Task
Team â”€â”€â”€< User
Team â”€â”€â”€ Leader (User)
```



##  Security Notes

* Passwords are stored using **bcrypt hashing**
* Authentication is **session-based**
* RFID access is logged and validated
* Unknown RFID attempts are tracked

---

## Hosting on Your IP / Network Access

1. Run the app bound to `0.0.0.0`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --http httptools
```

2. Find your machine IP (Linux):

```bash
ip addr show
```

(Windows):

```cmd
ipconfig
```

3. Access from other devices using `http://<your_ip>:8000/`.

---

##  Configuration & Environment Variables

Recommended environment variables (examples):

* `DATABASE_URL` SQLite path or other DB URL (default: `sqlite:///./attendance.db`)
* `SECRET_KEY` Session/signing secret
* `ADMIN_PASSWORD` Override default admin password
* `APP_PROFILE`  `development` or `production` (production disables expensive safety checks by default)
* `AUTO_SCHEMA_SYNC_ON_STARTUP` set `false` for faster startup after schema is stable
* `RUNTIME_SCHEMA_GUARD_ENABLED`  set `false` for lower per-request overhead in production
* `AUTO_TABLE_HEALTH_REPAIR`  set `false` to skip startup table check/repair
* `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT_SEC` â€” database concurrency tuning
* `ENABLE_GZIP` / `GZIP_MIN_SIZE`  response compression tuning for dashboard/API payloads
* `STATIC_ASSET_CACHE_SECONDS`  browser cache TTL for static assets (including 3D files under `/static`)

---

##  Security Notes

* **Change default Super Admin password** before deploying to production.
* Use **HTTPS** in production.
* Keep your `SECRET_KEY` and database credentials out of source control â€” use environment variables or a secret manager.
* Implement rate limiting for API endpoints exposed to the network.

---

##   Troubleshooting

* **405 Method Not Allowed**: Ensure your login form `action` is `/login` and the method is `POST`.
* **Styles Not Loading**: If using Tailwind CDN, check internet connectivity. For offline use, build Tailwind locally.
* **Database Errors**: Confirm the SQLite file path and write permissions for the process user.
* **RFID Not Recording**: Verify the ESP payload format and that the device is pointing to the correct endpoint and port.
* **Logs**: Check terminal output for FastAPI logs. Use browser dev tools for frontend issues.

---

##  Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests where appropriate.
4. Commit and push: `git push origin feature/my-feature`
5. Create a Pull Request describing your changes.

Please follow repository code style and ensure all new code is tested.

---


##  Support

If you run into issues:

* Check the **Troubleshooting** section above
* Review the code comments
* Open an issue in the repository with logs, steps to reproduce, and relevant environment details

---

**Made with TeamSync**


