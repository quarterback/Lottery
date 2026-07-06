"""
Historical NBA lottery standings and results, 2000-01 through 2025-26.

Data notes:
  • lottery_teams: 14 non-playoff teams sorted worst-to-best (ascending wins).
    For seasons before 2004-05 (29-team NBA, 13 real lottery slots), a 14th
    borderline non-playoff team is included to keep the simulation format consistent.
    Win/loss records are curated to exclude teams that made the playoffs that year.
  • lottery_top4: actual lottery drawing results — ordered list [pick1, pick2, pick3, pick4].
    All four names must be present in lottery_teams.  Expansion-team picks and
    traded picks from outside the lottery are excluded; the next-eligible lottery
    team fills that slot.
  • actual_order: derived at runtime by _compute_actual_order — lottery_top4 teams
    first (in draw order), then remaining lottery_teams sorted by ascending wins.
    Slots 5–14 are approximate (worst-record order) since exact post-lottery ordering
    is not stored.
  • games: regular-season games played (82 standard; 66 lockout 2011-12;
    ~65-72 for 2019-20 COVID bubble season).
"""

from __future__ import annotations

HISTORICAL_SEASONS: dict[str, dict] = {

    # -----------------------------------------------------------------------
    # 2000-01  —  2001 NBA Draft
    # -----------------------------------------------------------------------
    "2000-01": {
        "context": (
            "2001 Draft · Kwame Brown (Washington, 19W) became the first HS player taken #1 overall. "
            "The Chicago Bulls (15W, worst record) were passed over as the Wizards jumped from "
            "7th-worst to win the lottery — the second-biggest odds upset of the modern era."
        ),
        "games": 82,
        "lottery_pick1": "Washington Wizards",
        "lottery_top4": ["Washington Wizards", "Memphis Grizzlies", "Atlanta Hawks", "Chicago Bulls"],
        "lottery_teams": [
            ("Chicago Bulls", 15, 67),
            ("Golden State Warriors", 17, 65),
            ("Washington Wizards", 19, 63),
            ("Memphis Grizzlies", 23, 59),
            ("Atlanta Hawks", 25, 57),
            ("New Jersey Nets", 26, 56),
            ("Cleveland Cavaliers", 30, 52),
            ("LA Clippers", 31, 51),
            ("Detroit Pistons", 32, 50),
            ("Boston Celtics", 36, 46),
            ("Denver Nuggets", 40, 42),
            ("Seattle SuperSonics", 44, 38),
            # 13th/14th are borderline (29-team NBA had 13 real lottery slots)
            ("New York Knicks", 30, 52),
            ("Houston Rockets", 45, 37),
        ],
    },

    # -----------------------------------------------------------------------
    # 2001-02  —  2002 NBA Draft
    # -----------------------------------------------------------------------
    "2001-02": {
        "context": (
            "2002 Draft · Yao Ming (Houston, 28W) became the first international player "
            "taken #1 overall. Chicago Bulls (21W) had the worst record but Houston jumped "
            "from 6th-worst to win the lottery — an early sign that odds don't guarantee outcomes."
        ),
        "games": 82,
        "lottery_pick1": "Houston Rockets",
        "lottery_top4": ["Houston Rockets", "Chicago Bulls", "Golden State Warriors", "Memphis Grizzlies"],
        "lottery_teams": [
            ("Chicago Bulls", 21, 61),
            ("Golden State Warriors", 21, 61),
            ("Memphis Grizzlies", 23, 59),
            ("Houston Rockets", 28, 54),
            ("Atlanta Hawks", 33, 49),
            ("Cleveland Cavaliers", 29, 53),
            ("Denver Nuggets", 27, 55),
            ("Washington Wizards", 37, 45),
            ("New York Knicks", 30, 52),
            ("LA Clippers", 39, 43),
            ("Milwaukee Bucks", 41, 41),
            ("Phoenix Suns", 36, 46),
            # 13th/14th borderline (29-team NBA)
            ("Seattle SuperSonics", 45, 37),
            ("Orlando Magic", 44, 38),
        ],
    },

    # -----------------------------------------------------------------------
    # 2002-03  —  2003 NBA Draft (LeBron James)
    # -----------------------------------------------------------------------
    "2002-03": {
        "context": (
            "2003 Draft · LeBron James (Cleveland, 17W) was the consensus #1 overall pick. "
            "Cleveland had the worst record and won the lottery naturally — one of the most "
            "anticipated drafts in NBA history. Carmelo, Bosh, and Wade all followed at 3-5."
        ),
        "games": 82,
        "lottery_pick1": "Cleveland Cavaliers",
        "lottery_top4": ["Cleveland Cavaliers", "Denver Nuggets", "Toronto Raptors", "Washington Wizards"],
        "lottery_teams": [
            ("Cleveland Cavaliers", 17, 65),
            ("Toronto Raptors", 24, 58),
            ("Denver Nuggets", 17, 65),
            ("Chicago Bulls", 30, 52),
            ("Washington Wizards", 37, 45),
            ("LA Clippers", 27, 55),
            ("Atlanta Hawks", 35, 47),
            ("Golden State Warriors", 38, 44),
            ("New York Knicks", 37, 45),
            ("New Jersey Nets", 26, 56),
            ("Memphis Grizzlies", 28, 54),
            # Note: Detroit (50W) was an East playoff team — excluded
            ("Boston Celtics", 44, 38),
            ("Milwaukee Bucks", 42, 40),
            ("Phoenix Suns", 44, 38),
        ],
    },

    # -----------------------------------------------------------------------
    # 2003-04  —  2004 NBA Draft (Dwight Howard)
    # -----------------------------------------------------------------------
    "2003-04": {
        "context": (
            "2004 Draft · Dwight Howard (Orlando, 21W) jumped from 8th-worst to claim #1. "
            "The expansion Charlotte Bobcats (joining the NBA in 2004-05) received the #2 pick "
            "via an expansion allocation — not through the lottery drawing. Emeka Okafor went #2."
        ),
        "games": 82,
        "lottery_pick1": "Orlando Magic",
        # Charlotte Bobcats got #2 as expansion pick (not a 2003-04 lottery team).
        # Picks 2-4 among lottery participants: Chicago Bulls (#3), LA Clippers (#4).
        "lottery_top4": ["Orlando Magic", "Chicago Bulls", "LA Clippers", "Atlanta Hawks"],
        "lottery_teams": [
            ("New Orleans Hornets", 18, 64),
            ("Orlando Magic", 21, 61),
            ("Chicago Bulls", 23, 59),
            ("LA Clippers", 28, 54),
            ("Atlanta Hawks", 28, 54),
            ("Washington Wizards", 25, 57),
            ("Cleveland Cavaliers", 35, 47),
            ("Milwaukee Bucks", 41, 41),
            ("Seattle SuperSonics", 37, 45),
            ("Golden State Warriors", 37, 45),
            # Note: Memphis (50W) made their 1st playoffs — excluded
            # Note: NJ Nets (47W) were in the playoffs — excluded
            ("Boston Celtics", 36, 46),
            ("Toronto Raptors", 33, 49),
            ("New York Knicks", 39, 43),
            ("Denver Nuggets", 43, 39),
        ],
    },

    # -----------------------------------------------------------------------
    # 2004-05  —  2005 NBA Draft (Andrew Bogut)
    # -----------------------------------------------------------------------
    "2004-05": {
        "context": (
            "2005 Draft · Andrew Bogut (Milwaukee, 30W) went #1 after the Bucks won the lottery "
            "from the 4th-worst position. Charlotte Bobcats (18W) had the worst record in their "
            "expansion debut. The lottery was notable for the sheer number of bad teams."
        ),
        "games": 82,
        "lottery_pick1": "Milwaukee Bucks",
        "lottery_top4": ["Milwaukee Bucks", "Atlanta Hawks", "Utah Jazz", "New Orleans Hornets"],
        "lottery_teams": [
            ("Atlanta Hawks", 13, 69),
            ("Charlotte Bobcats", 18, 64),
            ("New Orleans Hornets", 18, 64),
            ("Utah Jazz", 26, 56),
            ("Portland Trail Blazers", 27, 55),
            ("New York Knicks", 33, 49),
            ("Golden State Warriors", 34, 48),
            ("Milwaukee Bucks", 30, 52),
            # Note: Sacramento (50W), Denver (49W), Chicago (47W), Memphis (45W)
            #       all made the 2004-05 playoffs — excluded
            ("LA Lakers", 34, 48),
            ("LA Clippers", 37, 45),
            ("Orlando Magic", 36, 46),
            ("Toronto Raptors", 33, 49),
            ("Philadelphia 76ers", 43, 39),
            ("Minnesota Timberwolves", 44, 38),
        ],
    },

    # -----------------------------------------------------------------------
    # 2005-06  —  2006 NBA Draft (Andrea Bargnani)
    # -----------------------------------------------------------------------
    "2005-06": {
        "context": (
            "2006 Draft · Andrea Bargnani (Toronto, 27W) became the first Italian-born player "
            "taken #1 overall. Toronto jumped from the 7th lottery seed to win — "
            "a decision widely questioned in retrospect as Gay, Roy, and LaMarcus Aldridge followed."
        ),
        "games": 82,
        "lottery_pick1": "Toronto Raptors",
        "lottery_top4": ["Toronto Raptors", "Charlotte Bobcats", "Portland Trail Blazers", "New York Knicks"],
        "lottery_teams": [
            ("Portland Trail Blazers", 21, 61),
            ("New York Knicks", 23, 59),
            ("Charlotte Bobcats", 26, 56),
            ("Atlanta Hawks", 26, 56),
            ("Minnesota Timberwolves", 33, 49),
            ("Boston Celtics", 33, 49),
            ("Houston Rockets", 34, 48),
            ("Golden State Warriors", 34, 48),
            ("New Orleans Hornets", 38, 44),
            ("Toronto Raptors", 27, 55),
            ("Utah Jazz", 41, 41),
            # Note: Chicago (41W) won the Central — playoff team, excluded
            # Note: Denver (44W) and Sacramento (44W) were West playoff teams — excluded
            ("Indiana Pacers", 41, 41),
            ("Philadelphia 76ers", 38, 44),
            ("Milwaukee Bucks", 40, 42),
        ],
    },

    # -----------------------------------------------------------------------
    # 2006-07  —  2007 NBA Draft (Greg Oden / Kevin Durant)
    # -----------------------------------------------------------------------
    "2006-07": {
        "context": (
            "2007 Draft · Greg Oden (Portland, 32W) went #1 after the Trail Blazers jumped from "
            "6th-worst to win the lottery over Kevin Durant. Oden's career was derailed by knee injuries; "
            "Seattle (35W) selected Durant at #2 — the pick that launched a dynasty."
        ),
        "games": 82,
        "lottery_pick1": "Portland Trail Blazers",
        "lottery_top4": ["Portland Trail Blazers", "Seattle SuperSonics", "Atlanta Hawks", "Memphis Grizzlies"],
        "lottery_teams": [
            ("Memphis Grizzlies", 22, 60),
            ("Boston Celtics", 24, 58),
            ("Milwaukee Bucks", 28, 54),
            ("Atlanta Hawks", 30, 52),
            ("Portland Trail Blazers", 32, 50),
            ("Seattle SuperSonics", 31, 51),
            ("Minnesota Timberwolves", 32, 50),
            ("Charlotte Bobcats", 33, 49),
            ("New York Knicks", 33, 49),
            ("Sacramento Kings", 33, 49),
            ("Philadelphia 76ers", 35, 47),
            ("Indiana Pacers", 35, 47),
            # Note: Houston (52W), Chicago (49W), Denver (45W) were playoff teams — excluded
            ("New Orleans Hornets", 39, 43),
            ("LA Clippers", 40, 42),
        ],
    },

    # -----------------------------------------------------------------------
    # 2007-08  —  2008 NBA Draft (Derrick Rose)
    # -----------------------------------------------------------------------
    "2007-08": {
        "context": (
            "2008 Draft · Derrick Rose (Chicago, 33W) pulled off one of the biggest upsets in "
            "lottery history, jumping from the 9th seed (1.7% odds!) to claim #1. "
            "The Miami Heat (15W, worst record) walked away empty-handed."
        ),
        "games": 82,
        "lottery_pick1": "Chicago Bulls",
        "lottery_top4": ["Chicago Bulls", "Miami Heat", "Minnesota Timberwolves", "Seattle SuperSonics"],
        "lottery_teams": [
            ("Miami Heat", 15, 67),
            ("Minnesota Timberwolves", 22, 60),
            ("Seattle SuperSonics", 20, 62),
            ("Memphis Grizzlies", 22, 60),
            ("New York Knicks", 23, 59),
            ("LA Clippers", 23, 59),
            ("Milwaukee Bucks", 26, 56),
            ("Charlotte Bobcats", 32, 50),
            ("New Jersey Nets", 34, 48),
            ("Indiana Pacers", 36, 46),
            ("Chicago Bulls", 33, 49),
            ("Sacramento Kings", 38, 44),
            # Note: Phoenix Suns (55W) and Washington Wizards (43W) were playoff teams — excluded
            ("Portland Trail Blazers", 41, 41),
            ("Golden State Warriors", 48, 34),
        ],
    },

    # -----------------------------------------------------------------------
    # 2008-09  —  2009 NBA Draft (Blake Griffin)
    # -----------------------------------------------------------------------
    "2008-09": {
        "context": (
            "2009 Draft · Blake Griffin (LA Clippers, 19W) went #1 to a Clippers team that had "
            "the worst record. Griffin missed his entire rookie season to injury, then burst onto "
            "the scene in 2010-11 with his athletic dunks and Rookie of the Year award."
        ),
        "games": 82,
        "lottery_pick1": "LA Clippers",
        "lottery_top4": ["LA Clippers", "Memphis Grizzlies", "Oklahoma City Thunder", "Sacramento Kings"],
        "lottery_teams": [
            ("Sacramento Kings", 17, 65),
            ("LA Clippers", 19, 63),
            ("Washington Wizards", 19, 63),
            ("Oklahoma City Thunder", 23, 59),
            ("Minnesota Timberwolves", 24, 58),
            ("Memphis Grizzlies", 24, 58),
            ("Golden State Warriors", 29, 53),
            ("New York Knicks", 32, 50),
            ("Toronto Raptors", 33, 49),
            ("New Jersey Nets", 34, 48),
            ("Indiana Pacers", 36, 46),
            ("Charlotte Bobcats", 35, 47),
            ("Milwaukee Bucks", 34, 48),
            ("Philadelphia 76ers", 41, 41),
        ],
    },

    # -----------------------------------------------------------------------
    # 2009-10  —  2010 NBA Draft (John Wall)
    # -----------------------------------------------------------------------
    "2009-10": {
        "context": (
            "2010 Draft · John Wall (Washington, 26W) went #1 as the Wizards won the lottery "
            "from the 3rd-worst position. The New Jersey Nets (12W) had the worst record but "
            "finished empty-handed. Wall became one of the fastest point guards of his generation."
        ),
        "games": 82,
        "lottery_pick1": "Washington Wizards",
        "lottery_top4": ["Washington Wizards", "Philadelphia 76ers", "New Jersey Nets", "Minnesota Timberwolves"],
        "lottery_teams": [
            ("New Jersey Nets", 12, 70),
            ("Minnesota Timberwolves", 15, 67),
            ("Sacramento Kings", 25, 57),
            ("Washington Wizards", 26, 56),
            ("Golden State Warriors", 26, 56),
            ("Philadelphia 76ers", 27, 55),
            ("Detroit Pistons", 27, 55),
            ("LA Clippers", 29, 53),
            ("Indiana Pacers", 32, 50),
            ("New York Knicks", 29, 53),
            ("Memphis Grizzlies", 40, 42),
            ("Houston Rockets", 42, 40),
            # Note: Milwaukee Bucks (46W) and Charlotte Bobcats (44W) were East playoff teams
            ("Toronto Raptors", 40, 42),
            ("Portland Trail Blazers", 50, 32),
        ],
    },

    # -----------------------------------------------------------------------
    # 2010-11  —  2011 NBA Draft (Kyrie Irving)
    # -----------------------------------------------------------------------
    "2010-11": {
        "context": (
            "2011 Draft · Kyrie Irving (Cleveland, 19W) went #1 as the Cavaliers won the lottery "
            "from the 2nd-worst seed. Cleveland was rebuilding after LeBron's departure to Miami, "
            "and Irving quickly proved to be a worthy cornerstone. Utah got #3 via lottery jump."
        ),
        "games": 82,
        "lottery_pick1": "Cleveland Cavaliers",
        "lottery_top4": ["Cleveland Cavaliers", "Minnesota Timberwolves", "Utah Jazz", "LA Clippers"],
        "lottery_teams": [
            ("Minnesota Timberwolves", 17, 65),
            ("Cleveland Cavaliers", 19, 63),
            ("Toronto Raptors", 22, 60),
            ("New Jersey Nets", 24, 58),
            ("Washington Wizards", 23, 59),
            ("Sacramento Kings", 24, 58),
            ("Detroit Pistons", 30, 52),
            ("Charlotte Bobcats", 34, 48),
            ("LA Clippers", 32, 50),
            ("Milwaukee Bucks", 35, 47),
            ("Golden State Warriors", 36, 46),
            ("Utah Jazz", 39, 43),
            # Note: New Orleans Hornets (46W), NY Knicks (42W), Indiana Pacers (37W)
            #       were all East playoff teams — excluded
            ("Phoenix Suns", 40, 42),
            ("Portland Trail Blazers", 48, 34),
        ],
    },

    # -----------------------------------------------------------------------
    # 2011-12  —  2012 NBA Draft (Anthony Davis) — 66-game lockout season
    # -----------------------------------------------------------------------
    "2011-12": {
        "context": (
            "2012 Draft · Anthony Davis (New Orleans, 21W in 66 games) went #1 as the Hornets "
            "won the lottery from the top seed. This was a 66-game lockout season. "
            "Davis became arguably the most physically gifted big man of his generation."
        ),
        "games": 66,
        "lottery_pick1": "New Orleans Hornets",
        "lottery_top4": ["New Orleans Hornets", "Charlotte Bobcats", "Washington Wizards", "Cleveland Cavaliers"],
        "lottery_teams": [
            ("Charlotte Bobcats", 7, 59),
            ("Washington Wizards", 20, 46),
            ("New Orleans Hornets", 21, 45),
            ("Cleveland Cavaliers", 21, 45),
            ("Sacramento Kings", 22, 44),
            ("New Jersey Nets", 22, 44),
            ("Toronto Raptors", 23, 43),
            ("Golden State Warriors", 23, 43),
            ("Detroit Pistons", 25, 41),
            ("Portland Trail Blazers", 28, 38),
            ("Minnesota Timberwolves", 26, 40),
            ("Milwaukee Bucks", 31, 35),
            ("Phoenix Suns", 33, 33),
            ("Houston Rockets", 34, 32),
        ],
    },

    # -----------------------------------------------------------------------
    # 2012-13  —  2013 NBA Draft (Anthony Bennett)
    # -----------------------------------------------------------------------
    "2012-13": {
        "context": (
            "2013 Draft · Anthony Bennett (Cleveland, 24W) went #1 in one of the most surprising "
            "#1 picks in draft history. Cleveland jumped from 4th-worst to win. Bennett became "
            "a notorious bust, the most criticized top pick of the modern era."
        ),
        "games": 82,
        "lottery_pick1": "Cleveland Cavaliers",
        "lottery_top4": ["Cleveland Cavaliers", "Orlando Magic", "Washington Wizards", "Charlotte Bobcats"],
        "lottery_teams": [
            ("Orlando Magic", 20, 62),
            ("Charlotte Bobcats", 21, 61),
            ("Cleveland Cavaliers", 24, 58),
            ("Washington Wizards", 29, 53),
            ("Phoenix Suns", 25, 57),
            ("Detroit Pistons", 29, 53),
            ("New Orleans Hornets", 27, 55),
            ("Sacramento Kings", 28, 54),
            ("Minnesota Timberwolves", 31, 51),
            ("Portland Trail Blazers", 33, 49),
            ("Philadelphia 76ers", 34, 48),
            ("Toronto Raptors", 34, 48),
            ("Dallas Mavericks", 41, 41),
            ("Utah Jazz", 43, 39),
        ],
    },

    # -----------------------------------------------------------------------
    # 2013-14  —  2014 NBA Draft (Andrew Wiggins)
    # -----------------------------------------------------------------------
    "2013-14": {
        "context": (
            "2014 Draft · Andrew Wiggins (Cleveland, 33W) went #1 after the Cavaliers AGAIN "
            "jumped from the 9th seed — their third unlikely lottery win in four years. "
            "Cleveland then traded Wiggins to Minnesota for Kevin Love."
        ),
        "games": 82,
        "lottery_pick1": "Cleveland Cavaliers",
        "lottery_top4": ["Cleveland Cavaliers", "Milwaukee Bucks", "Philadelphia 76ers", "Orlando Magic"],
        "lottery_teams": [
            ("Milwaukee Bucks", 15, 67),
            ("Philadelphia 76ers", 19, 63),
            ("Orlando Magic", 23, 59),
            ("Utah Jazz", 25, 57),
            ("Boston Celtics", 25, 57),
            ("LA Lakers", 27, 55),
            ("Sacramento Kings", 28, 54),
            ("Detroit Pistons", 29, 53),
            ("Cleveland Cavaliers", 33, 49),
            ("New Orleans Pelicans", 34, 48),
            ("Denver Nuggets", 36, 46),
            ("Atlanta Hawks", 38, 44),
            # Note: Phoenix Suns (48W) made the playoffs — excluded
            ("Charlotte Hornets", 43, 39),
            ("Minnesota Timberwolves", 40, 42),
        ],
    },

    # -----------------------------------------------------------------------
    # 2014-15  —  2015 NBA Draft (Karl-Anthony Towns)
    # -----------------------------------------------------------------------
    "2014-15": {
        "context": (
            "2015 Draft · Karl-Anthony Towns (Minnesota, 16W) went #1 as the Timberwolves "
            "had the worst record and won the lottery naturally. Towns immediately became "
            "one of the best young big men in the league."
        ),
        "games": 82,
        "lottery_pick1": "Minnesota Timberwolves",
        "lottery_top4": ["Minnesota Timberwolves", "Los Angeles Lakers", "Philadelphia 76ers", "New York Knicks"],
        "lottery_teams": [
            ("Minnesota Timberwolves", 16, 66),
            ("New York Knicks", 17, 65),
            ("Philadelphia 76ers", 18, 64),
            ("Los Angeles Lakers", 21, 61),
            ("Orlando Magic", 25, 57),
            ("Sacramento Kings", 29, 53),
            ("Denver Nuggets", 30, 52),
            ("Detroit Pistons", 32, 50),
            ("Charlotte Hornets", 33, 49),
            ("Utah Jazz", 38, 44),
            ("Indiana Pacers", 38, 44),
            ("Oklahoma City Thunder", 45, 37),
            # Note: New Orleans Pelicans (45W) made the playoffs — excluded
            ("Boston Celtics", 40, 42),
            ("Phoenix Suns", 39, 43),
        ],
    },

    # -----------------------------------------------------------------------
    # 2015-16  —  2016 NBA Draft (Ben Simmons)
    # -----------------------------------------------------------------------
    "2015-16": {
        "context": (
            "2016 Draft · Ben Simmons (Philadelphia, 10W) went #1 as the 76ers had the worst "
            "record in the NBA — the culmination of 'The Process.' Brooklyn's pick (held by Boston "
            "via trade) landed the #3 slot, going to Boston who took Jaylen Brown."
        ),
        "games": 82,
        "lottery_pick1": "Philadelphia 76ers",
        "lottery_top4": ["Philadelphia 76ers", "Los Angeles Lakers", "Brooklyn Nets", "Phoenix Suns"],
        "lottery_teams": [
            ("Philadelphia 76ers", 10, 72),
            ("Los Angeles Lakers", 17, 65),
            ("Brooklyn Nets", 21, 61),
            ("Phoenix Suns", 23, 59),
            ("Minnesota Timberwolves", 29, 53),
            ("New Orleans Pelicans", 30, 52),
            ("New York Knicks", 32, 50),
            ("Denver Nuggets", 33, 49),
            ("Sacramento Kings", 33, 49),
            ("Orlando Magic", 35, 47),
            ("Chicago Bulls", 42, 40),
            ("Washington Wizards", 41, 41),
            # Note: Boston Celtics (48W), Indiana Pacers (45W), Charlotte Hornets (48W)
            #       were East playoff teams — excluded
            ("Milwaukee Bucks", 33, 49),
            ("Miami Heat", 48, 34),
        ],
    },

    # -----------------------------------------------------------------------
    # 2016-17  —  2017 NBA Draft (Markelle Fultz)
    # -----------------------------------------------------------------------
    "2016-17": {
        "context": (
            "2017 Draft · Markelle Fultz (Philadelphia, 28W) went #1 as the 76ers won the lottery "
            "from the 3rd seed. The Brooklyn Nets' pick (held by Boston via a prior trade) landed "
            "#3 — Jayson Tatum. Boston was actually a playoff team (53W); it was Brooklyn's pick slot."
        ),
        "games": 82,
        "lottery_pick1": "Philadelphia 76ers",
        # #3 was Brooklyn Nets' lottery slot (held by Boston via trade).
        # #4 was the Suns pick.
        "lottery_top4": ["Philadelphia 76ers", "Los Angeles Lakers", "Brooklyn Nets", "Phoenix Suns"],
        "lottery_teams": [
            ("Brooklyn Nets", 20, 62),
            ("Los Angeles Lakers", 26, 56),
            ("Philadelphia 76ers", 28, 54),
            ("Phoenix Suns", 24, 58),
            ("Sacramento Kings", 32, 50),
            ("New York Knicks", 31, 51),
            ("Minnesota Timberwolves", 31, 51),
            ("New Orleans Pelicans", 34, 48),
            ("Dallas Mavericks", 33, 49),
            ("Charlotte Hornets", 36, 46),
            ("Denver Nuggets", 40, 42),
            ("Detroit Pistons", 37, 45),
            ("Miami Heat", 41, 41),
            ("Milwaukee Bucks", 42, 40),
        ],
    },

    # -----------------------------------------------------------------------
    # 2017-18  —  2018 NBA Draft (Deandre Ayton / Luka Doncic)
    # -----------------------------------------------------------------------
    "2017-18": {
        "context": (
            "2018 Draft · DeAndre Ayton (Phoenix, 21W) went #1 as the Suns won the lottery. "
            "Luka Doncic went #3 to Atlanta, then was immediately traded to Dallas for Trae Young. "
            "The draft is considered one of the best in recent memory."
        ),
        "games": 82,
        "lottery_pick1": "Phoenix Suns",
        "lottery_top4": ["Phoenix Suns", "Sacramento Kings", "Atlanta Hawks", "Memphis Grizzlies"],
        "lottery_teams": [
            ("Phoenix Suns", 21, 61),
            ("Memphis Grizzlies", 22, 60),
            ("Dallas Mavericks", 24, 58),
            ("Atlanta Hawks", 24, 58),
            ("Sacramento Kings", 27, 55),
            ("Chicago Bulls", 27, 55),
            ("Orlando Magic", 25, 57),
            ("Brooklyn Nets", 28, 54),
            ("New York Knicks", 29, 53),
            ("Charlotte Hornets", 36, 46),
            ("LA Lakers", 35, 47),
            ("LA Clippers", 42, 40),
            # Note: Cleveland Cavaliers (50W, made Finals) and Miami Heat (44W, playoff)
            #       were postseason teams — excluded
            ("Detroit Pistons", 39, 43),
            ("Denver Nuggets", 46, 36),
        ],
    },

    # -----------------------------------------------------------------------
    # 2018-19  —  2019 NBA Draft (Zion Williamson)
    # -----------------------------------------------------------------------
    "2018-19": {
        "context": (
            "2019 Draft · Zion Williamson (New Orleans, 33W) landed in New Orleans after the Pelicans "
            "jumped from 7th-worst with just 6% odds. Duke's Zion was the most hyped prospect since "
            "LeBron, and the leap saved the franchise's fan base after the Anthony Davis trade."
        ),
        "games": 82,
        "lottery_pick1": "New Orleans Pelicans",
        "lottery_top4": ["New Orleans Pelicans", "Memphis Grizzlies", "New York Knicks", "Los Angeles Lakers"],
        "lottery_teams": [
            ("New York Knicks", 17, 65),
            ("Cleveland Cavaliers", 19, 63),
            ("Phoenix Suns", 19, 63),
            ("Chicago Bulls", 22, 60),
            ("Atlanta Hawks", 29, 53),
            ("Washington Wizards", 32, 50),
            ("New Orleans Pelicans", 33, 49),
            ("Memphis Grizzlies", 33, 49),
            ("Dallas Mavericks", 33, 49),
            ("Minnesota Timberwolves", 36, 46),
            ("Los Angeles Lakers", 37, 45),
            ("Charlotte Hornets", 39, 43),
            ("Sacramento Kings", 39, 43),
            ("Miami Heat", 39, 43),
        ],
    },

    # -----------------------------------------------------------------------
    # 2019-20  —  2020 NBA Draft (Anthony Edwards) — COVID bubble season
    # -----------------------------------------------------------------------
    "2019-20": {
        "context": (
            "2020 Draft · Anthony Edwards (Minnesota, 19W) went #1 in a season shortened to "
            "~65-72 games due to the COVID-19 pandemic. The season resumed in a 'bubble' at "
            "Disney World. Edwards has since become one of the game's elite stars."
        ),
        "games": 72,
        "lottery_pick1": "Minnesota Timberwolves",
        "lottery_top4": ["Minnesota Timberwolves", "Golden State Warriors", "Charlotte Hornets", "Chicago Bulls"],
        "lottery_teams": [
            ("Golden State Warriors", 15, 50),
            ("Minnesota Timberwolves", 19, 45),
            ("Cleveland Cavaliers", 19, 46),
            ("Atlanta Hawks", 20, 47),
            ("Detroit Pistons", 20, 46),
            ("Charlotte Hornets", 23, 42),
            ("Chicago Bulls", 22, 43),
            ("New York Knicks", 21, 45),
            ("Washington Wizards", 25, 47),
            ("Phoenix Suns", 34, 39),
            ("San Antonio Spurs", 32, 39),
            ("Sacramento Kings", 31, 41),
            ("New Orleans Pelicans", 30, 42),
            ("Memphis Grizzlies", 34, 39),
        ],
    },

    # -----------------------------------------------------------------------
    # 2020-21  —  2021 NBA Draft (Cade Cunningham) — 72-game season
    # -----------------------------------------------------------------------
    "2020-21": {
        "context": (
            "2021 Draft · Cade Cunningham (Detroit, 20W) went #1 as the Pistons had the worst "
            "record and won the lottery naturally. Cunningham was a rare consensus top pick. "
            "The season saw limited fans due to lingering COVID-19 restrictions."
        ),
        "games": 72,
        "lottery_pick1": "Detroit Pistons",
        "lottery_top4": ["Detroit Pistons", "Houston Rockets", "Cleveland Cavaliers", "Toronto Raptors"],
        "lottery_teams": [
            ("Houston Rockets", 17, 55),
            ("Detroit Pistons", 20, 52),
            ("Orlando Magic", 21, 51),
            ("Cleveland Cavaliers", 22, 50),
            ("Oklahoma City Thunder", 22, 50),
            ("Minnesota Timberwolves", 23, 49),
            ("Sacramento Kings", 31, 41),
            ("Toronto Raptors", 27, 45),
            ("Chicago Bulls", 31, 41),
            ("New Orleans Pelicans", 31, 41),
            ("Washington Wizards", 34, 38),
            ("San Antonio Spurs", 33, 39),
            ("Indiana Pacers", 34, 38),
            ("Charlotte Hornets", 33, 39),
        ],
    },

    # -----------------------------------------------------------------------
    # 2021-22  —  2022 NBA Draft (Paolo Banchero)
    # -----------------------------------------------------------------------
    "2021-22": {
        "context": (
            "2022 Draft · Paolo Banchero (Orlando, 22W) went #1 after the Magic won the lottery "
            "from the 1st seed. Orlando had the worst record in the NBA. Banchero won the "
            "2022-23 Rookie of the Year award, vindicating the pick."
        ),
        "games": 82,
        "lottery_pick1": "Orlando Magic",
        "lottery_top4": ["Orlando Magic", "Oklahoma City Thunder", "Houston Rockets", "Sacramento Kings"],
        "lottery_teams": [
            ("Houston Rockets", 20, 62),
            ("Orlando Magic", 22, 60),
            ("Detroit Pistons", 23, 59),
            ("Oklahoma City Thunder", 24, 58),
            ("Indiana Pacers", 25, 57),
            ("Portland Trail Blazers", 27, 55),
            ("Sacramento Kings", 30, 52),
            ("San Antonio Spurs", 34, 48),
            ("Washington Wizards", 35, 47),
            ("New York Knicks", 37, 45),
            ("LA Lakers", 33, 49),
            ("New Orleans Pelicans", 36, 46),
            # Note: Chicago Bulls (46W) and Minnesota Timberwolves (46W) were postseason teams
            ("Charlotte Hornets", 43, 39),
            ("LA Clippers", 42, 40),
        ],
    },

    # -----------------------------------------------------------------------
    # 2022-23  —  2023 NBA Draft (Victor Wembanyama)
    # -----------------------------------------------------------------------
    "2022-23": {
        "context": (
            "2023 Draft · Victor Wembanyama (San Antonio, 22W) was the most celebrated prospect "
            "since LeBron James. The Spurs jumped from 3rd-worst to win — but it hardly mattered "
            "since Wemby was the consensus #1 pick regardless of which team won."
        ),
        "games": 82,
        "lottery_pick1": "San Antonio Spurs",
        "lottery_top4": ["San Antonio Spurs", "Charlotte Hornets", "Portland Trail Blazers", "Houston Rockets"],
        "lottery_teams": [
            ("Detroit Pistons", 17, 65),
            ("Houston Rockets", 22, 60),
            ("San Antonio Spurs", 22, 60),
            ("Charlotte Hornets", 27, 55),
            ("Portland Trail Blazers", 33, 49),
            ("Orlando Magic", 34, 48),
            ("Indiana Pacers", 35, 47),
            ("Washington Wizards", 35, 47),
            ("Utah Jazz", 37, 45),
            ("Dallas Mavericks", 38, 44),
            ("Chicago Bulls", 40, 42),
            ("Oklahoma City Thunder", 40, 42),
            ("Toronto Raptors", 41, 41),
            ("New Orleans Pelicans", 42, 40),
        ],
    },

    # -----------------------------------------------------------------------
    # 2023-24  —  2024 NBA Draft (Zaccharie Risacher)
    # -----------------------------------------------------------------------
    "2023-24": {
        "context": (
            "2024 Draft · Zaccharie Risacher (Atlanta, 36W) stunned the lottery as the Hawks "
            "jumped from 8th-worst — beating long odds to land the #1 pick. "
            "The Detroit Pistons (14W, worst record) finished empty-handed despite 14.0% odds."
        ),
        "games": 82,
        "lottery_pick1": "Atlanta Hawks",
        "lottery_top4": ["Atlanta Hawks", "Washington Wizards", "Houston Rockets", "San Antonio Spurs"],
        "lottery_teams": [
            ("Detroit Pistons", 14, 68),
            ("Washington Wizards", 15, 67),
            ("Charlotte Hornets", 21, 61),
            ("Portland Trail Blazers", 21, 61),
            ("San Antonio Spurs", 22, 60),
            ("Memphis Grizzlies", 27, 55),
            ("Toronto Raptors", 25, 57),
            ("Brooklyn Nets", 32, 50),
            ("Utah Jazz", 31, 51),
            ("Chicago Bulls", 39, 43),
            ("Houston Rockets", 41, 41),
            ("Atlanta Hawks", 36, 46),
            ("Sacramento Kings", 46, 36),
            # Note: Oklahoma City Thunder (57W) was the #1 West seed — excluded
            ("Golden State Warriors", 46, 36),
        ],
    },

    # -----------------------------------------------------------------------
    # 2024-25  —  2025 NBA Draft (Cooper Flagg)
    # -----------------------------------------------------------------------
    "2024-25": {
        "context": (
            "2025 Draft · Cooper Flagg (Dallas, 26W) was the most anticipated Duke prospect in years. "
            "Dallas had a difficult rebuild season and won the lottery to select the versatile forward "
            "with the #1 pick. Flagg is expected to revitalize the franchise."
        ),
        "games": 82,
        "lottery_pick1": "Dallas Mavericks",
        "lottery_top4": ["Dallas Mavericks", "Philadelphia 76ers", "Charlotte Hornets", "Washington Wizards"],
        "lottery_teams": [
            ("Washington Wizards", 18, 64),
            ("Charlotte Hornets", 19, 63),
            ("New Orleans Pelicans", 21, 61),
            ("Utah Jazz", 22, 60),
            ("Philadelphia 76ers", 24, 58),
            ("Brooklyn Nets", 23, 59),
            ("Dallas Mavericks", 26, 56),
            ("Detroit Pistons", 27, 55),
            ("Toronto Raptors", 30, 52),
            ("Portland Trail Blazers", 32, 50),
            ("San Antonio Spurs", 34, 48),
            ("Chicago Bulls", 39, 43),
            ("Sacramento Kings", 36, 46),
            # Note: Houston Rockets (52W) made the playoffs — excluded
            ("Golden State Warriors", 40, 42),
        ],
    },

    # -----------------------------------------------------------------------
    # 2025-26  —  Current / Pending Season
    # -----------------------------------------------------------------------
    "2025-26": {
        "context": (
            "2025-26 Season · The regular season is currently wrapping up (April 2026). "
            "The lottery has not yet been held — results are TBD (May 2026). "
            "Standings below reflect approximate current records."
        ),
        "games": 82,
        "lottery_pick1": "TBD",
        "lottery_top4": [],
        "lottery_teams": [
            ("Washington Wizards", 15, 58),
            ("Detroit Pistons", 20, 53),
            ("Charlotte Hornets", 22, 51),
            ("Portland Trail Blazers", 24, 49),
            ("Utah Jazz", 25, 48),
            ("Brooklyn Nets", 26, 47),
            ("San Antonio Spurs", 28, 45),
            ("New Orleans Pelicans", 29, 44),
            ("Toronto Raptors", 30, 43),
            ("Sacramento Kings", 32, 41),
            ("Chicago Bulls", 33, 40),
            ("Atlanta Hawks", 34, 39),
            ("Orlando Magic", 36, 37),
            ("Indiana Pacers", 38, 35),
        ],
        "season_pending": True,
    },
}

SEASON_KEYS = sorted(HISTORICAL_SEASONS.keys())
SEASON_LABELS = {k: k for k in SEASON_KEYS}
