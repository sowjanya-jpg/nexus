import { useState, useEffect } from 'react'
import { 
  Sparkles, 
  Play, 
  Check, 
  X, 
  ShieldAlert, 
  Cpu, 
  MessageSquare,
  RefreshCw,
  Send,
  AlertTriangle,
  BookOpen,
  LayoutDashboard,
  Award,
  Terminal,
  FileText,
  UserCheck,
  Activity,
  GitBranch,
  Globe
} from 'lucide-react'

interface Approval {
  id: number
  agent: string
  action: string
  reasoning: string
  status: string
  created_at: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface Lesson {
  id: string
  title: string
  role: string
  level: string
  description: string
  exercise: string
  options: string[]
  points: number
}

interface TelemetryMetric {
  timestamp: number
  metric: string
  value: number
  tags: Record<string, string>
}

function App() {
  // Tabs State
  const [activeTab, setActiveTab] = useState<'dashboard' | 'literacy'>('dashboard')

  // Stated Goals
  const [statedGoal, setStatedGoal] = useState('Optimize transformer maintenance in western plants')
  const [narrative, setNarrative] = useState('')
  const [isLoading, setIsLoading] = useState(false)

  // Live KPI States (dynamically updated!)
  const [kpiRevenue, setKpiRevenue] = useState(2.4) // Millions
  const [kpiUptime, setKpiUptime] = useState(94.3)  // Percent
  const [kpiTrust, setKpiTrust] = useState(87.0)    // Score
  const [kpiUptimeTrend, setKpiUptimeTrend] = useState('-1.1%')

  // Simulation State
  const [selectedScenario, setSelectedScenario] = useState('transformer_maintenance')
  const [interventionMagnitude, setInterventionMagnitude] = useState(1.0)
  const [simulationResult, setSimulationResult] = useState<any>(null)
  const [recommendationResult, setRecommendationResult] = useState<any>(null)

  // Approvals & Governance State
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [scanResult, setScanResult] = useState<any>(null)
  const [isScanning, setIsScanning] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')

  // Chat & Copilot State
  const [chatInput, setChatInput] = useState('')
  const [chatHistory, setChatHistory] = useState<Message[]>([
    { role: 'assistant', content: 'Welcome to the DataNexus AI workspace. Ask me anything about your data fabric, lineage, or simulation results.' }
  ])

  // Literacy Hub State
  const [userRole, setUserRole] = useState<'Analyst' | 'Engineer'>('Analyst')
  const [literacyScore, setLiteracyScore] = useState(100)
  const [lessons, setLessons] = useState<Lesson[]>([])
  const [selectedLessonAnswer, setSelectedLessonAnswer] = useState<Record<string, string>>({})
  const [lessonFeedback, setLessonFeedback] = useState<Record<string, any>>({})
  const [sandboxData, setSandboxData] = useState<any[]>([])

  // Telemetry & Novelty State
  const [telemetry, setTelemetry] = useState<TelemetryMetric[]>([])
  const [crossSimResult, setCrossSimResult] = useState<any>(null)
  const [isSimulatingCross, setIsSimulatingCross] = useState(false)
  const [syncStatus, setSyncStatus] = useState('')

  const backendUrl = 'http://localhost:8000'

  const handleSyncFabric = async () => {
    setSyncStatus('Syncing...')
    try {
      await Promise.all([
        fetchApprovals(),
        fetchLearningPath(),
        fetchSandboxData(),
        fetchTelemetry()
      ])
      setSyncStatus('Synchronized!')
      setTimeout(() => setSyncStatus(''), 2000)
    } catch (e) {
      setSyncStatus('Error!')
      setTimeout(() => setSyncStatus(''), 2000)
    }
  }

  // Load Dashboard data on Start
  useEffect(() => {
    handleGenerateDashboard()
    fetchApprovals()
    fetchLearningPath()
    fetchSandboxData()
    fetchTelemetry()
  }, [userRole])

  const handleGenerateDashboard = async (customGoal?: string) => {
    const goalToUse = customGoal || statedGoal
    setIsLoading(true)
    try {
      const res = await fetch(`${backendUrl}/api/v1/dashboard/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal: goalToUse })
      })
      const data = await res.json()
      if (data.status === 'success') {
        const narrRes = await fetch(`${backendUrl}/api/v1/dashboard/narrative`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ config: data.config })
        })
        const narrData = await narrRes.json()
        if (narrData.status === 'success') {
          setNarrative(narrData.narrative)
        }
      }
    } catch (e) {
      console.error('Error generating dashboard:', e)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSimulate = async () => {
    const startTime = performance.now()
    try {
      const res = await fetch(`${backendUrl}/api/v1/decision/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario: selectedScenario,
          interventions: [{ event: selectedScenario, magnitude: interventionMagnitude }]
        })
      })
      const data = await res.json()
      if (data.status === 'success') {
        setSimulationResult(data.simulation)
        
        // Dynamically alter KPIs based on the simulation outcome!
        const outcomes = data.simulation.ranked_outcomes
        outcomes.forEach((out: any) => {
          const changeVal = parseFloat(out.predicted_change)
          if (out.affected_metric === 'production_uptime') {
            setKpiUptime(Math.min(100.0, Math.round((94.3 + changeVal) * 10) / 10))
            setKpiUptimeTrend(`+${changeVal}%`)
          } else if (out.affected_metric === 'revenue') {
            setKpiRevenue(Math.round((2.4 + (changeVal / 10)) * 10) / 10)
          }
        })
      }

