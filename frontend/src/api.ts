export type Sensor = { id: string; room_id: string }

export type Purifier = {
  id: string
  room_id: string
  is_on: boolean
  desired_is_on: boolean
  pending_command_id: string | null
}

export type Room = {
  id: string
  name: string
  sensor: Sensor
  purifier: Purifier
}

export type SensorReading = {
  id: string
  pm25: number
  created_at: string
  sensor_id: string
  source_message_id: string | null
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { signal })
  if (!response.ok) throw new Error(`Request failed with status ${response.status}`)
  return response.json() as Promise<T>
}

export const getRooms = (signal?: AbortSignal) => getJson<Room[]>('/rooms', signal)
export const getRoom = (roomId: string, signal?: AbortSignal) =>
  getJson<Room>(`/rooms/${roomId}`, signal)
export const getRoomReadings = (roomId: string, signal?: AbortSignal) =>
  getJson<SensorReading[]>(`/rooms/${roomId}/readings`, signal)
export const getReadings = (signal?: AbortSignal) =>
  getJson<SensorReading[]>('/readings', signal)
