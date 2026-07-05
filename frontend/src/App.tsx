import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Sparkles, Download, Scissors, AlertCircle,
  Cpu, Clock, Zap, Play, CheckCircle2,
  Circle, Loader2, XCircle, Activity, Video, Sun, Moon
} from 'lucide-react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api'

// ─── Types ──────────────────────────────────────────────────────────────────

interface PipelineStage {
  key: string
  label: string
  icon: string
}

interface ProgressEvent {
  stage: string
  detail: string
  timestamp: number
  current_step: number
  total_steps: number
  elapsed_seconds: number
  eta_seconds: number | null
  progress_percent: number
}

interface SystemStats {
  cpu_percent: number
  cpu_count: number
  process_cpu_percent: number
  process_ram_gb: number
  ram_percent: number
  ram_used_gb: number
  ram_total_gb: number
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
  disk_free_gb: number
}

interface ClipResult {
  clip_index: number
  viral_clip: {
    start: number
    end: number
    title: string
    hook_description: string
    virality_score: number
    reasoning: string
    duration: number
  }
  clip_file_path: string
  subtitled_file_path: string
}

interface JobResults {
  status: string
  result: {
    clip_results: ClipResult[]
    video_metadata: {
      title: string
      channel: string
      duration_seconds: number
    }
    viral_clips_detected: any[]
  } | null
  error: string | null
  current_stage: string | null
  current_step: number
  total_steps: number
  elapsed_seconds: number
  stage_times: Record<string, { start: number; end: number | null }>
  stages: PipelineStage[]
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function formatTime(seconds: number): string {
  if (seconds < 0 || !isFinite(seconds)) return '--:--'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

function getStageBadgeClass(stage: string): string {
  const map: Record<string, string> = {
    DOWNLOAD: 'badge-download',
    TRANSCRIBE: 'badge-transcribe',
    ANALYZE: 'badge-analyze',
    CLIP: 'badge-clip',
    SUBTITLE: 'badge-subtitle',
    DONE: 'badge-done',
    ERROR: 'badge-error',
  }
  return map[stage] || ''
}

function getStageEmoji(key: string): string {
  const map: Record<string, string> = {
    DOWNLOAD: '⬇️',
    TRANSCRIBE: '🗣️',
    ANALYZE: '🤖',
    CLIP: '✂️',
    SUBTITLE: '🔤',
    DONE: '✅',
  }
  return map[key] || '▶️'
}

// ─── Components ─────────────────────────────────────────────────────────────

function ProgressRing({ percent }: { percent: number }) {
  const r = 34
  const circumference = 2 * Math.PI * r
  const offset = circumference - (percent / 100) * circumference

  return (
    <div className="progress-ring-container">
      <svg className="progress-ring" viewBox="0 0 80 80">
        <defs>
          <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#a78bfa" />
          </linearGradient>
        </defs>
        <circle className="progress-ring-bg" cx="40" cy="40" r={r} />
        <circle
          className="progress-ring-fill"
          cx="40" cy="40" r={r}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="progress-ring-label">{Math.round(percent)}%</div>
    </div>
  )
}

function getGaugeColorClass(value: number): string {
  if (value >= 85) return 'gauge-fill-high'
  if (value >= 50) return 'gauge-fill-med'
  return 'gauge-fill-low'
}

function HardwareGauges({ stats }: { stats: SystemStats | null }) {
  if (!stats) {
    return (
      <div className="gauge-stack">
        <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', textAlign: 'center', padding: '1rem 0' }}>
          Connecting...
        </div>
      </div>
    )
  }

  const gauges = [
    { label: 'System CPU', value: stats.cpu_percent || 0, detail: `${stats.cpu_count || 0} cores`, cls: getGaugeColorClass(stats.cpu_percent || 0) },
    { label: 'App CPU', value: stats.process_cpu_percent || 0, detail: `Current process`, cls: getGaugeColorClass(stats.process_cpu_percent || 0) },
    { label: 'System RAM', value: stats.ram_percent || 0, detail: `${stats.ram_used_gb || 0} / ${stats.ram_total_gb || 1} GB`, cls: getGaugeColorClass(stats.ram_percent || 0) },
    { label: 'App RAM', value: ((stats.process_ram_gb || 0) / (stats.ram_total_gb || 1)) * 100 || 1, detail: `${stats.process_ram_gb || 0} GB used`, cls: getGaugeColorClass(((stats.process_ram_gb || 0) / (stats.ram_total_gb || 1)) * 100) },
    { label: 'Disk Space', value: stats.disk_percent || 0, detail: `${stats.disk_free_gb || 0} GB free`, cls: getGaugeColorClass(stats.disk_percent || 0) },
  ]

  return (
    <div className="gauge-stack">
      {gauges.map((g) => (
        <div key={g.label} className="gauge-item">
          <div className="gauge-header">
            <span className="gauge-label">{g.label}</span>
            <span className="gauge-value">{g.value.toFixed(1)}%</span>
          </div>
          <div className="gauge-bar">
            <div className={`gauge-fill ${g.cls}`} style={{ width: `${Math.min(g.value, 100)}%` }} />
          </div>
          <span className="gauge-detail">{g.detail}</span>
        </div>
      ))}
    </div>
  )
}

function PipelineSteps({
  stages,
  currentStep,
  currentStage,
  stageTimes,
  status,
}: {
  stages: PipelineStage[]
  currentStep: number
  currentStage: string | null
  stageTimes: Record<string, { start: number; end: number | null }>
  status: string
}) {
  return (
    <div className="pipeline-steps stagger-children">
      {stages.map((stage, i) => {
        const stepNum = i + 1
        let state = 'step-pending'
        if (status === 'error' && currentStage === stage.key) {
          state = 'step-error'
        } else if (stepNum < currentStep || (status === 'completed' && stage.key === 'DONE')) {
          state = 'step-completed'
        } else if (stepNum === currentStep) {
          state = 'step-active'
        }

        // Calculate elapsed time for this stage
        const timing = stageTimes[stage.key]
        let stageElapsed = ''
        if (timing) {
          let end = timing.end
          if (!end) {
             // If this is the DONE stage, it doesn't take time.
             if (stage.key === 'DONE') {
                 end = timing.start
             } else {
                 end = Date.now() / 1000
             }
          }
          const elapsed = end - timing.start
          if (elapsed > 0 || stage.key !== 'DONE') {
             stageElapsed = formatDuration(elapsed)
          }
        }

        return (
          <div key={stage.key} className={`step-row ${state}`}>
            <div className="step-indicator">
              {state === 'step-completed' ? (
                <CheckCircle2 size={16} />
              ) : state === 'step-active' ? (
                <Loader2 size={16} className="spinner" />
              ) : state === 'step-error' ? (
                <XCircle size={16} />
              ) : (
                <Circle size={14} />
              )}
            </div>
            <span className="step-label">
              {getStageEmoji(stage.key)} {stage.label}
            </span>
            {stageElapsed && (
              <span className="step-time">{stageElapsed}</span>
            )}
          </div>
        )
      })}
    </div>
  )
}

function EventLog({ events }: { events: ProgressEvent[] }) {
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [events])

  if (events.length === 0) {
    return (
      <div className="event-log" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem' }}>
        Waiting for events...
      </div>
    )
  }

  return (
    <div className="event-log" ref={logRef}>
      {events.map((ev, i) => (
        <div key={i} className="event-row">
          <span className="event-time">{formatTime(ev.elapsed_seconds)}</span>
          <span className={`event-stage-badge ${getStageBadgeClass(ev.stage)}`}>
            {ev.stage}
          </span>
          <span className="event-text">{ev.detail}</span>
        </div>
      ))}
    </div>
  )
}

// ─── Main App ───────────────────────────────────────────────────────────────

function App() {
  // Theme state
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('clipforge-theme') as 'dark' | 'light') || 'dark'
    }
    return 'dark'
  })

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('clipforge-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))

  // Form state
  const [url, setUrl] = useState('')
  const [numClips, setNumClips] = useState(3)
  const [cropVertical, setCropVertical] = useState(true)

  // Job state
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<'idle' | 'processing' | 'completed' | 'error'>('idle')
  const [events, setEvents] = useState<ProgressEvent[]>([])
  const [errorMsg, setErrorMsg] = useState('')

  // Progress state
  const [currentStep, setCurrentStep] = useState(0)
  const [totalSteps, setTotalSteps] = useState(6)
  const [currentStage, setCurrentStage] = useState<string | null>(null)
  const [progressPercent, setProgressPercent] = useState(0)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [etaSeconds, setEtaSeconds] = useState<number | null>(null)
  const [stageTimes, setStageTimes] = useState<Record<string, { start: number; end: number | null }>>({})

  // Results
  const [clips, setClips] = useState<ClipResult[]>([])
  const [videoTitle, setVideoTitle] = useState('')
  const [totalElapsed, setTotalElapsed] = useState(0)

  // System stats
  const [systemStats, setSystemStats] = useState<SystemStats | null>(null)

  // Pipeline stages definition
  const [stages, setStages] = useState<PipelineStage[]>([
    { key: 'DOWNLOAD', label: 'Download Video', icon: '⬇️' },
    { key: 'TRANSCRIBE', label: 'Transcribe Audio', icon: '🗣️' },
    { key: 'ANALYZE', label: 'AI Viral Detection', icon: '🤖' },
    { key: 'CLIP', label: 'Extract Clips', icon: '✂️' },
    { key: 'SUBTITLE', label: 'Burn Subtitles', icon: '🔤' },
    { key: 'DONE', label: 'Complete', icon: '✅' },
  ])

  // Fetch true pipeline stages from backend on mount
  useEffect(() => {
    const fetchStages = async () => {
      try {
        const res = await fetch(`${API_BASE}/pipeline-stages`)
        if (res.ok) {
          const data = await res.json()
          if (data.stages) setStages(data.stages)
        }
      } catch (e) {
        // Silently use defaults if offline
      }
    }
    fetchStages()
  }, [])

  // ── System Stats Polling ────────────────────────────────────────────────
  useEffect(() => {
    let interval: ReturnType<typeof setInterval>

    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/system-stats`)
        if (res.ok) {
          setSystemStats(await res.json())
        }
      } catch {
        // Silently ignore — server may not be up yet
      }
    }

    fetchStats()
    // Poll faster during processing
    const pollInterval = status === 'processing' ? 2000 : 5000
    interval = setInterval(fetchStats, pollInterval)

    return () => clearInterval(interval)
  }, [status])

  // ── Elapsed Time Counter ────────────────────────────────────────────────
  const startTimeRef = useRef<number | null>(null)

  useEffect(() => {
    if (status !== 'processing') return

    if (!startTimeRef.current) {
      startTimeRef.current = Date.now()
    }

    const interval = setInterval(() => {
      if (startTimeRef.current) {
        setElapsedSeconds((Date.now() - startTimeRef.current) / 1000)
      }
    }, 1000)

    return () => clearInterval(interval)
  }, [status])

  // ── SSE Connection ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!jobId || status !== 'processing') return

    const sse = new EventSource(`${API_BASE}/status/${jobId}`)

    sse.onmessage = (e) => {
      const data: ProgressEvent = JSON.parse(e.data)

      if (data.stage === 'EOF') {
        sse.close()
        fetchResults(jobId)
      } else if (data.stage === 'ERROR') {
        setStatus('error')
        setErrorMsg(data.detail)
        sse.close()
      } else {
        setEvents((prev) => [...prev, data])
        setCurrentStep(data.current_step)
        setTotalSteps(data.total_steps)
        setProgressPercent(data.progress_percent)
        if (data.eta_seconds !== null) {
          setEtaSeconds(data.eta_seconds)
        }
        if (data.stage) {
          setCurrentStage(data.stage)
        }
      }
    }

    sse.onerror = () => {
      sse.close()
    }

    return () => sse.close()
  }, [jobId, status])

  // ── Fetch Results ───────────────────────────────────────────────────────
  const fetchResults = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/results/${id}`)
      const data: JobResults = await res.json()

      if (data.stages) {
        setStages(data.stages)
      }
      if (data.stage_times) {
        setStageTimes(data.stage_times)
      }
      setTotalElapsed(data.elapsed_seconds)

      if (data.status === 'completed' && data.result) {
        setStatus('completed')
        setProgressPercent(100)
        setCurrentStep(data.total_steps)
        const validClips = data.result.clip_results.filter(
          (c) => c.subtitled_file_path || c.clip_file_path
        )
        setClips(validClips)
        if (data.result.video_metadata) {
          setVideoTitle(data.result.video_metadata.title)
        }
      } else if (data.status === 'error') {
        setStatus('error')
        setErrorMsg(data.error || 'Unknown error')
      }
    } catch (err) {
      console.error('Failed to fetch results:', err)
    }
  }, [])

  // ── Submit ──────────────────────────────────────────────────────────────
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url) return

    // Reset all state
    setJobId(null)
    setEvents([])
    setClips([])
    setErrorMsg('')
    setCurrentStep(0)
    setCurrentStage(null)
    setProgressPercent(0)
    setElapsedSeconds(0)
    setEtaSeconds(null)
    setStageTimes({})
    setVideoTitle('')
    startTimeRef.current = null
    setStatus('processing')

    try {
      const res = await fetch(`${API_BASE}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url,
          num_clips: numClips,
          crop_vertical: cropVertical,
          subtitle_style: 'tiktok',
          highlight_words: true,
        }),
      })

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || 'Failed to start job')
      }
      const data = await res.json()
      setJobId(data.job_id)
    } catch (err: any) {
      setStatus('error')
      setErrorMsg(err.message || 'Network error — is the backend running?')
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────
  const isProcessing = status === 'processing'
  const showDashboard = isProcessing || status === 'completed' || status === 'error'

  return (
    <div className="app-container">
      {/* ── Theme Toggle ─────────────────────────────────── */}
      <button
        className="theme-toggle-btn"
        onClick={toggleTheme}
        aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
        title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      >
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </button>

      {/* ── Header ──────────────────────────────────────── */}
      <header className="app-header animate-fade-in">
        <h1>⚡ ClipForge</h1>
        <p className="tagline">
          AI-powered viral clip extraction — turn long videos into perfectly edited Shorts.
        </p>
      </header>

      {/* ── Form ────────────────────────────────────────── */}
      <div className="form-section animate-fade-in">
        <form onSubmit={handleSubmit} className="glass glass-panel">
          <div className="input-group">
            <label htmlFor="yt-url">YouTube URL</label>
            <input
              id="yt-url"
              type="url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              required
              disabled={isProcessing}
            />
          </div>

          <div className="options-row">
            <div className="input-group">
              <label htmlFor="num-clips">Clips to Extract</label>
              <select
                id="num-clips"
                value={numClips}
                onChange={(e) => setNumClips(parseInt(e.target.value))}
                disabled={isProcessing}
              >
                <option value={1}>1 Clip</option>
                <option value={3}>3 Clips</option>
                <option value={5}>5 Clips</option>
                <option value={10}>10 Clips</option>
              </select>
            </div>

            <div className="input-group" style={{ justifyContent: 'flex-end' }}>
              <label className="toggle-wrapper">
                <input
                  type="checkbox"
                  checked={cropVertical}
                  onChange={(e) => setCropVertical(e.target.checked)}
                  disabled={isProcessing}
                />
                <span className="toggle-label">9:16 Vertical Crop</span>
              </label>
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={isProcessing || !url}>
            {isProcessing ? (
              <><Loader2 size={18} className="spinner" /> Processing...</>
            ) : (
              <><Sparkles size={18} /> Generate Viral Clips</>
            )}
          </button>
        </form>
      </div>

      {/* ── Error Banner ────────────────────────────────── */}
      {status === 'error' && (
        <div className="error-banner animate-fade-in">
          <AlertCircle size={20} className="error-icon" />
          <div className="error-content">
            <h3>Pipeline Failed</h3>
            <p>{errorMsg}</p>
          </div>
        </div>
      )}

      {/* ── Dashboard ───────────────────────────────────── */}
      {showDashboard && (
        <div className="dashboard animate-fade-in-up">
          {/* Main Column */}
          <div className="dashboard-main">
            {/* Progress Overview */}
            <div className="section-card">
              <div className="progress-overview">
                <ProgressRing percent={progressPercent} />
                <div className="progress-details">
                  <div className="progress-detail-row">
                    <span className="progress-detail-label">
                      <Clock size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      Elapsed
                    </span>
                    <span className="progress-detail-value">
                      {formatDuration(status === 'completed' ? totalElapsed : elapsedSeconds)}
                    </span>
                  </div>
                  <div className="progress-detail-row">
                    <span className="progress-detail-label">
                      <Zap size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      ETA
                    </span>
                    <span className="progress-detail-value">
                      {status === 'completed'
                        ? 'Done!'
                        : etaSeconds !== null
                        ? `~${formatDuration(etaSeconds)}`
                        : 'Calculating...'}
                    </span>
                  </div>
                  <div className="progress-detail-row">
                    <span className="progress-detail-label">
                      <Activity size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                      Stage
                    </span>
                    <span className="progress-detail-value">
                      {currentStep}/{totalSteps}
                      {currentStage && ` · ${currentStage}`}
                    </span>
                  </div>
                  {videoTitle && (
                    <div className="progress-detail-row">
                      <span className="progress-detail-label">
                        <Video size={13} style={{ verticalAlign: 'middle', marginRight: 4 }} />
                        Video
                      </span>
                      <span className="progress-detail-value" style={{ fontSize: '0.72rem', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {videoTitle}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Event Log */}
            <div className="section-card">
              <div className="section-header">
                <span className="section-title">
                  <Activity size={14} /> Live Event Log
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  {events.length} events
                </span>
              </div>
              <EventLog events={events} />
            </div>
          </div>

          {/* Sidebar */}
          <div className="dashboard-sidebar">
            {/* Pipeline Steps */}
            <div className="section-card">
              <div className="section-header">
                <span className="section-title">
                  <Play size={14} /> Pipeline Steps
                </span>
              </div>
              <div className="section-body">
                <PipelineSteps
                  stages={stages}
                  currentStep={currentStep}
                  currentStage={currentStage}
                  stageTimes={stageTimes}
                  status={status}
                />
              </div>
            </div>

            {/* Hardware */}
            <div className="section-card">
              <div className="section-header">
                <span className="section-title">
                  <Cpu size={14} /> System Resources
                </span>
              </div>
              <div className="section-body">
                <HardwareGauges stats={systemStats} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Results Gallery ─────────────────────────────── */}
      {status === 'completed' && clips.length > 0 && (
        <div className="results-section animate-fade-in-up">
          <div className="results-header">
            <h2><Scissors size={22} /> Extracted Clips</h2>
            <div className="results-summary">
              <span className="stat">
                <Video size={14} /> {clips.length} clips
              </span>
              <span className="stat">
                <Clock size={14} /> {formatDuration(totalElapsed)}
              </span>
            </div>
          </div>

          <div className="clip-grid stagger-children">
            {clips.map((clip) => {
              const filePath = clip.subtitled_file_path || clip.clip_file_path
              const filename = filePath.split('/').pop()
              const videoUrl = `http://localhost:8000/media/${filename}`
              const duration = clip.viral_clip.duration || (clip.viral_clip.end - clip.viral_clip.start)

              return (
                <div key={clip.clip_index} className="clip-card">
                  <div className="clip-video-wrapper">
                    <video
                      className="clip-video"
                      controls
                      preload="metadata"
                      src={videoUrl}
                    />
                    <div className="clip-overlay">
                      <span className="clip-badge badge-score">
                        ⭐ {clip.viral_clip.virality_score.toFixed(1)}
                      </span>
                      <span className="clip-badge badge-duration">
                        {Math.round(duration)}s
                      </span>
                    </div>
                  </div>
                  <div className="clip-info">
                    <h3 className="clip-title">{clip.viral_clip.title}</h3>
                    <div className="clip-actions">
                      <a
                        href={videoUrl}
                        download
                        target="_blank"
                        rel="noreferrer"
                        style={{ textDecoration: 'none', flex: 1 }}
                      >
                        <button className="btn btn-primary btn-sm" style={{ width: '100%' }}>
                          <Download size={14} /> Download
                        </button>
                      </a>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Completed with no clips */}
      {status === 'completed' && clips.length === 0 && (
        <div className="empty-state animate-fade-in glass glass-panel" style={{ marginTop: '2rem', textAlign: 'center', borderColor: 'var(--warning)', boxShadow: '0 0 20px var(--warning-bg)' }}>
          <div className="empty-state-icon" style={{ fontSize: '4rem', marginBottom: '1rem' }}>🎵</div>
          <h2 style={{ color: 'var(--warning)', marginBottom: '0.5rem' }}>No Viral Hooks Found</h2>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto', fontSize: '1.1rem' }}>
            The AI could not identify any suitable spoken-word viral hooks in this video. 
            <strong> Is this a music video or heavily edited song?</strong> 
            <br/><br/>
            The detection prompt is strictly optimized for podcasts, speeches, and dialogue (looking for controversial takes, cliffhangers, and actionable advice). Music videos often yield 0 clips because the lyrics do not match these patterns.
          </p>
        </div>
      )}
    </div>
  )
}

export default App
