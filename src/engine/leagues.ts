// League configurations — ported from engine/leagues.py.
// Each league scales team count, schedule length, playoff structure, and points
// system, so any lottery system runs against any league.

export type PointsSystem = 'wins' | '3-2-1-0' | '2-1-1'

export interface LeagueConfig {
  id: string
  name: string
  teamNames: string[]
  numTeams: number
  playoffSpots: number
  gamesPerSeason: number
  weeksPerSeason: number
  playInSlots: number
  lotteryPicks: number
  chipWindowStart: number
  chipWindowLength: number
  pointsSystem: PointsSystem
  /** Share of decisive games ending in regulation (for points leagues). */
  regulationWinShare: number
}

export const lotteryTeams = (lg: LeagueConfig): number => lg.numTeams - lg.playoffSpots
export const safePlayoffCount = (lg: LeagueConfig): number => Math.max(0, lg.playoffSpots - lg.playInSlots)
export const playInCount = (lg: LeagueConfig): number => lg.playInSlots

const league = (c: Partial<LeagueConfig> & Pick<LeagueConfig, 'id' | 'name' | 'teamNames' | 'numTeams' | 'playoffSpots' | 'gamesPerSeason' | 'weeksPerSeason' | 'playInSlots' | 'lotteryPicks' | 'chipWindowStart' | 'chipWindowLength'>): LeagueConfig => ({
  pointsSystem: 'wins',
  regulationWinShare: 1.0,
  ...c,
})

export const NBA_CONFIG = league({
  id: 'nba',
  name: 'NBA',
  teamNames: [
    'Atlanta', 'Boston', 'Brooklyn', 'Charlotte', 'Chicago',
    'Cleveland', 'Dallas', 'Denver', 'Detroit', 'Golden State',
    'Houston', 'Indiana', 'LA Clippers', 'LA Lakers', 'Memphis',
    'Miami', 'Milwaukee', 'Minnesota', 'New Orleans', 'New York',
    'Oklahoma City', 'Orlando', 'Philadelphia', 'Phoenix', 'Portland',
    'Sacramento', 'San Antonio', 'Toronto', 'Utah', 'Washington',
  ],
  numTeams: 30,
  playoffSpots: 16,
  gamesPerSeason: 82,
  weeksPerSeason: 26,
  playInSlots: 4,
  lotteryPicks: 4,
  chipWindowStart: 61,
  chipWindowLength: 22,
})

export const NHL_CONFIG = league({
  id: 'nhl',
  name: 'NHL',
  teamNames: [
    'Anaheim', 'Boston', 'Buffalo', 'Calgary', 'Carolina',
    'Chicago', 'Colorado', 'Columbus', 'Dallas', 'Detroit',
    'Edmonton', 'Florida', 'Los Angeles', 'Minnesota', 'Montreal',
    'Nashville', 'New Jersey', 'NY Islanders', 'NY Rangers', 'Ottawa',
    'Philadelphia', 'Pittsburgh', 'San Jose', 'Seattle', 'St. Louis',
    'Tampa Bay', 'Toronto', 'Utah', 'Vancouver', 'Vegas',
    'Washington', 'Winnipeg',
  ],
  numTeams: 32,
  playoffSpots: 16,
  gamesPerSeason: 82,
  weeksPerSeason: 26,
  playInSlots: 0,
  lotteryPicks: 4,
  chipWindowStart: 61,
  chipWindowLength: 22,
})

export const MLB_CONFIG = league({
  id: 'mlb',
  name: 'MLB',
  teamNames: [
    'Arizona', 'Atlanta', 'Baltimore', 'Boston', 'Chicago Cubs',
    'Chicago White Sox', 'Cincinnati', 'Cleveland', 'Colorado', 'Detroit',
    'Houston', 'Kansas City', 'LA Angels', 'LA Dodgers', 'Miami',
    'Milwaukee', 'Minnesota', 'NY Mets', 'NY Yankees', 'Oakland',
    'Philadelphia', 'Pittsburgh', 'San Diego', 'San Francisco', 'Seattle',
    'St. Louis', 'Tampa Bay', 'Texas', 'Toronto', 'Washington',
  ],
  numTeams: 30,
  playoffSpots: 12,
  gamesPerSeason: 162,
  weeksPerSeason: 26,
  playInSlots: 0,
  lotteryPicks: 4,
  chipWindowStart: 141,
  chipWindowLength: 22,
})

