import { useEffect, useState } from 'react'
import './ui/lottery.css'
import { Simulator } from './pages/Simulator'
import { ChipWindow } from './pages/ChipWindow'
import { Historical } from './pages/Historical'

type Route = 'simulator' | 'chip-window' | 'historical'
const ROUTES: { id: Route; hash: string; label: string }[] = [
  { id: 'simulator', hash: '#/', label: 'Simulator' },
  { id: 'chip-window', hash: '#/chip-window', label: 'Chip Window' },
  { id: 'historical', hash: '#/historical', label: 'Historical' },
]

const HEROES: Record<Route, { h1: string; p: string }> = {
  simulator: {
    h1: 'Design a draft lottery. Watch it play out.',
    p: 'Pick up to two lottery systems, choose a league, and run Monte Carlo seasons to see how each shapes tanking, fairness, and competitive balance.',
  },
  'chip-window': {
    h1: 'The Chip Window.',
    p: 'A betting-based draft mechanic where teams wager chips over the season’s final stretch. Final chips are the draft order — so tanking is structurally impossible.',
  },
  historical: {
    h1: 'Replay any real lottery.',
    p: 'Run a real NBA season’s standings through any lottery system thousands of times and compare the simulated odds to what actually happened.',
  },
}

function routeFromHash(): Route {
  const h = location.hash || '#/'
  return ROUTES.find((r) => r.hash === h)?.id ?? 'simulator'
}

function useTheme(): [string, () => void] {
  const [theme, setTheme] = useState<string>(() => localStorage.getItem('lottery-theme') ?? 'auto')
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'auto') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    localStorage.setItem('lottery-theme', theme)
  }, [theme])
  return [theme, () => setTheme((t) => (t === 'auto' ? 'light' : t === 'light' ? 'dark' : 'auto'))]
}

export function App() {
  const [theme, cycleTheme] = useTheme()
  const [route, setRoute] = useState<Route>(routeFromHash)

  useEffect(() => {
    const onHash = () => setRoute(routeFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const themeIcon = theme === 'dark' ? '☾' : theme === 'light' ? '☀' : '◐'
  const hero = HEROES[route]

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="ball" />
          Lottery Lab
          <small>draft-lottery simulator</small>
        </div>
        <div className="topbar__spacer" />
        <nav className="nav">
          {ROUTES.map((r) => (
            <a key={r.id} href={r.hash} data-active={route === r.id}>{r.label}</a>
          ))}
        </nav>
        <button className="btn" style={{ padding: '6px 10px' }} onClick={cycleTheme} title={`Theme: ${theme}`} aria-label="Toggle theme">
          {themeIcon}
        </button>
      </header>

      <div className="shell">
        <div className="hero">
          <h1>{hero.h1}</h1>
          <p>{hero.p}</p>
        </div>

        {route === 'simulator' && <Simulator />}
        {route === 'chip-window' && <ChipWindow />}
        {route === 'historical' && <Historical />}
      </div>
    </>
  )
}
