// ESPN requests (SPEC section 4). They run in the side panel with the ESPN login of the user.
// The browser attaches the cookies, so this code never reads, stores or sends espn_s2.
// The only cookie that this code reads is SWID. SWID says who the user is.
// SWID is an id. It is not a login credential.

export const ESPN_API = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl";

// The user has no ESPN login, or the account cannot see the league.
export class EspnAuthError extends Error {}
// ESPN answered with an error status.
export class EspnHttpError extends Error {
  constructor(status) {
    super(`ESPN answered HTTP ${status}`);
    this.status = status;
  }
}
// ESPN answered 200, but the answer is not JSON. An example is a login page.
export class EspnFormatError extends Error {}

// The NFL names a season after the year in which it starts.
// From June on, the new season applies, because leagues exist before the September kickoff.
export function defaultSeason(now = new Date()) {
  return now.getMonth() >= 5 ? now.getFullYear() : now.getFullYear() - 1;
}

// https://fantasy.espn.com/football/team?leagueId=1669256142&seasonId=2026&teamId=16
export function parseEspnUrl(url) {
  try {
    const u = new URL(url);
    if (!u.hostname.endsWith("espn.com")) return null;
    const leagueId = u.searchParams.get("leagueId");
    if (!leagueId || !/^\d+$/.test(leagueId)) return null;
    const teamId = u.searchParams.get("teamId");
    const seasonId = u.searchParams.get("seasonId");
    return {
      leagueId,
      teamId: teamId && /^\d+$/.test(teamId) ? teamId : "",
      season: seasonId && /^\d+$/.test(seasonId) ? Number(seasonId) : null,
    };
  } catch {
    return null;
  }
}

export function leagueUrl(season, leagueId, views, extra = {}) {
  const params = new URLSearchParams();
  for (const view of views) params.append("view", view);
  for (const [key, value] of Object.entries(extra)) params.append(key, String(value));
  return `${ESPN_API}/seasons/${season}/segments/0/leagues/${leagueId}?${params}`;
}

export function scheduleUrl(season) {
  return `${ESPN_API}/seasons/${season}?view=proTeamSchedules_wl`;
}

export const FREE_AGENT_FILTER = {
  players: {
    filterStatus: { value: ["FREEAGENT", "WAIVERS"] },
    limit: 100,
    sortPercOwned: { sortPriority: 1, sortAsc: false },
  },
};

async function getJson(url, headers = {}, fetchFn = fetch) {
  const response = await fetchFn(url, { credentials: "include", headers: { Accept: "application/json", ...headers } });
  if (response.status === 401 || response.status === 403) throw new EspnAuthError();
  if (!response.ok) throw new EspnHttpError(response.status);
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new EspnFormatError("ESPN did not return JSON. You may be logged out of espn.com.");
  }
}

// One request with the views that the analysis needs.
// The scoring period defaults to the current NFL week. ESPN reports the week in `scoringPeriodId`.
export function fetchLeague(season, leagueId, fetchFn = fetch) {
  return getJson(leagueUrl(season, leagueId, ["mSettings", "mTeam", "mRoster", "mMatchupScore"]), {}, fetchFn);
}

export function fetchProSchedule(season, fetchFn = fetch) {
  return getJson(scheduleUrl(season), {}, fetchFn);
}

export function fetchFreeAgents(season, leagueId, week, fetchFn = fetch) {
  const url = leagueUrl(season, leagueId, ["kona_player_info"], { scoringPeriodId: week });
  return getJson(url, { "x-fantasy-filter": JSON.stringify(FREE_AGENT_FILTER) }, fetchFn);
}

// SWID looks like {XXXXXXXX-XXXX-...}. Chrome can show it URL-encoded.
export async function readSwid(cookiesApi = chrome.cookies) {
  try {
    const cookie = await cookiesApi.get({ url: "https://www.espn.com", name: "SWID" });
    return cookie ? decodeURIComponent(cookie.value) : "";
  } catch {
    return "";
  }
}
