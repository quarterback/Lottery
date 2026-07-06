from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LeagueConfig:
    id: str
    name: str
    team_names: list[str]
    num_teams: int
    playoff_spots: int
    games_per_season: int
    weeks_per_season: int
    play_in_slots: int
    lottery_picks: int
    chip_window_start: int
    chip_window_length: int
    points_system: str = "wins"          # "wins" | "3-2-1-0" | "2-1-1"
    regulation_win_share: float = 1.0    # share of decisive games ending in regulation

    @property
    def lottery_teams(self) -> int:
        return self.num_teams - self.playoff_spots

    @property
    def safe_playoff_count(self) -> int:
        return max(0, self.playoff_spots - self.play_in_slots)

    @property
    def play_in_count(self) -> int:
        return self.play_in_slots


NBA_CONFIG = LeagueConfig(
    id="nba",
    name="NBA",
    team_names=[
        "Atlanta", "Boston", "Brooklyn", "Charlotte", "Chicago",
        "Cleveland", "Dallas", "Denver", "Detroit", "Golden State",
        "Houston", "Indiana", "LA Clippers", "LA Lakers", "Memphis",
        "Miami", "Milwaukee", "Minnesota", "New Orleans", "New York",
        "Oklahoma City", "Orlando", "Philadelphia", "Phoenix", "Portland",
        "Sacramento", "San Antonio", "Toronto", "Utah", "Washington",
    ],
    num_teams=30,
    playoff_spots=16,
    games_per_season=82,
    weeks_per_season=26,
    play_in_slots=4,
    lottery_picks=4,
    chip_window_start=61,
    chip_window_length=22,
)

NHL_CONFIG = LeagueConfig(
    id="nhl",
    name="NHL",
    team_names=[
        "Anaheim", "Boston", "Buffalo", "Calgary", "Carolina",
        "Chicago", "Colorado", "Columbus", "Dallas", "Detroit",
        "Edmonton", "Florida", "Los Angeles", "Minnesota", "Montreal",
        "Nashville", "New Jersey", "NY Islanders", "NY Rangers", "Ottawa",
        "Philadelphia", "Pittsburgh", "San Jose", "Seattle", "St. Louis",
        "Tampa Bay", "Toronto", "Utah", "Vancouver", "Vegas",
        "Washington", "Winnipeg",
    ],
    num_teams=32,
    playoff_spots=16,
    games_per_season=82,
    weeks_per_season=26,
    play_in_slots=0,
    lottery_picks=4,
    chip_window_start=61,
    chip_window_length=22,
)

MLB_CONFIG = LeagueConfig(
    id="mlb",
    name="MLB",
    team_names=[
        "Arizona", "Atlanta", "Baltimore", "Boston", "Chicago Cubs",
        "Chicago White Sox", "Cincinnati", "Cleveland", "Colorado", "Detroit",
        "Houston", "Kansas City", "LA Angels", "LA Dodgers", "Miami",
        "Milwaukee", "Minnesota", "NY Mets", "NY Yankees", "Oakland",
        "Philadelphia", "Pittsburgh", "San Diego", "San Francisco", "Seattle",
        "St. Louis", "Tampa Bay", "Texas", "Toronto", "Washington",
    ],
    num_teams=30,
    playoff_spots=12,
    games_per_season=162,
    weeks_per_season=26,
    play_in_slots=0,
    lottery_picks=4,
    chip_window_start=141,
    chip_window_length=22,
)

WNBA_CONFIG = LeagueConfig(
    id="wnba",
    name="WNBA",
    team_names=[
        "Atlanta Dream", "Chicago Sky", "Connecticut Sun", "Dallas Wings",
        "Golden State Valkyries", "Indiana Fever", "Las Vegas Aces",
        "Los Angeles Sparks", "Minnesota Lynx", "New York Liberty",
        "Phoenix Mercury", "Portland Fire", "Seattle Storm",
        "Toronto Tempo", "Washington Mystics",
    ],
    num_teams=15,
    playoff_spots=8,
    games_per_season=40,
    weeks_per_season=13,
    play_in_slots=0,
    lottery_picks=3,
    chip_window_start=31,
    chip_window_length=10,
)

PWHL_CONFIG = LeagueConfig(
    id="pwhl",
    name="PWHL",
    team_names=[
        "Boston Fleet", "Minnesota Frost", "Montreal Victoire",
        "New York Sirens", "Ottawa Charge", "Seattle Torrent",
        "Toronto Sceptres", "Vancouver Goldeneyes",
    ],
    num_teams=8,
    playoff_spots=4,
    games_per_season=32,
    weeks_per_season=11,
    play_in_slots=0,
    lottery_picks=2,
    chip_window_start=25,
    chip_window_length=8,
    points_system="3-2-1-0",
    regulation_win_share=0.77,
)

MLS_CONFIG = LeagueConfig(
    id="mls",
    name="MLS",
    team_names=[
        "Atlanta", "Austin", "Charlotte", "Chicago", "Colorado",
        "Columbus", "D.C. United", "FC Cincinnati", "FC Dallas", "Houston",
        "Inter Miami", "LA Galaxy", "LAFC", "Minnesota", "Montreal",
        "Nashville", "New England", "New York City", "NY Red Bulls", "Orlando",
        "Philadelphia", "Portland", "Real Salt Lake", "San Jose", "Seattle",
        "Sporting KC", "St. Louis", "Toronto", "Vancouver",
    ],
    num_teams=29,
    playoff_spots=18,
    games_per_season=34,
    weeks_per_season=11,
    play_in_slots=0,
    lottery_picks=3,
    chip_window_start=25,
    chip_window_length=10,
)

LEAGUES: dict[str, LeagueConfig] = {
    "nba": NBA_CONFIG,
    "nhl": NHL_CONFIG,
    "mlb": MLB_CONFIG,
    "wnba": WNBA_CONFIG,
    "pwhl": PWHL_CONFIG,
    "mls": MLS_CONFIG,
}


def get_league(league_id: str) -> LeagueConfig:
    """Return the LeagueConfig for the given id, defaulting to NBA."""
    return LEAGUES.get(league_id.lower().strip(), NBA_CONFIG)


def chips_for_rank(rank_0: int, n_teams: int = 30) -> float:
    """
    Starting chip allocation for a team at zero-based record rank `rank_0`
    (rank 0 = worst record), scaled to the league's team count.

    Seven tiers at proportional breakpoints [10%, 20%, 30%, 40%, 60%, 80%, 100%]
    give values [140, 120, 100, 80, 60, 40, 20].

    For 30 teams this reproduces the original breakpoints exactly (3/3/3/3/6/6/6).
    """
    CHIP_VALUES = [140.0, 120.0, 100.0, 80.0, 60.0, 40.0, 20.0]
    FRACTIONS   = [0.10,   0.20,  0.30,  0.40,  0.60,  0.80,  1.00]
    for chips, frac in zip(CHIP_VALUES, FRACTIONS):
        if rank_0 < max(1, math.ceil(n_teams * frac)):
            return chips
    return 20.0
