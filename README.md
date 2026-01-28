# Attendance Management System

A comprehensive **RFID-based attendance tracking system** built with **FastAPI**, **MariaDB**, and **Tailwind CSS**. This application allows organizations to monitor employee attendance in real-time, manage user roles, and generate reports.

---

## Table of Contents

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
* [Database Schema](#database-schema)
* [Hosting on Your IP / Network Access](#hosting-on-your-ip--network-access)
* [Configuration & Environment Variables](#configuration--environment-variables)
* [Release / Version](#release--version)
* [Security Configuration Table](#security-configuration-table)
* [HTTPS / TLS Setup](#https--tls-setup)
* [Logging Locations](#logging-locations)
* [Session Timer & Reload Behavior](#session-timer--reload-behavior)
* [Deployment Checklist](#deployment-checklist)
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

## Security Features

* **Encrypted Sessions**: Fernet-encrypted session cookies with idle/absolute timeouts.
* **HTTPS Enforcement**: Configurable HTTPS redirect and secure cookie handling.
* **CSRF Protection**: Middleware support, toggled by environment.
* **Security Headers**: HSTS, X-Frame-Options, and related headers (configurable).
* **XSS Protection**: Response header hardening for script injection defenses.
* **Input Safety**: Body size limits and sanitization helpers for user input.
* **Login Throttling**: Login attempt limiting to reduce brute-force attacks.
* **Request Tracing**: Request ID injection for auditability.
* **Activity Logging**: Access logs to logs/security.log.
* **Audit Trail**: Structured audit events to logs/audit.log.
* **Encryption at Rest**: AES-256-GCM helpers for sensitive fields.

* **Security Integration Layer**: Centralized wiring in [security_integration.py](security_integration.py).
* **Environment Profiles**: Separate config files: [.env.localhost](.env.localhost) and [.env.production](.env.production).
* **Env Selection**: `APP_ENV` or `ENV_ACTIVE` toggles which env file loads at startup.
* **Auto Key Generation**: `SECRET_KEY` and `ENCRYPTION_KEY` auto-generate in production when set to `AUTO_GENERATE`.
* **Session Timer UI**: Live countdown header pill with /api/session/timing.
* **Reload Logout Modal**: Corporate-style reload confirmation with logout on continue.

## Tech Stack

* **Backend**: FastAPI (Python)
* **Database**: MariaDB
* **Frontend**: HTML + Tailwind CSS
* **Auth**: Session-based with bcrypt password hashing
* **Security**:
  * **Language**: Python
  * **Session Security**: Encrypted session cookies (Fernet)
  * **Password Hashing**: bcrypt
  * **CSRF**: Middleware-based CSRF validation
  * **HTTPS/TLS**: Redirect and secure-cookie enforcement
  * **Headers**: HSTS and security header hardening
  * **XSS**: Response header protection
  * **Input Safety**: Body size limits and sanitization helpers
  * **Rate Limiting**: Login attempt throttling
  * **Audit/Logging**: Activity logs + audit trail
  * **Encryption at Rest**: AES-256-GCM helpers
* **Hardware**: ESP32 / microcontroller for RFID reading

---

## Prerequisites

* Python 3.8+
* `pip` (Python package manager)
* Git (optional, for cloning)

---

## Installation

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

## Running the Application (Development)

```bash
# Start with auto-reload for development
uvicorn main:app --reload
```

Open your browser and go to: `http://127.0.0.1:8000`

For network access on your LAN:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Usage

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
  "timestamp": "2025-10-27T11:34:00+05:30",
  "block": "A1"
}
```

**Endpoint**: `POST /api/attendance`

* The backend will match `rfid_tag` with a user in the `users` table and create or update an `attendance` record (entry/exit/duration).
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

## Database Schema

**Tables**

* `users` — Employee/admin information

  * Key fields: `id`, `employee_id`, `name`, `email`, `rfid_tag`, `role`, `department`, `password_hash`
* `attendance` — Entry/exit records

  * Key fields: `id`, `employee_id`, `rfid_tag`, `entry_time`, `exit_time`, `duration`, `block`
* `removed_employees` — Archive of removed employees
* `unknown_rfids` — Logs of unrecognized RFID tags

> Tip: Inspect `models.py` (or your ORM definitions) for the exact table and column names used in your project.

---

## 📦 Database Schema

This project uses **SQLAlchemy ORM** with a relational database.
Below is an overview of the core tables and their relationships.



## 👤 users

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
| current_team_id | Integer (FK → teams.id) | Assigned team                        |
| active_leader   | Boolean                 | Leader status                        |



## 🕒 attendance

Tracks daily attendance using RFID.

| Column        | Type                            | Description        |
| ------------- | ------------------------------- | ------------------ |
| id            | Integer (PK)                    | Attendance ID      |
| employee_id   | String (FK → users.employee_id) | Employee reference |
| date          | Date                            | Attendance date    |
| entry_time    | DateTime                        | Entry timestamp    |
| exit_time     | DateTime                        | Exit timestamp     |
| duration      | Float                           | Working hours      |
| status        | String                          | PRESENT / ABSENT   |
| location_name | String                          | Location           |
| room_no       | String                          | Room number        |

🔗 **Relationship**:

* One user → many attendance records



## ❌ removed_employees

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



## 🚫 unknown_rfids

Logs unauthorized or unknown RFID scans.

| Column    | Type         | Description   |
| --------- | ------------ | ------------- |
| id        | Integer (PK) | Record ID     |
| rfid_tag  | String       | Unknown RFID  |
| location  | String       | Scan location |
| timestamp | DateTime     | Scan time     |



## 🏢 rooms

Stores physical room details.

| Column        | Type         | Description          |
| ------------- | ------------ | -------------------- |
| id            | Integer (PK) | Room ID              |
| room_id       | String       | Unique room code     |
| room_no       | String       | Room number          |
| location_name | String       | Location             |
| description   | String       | Optional description |



## 🏬 departments

Organization departments.

| Column      | Type         | Description     |
| ----------- | ------------ | --------------- |
| id          | Integer (PK) | Department ID   |
| name        | String       | Department name |
| description | String       | Optional info   |



## 📝 tasks

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



## 🏖 leave_requests

Employee leave management.

| Column      | Type                            | Description                   |
| ----------- | ------------------------------- | ----------------------------- |
| id          | Integer (PK)                    | Request ID                    |
| employee_id | String (FK → users.employee_id) | Employee                      |
| start_date  | Date                            | Leave start                   |
| end_date    | Date                            | Leave end                     |
| reason      | String                          | Leave reason                  |
| status      | String                          | Pending / Approved / Rejected |



## 👥 teams

Team and leadership structure.

| Column     | Type                    | Description       |
| ---------- | ----------------------- | ----------------- |
| id         | Integer (PK)            | Team ID           |
| name       | String                  | Team name         |
| department | String                  | Department        |
| leader_id  | Integer (FK → users.id) | Team leader       |
| created_at | DateTime                | Created timestamp |

🔗 **Relationships**:

* One team → many users
* One team → one leader



## 🔗 Entity Relationship Overview

```
User ───< Attendance
User ───< LeaveRequest
User ───< Task
Team ───< User
Team ─── Leader (User)
```



## 🛡 Security Notes

* Passwords are stored using **bcrypt hashing**
* Authentication is **session-based**
* RFID access is logged and validated
* Unknown RFID attempts are tracked

---

## Hosting on Your IP / Network Access

1. Run the app bound to `0.0.0.0`:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
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

## Configuration & Environment Variables

Environment profiles:

* Local development: [.env.localhost](.env.localhost)
* Production: [.env.production](.env.production)

Selection:

* Set `APP_ENV=production` to load production settings.
* If `APP_ENV` is not set, `ENV_ACTIVE=true` in the env file determines which profile is active.

Recommended environment variables (examples):

* `DATABASE_URL` — SQLite path or other DB URL (default: `sqlite:///./attendance.db`)
* `SECRET_KEY` — Session/signing secret
* `ADMIN_PASSWORD` — Override default admin password

---

## Release / Version

* Versioning: Semantic versioning recommended (MAJOR.MINOR.PATCH).
* Track releases in your Git tags (e.g., v1.0.0).

---

## Security Configuration Table

| Flag | Description | Default | Recommended (Prod) |
| --- | --- | --- | --- |
| `FORCE_HTTPS` | Redirect HTTP to HTTPS | false | true |
| `ALLOW_INSECURE_LOCALHOST` | Allow HTTP on localhost | true | false |
| `HSTS_ENABLED` | Enable security headers | false | true |
| `CSRF_ENABLED` | Enforce CSRF tokens | false | true |
| `SESSION_HTTPS_ONLY` | HTTPS-only cookies | false | true |
| `SESSION_MAX_AGE` | Session max age (seconds) | 600 | 3600 |
| `SESSION_IDLE_TIMEOUT` | Idle timeout (seconds) | 600 | 1800 |

---

## HTTPS / TLS Setup

1. Set `FORCE_HTTPS="true"` and `ALLOW_INSECURE_LOCALHOST="false"` in [.env.production](.env.production).
2. Provide certificate paths:
  * `TLS_CERT_FILE`
  * `TLS_KEY_FILE`
  * `TLS_CA_FILE` (optional)
3. Run the TLS server:
  ```bash
  python Security/run_tls.py
  ```

---

## Logging Locations

* Activity logs: `logs/security.log`
* Audit trail: `logs/audit.log`

---

## Session Timer & Reload Behavior

* Session countdown appears in the header and updates via `/api/session/timing`.
* Reloading a page shows a confirmation modal:
  * **Cancel** keeps the current session.
  * **Continue** logs out and redirects to the login page.

---

## Deployment Checklist

* Set `APP_ENV=production`
* Set `FORCE_HTTPS="true"`
* Set `ALLOW_INSECURE_LOCALHOST="false"`
* Set `CSRF_ENABLED="true"`
* Set `HSTS_ENABLED="true"`
* Set `SESSION_HTTPS_ONLY="true"`
* Update `CORS_ORIGINS` to your domain
* Confirm `SECRET_KEY` and `ENCRYPTION_KEY` are set (auto-generated if `AUTO_GENERATE`)
* Configure TLS cert paths and run `Security/run_tls.py`

---

## Security Notes

* **Change default Super Admin password** before deploying to production.
* Use **HTTPS** in production.
* Keep your `SECRET_KEY` and database credentials out of source control — use environment variables or a secret manager.
* Implement rate limiting for API endpoints exposed to the network.

---

## Troubleshooting

* **405 Method Not Allowed**: Ensure your login form `action` is `/login` and the method is `POST`.
* **Styles Not Loading**: If using Tailwind CDN, check internet connectivity. For offline use, build Tailwind locally.
* **Database Errors**: Confirm the SQLite file path and write permissions for the process user.
* **RFID Not Recording**: Verify the ESP payload format and that the device is pointing to the correct endpoint and port.
* **Logs**: Check terminal output for FastAPI logs. Use browser dev tools for frontend issues.

---

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests where appropriate.
4. Commit and push: `git push origin feature/my-feature`
5. Create a Pull Request describing your changes.

Please follow repository code style and ensure all new code is tested.

---


## Support

If you run into issues:

* Check the **Troubleshooting** section above
* Review the code comments
* Open an issue in the repository with logs, steps to reproduce, and relevant environment details

---

**Made with ❤️ — TeamSync**
