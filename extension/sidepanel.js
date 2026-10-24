// Side panel UI. The panel requests nothing from ESPN until the user clicks "Analyze".
// The panel calls the AI only when the user clicks "Explain with AI".
import {
  EspnAuthError,
  EspnFormatError,
  EspnHttpError,
  defaultSeason,
  fetchFreeAgents,
  fetchLeague,
  fetchProSchedule,
  parseEspnUrl,
  readSwid,
} from "./espn.js";
import { ServiceDownError, ServiceError, analyze, explain, health } from "./service.js";

const DEFAULT_BASE = "http://127.0.0.1:8765";
const ANTHROPIC_MODELS = ["claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-5-5", "claude-fable-5-1"];

const $ = (id) => document.getElementById(id);
const el = {
  leagueSelect: $("league-select"), leagueInput: $("league-input"), season: $("season"), teamId: $("team-id"),
  analyze: $("analyze"), status: $("status"), results: $("results"), serviceStatus: $("service-status"),
  explainBar: $("explain-bar"), explain: $("explain"), explainHint: $("explain-hint"),
  aiProvider: $("ai-provider"), aiKey: $("ai-key"), aiModel: $("ai-model"), aiBase: $("ai-base"),
  aiBaseRow: $("ai-base-row"), presets: $("model-presets"), serviceBase: $("service-base"),
};

// leagues is a list of {id, teamId}. selected is a league id, or "all".
const state = {
  leagues: [], selected: "all", season: defaultSeason(), serviceBase: DEFAULT_BASE,
  ai: { provider: "anthropic", apiKey: "", model: ANTHROPIC_MODELS[0], baseUrl: "" },
  results: [], // [{league, result}] from the last Analyze click
};

// A small DOM helper. It writes text only, so ESPN data never goes through innerHTML.
function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "class") node.className = value;
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// Storage
async function load() {
  try {
    const saved = await chrome.storage.local.get(["leagues", "selected", "season", "ai", "serviceBase"]);
    Object.assign(state, {
      leagues: saved.leagues ?? state.leagues,
      selected: saved.selected ?? state.selected,
      season: saved.season ?? state.season,
      serviceBase: saved.serviceBase ?? state.serviceBase,
      ai: { ...state.ai, ...(saved.ai ?? {}) },
    });
  } catch {
    // Storage can be unavailable. The panel then works with the defaults.
  }
}
const save = () => chrome.storage.local.set({
  leagues: state.leagues, selected: state.selected, season: state.season, ai: state.ai, serviceBase: state.serviceBase,
}).catch(() => {});

// Status line
function setStatus(text, isError = false) {
  el.status.textContent = text;
  el.status.className = isError ? "error" : "";
}

function describeError(error) {
  if (error instanceof ServiceDownError) return error.message;
  if (error instanceof EspnAuthError) {
    return "ESPN says you are not logged in, or this account cannot see the league.\nOpen espn.com, log in, then click Analyze again.";
  }
  if (error instanceof EspnHttpError) return `${error.message}. Check the league id and season.`;
  if (error instanceof EspnFormatError) return error.message;
  if (error instanceof ServiceError) {
    if (error.kind === "parse") {
      return `ESPN's data was not what ffai expected:\n${error.message}\nIf this says SWID, type your team id in the Team id box.`;
    }
    return error.message;
  }
  return `Unexpected error: ${error && error.message ? error.message : error}`;
}

// League list
function currentLeague() {
  return state.leagues.find((l) => l.id === state.selected) ?? null;
}

function renderLeagues() {
  el.leagueSelect.replaceChildren(
    h("option", { value: "all" }, state.leagues.length > 1 ? "All leagues" : "(add a league below)"),
    ...state.leagues.map((l) => h("option", { value: l.id }, `League ${l.id}`)),
  );
  if (state.selected !== "all" && !currentLeague()) state.selected = "all";
  el.leagueSelect.value = state.selected;
  el.season.value = state.season;
  const league = currentLeague();
  el.teamId.value = league ? league.teamId : "";
  el.teamId.disabled = !league;
}

function addLeague(id, teamId = "") {
  if (!/^\d+$/.test(id)) return setStatus("A league id is a number, for example 1669256142.", true);
  const existing = state.leagues.find((l) => l.id === id);
  if (existing) {
    if (teamId) existing.teamId = teamId;
  } else {
    state.leagues.push({ id, teamId });
  }
  state.selected = id;
  save();
  renderLeagues();
  setStatus("");
}

