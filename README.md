# Attendance Management System

A comprehensive **RFID-based attendance tracking system** built with **FastAPI**, **SQLite**, and **Tailwind CSS**. This application allows organizations to monitor employee attendance in real-time, manage user roles, and generate reports.

---

## Table of Contents

* [Features](#features)
* [Tech Stack](#tech-stack)
* [Prerequisites](#prerequisites)
* [Installation](#installation)
* [Running the Application](#running-the-application-development)
* [Default Credentials](#default-credentials)
* [Usage](#usage)

  * [Login and Navigation](#login-and-navigation)
  * [Admin Functions](#admin-functions)
  * [RFID Integration (ESP32/Microcontroller)](#rfid-integration-esp32microcontroller)
* [API Endpoints](#api-endpoints)
* [Database Schema](#database-schema)
* [Deployment](#deployment)
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

## Tech Stack

* **Backend**: FastAPI (Python)
* **Database**: SQLite
* **Frontend**: HTML + Tailwind CSS
* **Auth**: Session-based with bcrypt password hashing
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

4. **(Optional) Create a `.env` file or export environment variables if you want to override defaults (see Configuration section).**

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

## Default Credentials

> **Change these in production!**

* **Super Admin**

  * Username: `sudoadmin`
  * Password: `passcode@1234`

---

## Usage

### Login and Navigation

* Visit the root URL (`/`) to access the login page.
* Enter credentials appropriate to the role (Employee, Admin, Super Admin).
* Use the navigation links to move between dashboards.

### Admin Functions

* **Add Employee**: Provide `name`, `email`, `rfid_tag`, `role`, and `department`.
* **Remove Employee**: Select employee to remove (may require Super Admin approval depending on settings).
* **View Attendance**: Check current occupancy per block or view detailed summaries.
* **Handle Unknown RFIDs**: Review and resolve logged unrecognized tags.

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
* `GET /super_admin` - Super Admin dashboard

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

## Deployment

### Local / Small Deployment

* Development: use `uvicorn main:app --reload`.
* Production: use a production-ready server such as Gunicorn with Uvicorn workers.

Example using Gunicorn (Linux):

```bash
gunicorn -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000 --workers 4
```

Place Nginx in front as a reverse proxy for TLS termination and static file serving.

### Considerations for Production

* Move from SQLite to PostgreSQL or MySQL for concurrency and reliability.
* Use environment variables for secrets and configuration.
* Use HTTPS (TLS) and set up a firewall and rate-limiting.

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

3. Access from other devices using `http://<your_ip>:8000`.

---

## Configuration & Environment Variables

Recommended environment variables (examples):

* `DATABASE_URL` — SQLite path or other DB URL (default: `sqlite:///./attendance.db`)
* `SECRET_KEY` — Session/signing secret
* `ADMIN_PASSWORD` — Override default admin password

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

**Made with ❤️ — Attendance Management System**