export const WNBA_CONFIG = league({
  id: 'wnba',
  name: 'WNBA',
  teamNames: [
    'Atlanta Dream', 'Chicago Sky', 'Connecticut Sun', 'Dallas Wings',
    'Golden State Valkyries', 'Indiana Fever', 'Las Vegas Aces',
    'Los Angeles Sparks', 'Minnesota Lynx', 'New York Liberty',
    'Phoenix Mercury', 'Portland Fire', 'Seattle Storm',
    'Toronto Tempo', 'Washington Mystics',
  ],
  numTeams: 15,
  playoffSpots: 8,
  gamesPerSeason: 40,
  weeksPerSeason: 13,
  playInSlots: 0,
  lotteryPicks: 3,
  chipWindowStart: 31,
  chipWindowLength: 10,
})

export const PWHL_CONFIG = league({
  id: 'pwhl',
  name: 'PWHL',
  teamNames: [
    'Boston Fleet', 'Minnesota Frost', 'Montreal Victoire',
    'New York Sirens', 'Ottawa Charge', 'Seattle Torrent',
    'Toronto Sceptres', 'Vancouver Goldeneyes',
  ],
  numTeams: 8,
  playoffSpots: 4,
  gamesPerSeason: 32,
  weeksPerSeason: 11,
  playInSlots: 0,
  lotteryPicks: 2,
  chipWindowStart: 25,
  chipWindowLength: 8,
  pointsSystem: '3-2-1-0',
  regulationWinShare: 0.77,
})

export const MLS_CONFIG = league({
  id: 'mls',
  name: 'MLS',
  teamNames: [
    'Atlanta', 'Austin', 'Charlotte', 'Chicago', 'Colorado',
    'Columbus', 'D.C. United', 'FC Cincinnati', 'FC Dallas', 'Houston',
    'Inter Miami', 'LA Galaxy', 'LAFC', 'Minnesota', 'Montreal',
    'Nashville', 'New England', 'New York City', 'NY Red Bulls', 'Orlando',
    'Philadelphia', 'Portland', 'Real Salt Lake', 'San Jose', 'Seattle',
    'Sporting KC', 'St. Louis', 'Toronto', 'Vancouver',
  ],
  numTeams: 29,
  playoffSpots: 18,
  gamesPerSeason: 34,
  weeksPerSeason: 11,
  playInSlots: 0,
  lotteryPicks: 3,
  chipWindowStart: 25,
  chipWindowLength: 10,
})

export const LEAGUES: Record<string, LeagueConfig> = {
  nba: NBA_CONFIG,
  nhl: NHL_CONFIG,
  mlb: MLB_CONFIG,
  wnba: WNBA_CONFIG,
  pwhl: PWHL_CONFIG,
  mls: MLS_CONFIG,
}

export const LEAGUE_LIST = [NBA_CONFIG, NHL_CONFIG, MLB_CONFIG, WNBA_CONFIG, PWHL_CONFIG, MLS_CONFIG]

export function getLeague(id: string): LeagueConfig {
  return LEAGUES[id.toLowerCase().trim()] ?? NBA_CONFIG
}

/**
 * Starting chip allocation for a team at zero-based record rank `rank0`
 * (rank 0 = worst record), scaled to the league's team count.
 * Seven tiers at proportional breakpoints [10,20,30,40,60,80,100]%.
 */
export function chipsForRank(rank0: number, nTeams = 30): number {
  const CHIP_VALUES = [140, 120, 100, 80, 60, 40, 20]
  const FRACTIONS = [0.1, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0]
  for (let i = 0; i < CHIP_VALUES.length; i++) {
    if (rank0 < Math.max(1, Math.ceil(nTeams * FRACTIONS[i]!))) return CHIP_VALUES[i]!
  }
  return 20.0
}