// AI settings
function renderAi() {
  const { provider, apiKey, model, baseUrl } = state.ai;
  el.aiProvider.value = provider;
  el.aiKey.value = apiKey;
  el.aiModel.value = model;
  el.aiBase.value = baseUrl;
  el.aiBaseRow.hidden = provider !== "openai";
  el.presets.replaceChildren(...(provider === "anthropic" ? ANTHROPIC_MODELS : []).map((m) => h("option", { value: m })));
  el.aiModel.placeholder = provider === "openai" ? "for example deepseek-chat" : "";
  updateExplainState();
}

function aiReady() {
  return Boolean(state.ai.apiKey && state.ai.model);
}

function updateExplainState() {
  el.explainBar.hidden = state.results.length === 0;
  el.explain.disabled = !aiReady();
  el.explainHint.textContent = aiReady() ? "" : "Enter an API key and a model in AI settings.";
}

// Render the result
const fmt = (n) => (n === null || n === undefined ? "-" : Number(n).toFixed(1));

function gameCell(p) {
  if (p.bye) return "BYE";
  if (!p.kickoff) return "-";
  const when = new Date(p.kickoff).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
  return p.started ? `${when} (started)` : when;
}

function statusTag(injury) {
  if (injury === "ACTIVE") return "";
  const level = ["OUT", "INJURY_RESERVE", "SUSPENSION"].includes(injury) ? "out" : "soft";
  return h("span", { class: `tag ${level}` }, injury.replace("INJURY_RESERVE", "IR").replace("QUESTIONABLE", "Q").replace("DOUBTFUL", "D"));
}

function playerTable(players) {
  return h(
    "table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Slot"), h("th", {}, "Player"), h("th", {}, "Status"), h("th", { class: "num" }, "Proj"), h("th", { class: "num" }, "Pts"), h("th", {}, "Game"))),
    h("tbody", {}, players.map((p) => h(
      "tr", {},
      h("td", {}, p.slot),
      h("td", {}, `${p.name} `, h("span", { class: "muted" }, [p.position, p.pro_team].filter(Boolean).join(" "))),
      h("td", {}, statusTag(p.injury)),
      h("td", { class: "num" }, fmt(p.projected)),
      h("td", { class: "num" }, fmt(p.actual)),
      h("td", {}, gameCell(p)),
    ))),
  );
}

function freeAgentTable(agents) {
  return h(
    "table", {},
    h("thead", {}, h("tr", {}, h("th", {}, "Player"), h("th", {}, "Status"), h("th", { class: "num" }, "% own"), h("th", { class: "num" }, "Change"))),
    h("tbody", {}, agents.map((a) => h(
      "tr", {},
      h("td", {}, `${a.name} `, h("span", { class: "muted" }, [a.position, a.pro_team].filter(Boolean).join(" ")), " ", statusTag(a.injury)),
      h("td", {}, a.status === "WAIVERS" ? "waivers" : "free"),
      h("td", { class: "num" }, fmt(a.percent_owned)),
      h("td", { class: "num" }, (a.percent_change > 0 ? "+" : "") + fmt(a.percent_change)),
    ))),
  );
}

function resultCard(league, result) {
  const card = h("article", { class: "card", "data-league": league.id });
  card.append(h("h2", {}, `${result.team.name}`), h("div", { class: "muted" }, `${result.league.name} - week ${result.league.week}`));
  const warnings = result.warnings.length
    ? h("ul", { class: "warnings" }, result.warnings.map((w) => h("li", { class: w.level }, w.text)))
    : h("p", { class: "muted" }, "No problems found by the checks that exist so far.");
  card.append(warnings, h("h3", {}, "Starting lineup"), playerTable(result.starters));
  if (result.bench.length) card.append(h("details", {}, h("summary", {}, `Bench (${result.bench.length})`), playerTable(result.bench)));
  if (result.ir.length) card.append(h("details", {}, h("summary", {}, `IR (${result.ir.length})`), playerTable(result.ir)));
  if (result.free_agents.length) card.append(h("details", {}, h("summary", {}, "Top free agents by ownership"), freeAgentTable(result.free_agents)));
  if (result.pending.length) card.append(h("p", { class: "muted" }, `Not checked yet: ${result.pending.join(", ")}.`));
  card.append(h("div", { class: "explain-slot" }));
  return card;
}

function errorCard(league, error) {
  return h("article", { class: "card" }, h("h2", {}, `League ${league.id}`), h("div", { class: "error-card" }, describeError(error)));
}

