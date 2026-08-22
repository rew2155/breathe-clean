import { useEffect, useMemo, useState } from 'react'
import { Link, Route, Routes, useParams } from 'react-router-dom'
import {
  getReadings,
  getRoom,
  getRoomReadings,
  getRooms,
  type Room,
  type SensorReading,
} from './api'
import './App.css'

type DashboardData = { rooms: Room[]; readings: SensorReading[] }

function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const loadDashboard = () => {
      Promise.all([getRooms(controller.signal), getReadings(controller.signal)])
        .then(([rooms, readings]) => {
          setData({ rooms, readings })
          setError(null)
        })
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.name !== 'AbortError') {
            setError('The dashboard could not reach the Breathe Clean API.')
          }
        })
    }

    loadDashboard()
    const refreshTimer = window.setInterval(loadDashboard, 15_000)
    return () => {
      window.clearInterval(refreshTimer)
      controller.abort()
    }
  }, [])

  const latestReadings = useMemo(() => {
    const latest = new Map<string, SensorReading>()
    for (const reading of data?.readings ?? []) {
      const current = latest.get(reading.sensor_id)
      if (!current || reading.created_at > current.created_at) {
        latest.set(reading.sensor_id, reading)
      }
    }
    return latest
  }, [data?.readings])

  const purifierCount = data?.rooms.filter((room) => room.purifier.is_on).length ?? 0

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Breathe Clean home">
          <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
          <span>Breathe Clean</span>
        </a>
        <span className="system-status">
          <span className={`status-dot ${error ? 'status-error' : ''}`} />
          {error ? 'API unavailable' : data ? 'API connected' : 'Connecting…'}
        </span>
      </header>

      <main>
        <section className="intro">
          <div>
            <p className="eyebrow">Indoor air overview</p>
            <h1>A clearer view of the air at home.</h1>
            <p className="lede">Live room readings and automatic purifier activity, all in one place.</p>
          </div>
          <dl className="summary" aria-label="Home air summary">
            <div><dt>Rooms</dt><dd>{data?.rooms.length ?? '—'}</dd></div>
            <div><dt>Purifiers on</dt><dd>{data ? purifierCount : '—'}</dd></div>
            <div><dt>Recent readings</dt><dd>{data?.readings.length ?? '—'}</dd></div>
          </dl>
        </section>

        <section className="rooms-section" aria-labelledby="rooms-heading">
          <div className="section-heading">
            <div><p className="eyebrow">Your home</p><h2 id="rooms-heading">Room monitors</h2></div>
            <span className="updated-label">Updates automatically</span>
          </div>

          {error && <div className="notice error-notice">{error}</div>}
          {!data && !error && <div className="notice">Loading room conditions…</div>}
          {data?.rooms.length === 0 && (
            <div className="empty-state">
              <span className="empty-icon" aria-hidden="true">+</span>
              <h3>No rooms configured yet</h3>
              <p>Create your first room through the API to begin monitoring.</p>
            </div>
          )}

          <div className="room-grid">
            {data?.rooms.map((room) => (
              <Link className="room-card-link" to={`/rooms/${room.id}`} key={room.id}>
                <RoomCard room={room} reading={latestReadings.get(room.sensor.id)} />
              </Link>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}

function RoomCard({ room, reading }: { room: Room; reading?: SensorReading }) {
  const quality = getAirQuality(reading)
  const commandPending = room.purifier.pending_command_id !== null
  const isLegacyRoom = room.name === 'Legacy Room'

  return (
    <article className="room-card">
      <div className="card-topline">
        <div>
          <p className="room-label">{isLegacyRoom ? 'Imported data' : 'Room'}</p>
          <h3>{room.name}</h3>
        </div>
        <span className={`quality-badge quality-${quality.tone}`}>{quality.label}</span>
      </div>
      <div className="reading-block">
        <div className="reading-value"><strong>{reading ? reading.pm25.toFixed(1) : '—'}</strong><span>µg/m³</span></div>
        <p>PM2.5</p>
      </div>
      <div className="device-row">
        <div>
          <span className={`device-icon ${room.purifier.is_on ? 'device-on' : ''}`} aria-hidden="true">⏻</span>
          <div><p>Air purifier</p><strong>{room.purifier.is_on ? 'Running' : 'Off'}</strong></div>
        </div>
        <span className={commandPending ? 'pending' : 'confirmed'}>
          {commandPending ? 'Changing…' : 'Automatic'}
        </span>
      </div>
      <p className="reading-time">
        {reading ? `Last reading ${formatRelativeTime(reading.created_at)}` : 'Waiting for the first sensor reading'}
      </p>
    </article>
  )
}

function getAirQuality(reading?: SensorReading) {
  if (!reading) return { label: 'No data', tone: 'neutral' }
  const age = Date.now() - Date.parse(reading.created_at)
  if (age > 5 * 60 * 1000) return { label: 'Stale', tone: 'stale' }
  if (reading.pm25 <= 9) return { label: 'Good', tone: 'good' }
  if (reading.pm25 < 15) return { label: 'Moderate', tone: 'moderate' }
  return { label: 'Elevated', tone: 'elevated' }
}

function formatRelativeTime(value: string) {
  const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(value)) / 1000))
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} min ago`
  return `${Math.floor(minutes / 60)} hr ago`
}

function RoomHistoryPage() {
  const { roomId } = useParams()
  const [room, setRoom] = useState<Room | null>(null)
  const [readings, setReadings] = useState<SensorReading[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!roomId) return
    const controller = new AbortController()
    const loadRoom = () => {
      Promise.all([
        getRoom(roomId, controller.signal),
        getRoomReadings(roomId, controller.signal),
      ])
        .then(([roomResponse, readingResponse]) => {
          setRoom(roomResponse)
          setReadings(readingResponse)
          setError(null)
        })
        .catch((requestError: unknown) => {
          if (requestError instanceof Error && requestError.name !== 'AbortError') {
            setError('This room’s history could not be loaded.')
          }
        })
    }
    loadRoom()
    const refreshTimer = window.setInterval(loadRoom, 15_000)
    return () => {
      window.clearInterval(refreshTimer)
      controller.abort()
    }
  }, [roomId])

  const chronologicalReadings = useMemo(
    () => [...readings].reverse(),
    [readings],
  )
  const latest = readings[0]

  return (
    <div className="app-shell">
      <Topbar error={error !== null} connected={room !== null} />
      <main className="history-main">
        <Link className="back-link" to="/">← All rooms</Link>
        {error && <div className="notice error-notice">{error}</div>}
        {!room && !error && <div className="notice">Loading room history…</div>}
        {room && (
          <>
            <section className="history-heading">
              <div>
                <p className="eyebrow">Room history</p>
                <h1>{room.name}</h1>
                <p className="lede">PM2.5 readings collected by this room’s sensor.</p>
              </div>
              <div className="history-current">
                <span>Current</span>
                <strong>{latest ? latest.pm25.toFixed(1) : '—'}</strong>
                <small>µg/m³</small>
              </div>
            </section>
            <section className="history-panel">
              <div className="section-heading">
                <div><p className="eyebrow">PM2.5 trend</p><h2>Reading history</h2></div>
                <span className="updated-label">{readings.length} readings</span>
              </div>
              {readings.length === 0 ? (
                <div className="notice">Waiting for the first sensor reading…</div>
              ) : (
                <>
                  <ReadingChart readings={chronologicalReadings} />
                  <div className="reading-list">
                    {readings.map((reading) => (
                      <div className="history-row" key={reading.id}>
                        <time dateTime={reading.created_at}>{formatTimestamp(reading.created_at)}</time>
                        <strong>{reading.pm25.toFixed(1)} <span>µg/m³</span></strong>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}

function ReadingChart({ readings }: { readings: SensorReading[] }) {
  const width = 900
  const height = 240
  const padding = 24
  const maximum = Math.max(25, ...readings.map((reading) => reading.pm25))
  const points = readings.map((reading, index) => {
    const x = readings.length === 1
      ? width / 2
      : padding + (index / (readings.length - 1)) * (width - padding * 2)
    const y = height - padding - (reading.pm25 / maximum) * (height - padding * 2)
    return { x, y, reading }
  })
  const path = points.map(({ x, y }) => `${x},${y}`).join(' ')

  return (
    <div className="chart-wrap">
      <svg className="history-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="PM2.5 reading trend">
        <line className="threshold-line" x1={padding} x2={width - padding} y1={height - padding - (15 / maximum) * (height - padding * 2)} y2={height - padding - (15 / maximum) * (height - padding * 2)} />
        <polyline points={path} />
        {points.map(({ x, y, reading }) => <circle key={reading.id} cx={x} cy={y} r="5"><title>{reading.pm25.toFixed(1)} µg/m³</title></circle>)}
      </svg>
      <div className="chart-legend"><span /> Automatic-on threshold: 15 µg/m³</div>
    </div>
  )
}

function Topbar({ error, connected }: { error: boolean; connected: boolean }) {
  return (
    <header className="topbar">
      <Link className="brand" to="/" aria-label="Breathe Clean home">
        <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
        <span>Breathe Clean</span>
      </Link>
      <span className="system-status">
        <span className={`status-dot ${error ? 'status-error' : ''}`} />
        {error ? 'API unavailable' : connected ? 'API connected' : 'Connecting…'}
      </span>
    </header>
  )
}

function formatTimestamp(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/rooms/:roomId" element={<RoomHistoryPage />} />
    </Routes>
  )
}

export default App
