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

## API
**POST /readings** - Stores a new PM2.5 reading

```text
{
    "pm25": 20.5
}
```

Goal:

The long-term goal for Breathe Clean is to collect air-quality measurements, determine when the air quality requires intervention, and provide effective intervention by controlling one or many nearby air purifiers. I am currently completing research about the most effective way to time this intervention in order to achieve a sustainably breathable home environment.