// Analyze
async function runAnalyze() {
  const targets = state.selected === "all" ? state.leagues : [currentLeague()].filter(Boolean);
  if (!targets.length) return setStatus("Add a league id first.", true);

  el.analyze.disabled = true;
  el.explain.disabled = true;
  el.results.replaceChildren();
  state.results = [];
  let failures = 0;
  try {
    const base = state.serviceBase.replace(/\/$/, "");
    setStatus("Checking the ffai service...");
    await health(base); // Fail fast, before any ESPN request.
    const swid = await readSwid();
    let schedule = null;
    for (const league of targets) {
      try {
        setStatus(`League ${league.id}: reading ESPN...`);
        const raw = await fetchLeague(state.season, league.id);
        schedule ??= await fetchProSchedule(state.season);
        // Free agents are optional. When this request fails, the rest still works.
        const freeAgents = await fetchFreeAgents(state.season, league.id, raw.scoringPeriodId).catch(() => null);
        setStatus(`League ${league.id}: analyzing...`);
        const result = await analyze(base, {
          league: raw, pro_schedule: schedule, free_agents: freeAgents, swid, team_id: league.teamId || undefined,
        });
        state.results.push({ league, result });
        el.results.append(resultCard(league, result));
      } catch (error) {
        failures += 1;
        el.results.append(errorCard(league, error));
        // The next league cannot work when the service is down, so stop here.
        if (error instanceof ServiceDownError) break;
      }
    }
    setStatus(failures ? `Done, with ${failures} problem${failures > 1 ? "s" : ""}.` : "Done.", failures > 0);
  } catch (error) {
    setStatus(describeError(error), true);
    refreshServiceStatus();
  } finally {
    el.analyze.disabled = false;
    updateExplainState();
  }
}

// Explain
async function runExplain() {
  if (!aiReady() || !state.results.length) return;
  el.explain.disabled = true;
  el.analyze.disabled = true;
  try {
    const base = state.serviceBase.replace(/\/$/, "");
    for (const { league, result } of state.results) {
      const slot = el.results.querySelector(`[data-league="${league.id}"] .explain-slot`);
      setStatus(`League ${league.id}: asking the AI...`);
      try {
        const out = await explain(base, result, {
          provider: state.ai.provider, api_key: state.ai.apiKey, model: state.ai.model, base_url: state.ai.baseUrl,
        });
        const source = out.source === "ai" ? `AI (${state.ai.model})` : `Template - AI not used: ${out.error}`;
        slot.replaceChildren(h("div", { class: "explain" }, h("span", { class: "src" }, source), out.text));
      } catch (error) {
        slot.replaceChildren(h("div", { class: "error-card" }, describeError(error)));
      }
    }
    setStatus("Done.");
  } finally {
    el.analyze.disabled = false;
    updateExplainState();
  }
}

// Service status. This is a local ping only. It sends no ESPN request.
async function refreshServiceStatus() {
  try {
    await health(state.serviceBase.replace(/\/$/, ""));
    el.serviceStatus.textContent = "service: running";
    el.serviceStatus.className = "pill ok";
  } catch {
    el.serviceStatus.textContent = "service: not running";
    el.serviceStatus.className = "pill down";
  }
}

// Wiring
function bind() {
  $("add-league").addEventListener("click", () => {
    addLeague(el.leagueInput.value.trim());
    el.leagueInput.value = "";
  });
  $("use-tab").addEventListener("click", async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const found = tab && tab.url ? parseEspnUrl(tab.url) : null;
    if (!found) return setStatus("The current tab is not an ESPN fantasy league page (the address needs leagueId=...).", true);
    if (found.season) state.season = found.season;
    addLeague(found.leagueId, found.teamId);
  });
  $("remove-league").addEventListener("click", () => {
    state.leagues = state.leagues.filter((l) => l.id !== state.selected);
    state.selected = "all";
    save();
    renderLeagues();
  });
  el.leagueSelect.addEventListener("change", () => { state.selected = el.leagueSelect.value; save(); renderLeagues(); });
  el.season.addEventListener("change", () => { state.season = Number(el.season.value) || defaultSeason(); save(); });
  el.teamId.addEventListener("change", () => {
    const league = currentLeague();
    if (league) { league.teamId = el.teamId.value.trim().replace(/\D/g, ""); save(); renderLeagues(); }
  });
  el.analyze.addEventListener("click", runAnalyze);
  el.explain.addEventListener("click", runExplain);

  el.aiProvider.addEventListener("change", () => {
    state.ai.provider = el.aiProvider.value;
    state.ai.model = state.ai.provider === "anthropic" ? ANTHROPIC_MODELS[0] : "";
    save();
    renderAi();
  });
  for (const [input, field] of [[el.aiKey, "apiKey"], [el.aiModel, "model"], [el.aiBase, "baseUrl"]]) {
    input.addEventListener("input", () => { state.ai[field] = input.value.trim(); save(); updateExplainState(); });
  }
  el.serviceBase.addEventListener("change", () => {
    state.serviceBase = el.serviceBase.value.trim() || DEFAULT_BASE;
    save();
    refreshServiceStatus();
  });
}

await load();
renderLeagues();
renderAi();
el.serviceBase.value = state.serviceBase;
bind();
refreshServiceStatus();
