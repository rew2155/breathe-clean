# Breathe Clean

The beginning of Breathe Clean: an application that monitors the air quality of a room and adjusts a nearby air purifier accordingly :)

## Overview

Breathe Clean is an IoT-style project for monitoring indoor air quality and controlling an air purifier based on the PM2.5 air quality reading. 
The project currently includes a mock PM2.5 sensor, a FastAPI backend, and a PostgreSQL integration.

### Current Data Flow

```text
Mock Sensor
    |
    | POST /readings
    v
FastAPI Backend
    |
    v
PostgreSQL
    |
    | GET /readings
    v
API Client
```

The mock sensor generates PM2.5 readings and sends them to the FastAPI backend which stores readings in a PostgreSQL database.

## Installation

### Prerequisites

- Python 3.12 or later
- PostgreSQL

Clone the repository and move into its root directory. Then create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Install the backend dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

## Database Setup

Create a local PostgreSQL database:

```bash
createdb breathe_clean
```

Copy the example environment file:

```bash
cp .envexample .env
```

Update `DATABASE_URL` in `.env` with your PostgreSQL username and password:

```env
DATABASE_URL=postgresql+psycopg://username:password@localhost/breathe_clean
```

Apply all database migrations:

```bash
cd backend
alembic upgrade head
cd ..
```

If you created `sensor_readings` with the earlier manual setup command, record the initial migration as already applied instead of trying to create the table again:

```bash
cd backend
alembic stamp head
cd ..
```

Only use `alembic stamp head` when the existing table already matches the current SQLAlchemy model.

When the SQLAlchemy models change, create and review a new migration before applying it:

```bash
cd backend
alembic revision --autogenerate -m "describe the schema change"
alembic upgrade head
```

## Running the Project

From the repository root, start the FastAPI development server:

```bash
cd backend
uvicorn main:app --reload
```

The API is available at `http://127.0.0.1:8000`, and its interactive documentation is available at `http://127.0.0.1:8000/docs`.

With the API still running, open another terminal in the repository root, activate the virtual environment, and send a mock sensor reading:

```bash
source .venv/bin/activate
python backend/mock_sensor.py
```

Retrieve the stored readings with:

```bash
curl http://127.0.0.1:8000/readings
```

## API

**POST /readings** - Stores a new PM2.5 reading

```json
{
    "pm25": 20.5
}
```

**GET /readings** - Retrieves all stored PM2.5 readings

```json
[
    {
        "id": 48293482938423,
        "pm25": 20.5,
        "created_at": "2026-08-14T04:30:12.123456Z"
    }
]
```

## Goal

The long-term goal for Breathe Clean is to collect air-quality measurements, determine when the air quality requires intervention, and provide effective intervention by controlling one or many nearby air purifiers. I am currently completing research about the most effective way to time this intervention in order to achieve a sustainably breathable home environment.