      const recRes = await fetch(`${backendUrl}/api/v1/decision/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: selectedScenario })
      })
      const recData = await recRes.json()
      if (recData.status === 'success') {
        setRecommendationResult(recData.recommendation)
      }
      
      // Log telemetry for simulation request
      const endTime = performance.now()
      const latencyVal = Math.round(endTime - startTime)
      await fetch(`${backendUrl}/api/v1/metrics`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'simulation_run_latency_ms', value: latencyVal, tags: { scenario: selectedScenario } })
      })
      fetchTelemetry()
    } catch (e) {
      console.error('Error simulating decision:', e)
    }
  }

  const fetchApprovals = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/v1/agents/approvals`)
      const data = await res.json()
      setApprovals(data)
    } catch (e) {
      console.error('Error fetching approvals:', e)
    }
  }

  const handleResolveApproval = async (id: number, decision: 'approved' | 'rejected') => {
    try {
      const res = await fetch(`${backendUrl}/api/v1/agents/approvals/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, feedback: feedbackText })
      })
      const data = await res.json()
      if (data.status === 'success') {
        fetchApprovals()
        setFeedbackText('')
        
        // Trigger self-improving feedback loop to adjust table trust scores
        const loopRes = await fetch(`${backendUrl}/api/v1/novelty/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ table_name: 'clean_sensor_logs', status: decision, current_trust: kpiTrust })
        })
        const loopData = await loopRes.json()
        if (loopData.status === 'success') {
          // Live-update the trust score KPI card!
          setKpiTrust(loopData.new_trust_score)
        }
      }
    } catch (e) {
      console.error('Error resolving approval:', e)
    }
  }

  const handleRunGovernanceScan = async () => {
    setIsScanning(true)
    try {
      const res = await fetch(`${backendUrl}/api/v1/governance/scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          table_name: 'raw_manufacturing_logs',
          sample_data: [
            { id: 1, name: 'John Doe', email: 'john.doe@example.com', ssn: '123-45-6789' },
            { id: 2, name: 'Jane Smith', email: 'jane.smith@example.com', ssn: '987-65-4321' }
          ]
        })
      })
      const data = await res.json()
      if (data.status === 'success') {
        setScanResult(data.data)
        fetchApprovals()
      }
    } catch (e) {
      console.error('Error scanning governance:', e)
    } finally {
      setIsScanning(false)
    }
  }

  const handleSendChat = async () => {
    if (!chatInput.trim()) return
    const userMsg = chatInput
    setChatHistory(prev => [...prev, { role: 'user', content: userMsg }])
    setChatInput('')

    try {
      const res = await fetch(`${backendUrl}/api/v1/agents/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      })
      const data = await res.json()
      if (data.status === 'success') {
        setChatHistory(prev => [...prev, { role: 'assistant', content: data.data.response }])
        fetchApprovals()
      }
    } catch (e) {
      console.error('Error sending chat:', e)
    }
  }

  // Copilot Actions
  const handleExplainSQL = async () => {
    setChatHistory(prev => [...prev, { role: 'user', content: 'Explain current active sales pipeline SQL query structure.' }])
    try {
      const res = await fetch(`${backendUrl}/api/v1/copilot/explain`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql_query: 'SELECT region, sum(revenue)...' })
      })
      const data = await res.json()
      if (data.status === 'success') {
        setChatHistory(prev => [...prev, { role: 'assistant', content: `Here is the explanation of the pipeline query:\n\n${data.explanation}` }])
      }
    } catch (e) {
      console.error('Error explaining SQL:', e)
    }
  }

  const handleExecuteQ2Summary = async () => {
    setChatHistory(prev => [...prev, { role: 'user', content: 'Generate and send Q2 board summary to stakeholders.' }])
    try {
      const res = await fetch(`${backendUrl}/api/v1/copilot/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_name: 'Generate and send Q2 Board Summary' })
      })
      const data = await res.json()
      if (data.status === 'success') {
        const payload = data.data
        if (payload.status === 'queued_for_approval') {
          setChatHistory(prev => [...prev, { 
            role: 'assistant', 
            content: `I've prepared the Q2 Board Summary, but since sending external reports is a high-risk activity, it has been gated behind human approval. (Approval Ticket #${payload.approval_id})` 
          }])
          fetchApprovals()
        } else {
          setChatHistory(prev => [...prev, { role: 'assistant', content: payload.message }])
        }
      }
    } catch (e) {
      console.error('Error executing task:', e)
    }
  }

  // Literacy Hub Functions
  const fetchLearningPath = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/v1/literacy/learning-path?role=${userRole}`)
      const data = await res.json()
      if (data.status === 'success') {
        setLessons(data.learning_path)
      }
    } catch (e) {
      console.error('Error fetching learning path:', e)
    }
  }

  const fetchSandboxData = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/v1/literacy/sandbox?sandbox_id=maintenance_sandbox`)
      const data = await res.json()
      if (data.status === 'success') {
        setSandboxData(data.dataset)
      }
    } catch (e) {
      console.error('Error fetching sandbox data:', e)
    }
  }

  const handleSelectOption = (lessonId: string, option: string) => {
    setSelectedLessonAnswer(prev => ({
      ...prev,
      [lessonId]: option
    }))
  }

  const handleSubmitLesson = async (lessonId: string) => {
    const answer = selectedLessonAnswer[lessonId]
    if (!answer) return
    try {
      const res = await fetch(`${backendUrl}/api/v1/literacy/exercise/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lesson_id: lessonId, answer })
      })
      const data = await res.json()
      if (data.status === 'success') {
        const result = data.result
        setLessonFeedback(prev => ({
          ...prev,
          [lessonId]: result
        }))
        if (result.correct) {
          setLiteracyScore(prev => prev + result.points_awarded)
        }
      }
    } catch (e) {
      console.error('Error submitting lesson answer:', e)
    }
  }

  // Telemetry & Novelty Functions
  const fetchTelemetry = async () => {
    try {
      const res = await fetch(`${backendUrl}/api/v1/metrics`)
      const data = await res.json()
      if (data.status === 'success') {
        setTelemetry(data.metrics)
      }
    } catch (e) {
      console.error('Error fetching telemetry:', e)
    }
  }

  const handleRunCrossSimulation = async () => {
    setIsSimulatingCross(true)
    try {
      const res = await fetch(`${backendUrl}/api/v1/novelty/cross-simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: 'Inventory lead-time sharing', supplier_id: 'Supplier X' })
      })
      const data = await res.json()
      if (data.status === 'success') {
        setCrossSimResult(data.simulation)
      }
    } catch (e) {
      console.error('Error simulating partner data share:', e)
    } finally {
      setIsSimulatingCross(false)
    }
  }

  return (
    <>
      <header className="app-header">
        <div className="logo-container">
          <div className="logo-icon">N</div>
          <div className="logo-text">
            <h1>DataNexus AI</h1>
            <p>Living Context Graph &amp; Decision Intelligence Hub</p>
          </div>
        </div>
        
        {/* Navigation Tabs */}
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <button 
            className={`btn btn-sm ${activeTab === 'dashboard' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <LayoutDashboard size={16} /> Operational Control
          </button>
          <button 
            className={`btn btn-sm ${activeTab === 'literacy' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('literacy')}
          >
            <BookOpen size={16} /> Literacy &amp; Sandbox Hub
          </button>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          {syncStatus && (
            <span style={{ fontSize: '0.8rem', color: syncStatus.includes('Error') ? 'var(--accent-red)' : 'var(--accent-green)', fontWeight: 600 }}>
              {syncStatus}
            </span>
          )}
          <button className="btn btn-secondary btn-sm" onClick={handleSyncFabric}>
            <RefreshCw size={16} /> Sync Fabric
          </button>
          <div className="tag tag-cyan">Environment: Dev Sandbox</div>
        </div>
      </header>

      {activeTab === 'dashboard' ? (
        /* Operational Control View */
        <div className="dashboard-grid">
          {/* Left Control Column */}
          <aside className="sidebar">
            {/* AI Layout Studio */}
            <div className="glass-panel">
              <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
                <Sparkles size={18} className="trend-up" /> AI Layout Studio
              </h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                Describe a business goal to dynamically adapt widgets &amp; analytical flow.
              </p>
              <div className="input-group" style={{ marginBottom: '1rem' }}>
                <textarea 
                  className="text-input" 
                  rows={3}
                  value={statedGoal} 
                  onChange={(e) => setStatedGoal(e.target.value)}
                  placeholder="Enter objective..."
                  style={{ resize: 'none' }}
                />
              </div>
              <button 
                className="btn btn-primary" 
                style={{ width: '100%', marginBottom: '1rem' }}
                onClick={() => handleGenerateDashboard()}
                disabled={isLoading}
              >
                {isLoading ? 'Adapting Layout...' : 'Regenerate Workspace'}
              </button>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <button 
                  className="btn btn-secondary btn-sm" 
                  onClick={() => {
                    setStatedGoal('Optimize transformer maintenance in western plants')
                    handleGenerateDashboard('Optimize transformer maintenance in western plants')
                  }}
                >
                  Manufacturing Uptime
                </button>
                <button 
                  className="btn btn-secondary btn-sm" 
                  onClick={() => {
                    setStatedGoal('Analyze CRM anomalies & revenue impact')
                    handleGenerateDashboard('Analyze CRM anomalies & revenue impact')
                  }}
                >
                  Revenue Risk &amp; CRM
                </button>
              </div>
            </div>

            {/* Governance & Steward Agent */}
            <div className="glass-panel">
              <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
                <ShieldAlert size={18} style={{ color: 'var(--accent-yellow)' }} /> Steward AI Guard
              </h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                Scan clean fabric zones for PII leaks or freshness anomalies.
              </p>
              <button 
                className="btn btn-secondary" 
                style={{ width: '100%', borderColor: 'var(--accent-yellow)', color: 'var(--text-primary)' }}
                onClick={handleRunGovernanceScan}
                disabled={isScanning}
              >
                {isScanning ? 'Scanning...' : 'Trigger Governance Scan'}
              </button>
              {scanResult && (
                <div style={{ marginTop: '1rem', background: 'rgba(0,0,0,0.2)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.8rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem' }}>
                    <span>PII Issues:</span>
                    <span className="trend-down" style={{ fontWeight: 'bold' }}>{scanResult.pii_issues_found} Found</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span>Stale Tables:</span>
                    <span className="trend-neutral">{scanResult.stale_tables_found}</span>
                  </div>
                  {scanResult.actions_queued.length > 0 && (
                    <div style={{ color: 'var(--accent-yellow)', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <AlertTriangle size={12} /> Auto-queued masking approval ticket!
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Observability telemetry metrics */}
            <div className="glass-panel">
              <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
                <Activity size={18} style={{ color: 'var(--accent-cyan)' }} /> Telemetry Metrics
              </h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                Active Prometheus OpenTelemetry agent execution spans.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.8rem' }}>
                {telemetry.map((m, idx) => (
                  <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', background: 'rgba(0,0,0,0.2)', padding: '0.4rem', borderRadius: '4px' }}>
                    <span style={{ color: 'var(--text-secondary)' }}>{m.metric.replace(/_/g, ' ')}</span>
                    <span style={{ fontWeight: 'bold', color: 'var(--accent-cyan)' }}>{m.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </aside>

          {/* Right Dashboard Area */}
          <main className="main-workspace">
            {/* Dynamic Narrative Summary */}
            {narrative && (
              <div className="glass-panel glow-panel" style={{ borderLeft: '4px solid var(--accent-purple)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                  <Cpu size={18} className="trend-up" />
                  <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--accent-purple)' }}>AI Copilot Narrative Insight</span>
                </div>
                <p style={{ fontSize: '0.95rem', lineHeight: '1.5', color: 'var(--text-primary)', textAlign: 'left' }}>
                  {narrative}
                </p>
              </div>
            )}

            {/* Dynamic Lineage Explorer Widget */}
            <div className="glass-panel">
              <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <GitBranch size={18} style={{ color: 'var(--accent-cyan)' }} /> Context Graph Lineage Map
              </h2>
              <div style={{ display: 'flex', justifyContent: 'center', background: 'rgba(0,0,0,0.2)', borderRadius: '10px', padding: '1rem' }}>
                <svg viewBox="0 0 600 80" style={{ width: '100%', maxWidth: '600px' }}>
                  <rect x="10" y="20" width="80" height="40" rx="6" fill="rgba(255,255,255,0.05)" stroke="var(--border-color)" />
                  <text x="50" y="45" fill="var(--text-primary)" fontSize="10" textAnchor="middle">Raw Sales</text>

                  <rect x="150" y="20" width="90" height="40" rx="6" fill="rgba(168, 85, 247, 0.15)" stroke="var(--accent-purple)" />
                  <text x="195" y="45" fill="var(--text-primary)" fontSize="10" textAnchor="middle">Clean Zone</text>

                  <rect x="300" y="20" width="110" height="40" rx="6" fill="rgba(6, 182, 212, 0.15)" stroke="var(--accent-cyan)" />
                  <text x="355" y="45" fill="var(--text-primary)" fontSize="10" textAnchor="middle">Maintenance Event</text>

                  <rect x="470" y="20" width="110" height="40" rx="6" fill="rgba(16, 185, 129, 0.15)" stroke="var(--accent-green)" />
                  <text x="525" y="45" fill="var(--text-primary)" fontSize="10" textAnchor="middle">Revenue KPI</text>

                  <line x1="90" y1="40" x2="150" y2="40" stroke="var(--text-secondary)" strokeDasharray="4" />
                  <line x1="240" y1="40" x2="300" y2="40" stroke="var(--accent-purple)" />
                  <line x1="410" y1="40" x2="470" y2="40" stroke="var(--accent-cyan)" />
                </svg>
              </div>
            </div>

            {/* KPI Cards Row (Stateful & Dynamic!) */}
            <div className="kpi-row" style={{ width: '100%' }}>
              <div className="kpi-card">
                <div className="kpi-label">Revenue</div>
                <div className="kpi-value">${kpiRevenue}M</div>
                <div className="kpi-trend trend-up">▲ +5.2%</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Production Uptime</div>
                <div className="kpi-value">{kpiUptime}%</div>
                <div className={`kpi-trend trend-${parseFloat(kpiUptimeTrend) >= 0 ? 'up' : 'down'}`}>
                  {parseFloat(kpiUptimeTrend) >= 0 ? '▲' : '▼'} {kpiUptimeTrend}
                </div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Fabric Trust Score</div>
                <div className="kpi-value">{kpiTrust}/100</div>
                <div className="kpi-trend trend-up">▲ Dynamic</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Open Approvals</div>
                <div className="kpi-value">{approvals.length}</div>
                <div className="kpi-trend trend-neutral">■ Pending</div>
              </div>
            </div>

            {/* SVG Charts */}
            <div className="widgets-container" style={{ marginTop: '1.5rem', width: '100%' }}>
              <div className="widget-wrapper glass-panel" style={{ gridColumn: 'span 6' }}>
                <div className="widget-header">
                  <span className="widget-title">Production Uptime Trend</span>
                  <span className="tag tag-purple">Operational Graph</span>
                </div>
                <div style={{ height: '200px', width: '100%', position: 'relative' }}>
                  <svg viewBox="0 0 500 200" style={{ width: '100%', height: '100%' }}>
                    <defs>
                      <linearGradient id="gradient-line" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0.4" />
                        <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    <line x1="30" y1="20" x2="480" y2="20" stroke="rgba(255,255,255,0.05)" />
                    <line x1="30" y1="70" x2="480" y2="70" stroke="rgba(255,255,255,0.05)" />
                    <line x1="30" y1="120" x2="480" y2="120" stroke="rgba(255,255,255,0.05)" />
                    <line x1="30" y1="170" x2="480" y2="170" stroke="rgba(255,255,255,0.1)" />
                    <path 
                      d={`M30,150 Q100,${160 - (kpiUptime - 90)*8} 180,${170 - (kpiUptime - 90)*9} T320,${150 - (kpiUptime - 90)*10} T480,${160 - (kpiUptime - 90)*6}`} 
                      fill="none" 
                      stroke="var(--accent-cyan)" 
                      strokeWidth="3" 
                    />
                    <path 
                      d={`M30,150 Q100,${160 - (kpiUptime - 90)*8} 180,${170 - (kpiUptime - 90)*9} T320,${150 - (kpiUptime - 90)*10} T480,${160 - (kpiUptime - 90)*6} L480,170 L30,170 Z`} 
                      fill="url(#gradient-line)" 
                    />
                  </svg>
                </div>
              </div>

              <div className="widget-wrapper glass-panel" style={{ gridColumn: 'span 6' }}>
                <div className="widget-header">
                  <span className="widget-title">Maintenance Events by Region</span>
                  <span className="tag tag-purple">Operational Graph</span>
                </div>
                <div style={{ height: '200px', width: '100%', position: 'relative' }}>
                  <svg viewBox="0 0 500 200" style={{ width: '100%', height: '100%' }}>
                    <line x1="30" y1="170" x2="480" y2="170" stroke="rgba(255,255,255,0.1)" />
                    <rect x="50" y="60" width="30" height="110" rx="4" fill="var(--accent-purple)" opacity="0.8" />
                    <rect x="150" y="90" width="30" height="80" rx="4" fill="var(--accent-purple)" opacity="0.8" />
                    <rect x="250" y="40" width="30" height="130" rx="4" fill="var(--accent-purple)" opacity="0.8" />
                    <rect x="350" y="110" width="30" height="60" rx="4" fill="var(--accent-purple)" opacity="0.8" />
                    <rect x="450" y="80" width="30" height="90" rx="4" fill="var(--accent-purple)" opacity="0.8" />
                  </svg>
                </div>
              </div>
            </div>

            {/* What-If simulation block */}
            <div className="glass-panel" style={{ width: '100%', marginTop: '1.5rem' }}>
              <div className="widget-header">
                <span className="widget-title">What-If: Adjust Maintenance Budget</span>
                <span className="tag tag-cyan">Decision Simulation Engine</span>
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '1.5rem', textAlign: 'left' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div className="input-group">
                    <label className="input-label">Scenario Target</label>
                    <select 
                      className="text-input" 
                      value={selectedScenario}
                      onChange={(e) => setSelectedScenario(e.target.value)}
                    >
                      <option value="transformer_maintenance">Transformer Maintenance Frequency</option>
                      <option value="supply_disruptions">Supply Disruption Recovery</option>
                    </select>
                  </div>
                  
                  <div className="slider-container">
                    <div className="slider-label-row">
                      <span>Intervention Magnitude</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 'bold', color: 'var(--accent-purple)' }}>{interventionMagnitude}x</span>
                    </div>
                    <input 
                      type="range" 
                      min="0.1" 
                      max="3.0" 
                      step="0.1"
                      className="styled-slider"
                      value={interventionMagnitude}
                      onChange={(e) => setInterventionMagnitude(parseFloat(e.target.value))}
                    />
                  </div>

                  <button className="btn btn-primary" onClick={handleSimulate}>
                    <Play size={16} /> Run Scenario Simulation
                  </button>
                </div>

                <div style={{ background: 'rgba(0,0,0,0.15)', padding: '1rem', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                  {simulationResult ? (
                    <div>
                      <h4 style={{ fontSize: '0.9rem', marginBottom: '0.75rem', fontWeight: 600, color: 'var(--accent-cyan)' }}>
                        Predicted Causal Consequences
                      </h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {simulationResult.ranked_outcomes.map((out: any, idx: number) => (
                          <div key={idx} style={{ padding: '0.5rem', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', borderLeft: '3px solid var(--accent-cyan)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', fontWeight: 600 }}>
                              <span>{out.affected_metric}</span>
                              <span className="trend-up" style={{ marginLeft: 'auto' }}>{out.predicted_change}</span>
                            </div>
                            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{out.explanation}</p>
                            <div style={{ marginTop: '0.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span className={`tag tag-${out.risk_level === 'low' ? 'green' : 'yellow'}`}>Risk: {out.risk_level}</span>
                              <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Confidence: {out.confidence * 100}%</span>
                            </div>
                          </div>
                        ))}
                      </div>

                      {recommendationResult && (
                        <div style={{ marginTop: '1rem', paddingTop: '0.75rem', borderTop: '1px solid var(--border-color)', fontSize: '0.8rem' }}>
                          <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Governance Recommendation:</div>
                          <p style={{ color: 'var(--text-primary)' }}>{recommendationResult.recommendation}</p>
                          <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                            <span className="tag tag-green">Governance: Passed</span>
                            <span className="tag tag-purple">Lineage: Causal Metadata</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                      Click Run Scenario Simulation to compute causal impacts.
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Cross Enterprise simulations */}
            <div className="glass-panel" style={{ width: '100%', marginTop: '1.5rem' }}>
              <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Globe size={18} style={{ color: 'var(--accent-cyan)' }} /> Cross-Enterprise Collaboration (Supplier X)
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', textAlign: 'left' }}>
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                    Share core operational bounds with external partners to optimize lead times.
                  </p>
                  <button className="btn btn-secondary" onClick={handleRunCrossSimulation} disabled={isSimulatingCross}>
                    {isSimulatingCross ? 'Simulating...' : 'Simulate Partner Data-Share'}
                  </button>
                </div>
                <div style={{ background: 'rgba(0,0,0,0.15)', padding: '0.75rem', borderRadius: '8px' }}>
                  {crossSimResult ? (
                    <div style={{ fontSize: '0.8rem' }}>
                      <div style={{ fontWeight: 'bold', color: 'var(--accent-green)', marginBottom: '0.25rem' }}>Simulation Successful</div>
                      <div>Partner: {crossSimResult.partner}</div>
                      <div>Lead Time Change: <span style={{ color: 'var(--accent-green)', fontWeight: 'bold' }}>{crossSimResult.simulated_lead_time_change}</span></div>
                      <div>Cost Reduction: <span style={{ color: 'var(--accent-green)', fontWeight: 'bold' }}>{crossSimResult.predicted_cost_reduction}</span></div>
                    </div>
                  ) : (
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', textAlign: 'center', paddingTop: '1rem' }}>
                      No active cross-enterprise simulation run.
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Split panel: Approvals & Interactive Copilot */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '1.5rem', textAlign: 'left', marginTop: '1.5rem', width: '100%' }}>
              {/* Agent Approvals */}
              <div className="glass-panel">
                <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Check size={18} className="trend-up" /> Pending Governance Approvals
                </h2>
                {approvals.length === 0 ? (
                  <div style={{ padding: '2rem 0', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                    No pending actions requiring approval.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {approvals.map((appr) => (
                      <div key={appr.id} style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem', fontSize: '0.8rem' }}>
                          <span style={{ fontWeight: 600 }} className="tag tag-purple">{appr.agent}</span>
                          <span style={{ color: 'var(--text-secondary)' }}>Ticket #{appr.id}</span>
                        </div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>
                          Action: {appr.action}
                        </div>
                        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                          Reasoning: {appr.reasoning}
                        </p>
                        
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <input 
                            type="text" 
                            className="text-input" 
                            placeholder="Feedback (optional)..." 
                            style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                            value={feedbackText}
                            onChange={(e) => setFeedbackText(e.target.value)}
                          />
                          <button className="btn btn-secondary btn-sm" onClick={() => handleResolveApproval(appr.id, 'rejected')}>
                            <X size={14} className="trend-down" /> Reject
                          </button>
                          <button className="btn btn-primary btn-sm" onClick={() => handleResolveApproval(appr.id, 'approved')}>
                            <Check size={14} /> Approve
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Interactive Copilot Chat */}
              <div className="glass-panel">
                <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <MessageSquare size={18} className="trend-up" /> Enterprise Knowledge Copilot
                </h2>
                
                {/* Copilot Task Buttons */}
                <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <button className="btn btn-secondary btn-sm" onClick={handleExplainSQL}>
                    <FileText size={14} /> Explain SQL Pipeline
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={handleExecuteQ2Summary}>
                    <Send size={14} /> Send Q2 Board Summary
                  </button>
                </div>

                <div style={{ 
                  height: '200px', 
                  overflowY: 'auto', 
                  background: 'rgba(0,0,0,0.2)', 
                  padding: '1rem', 
                  borderRadius: '10px', 
                  border: '1px solid var(--border-color)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.75rem',
                  marginBottom: '1rem'
                }}>
                  {chatHistory.map((msg, idx) => (
                    <div key={idx} style={{ 
                      alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      background: msg.role === 'user' ? 'var(--accent-purple)' : 'rgba(255,255,255,0.05)',
                      padding: '0.6rem 0.9rem',
                      borderRadius: '12px',
                      maxWidth: '85%',
                      fontSize: '0.85rem',
                      lineHeight: '1.4',
                      whiteSpace: 'pre-line'
                    }}>
                      {msg.content}
                    </div>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input 
                    type="text" 
                    className="text-input" 
                    placeholder="Ask context graph or request simulations..." 
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                  />
                  <button className="btn btn-primary" onClick={handleSendChat}>
                    <Send size={16} />
                  </button>
                </div>
              </div>
            </div>
          </main>
        </div>
      ) : (
        /* Data Democratization & Literacy Hub View */
        <div className="main-workspace" style={{ textAlign: 'left' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
            <div className="sidebar" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div className="glass-panel" style={{ borderLeft: '4px solid var(--accent-green)' }}>
                <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.15rem' }}>
                  <Award size={20} className="trend-up" /> User Literacy Profile
                </h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginTop: '1rem' }}>
                  <div style={{ background: 'var(--accent-green-glow)', padding: '0.75rem', borderRadius: '10px' }}>
                    <UserCheck size={24} style={{ color: 'var(--accent-green)' }} />
                  </div>
                  <div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Current Score:</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {literacyScore} XP
                    </div>
                  </div>
                </div>

                <div className="input-group" style={{ marginTop: '1.25rem' }}>
                  <label className="input-label">Select Learning Persona</label>
                  <select 
                    className="text-input"
                    value={userRole}
                    onChange={(e) => setUserRole(e.target.value as any)}
                  >
                    <option value="Analyst">Analyst Path</option>
                    <option value="Engineer">Data Engineer Path</option>
                  </select>
                </div>
              </div>

              <div className="glass-panel">
                <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1.1rem' }}>
                  <Terminal size={18} style={{ color: 'var(--accent-cyan)' }} /> Practice Sandbox Playground
                </h2>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  A secure sandbox dataset with masked entries for self-training.
                </p>
                <div style={{ maxHeight: '180px', overflowY: 'auto', background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '8px' }}>
                  <table className="styled-table" style={{ fontSize: '0.8rem' }}>
                    <thead>
                      <tr>
                        {sandboxData.length > 0 && Object.keys(sandboxData[0]).map((k, idx) => (
                          <th key={idx}>{k}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sandboxData.map((row, idx) => (
                        <tr key={idx}>
                          {Object.values(row).map((val: any, cellIdx) => (
                            <td key={cellIdx}>{String(val)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              <div className="glass-panel">
                <h2 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>Personalized Learning Roadmap ({userRole})</h2>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                  Complete sandbox lessons to improve your Data Literacy Score and unlock advanced query access.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                  {lessons.map((lesson) => (
                    <div key={lesson.id} style={{ 
                      padding: '1.25rem', 
                      background: 'rgba(255,255,255,0.01)', 
                      borderRadius: '12px', 
                      border: '1px solid var(--border-color)' 
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                        <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)' }}>{lesson.title}</h3>
                        <span className="tag tag-purple">+{lesson.points} XP</span>
                      </div>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                        {lesson.description}
                      </p>

                      <div style={{ background: 'rgba(0,0,0,0.15)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem' }}>
                        <div style={{ fontSize: '0.9rem', fontWeight: 500, marginBottom: '0.75rem', color: 'var(--text-primary)' }}>
                          Exercise Question: {lesson.exercise}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          {lesson.options.map((option, optIdx) => (
                            <label key={optIdx} style={{ 
                              display: 'flex', 
                              alignItems: 'center', 
                              gap: '0.5rem', 
                              fontSize: '0.85rem', 
                              cursor: 'pointer',
                              padding: '0.4rem',
                              borderRadius: '4px',
                              background: selectedLessonAnswer[lesson.id] === option ? 'rgba(168, 85, 247, 0.1)' : 'transparent'
                            }}>
                              <input 
                                type="radio" 
                                name={`question-${lesson.id}`} 
                                checked={selectedLessonAnswer[lesson.id] === option}
                                onChange={() => handleSelectOption(lesson.id, option)}
                              />
                              {option}
                            </label>
                          ))}
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                        <button 
                          className="btn btn-primary btn-sm"
                          onClick={() => handleSubmitLesson(lesson.id)}
                          disabled={!selectedLessonAnswer[lesson.id]}
                        >
                          Submit Answer
                        </button>
                        
                        {lessonFeedback[lesson.id] && (
                          <div style={{ 
                            fontSize: '0.85rem', 
                            color: lessonFeedback[lesson.id].correct ? 'var(--accent-green)' : 'var(--accent-red)',
                            fontWeight: 500
                          }}>
                            {lessonFeedback[lesson.id].explanation}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default App
