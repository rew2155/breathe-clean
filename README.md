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
- Eclipse Mosquitto for local MQTT development

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
SENSOR_ID=<configured-sensor-id> python backend/mock_sensor.py
```

Retrieve the stored readings with:

```bash
curl http://127.0.0.1:8000/readings
```

Run the backend unit tests with:

```bash
cd backend
python -m unittest discover -s tests
```

## Air-Quality Policy

The initial purifier policy uses separate thresholds to avoid rapid on/off cycling:

- When off, the purifier turns on at an average PM2.5 reading of `15 µg/m³` or higher.
- When on, the purifier turns off at an average PM2.5 reading of `8 µg/m³` or lower.
- Between those thresholds, the purifier keeps its current state.
- The average uses readings from the previous five minutes.
- At least three recent readings are required before changing state.
- Too few readings preserve the current purifier state.
- A sensor with historical readings but none in the window is reported as stale.

This policy is an initial engineering rule and does not represent regulatory compliance. The thresholds and averaging window will be tuned using real sensor data.

## Purifier Control

The backend currently uses a simulated purifier adapter. When an air-quality evaluation is ready and its desired state differs from the purifier's requested state, the adapter records an on/off command. Repeated readings do not issue duplicate commands when the purifier already has that requested state.

Purifiers track two states:

- `desired_is_on` records the state requested by the backend.
- `is_on` records the state confirmed by the device.
- `pending_command_id` links an outstanding MQTT command to its acknowledgment.

The simulator confirms commands immediately, so it updates both state values. The MQTT adapter publishes a command, records it as pending, and leaves `is_on` unchanged. A matching state message confirms the command and updates `is_on`; acknowledgments for older commands are ignored.

A failed purifier command returns `503 Service Unavailable`, leaves the purifier state unchanged, and rolls back the reading being processed.

## MQTT Protocol

Device messages use versioned MQTT topics so the protocol can evolve without silently breaking existing clients:

```text
breathe-clean/v1/sensors/{sensor_id}/readings
breathe-clean/v1/purifiers/{purifier_id}/commands
breathe-clean/v1/purifiers/{purifier_id}/state
```

Every JSON message includes a UUID message identifier, a device identifier, and a timezone-aware timestamp. Purifier state messages also reference the command they acknowledge.

Sensor message IDs are stored with their readings and uniquely constrained. If a QoS 1 message is delivered again, the consumer recognizes it as already processed instead of storing another reading or repeating a purifier command.

The backend MQTT transport defaults to a local broker. These values can be changed in `.env`:

```env
MQTT_HOST=localhost
MQTT_PORT=1883
MQTT_CLIENT_ID=breathe-clean-backend
MQTT_ENABLED=false
```

Start an installed Mosquitto broker for local development with:

```bash
mosquitto -v
```

Set `MQTT_ENABLED=true` after the broker is running. When enabled, FastAPI connects during application startup, consumes sensor readings and purifier acknowledgments, and publishes purifier commands. When disabled, the REST API continues to use the simulated purifier adapter and does not require a broker.

MQTT publishes use quality of service level 1 and wait for broker acknowledgment. Subscriptions are renewed whenever the transport reconnects.

## API

**POST /rooms** - Creates a room with one sensor and one purifier

```json
{
    "name": "Master Bedroom"
}
```

**GET /rooms** - Retrieves rooms and their configured devices

```json
[
    {
        "id": 123,
        "name": "Master Bedroom",
        "sensor": {
            "id": 456,
            "room_id": 123
        },
        "purifier": {
            "id": 789,
            "room_id": 123,
            "is_on": false,
            "desired_is_on": false,
            "pending_command_id": null
        }
    }
]
```

**POST /readings** - Stores a new PM2.5 reading

```json
{
    "pm25": 20.5,
    "sensor_id": 456
}
```

The response includes the stored reading and the current policy evaluation:

```json
{
    "reading": {
        "id": 48293482938423,
        "pm25": 20.5,
        "created_at": "2026-08-14T04:30:12.123456Z",
        "sensor_id": 456,
        "source_message_id": null
    },
    "evaluation": {
        "status": "ready",
        "desired_purifier_state": true,
        "reading_count": 3,
        "average_pm25": 18.2
    }
}
```

**GET /readings** - Retrieves all stored PM2.5 readings

```json
[
    {
        "id": 48293482938423,
        "pm25": 20.5,
        "created_at": "2026-08-14T04:30:12.123456Z",
        "sensor_id": 456,
        "source_message_id": null
    }
]
```

## Goal

The long-term goal for Breathe Clean is to collect air-quality measurements, determine when the air quality requires intervention, and provide effective intervention by controlling one or many nearby air purifiers. I am currently completing research about the most effective way to time this intervention in order to achieve a sustainably breathable home environment.
