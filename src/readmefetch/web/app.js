/* readmefetch web: edit readmefetch.toml with a live preview.
 *
 * The config lives here as the same JSON shape the server's config.to_dict() returns.
 * Every change re-renders through the server (POST /api/render), so the preview is the
 * exact SVG the command line would write. No framework: h() builds elements.
 */
"use strict";

const API_VERSION = 2; // must match web.py's API_VERSION: what /api/state sends

// ---- small helpers ------------------------------------------------------------------

function h(tag, props, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k === "style") Object.assign(el.style, v);
    else if (k === "value") el.value = v;
    else if (k === "checked") el.checked = Boolean(v);
    else if (k === "dataset") Object.assign(el.dataset, v);
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : String(kid));
  }
  return el;
}
const $ = (sel) => document.querySelector(sel);
const SVG_NS = "http://www.w3.org/2000/svg";

// An icon from a {box, svg} record (the vendored icon sets), drawn in the current text colour.
function svgIcon(rec, cls = "oct") {
  const el = document.createElementNS(SVG_NS, "svg");
  el.setAttribute("viewBox", rec.box.join(" "));
  el.setAttribute("aria-hidden", "true");
  el.setAttribute("class", cls);
  el.innerHTML = rec.svg;
  return el;
}
const oct = (name) => (S.meta?.ui_icons?.[name] ? svgIcon(S.meta.ui_icons[name]) : null);
const clone = (x) => JSON.parse(JSON.stringify(x));
const sentence = (t) => (t ? t[0].toUpperCase() + t.slice(1) + "." : "");

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const type = res.headers.get("Content-Type") || "";
  if (type.startsWith("application/json")) return res.json();
  if (!res.ok) return { ok: false, error: `${res.status} ${res.statusText}` };
  return { ok: true, blob: await res.blob() };
}

function download(name, data, type) {
  const url = URL.createObjectURL(data instanceof Blob ? data : new Blob([data], { type }));
  const a = h("a", { href: url, download: name });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function copy(text, what) {
  try {
    await navigator.clipboard.writeText(text);
    flash(`Copied the ${what}.`, "success", 2500);
  } catch {
    dialog(`Copy the ${what}`, [h("textarea", { class: "form-control", readonly: true, value: text })], [{ label: "Close" }]);
  }
}

let flashTimer = 0;
function flash(message, kind = "error", ms = 0, action = null) {
  const el = $("#flash");
  clearTimeout(flashTimer);
  if (!message && S.meta && S.meta.api !== API_VERSION) message = STALE_SERVER; // keep that one up: nothing works right
  if (!message) { el.hidden = true; return; }
  el.className = `flash ${kind}`;
  el.replaceChildren(h("span", { class: "flash-text", text: message }),
    ...(action ? [h("button", { type: "button", class: "btn btn-sm", onclick: () => { el.hidden = true; action.onclick(); } }, action.label)] : []));
  el.hidden = false;
  if (ms) flashTimer = setTimeout(() => { el.hidden = true; }, ms);
}

function dialog(title, body, actions) {
  const dlg = $("#dialog");
  $("#dialog-title").textContent = title;
  $("#dialog-body").replaceChildren(...body);
  $("#dialog-actions").replaceChildren(...actions.map((a) => h("button", {
    type: a.submit ? "submit" : "button",
    class: `btn${a.primary ? " btn-primary" : ""}${a.danger ? " btn-danger" : ""}`,
    onclick: async (e) => {
      e.preventDefault();
      if (a.onclick && (await a.onclick()) === false) return;
      dlg.close();
    },
  }, a.label)));
  dlg.showModal();
}

// ---- state ----------------------------------------------------------------------------

const S = {
  meta: null,        // themes, logo catalogue, fonts, defaults ... from /api/state
  cfg: null,         // the config being edited
  live: false,       // fetch live GitHub numbers
  tab: "profile",
  last: null,        // last successful render
  seq: 0,
  timer: 0,
  url: "",
  dirty: false,
  focus: null,       // the last focused text input (placeholder chips insert there)
  search: "",
};

const TABS = [
  ["profile", "Profile", "person"], ["info", "Info", "list-unordered"], ["logos", "Logos", "image"], ["motion", "Motion", "play"],
  ["look", "Look", "paintbrush"], ["window", "Window", "browser"], ["badges", "Badges", "tag"], ["editor", "Draw", "pencil"],
];

function setDirty(v) {
  S.dirty = v;
  document.body.classList.toggle("is-dirty", v);
}

function changed() {
  setDirty(true);
  clearTimeout(S.timer);
  S.timer = setTimeout(renderPreview, 250);
}

function refresh() {
  const panel = $("#panel");
  const top = panel.scrollTop;
  let kids;
  try {
    kids = TAB_VIEWS[S.tab]();
  } catch (e) {
    // Never fail silently: say which tab broke and why, and keep the rest of the app usable.
    console.error(e);
    const label = (TABS.find(([name]) => name === S.tab) || [, S.tab])[1];
    kids = h("div", { class: "section" }, callout("danger", "alert",
      `The ${label} tab couldn't open: ${e.message}. `,
      S.meta.api === API_VERSION ? "Please report this." : STALE_SERVER));
  }
  panel.replaceChildren(...[kids].flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false));
  panel.scrollTop = top;
  if (S.tab === "badges" && S.last) drawBadgePreviews();
}

const STALE_SERVER = "The readmefetch server running this page is older than the page. Stop it (Ctrl+C), "
  + "start `readmefetch web` again, then reload this tab.";

function showTab(name) {
  S.tab = name;
  for (const b of document.querySelectorAll(".tab")) b.setAttribute("aria-selected", String(b.dataset.tab === name));
  $("#panel").scrollTop = 0;
  refresh();
  if (S.last) drawBadgePreviews();
}

// ---- colours (mirrors themes.py) --------------------------------------------------------

const ALIASES = { default: "fg", gray: "bright-black", grey: "bright-black", foreground: "fg" };
function normalizeColor(name) {
  const n = String(name || "").trim().toLowerCase().replace(/_/g, "-").replace(/^(light|bright)-?/, "bright-");
  return ALIASES[n] || n;
}
function expandHex(c) {
  return c.length === 4 ? "#" + [...c.slice(1)].map((x) => x + x).join("") : c;
}
function resolveIn(c, pal) {
  const s = String(c || "").trim();
  if (/^#([0-9a-f]{3}){1,2}$/i.test(s)) return expandHex(s.toLowerCase());
  return pal[normalizeColor(s)] || null;
}
function palette() {
  const pal = { ...(S.meta.themes[S.cfg.theme] || S.meta.themes["github-dark"]) };
  for (const [k, v] of Object.entries(S.cfg.colors || {})) {
    const key = normalizeColor(k);
    const hex = resolveIn(v, pal);
    if (key in pal && hex) pal[key] = hex;
  }
  return pal;
}
const resolveColor = (c) => resolveIn(c, palette());

// ---- form building blocks -----------------------------------------------------------------

function section(title, lead, ...kids) {
  return h("section", { class: "section" }, h("h2", { text: title }), lead ? h("p", { class: "lead", text: lead }) : null, kids);
}
// A section whose heading has something on its right (a button, a count).
function sectionWith(title, lead, aside, ...kids) {
  return h("section", { class: "section" },
    h("div", { class: "section-head" }, h("h2", { text: title }), h("span", { class: "spacer" }), aside),
    lead ? h("p", { class: "lead", text: lead }) : null, kids);
}
function callout(kind, icon, ...kids) {
  return h("div", { class: `callout${kind ? " " + kind : ""}` }, oct(icon), h("p", {}, kids));
}
let fieldIds = 0;
function field(label, control, note) {
  // Only a lone input gets a real <label>: a label around a group would forward clicks to its first button.
  const single = ["INPUT", "SELECT", "TEXTAREA"].includes(control.tagName);
  const id = single ? (control.id ||= `f${++fieldIds}`) : null;
  if (!single && !control.getAttribute("aria-label")) control.setAttribute("aria-label", label);
  return h("div", { class: "field" },
    single ? h("label", { class: "label", for: id, text: label }) : h("span", { class: "label", text: label }),
    control, note ? h("span", { class: "note", text: note }) : null);
}
const fieldRow = (...kids) => h("div", { class: "field-row" }, kids);

function text(obj, key, opts = {}) {
  return h("input", {
    class: `form-control${opts.mono ? " mono" : ""}`, type: opts.type || "text", value: obj[key] ?? "", id: opts.id,
    placeholder: opts.placeholder, maxlength: opts.maxlength, spellcheck: opts.mono ? "false" : null,
    oninput: (e) => { obj[key] = e.target.value; if (opts.after) opts.after(); changed(); },
    onfocus: (e) => { S.focus = e.target; },
  });
}

function number(obj, key, opts = {}) {
  return h("input", {
    class: "form-control", type: "number", value: obj[key] ?? "", min: opts.min, max: opts.max, step: opts.step || "any",
    placeholder: opts.placeholder,
    oninput: (e) => {
      const v = e.target.value.trim();
      if (v === "") { if (opts.optional) delete obj[key]; else return; } else obj[key] = Number(v);
      changed();
    },
  });
}

function checkbox(label, get, set) {
  return h("label", { class: "check field" },
    h("input", { type: "checkbox", checked: get(), onchange: (e) => { set(e.target.checked); changed(); } }), h("span", { text: label }));
}

function select(options, get, set) {
  const el = h("select", { class: "form-select", onchange: (e) => { set(e.target.value); changed(); } },
    options.map(([value, label]) => h("option", { value }, label)));
  el.value = get();
  return el;
}

function segmented(options, get, set, disabled = false) {
  const wrap = h("div", { class: `segmented${disabled ? " disabled" : ""}`, role: "group" });
  const draw = () => wrap.replaceChildren(...options.map(([value, label, title]) => h("button", {
    type: "button", "aria-pressed": String(get() === value), title,
    onclick: () => { set(value); draw(); changed(); },
  }, label)));
  draw();
  return wrap;
}

function colorField(get, set, opts = {}) {
  const swatch = h("input", { type: "color", "aria-label": "Pick a colour" });
  const input = h("input", {
    class: "form-control", value: get() || "", placeholder: opts.placeholder || "name or #hex", list: "color-names",
    oninput: (e) => { set(e.target.value.trim()); sync(); changed(); },
  });
  function sync() { swatch.value = resolveColor(get() || opts.placeholder) || "#000000"; }
  swatch.addEventListener("input", (e) => { input.value = e.target.value; set(e.target.value); changed(); });
  sync();
  return h("div", { class: "color-field" }, swatch, input);
}

function iconButton(label, title, disabled, onclick) {
  return h("button", { type: "button", class: "btn btn-icon", title, "aria-label": title, disabled, onclick }, label);
}

function move(list, i, j) {
  const [x] = list.splice(i, 1);
  list.splice(j, 0, x);
}

function insertAtFocus(token, fallback) {
  const el = S.focus;
  if (el && document.body.contains(el)) {
    const at = el.selectionStart ?? el.value.length;
    el.value = el.value.slice(0, at) + token + el.value.slice(el.selectionEnd ?? at);
    el.focus();
    el.setSelectionRange(at + token.length, at + token.length);
    el.dispatchEvent(new Event("input"));
  } else if (fallback) fallback(token);
}

// ---- tabs --------------------------------------------------------------------------

function profileTab() {
  const c = S.cfg;
  return [
    section("You", "Shown as user@host in the prompt, the title bar and above the info.",
      fieldRow(field("User", text(c, "user")), field("Host", text(c, "host"))),
      fieldRow(
        field("Directory", text(c, "cwd", { mono: true }), "The folder in the prompt, like ~ or ~/code"),
        field("Typed command", text(c, "command", { mono: true }), "What types itself at the prompt"),
      )),
    section("GitHub", null,
      field("GitHub username", text(c, "github", { placeholder: "your-username", id: "f-github" }),
        "Turns on the live numbers, graphs and languages: see Info → GitHub."),
      fieldRow(
        field("Uptime counts from", text(c, "uptime_since", { type: "date" }), "Used by {uptime}"),
        field("Drone initials", text(c, "initials", { maxlength: 2, placeholder: "auto" }), "Two letters on the drone"),
      )),
    section("Files", null,
      field("SVG file", text(c, "output", { mono: true }), "Where Save writes the image, next to the config file"),
      h("p", { class: "hint" }, "Editing ", h("code", { text: S.meta.path }),
        S.meta.exists ? ". Save backs the old file up first." : ". It doesn't exist yet: Save creates it.")),
  ];
}

// ---- icons ------------------------------------------------------------------------------

async function iconCatalog() {
  if (!S.icons) {
    const res = await api("/api/icons");
    S.icons = Array.isArray(res) ? res : [];
  }
  return S.icons;
}

// A searchable grid of the icon library; onPick(icon) gets the catalogue entry.
function iconPicker(onPick) {
  const grid = h("div", { class: "icon-grid", role: "list", "aria-label": "Icons" });
  const search = h("input", {
    class: "form-control", type: "search", placeholder: "Search icons: python, star, arch, nf-oct…", value: S.iconSearch || "",
    "aria-label": "Search icons",
  });
  function draw() {
    const q = search.value.trim().toLowerCase().replace(/^:|:$/g, "");
    S.iconSearch = search.value;
    const items = (S.icons || []).filter((i) => !q || i.name.includes(q) || i.title.toLowerCase().includes(q) || i.nerd.includes(q) || i.aliases.some((a) => a.includes(q)));
    const kids = [];
    let group = null;
    for (const i of items) {
      if (i.group !== group) { group = i.group; kids.push(h("div", { class: "icon-group-title", text: group })); }
      kids.push(h("button", {
        type: "button", class: "icon-cell", role: "listitem",
        title: `:${i.name}:${i.aliases.length ? ` (also ${i.aliases.map((a) => `:${a}:`).join(" ")})` : ""}${i.nerd ? `  ·  :${i.nerd}:` : ""}\n${i.title}`, onclick: () => onPick(i),
      }, svgIcon(i, ""), h("span", { text: i.name })));
    }
    grid.replaceChildren(...(kids.length ? kids : [h("p", { class: "icon-empty", text: S.icons ? `No icon matches “${q}”.` : "Loading icons…" })]));
  }
  search.addEventListener("input", draw);
  draw();
  if (!S.icons) iconCatalog().then(draw);
  return h("div", {}, h("div", { class: "icon-tools" }, h("div", { class: "input-icon" }, oct("search"), search)), grid);
}

function pickIconDialog(onPick) {
  dialog("Choose an icon", [
    h("p", { class: "muted small", text: "Octicons (MIT), Simple Icons (CC0), font-logos (Unlicense) and Devicon (MIT). Brand logos are their owners' trademarks." }),
    iconPicker((i) => { onPick(i); $("#dialog").close(); }),
  ], [{ label: "Cancel" }]);
  $("#dialog").classList.add("wide");
  $("#dialog").addEventListener("close", () => $("#dialog").classList.remove("wide"), { once: true });
}

// ---- info ---------------------------------------------------------------------------------

const GH_LINES = [
  ["repo", "Repositories", ":repo: Repos: {repos}"],
  ["star", "Stars", ":star: Stars: {stars}"],
  ["people", "Followers", ":people: Followers: {followers}"],
  ["git-commit", "Commits", ":git-commit: Commits: {commits}", true],
  ["git-pull-request", "Pull requests", ":git-pull-request: PRs: {prs}"],
  ["issue-opened", "Issues", ":issue-opened: Issues: {issues}"],
  ["graph", "Contributions", ":graph: Contributions: {contributions}", true],
  ["flame", "Streak", ":flame: Streak: {streak} days (best {longest_streak})", true],
  ["mark-github", "Summary", ":mark-github: GitHub: {repos} repos · {stars} stars · {followers} followers"],
  ["code", "Top language", ":code: Top language: {top_language}"],
  ["graph", "Activity bars", "Activity: {graph}", true],
  ["calendar", "Heatmap (4 lines)", "{heatmap}", true],
  ["sliders", "Language bar", "Languages: {langbar}"],
  ["list-unordered", "Language legend", "{languages}"],
];

function infoTab() {
  const lines = S.cfg.info;
  const list = h("ol", { class: "list", "data-empty": "No lines yet. Add one, or pick a GitHub line below." }, lines.map((value, i) => h("li", { class: "line-row" },
    h("span", { class: "num", text: i + 1 }),
    h("input", {
      class: "form-control mono", value, placeholder: "(blank line)", "aria-label": `Line ${i + 1}`, spellcheck: "false",
      oninput: (e) => { lines[i] = e.target.value; changed(); }, onfocus: (e) => { S.focus = e.target; },
    }),
    iconButton("↑", "Move up", i === 0, () => { move(lines, i, i - 1); refresh(); changed(); }),
    iconButton("↓", "Move down", i === lines.length - 1, () => { move(lines, i, i + 1); refresh(); changed(); }),
    iconButton("×", "Remove", false, () => { lines.splice(i, 1); refresh(); changed(); }),
  )));
  const add = (value) => () => {
    lines.push(value);
    refresh();
    changed();
    const inputs = document.querySelectorAll(".line-row input");
    inputs[inputs.length - 1]?.focus();
  };
  const groups = [
    ["You", Object.keys(S.meta.placeholders).filter((n) => !S.meta.github_keys.includes(n)), ""],
    ["GitHub numbers", S.meta.github_keys.filter((n) => !S.meta.visuals.includes(n)), "live"],
    ["GitHub visuals (a line of their own reads best)", S.meta.visuals, "visual"],
  ];
  const chips = groups.map(([title, names, kind]) => h("div", { class: "chip-group" }, h("h3", { text: title }),
    h("div", { class: "chips" }, names.map((name) => h("button", {
      type: "button", class: `chip${kind ? " " + kind : ""}`, title: S.meta.placeholders[name],
      onclick: () => insertAtFocus(`{${name}}`, (tok) => { lines.push(`Key: ${tok}`); refresh(); changed(); }),
    }, `{${name}}`)))));

  const noUser = !S.cfg.github;
  const ghButtons = h("div", { class: "gh-lines" }, GH_LINES.map(([icon, title, line, token]) => h("button", {
    type: "button", class: `gh-line${token ? " token" : ""}`, title: `Adds: ${line}`, onclick: add(line),
  }, h("strong", {}, oct(icon), title), h("code", { text: line }))));

  const mt = (S.cfg.metrics ||= {});
  const md = S.meta.metrics_defaults;
  const colors = Array.isArray(mt.colors) && mt.colors.length === 5 ? mt.colors : null;
  const greens = (palette().bg && parseInt(palette().bg.slice(1, 3), 16) > 140)
    ? ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"] : ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"];
  const swatches = h("div", { class: "swatches" }, (colors || greens).map((c, i) => h("input", {
    type: "color", value: c, title: i === 0 ? "No contributions" : `Level ${i}`, "aria-label": i === 0 ? "Empty colour" : `Level ${i} colour`,
    oninput: (e) => { const next = [...(colors || greens)]; next[i] = e.target.value; mt.colors = next; changed(); },
  })), colors ? h("button", { type: "button", class: "btn btn-sm btn-invisible", onclick: () => { mt.colors = []; refresh(); changed(); } }, "GitHub's greens") : null);

  const visualSettings = h("details", {}, h("summary", { text: "Graph and language settings" }), h("div", { style: { marginTop: "12px" } },
    fieldRow(
      field("Weeks shown", number(mt, "weeks", { min: 4, max: 53, step: 1, placeholder: String(md.weeks) }), "In {graph} and {heatmap}"),
      field("Languages named", number(mt, "languages", { min: 1, max: 10, step: 1, placeholder: String(md.languages) }), "The rest become “Other”")),
    fieldRow(
      field("Language bar width", number(mt, "bar_width", { min: 6, max: 80, step: 1, placeholder: String(md.bar_width) }), "In characters"),
      field("Leave out", h("input", {
        class: "form-control", value: (mt.exclude || []).join(", "), placeholder: "HTML, Jupyter Notebook",
        oninput: (e) => { mt.exclude = e.target.value.split(",").map((s) => s.trim()).filter(Boolean); changed(); },
      }), "Languages to skip, comma separated")),
    field("Graph colours", swatches, "Empty, then four levels of activity")));

  return [
    sectionWith("Lines", "“Key: value” prints the key in the logo's colour. A line without a key prints as plain text, and an empty line leaves a gap.",
      h("span", { class: "muted small", text: `${lines.length} line${lines.length === 1 ? "" : "s"}` }),
      list,
      h("div", { class: "row-actions" },
        h("button", { type: "button", class: "btn btn-sm", onclick: add("Key: value") }, oct("plus"), "Add line"),
        h("button", { type: "button", class: "btn btn-sm", onclick: add("") }, "Add blank line"))),
    section("GitHub", "One click adds a line with your live numbers or a graph. Lines marked “needs a token” use GitHub's GraphQL API: the Action has one, and locally GITHUB_TOKEN or gh auth login work.",
      noUser ? callout("warn", "alert", "These need your GitHub username. ",
        h("button", { type: "button", class: "btn btn-sm btn-invisible", onclick: () => { showTab("profile"); setTimeout(() => document.querySelector("#f-github")?.focus(), 50); } }, "Set it in Profile")) : null,
      ghButtons, h("div", { style: { marginTop: "12px" } }, visualSettings)),
    section("Icons", "Click one to put it at your cursor, like :repo: or :python:. They're drawn as shapes, so every visitor sees them (no Nerd Font needed). Nerd Font names like :nf-dev-python: work too.",
      iconPicker((i) => insertAtFocus(`:${i.name}: `, (tok) => { lines.push(`${tok}Key: value`); refresh(); changed(); }))),
    section("Placeholders", "Click one to insert it at your cursor. Green ones are live from GitHub; purple ones are drawn.", chips,
      h("p", { class: "hint" }, "Write {{ and }} for literal braces.")),
    section("Colour blocks", null,
      checkbox("Show the two rows of colour swatches under the info", () => S.cfg.color_blocks, (v) => { S.cfg.color_blocks = v; })),
  ];
}

const catalogEntry = (name) => S.meta.logos.find((l) => l.name === name.toLowerCase());
const isCustom = (name) => Boolean(S.cfg.logo?.[name] && "art" in S.cfg.logo[name]);

function thumbUrl(name) {
  const q = new URLSearchParams({ name, theme: S.cfg.theme, user: S.cfg.user || "", initials: S.cfg.initials || "" });
  return `/api/thumb?${q}`;
}

function logoSettings(name) {
  const custom = isCustom(name);
  const entry = catalogEntry(name);
  S.cfg.logo ||= {};
  const spec = S.cfg.logo[name] || {};
  const write = (key, value, isDefault) => {
    const target = (S.cfg.logo[name] ||= {});
    if (isDefault) delete target[key]; else target[key] = value;
    if (!custom && Object.keys(target).length === 0) delete S.cfg.logo[name];
  };
  const defEnter = custom ? "print" : entry?.enter || "print";
  const defHover = custom ? false : Boolean(entry?.hover);
  const enter = select([["", `Default (${defEnter})`], ...S.meta.enters.map((e) => [e, e])],
    () => spec.enter || "", (v) => write("enter", v, v === "" || (!custom && v === defEnter)));
  const hover = select([["", `Default (${defHover ? "on" : "off"})`], ["on", "on"], ["off", "off"]],
    () => (spec.hover === undefined ? "" : spec.hover ? "on" : "off"), (v) => write("hover", v === "on", v === ""));
  const kids = [field("Entrance", enter), field("Hover", hover)];
  if (!custom && entry?.animated) {
    kids.push(checkbox("Animate (blink, spin, flicker)", () => spec.animate !== false, (v) => write("animate", false, v)));
  }
  kids.push(field("Info key colour", colorField(() => spec.accent, (v) => write("accent", v, v === ""), { placeholder: entry?.accent || "accent" })));
  return h("div", { class: "logo-motion" }, kids);
}

function logosTab() {
  const c = S.cfg;
  const chosen = h("ol", { class: "list", "data-empty": "No logos: the info fills the window." }, c.logos.map((name, i) => {
    const entry = catalogEntry(name);
    const custom = isCustom(name);
    const credit = custom ? (c.logo[name].credit || "your own art") : entry?.credit || "unknown logo";
    return h("li", {},
      h("div", { class: "logo-head" },
        custom ? h("span", { class: "thumb thumb-text", text: "custom" }) : h("img", { class: "thumb", src: thumbUrl(name), alt: "" }),
        h("div", { class: "who" }, h("strong", { text: name }), h("span", { text: credit, title: credit })),
        custom ? h("button", { type: "button", class: "btn btn-sm", onclick: () => { editorLoad(name); showTab("editor"); } }, "Edit") : null,
        iconButton("↑", "Show earlier", i === 0, () => { move(c.logos, i, i - 1); refresh(); changed(); }),
        iconButton("↓", "Show later", i === c.logos.length - 1, () => { move(c.logos, i, i + 1); refresh(); changed(); }),
        iconButton("×", "Remove", false, () => { c.logos.splice(i, 1); refresh(); changed(); })),
      h("details", {}, h("summary", { text: "Motion and colour" }), logoSettings(name)));
  }));

  const groups = {};
  const term = S.search.trim().toLowerCase();
  for (const l of S.meta.logos) {
    if (term && !l.name.includes(term) && !l.source.toLowerCase().includes(term)) continue;
    (groups[l.group] ||= []).push(l);
  }
  const customs = Object.entries(c.logo || {}).filter(([, spec]) => "art" in spec).map(([name]) => name);
  const pick = (name) => () => { c.logos.push(name); refresh(); changed(); };
  const grid = h("div", {},
    customs.length ? h("div", { class: "picker-group" }, h("h3", { text: "Your logos" }), h("div", { class: "picker-grid" },
      customs.map((name) => h("button", { type: "button", class: `pick${c.logos.includes(name) ? " added" : ""}`, onclick: pick(name) },
        h("span", { class: "thumb-text", text: "custom" }), name)))) : null,
    Object.entries(groups).map(([group, items]) => h("div", { class: "picker-group" }, h("h3", { text: group }),
      h("div", { class: "picker-grid" }, items.map((l) => h("button", {
        type: "button", class: `pick${c.logos.includes(l.name) ? " added" : ""}`, title: `${l.credit}\n\nClick to add.`, onclick: pick(l.name),
      }, h("img", { src: thumbUrl(l.name), alt: "", loading: "lazy" }), l.name,
      c.logos.includes(l.name) ? h("span", { class: "badge", text: "added" }) : null))))));

  const search = h("input", {
    class: "form-control picker-search", type: "search", placeholder: "Search logos", value: S.search,
    oninput: (e) => {
      S.search = e.target.value;
      const at = e.target.selectionStart;
      refresh();
      const again = document.querySelector(".picker-search");
      again.focus();
      again.setSelectionRange(at, at);
    },
  });

  const b = (c.banner ||= {});
  const colors = Array.isArray(b.colors) ? b.colors : (b.colors ? [b.colors] : []);
  const bannerColors = h("div", { class: "ed-colors" }, colors.map((col, i) => h("div", { class: "ed-color" },
    colorField(() => colors[i], (v) => { colors[i] = v; b.colors = colors; }),
    iconButton("×", "Remove colour", false, () => { colors.splice(i, 1); b.colors = colors; if (!colors.length) delete b.colors; refresh(); changed(); }))));

  return [
    section("Showing", "Logos take turns beside the info, and the info keys switch to each logo's colour.",
      chosen,
      h("div", { class: "field-row", style: { marginTop: "12px" } },
        field("Seconds per logo", number(c, "seconds_per_logo", { min: 2, step: 0.5 }))),
    ),
    section("Add a logo", "Every logo's artist and licence is kept in the SVG and listed in CREDITS.md.", search, grid),
    section("Banner", "The banner logo writes text in big FIGlet letters with a colour wave.",
      fieldRow(field("Text", text(b, "text", { placeholder: c.user })),
        field("Font", select(S.meta.fonts.map((f) => [f, f]), () => b.font || "slant", (v) => { b.font = v; }))),
      field("Colours", h("div", {}, bannerColors, h("button", {
        type: "button", class: "btn btn-sm", style: { marginTop: "6px" },
        onclick: () => { colors.push("bright-cyan"); b.colors = colors; refresh(); changed(); },
      }, "Add colour")), "Empty: cyan, blue and magenta"),
      checkbox("Colour wave", () => b.wave !== false, (v) => { if (v) delete b.wave; else b.wave = false; }),
      c.logos.includes("banner") ? null : h("button", { type: "button", class: "btn btn-sm", onclick: pick("banner") }, "Show the banner")),
  ];
}

function motionTab() {
  const it = (S.cfg.intro ||= {});
  const cur = (S.cfg.cursor ||= {});
  const d = S.meta.defaults;
  const off = (it.scope || d.intro.scope) === "none";
  const horizontal = ["left-to-right", "right-to-left"].includes(it.direction || d.intro.direction);
  return [
    section("First visit", "How the output appears when someone opens your profile. It plays once, then the logos keep taking turns.",
      field("What types itself", segmented([["none", "Nothing"], ["info", "The info"], ["all", "Everything"]],
        () => it.scope || d.intro.scope, (v) => { it.scope = v; refresh(); }), sentence(S.meta.scopes[it.scope || d.intro.scope])),
      field("Direction", segmented([
        ["left-to-right", "→ Left to right"], ["right-to-left", "← Right to left"],
        ["top-to-bottom", "↓ Top to bottom"], ["bottom-to-top", "↑ Bottom to top"],
      ], () => it.direction || d.intro.direction, (v) => { it.direction = v; refresh(); }, off), sentence(S.meta.directions[it.direction || d.intro.direction])),
      fieldRow(
        field("Speed", number(it, "speed", { min: 1, optional: true, placeholder: horizontal ? "50 (auto)" : "24 (auto)" }),
          horizontal ? "Characters per second" : "Rows per second"),
        field("Stagger", number(it, "stagger", { min: 0, step: 0.005, optional: true, placeholder: horizontal ? "0.08 (auto)" : "0.015 (auto)" }),
          horizontal ? "Seconds between lines starting" : "Seconds between columns starting")),
      field("Speed variety", h("input", {
        type: "range", min: 0, max: 0.95, step: 0.05, value: it.variance ?? d.intro.variance,
        oninput: (e) => { it.variance = Number(e.target.value); e.target.nextElementSibling.textContent = `±${Math.round(it.variance * 100)}%`; changed(); },
      }), `±${Math.round((it.variance ?? d.intro.variance) * 100)}%`),
      fieldRow(
        field("Seed", h("div", { class: "color-field" }, number(it, "seed", { step: 1 }),
          h("button", { type: "button", class: "btn", title: "Another random mix of speeds", onclick: () => { it.seed = Math.floor(Math.random() * 10000); refresh(); changed(); } }, "Shuffle")),
          "Picks which lines are fast and which are slow"),
        field("Command speed", number(it, "command_speed", { min: 1 }), "Characters per second at the prompt")),
    ),
    section("Cursor", null,
      field("Style", segmented(S.meta.cursors.map((s) => [s, s[0].toUpperCase() + s.slice(1)]), () => cur.style || d.cursor.style, (v) => { cur.style = v; })),
      fieldRow(
        h("div", { class: "align-input" }, checkbox("Blink", () => cur.blink !== false, (v) => { cur.blink = v; })),
        field("Seconds per blink", number(cur, "period", { min: 0.2, max: 10, step: 0.1 }))),
      field("Colour", colorField(() => cur.color, (v) => { cur.color = v || "fg"; }, { placeholder: "fg" }))),
  ];
}

function themeGroup(name, t) {
  if (Object.values(S.meta.presets).some((p) => p.theme === name)) return "Classic terminals";
  const bg = t.bg.replace("#", "");
  const lum = (0.299 * parseInt(bg.slice(0, 2), 16) + 0.587 * parseInt(bg.slice(2, 4), 16) + 0.114 * parseInt(bg.slice(4, 6), 16)) / 255;
  return lum > 0.5 ? "Light" : "Dark";
}

function lookTab() {
  const c = S.cfg;
  c.colors ||= {};
  const grouped = {};
  for (const [name, t] of Object.entries(S.meta.themes)) (grouped[themeGroup(name, t)] ||= []).push([name, t]);
  const themes = ["Dark", "Light", "Classic terminals"].filter((g) => grouped[g]).map((g) => h("div", { class: "picker-group" },
    h("h3", { text: g }), h("div", { class: "themes" }, grouped[g].map(([name, t]) => h("button", {
      type: "button", class: "theme-card", "aria-pressed": String(c.theme === name), style: { background: t.bg, color: t.fg },
      onclick: () => { c.theme = name; refresh(); changed(); },
    }, name, h("span", { class: "sw" }, ["red", "green", "yellow", "blue", "magenta", "cyan"].map((k) => h("i", { style: { background: t[k] } }))))))));

  const base = ["accent", "fg", "dim", "bg"];
  const keys = [...new Set([...base, ...Object.keys(c.colors)])];
  const overrides = h("div", { class: "ed-colors" }, keys.map((key) => h("div", { class: "ed-color" },
    h("span", { class: "mono", style: { width: "110px", flex: "none" }, text: key }),
    colorField(() => c.colors[key], (v) => { if (v) c.colors[key] = v; else delete c.colors[key]; },
      { placeholder: S.meta.themes[c.theme][normalizeColor(key)] || "" }))));
  const palKeys = Object.keys(S.meta.themes[c.theme]).filter((k) => !keys.includes(k));
  const addOverride = select([["", "Override another colour…"], ...palKeys.map((k) => [k, k])], () => "", (v) => {
    if (v) { c.colors[v] = S.meta.themes[c.theme][v]; refresh(); }
  });

  const p = (c.prompt ||= {});
  const chips = ["user", "host", "cwd"].map((n) => h("button", { type: "button", class: "chip", onclick: () => insertAtFocus(`{${n}}`) }, `{${n}}`));
  return [
    section("Theme", "The terminal's colours. Classic terminals go with the window styles' presets (Window tab).", themes),
    section("Colours", "Theme colour names (red, bright-blue, accent, …) or #hex. Empty uses the theme's.", overrides,
      h("div", { style: { marginTop: "8px" } }, addOverride)),
    section("Prompt", null,
      field("Format", text(p, "format", { mono: true }), "Try “{cwd} ❯ ” or “[{user}@{host} {cwd}]$ ”, or a window style's own prompt (Window tab)"),
      h("div", { class: "chips", style: { marginBottom: "14px" } }, chips),
      fieldRow(field("user@host colour", colorField(() => p.user_color, (v) => { p.user_color = v || "green"; }, { placeholder: "green" })),
        field("Directory colour", colorField(() => p.cwd_color, (v) => { p.cwd_color = v || "blue"; }, { placeholder: "blue" })))),
  ];
}

// ---- window --------------------------------------------------------------------------------

const WINDOW_GROUPS = [["macOS", ["macos", "tahoe", "aqua", "platinum", "system7"]], ["Windows", ["win11", "win7", "winxp", "win95"]],
  ["Other", ["none"]]];

function applyPreset(style, full) {
  const p = S.meta.presets[style];
  const label = S.meta.window_labels[style];
  const before = clone({ prompt: S.cfg.prompt || {}, theme: S.cfg.theme, window: S.cfg.window || {}, cursor: S.cfg.cursor || {} });
  S.cfg.prompt = { ...(S.cfg.prompt || {}), format: p.prompt, user_color: p.user_color, cwd_color: p.cwd_color };
  if (full) {
    S.cfg.theme = p.theme;
    S.cfg.window = { ...(S.cfg.window || {}), style, title: p.title };
    S.cfg.cursor = { ...(S.cfg.cursor || {}), style: p.cursor };
  }
  refresh();
  changed();
  flash(full ? `Applied the ${label} preset: its prompt, the ${p.theme} theme, the title and ${/^[aeiou]/.test(p.cursor) ? "an" : "a"} ${p.cursor} cursor.`
    : `The prompt is now “${p.prompt}”.`, "success", 10000,
  { label: "Undo", onclick: () => { Object.assign(S.cfg, before); refresh(); changed(); } });
}

function windowTab() {
  const w = (S.cfg.window ||= {});
  const cur = w.style || "macos";
  const card = (name) => h("button", {
    type: "button", class: "pick-card", "aria-pressed": String(cur === name), title: S.meta.window_styles[name],
    onclick: () => { w.style = name; refresh(); changed(); },
  }, h("div", { class: "art" }, h("img", {
    src: `/api/frame?${new URLSearchParams({ style: name, theme: S.cfg.theme, title: "Terminal" })}`, alt: "", loading: "lazy",
  })), h("strong", { text: S.meta.window_labels[name] }), h("span", { class: "sub", text: S.meta.window_styles[name].split(": ").slice(1).join(": ") }));

  const p = S.meta.presets[cur];
  const label = S.meta.window_labels[cur];
  const presetBar = p ? h("div", { class: "preset-bar" },
    h("div", { class: "preset-text" }, oct("sparkle-fill"), h("div", {},
      h("div", {}, h("strong", { text: `${label}'s own terminal` })),
      h("div", { class: "muted small" }, "Prompt ", h("code", { text: p.prompt }), `, the ${p.theme} theme, the title “${p.title}” and ${/^[aeiou]/.test(p.cursor) ? "an" : "a"} ${p.cursor} cursor.`))),
    h("div", { class: "row-actions", style: { margin: 0 } },
      h("button", { type: "button", class: "btn btn-sm", onclick: () => applyPreset(cur, false) }, oct("terminal"), "Use its prompt"),
      h("button", { type: "button", class: "btn btn-sm btn-primary", onclick: () => applyPreset(cur, true) }, oct("zap"), "Apply the full preset"))) : null;

  const chips = ["user", "host", "cwd"].map((n) => h("button", { type: "button", class: "chip", onclick: () => insertAtFocus(`{${n}}`) }, `{${n}}`));
  return [
    section("Window style", "The frame around the terminal. Pick one, then keep your own prompt or take that system's.",
      WINDOW_GROUPS.map(([g, names]) => h("div", { class: "picker-group" }, h("h3", { text: g }), h("div", { class: "card-grid" }, names.map(card)))),
      presetBar),
    section("Title bar", null,
      field("Title", text(w, "title", { mono: true }), "Empty hides it. Placeholders: {user} {host} {cwd}"),
      h("div", { class: "chips", style: { marginBottom: "14px" } }, chips),
      checkbox(cur.startsWith("win") ? "Minimise, maximise and close buttons" : "Window buttons (the traffic lights on a Mac)",
        () => w.buttons !== false, (v) => { w.buttons = v; })),
    section("Badges", null, h("p", { class: "muted small", style: { margin: 0 } },
      "Badges can match the window too: give them the style “window” in the Badges tab.")),
  ];
}

// ---- logo editor -----------------------------------------------------------------------------

const blank = (rows, cols) => Array.from({ length: rows }, () => Array(cols).fill(null));
const ED = {
  name: "mine", cols: 34, rows: 12, colors: ["accent", "fg"], cur: 0, frames: [blank(12, 34)], durations: [0.4], frame: 0,
  mode: "type", r: 0, c: 0, home: 0, enter: "print", hover: false, accent: "", credit: "", editing: null,
  undo: [], timer: 0, url: "", cells: null, gridEl: null, drag: false,
};

function snapshot() {
  ED.undo.push(JSON.stringify({ frames: ED.frames, colors: ED.colors, rows: ED.rows, cols: ED.cols, durations: ED.durations }));
  if (ED.undo.length > 100) ED.undo.shift();
}
function undo() {
  const s = ED.undo.pop();
  if (!s) return;
  Object.assign(ED, JSON.parse(s));
  ED.frame = Math.min(ED.frame, ED.frames.length - 1);
  refresh();
  editorChanged();
}

// fastfetch syntax: $1..$9 pick a colour (sticky across lines), $$ is a literal $
function parseDollar(textValue, ncolors) {
  let cur = 0;
  return textValue.replace(/\t/g, "    ").split("\n").map((line) => {
    const row = [];
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === "$" && i + 1 < line.length) {
        const nx = line[i + 1];
        if (nx === "$") { row.push(["$", cur]); i++; continue; }
        if (nx >= "1" && nx <= "9") { if (Number(nx) <= ncolors) cur = Number(nx) - 1; i++; continue; }
      }
      row.push(ch === " " ? null : [ch, cur]);
    }
    return row;
  });
}

function toDollar(grid) {
  let cur = -1;
  const lines = grid.map((row) => {
    let out = "";
    for (const cell of row) {
      if (!cell) { out += " "; continue; }
      if (cell[1] !== cur) { out += `$${cell[1] + 1}`; cur = cell[1]; }
      out += cell[0] === "$" ? "$$" : cell[0];
    }
    return out.replace(/\s+$/, "");
  });
  while (lines.length && lines[lines.length - 1] === "") lines.pop();
  return lines.join("\n");
}

const same = (a, b) => (a === null && b === null) || (a !== null && b !== null && a[0] === b[0] && a[1] === b[1]);

function editorSpec() {
  let top = Infinity, left = Infinity, bottom = -1, right = -1;
  for (const f of ED.frames) f.forEach((row, r) => row.forEach((cell, c) => {
    if (cell) { top = Math.min(top, r); left = Math.min(left, c); bottom = Math.max(bottom, r); right = Math.max(right, c); }
  }));
  if (bottom < 0) return { error: "Draw or type something first." };
  const crop = (g, r0, r1, c0, c1) => g.slice(r0, r1 + 1).map((row) => row.slice(c0, c1 + 1));
  const frames = ED.frames.map((g) => crop(g, top, bottom, left, right));
  const spec = { colors: ED.colors.map((c) => c || "fg"), art: toDollar(frames[0]) };
  if (frames.length > 1) {
    let r0 = Infinity, c0 = Infinity, r1 = -1, c1 = -1;
    frames[0].forEach((row, r) => row.forEach((cell, c) => {
      if (frames.some((f) => !same(f[r][c], cell))) { r0 = Math.min(r0, r); c0 = Math.min(c0, c); r1 = Math.max(r1, r); c1 = Math.max(c1, c); }
    }));
    if (r1 >= 0) {
      const durations = ED.durations.map((d) => Math.max(0.05, Number(d) || 0.4));
      spec.layers = [{
        row: r0, col: c0, period: Number(durations.reduce((a, b) => a + b, 0).toFixed(3)), weights: durations,
        frames: frames.map((f) => toDollar(crop(f, r0, r1, c0, c1))),
      }];
    }
  }
  spec.enter = ED.enter;
  if (ED.hover) spec.hover = true;
  if (ED.accent) spec.accent = ED.accent;
  if (ED.credit.trim()) spec.credit = ED.credit.trim();
  return spec;
}

function editorFromSpec(name, spec) {
  const colors = (Array.isArray(spec.colors) ? spec.colors : [spec.colors || "accent"]).slice(0, 9);
  const base = parseDollar(String(spec.art || "").replace(/\n+$/, ""), colors.length);
  const layers = (spec.layers || []).map((l) => ({ ...l, grids: (l.frames || []).map((f) => parseDollar(String(f).replace(/\n+$/, ""), colors.length)) }));
  const owned = new Set();
  for (const l of layers) for (const g of l.grids) g.forEach((row, r) => row.forEach((cell, c) => { if (cell) owned.add(`${(l.row || 0) + r},${(l.col || 0) + c}`); }));
  let rows = base.length, cols = Math.max(0, ...base.map((r) => r.length));
  for (const l of layers) for (const g of l.grids) {
    rows = Math.max(rows, (l.row || 0) + g.length);
    cols = Math.max(cols, (l.col || 0) + Math.max(0, ...g.map((r) => r.length)));
  }
  rows = Math.max(rows + 1, 8); cols = Math.max(cols + 2, 20);
  const count = Math.max(1, ...layers.map((l) => l.grids.length));
  const frames = [];
  for (let i = 0; i < count; i++) {
    const g = blank(rows, cols);
    base.forEach((row, r) => row.forEach((cell, c) => { if (cell && (!layers.length || !owned.has(`${r},${c}`))) g[r][c] = cell; }));
    for (const l of layers) {
      const f = l.grids[i % l.grids.length];
      f.forEach((row, r) => row.forEach((cell, c) => { if (cell) g[(l.row || 0) + r][(l.col || 0) + c] = cell; }));
    }
    frames.push(g);
  }
  const first = layers[0];
  const weights = first?.weights || Array(count).fill(1);
  const total = weights.reduce((a, b) => a + Number(b), 0) || 1;
  const durations = first ? weights.map((w) => Number(((first.period || 1) * w / total).toFixed(3))) : [0.4];
  Object.assign(ED, {
    name, colors: colors.length ? colors : ["accent"], cur: 0, frames, durations: durations.slice(0, count), frame: 0, rows, cols,
    r: 0, c: 0, home: 0, enter: spec.enter || "print", hover: Boolean(spec.hover), accent: spec.accent || "", credit: spec.credit || "", undo: [],
  });
  while (ED.durations.length < count) ED.durations.push(0.4);
}

function editorLoad(name) {
  editorFromSpec(name, S.cfg.logo[name]);
  ED.editing = name;
}

function cellColor(cell) {
  return cell ? resolveColor(ED.colors[cell[1]] || "fg") || palette().fg : null;
}

function drawCell(r, c) {
  const span = ED.cells?.[r]?.[c];
  if (!span) return;
  const cell = ED.frames[ED.frame][r][c];
  span.textContent = cell ? cell[0] : " ";
  span.style.color = cell ? cellColor(cell) : "";
  span.classList.toggle("cur", r === ED.r && c === ED.c);
  span.classList.toggle("diff", ED.frame > 0 && !same(cell, ED.frames[0][r][c]));
}

function setCursor(r, c) {
  const pr = ED.r, pc = ED.c;
  ED.r = Math.max(0, Math.min(ED.rows - 1, r));
  ED.c = Math.max(0, Math.min(ED.cols - 1, c));
  drawCell(pr, pc);
  drawCell(ED.r, ED.c);
  ED.cells?.[ED.r]?.[ED.c]?.scrollIntoView({ block: "nearest", inline: "nearest" });
}

function put(r, c, cell) {
  if (r < 0 || c < 0 || r >= ED.rows || c >= ED.cols) return;
  ED.frames[ED.frame][r][c] = cell;
  drawCell(r, c);
}

function editorChanged() {
  clearTimeout(ED.timer);
  ED.timer = setTimeout(editorPreview, 300);
}

async function editorPreview() {
  const img = $("#ed-preview-img");
  const note = $("#ed-preview-note");
  if (!img) return;
  const spec = editorSpec();
  if (spec.error) { img.hidden = true; note.textContent = spec.error; return; }
  const res = await api("/api/logo", { spec, name: ED.name || "mine", theme: S.cfg.theme, colors: S.cfg.colors });
  if (!res.ok) { img.hidden = true; note.textContent = res.error; return; }
  URL.revokeObjectURL(ED.url);
  ED.url = URL.createObjectURL(new Blob([res.svg], { type: "image/svg+xml" }));
  img.src = ED.url;
  img.hidden = false;
  note.textContent = spec.layers ? `${ED.frames.length} frames, ${spec.layers[0].period}s per loop` : "";
}

function resize(rows, cols) {
  snapshot();
  ED.frames = ED.frames.map((g) => Array.from({ length: rows }, (_, r) => Array.from({ length: cols }, (_, c) => g[r]?.[c] ?? null)));
  ED.rows = rows; ED.cols = cols;
  ED.r = Math.min(ED.r, rows - 1); ED.c = Math.min(ED.c, cols - 1);
  refresh();
  editorChanged();
}

function pasteText(value, dollar) {
  snapshot();
  const grid = dollar ? parseDollar(value.replace(/\r/g, ""), ED.colors.length)
    : value.replace(/\r/g, "").replace(/\t/g, "    ").split("\n").map((line) => [...line].map((ch) => (ch === " " ? null : [ch, ED.cur])));
  while (grid.length && !grid[grid.length - 1].length) grid.pop();
  const needRows = ED.r + grid.length, needCols = ED.c + Math.max(0, ...grid.map((r) => r.length));
  if (needRows > ED.rows || needCols > ED.cols) {
    ED.frames = ED.frames.map((g) => Array.from({ length: Math.max(ED.rows, needRows) }, (_, r) =>
      Array.from({ length: Math.max(ED.cols, needCols) }, (_, c) => g[r]?.[c] ?? null)));
    ED.rows = Math.max(ED.rows, needRows); ED.cols = Math.max(ED.cols, needCols);
  }
  grid.forEach((row, r) => row.forEach((cell, c) => { ED.frames[ED.frame][ED.r + r][ED.c + c] = cell; }));
  refresh();
  editorChanged();
}

function gridKey(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  const k = e.key;
  const moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
  if (moves[k]) { e.preventDefault(); setCursor(ED.r + moves[k][0], ED.c + moves[k][1]); return; }
  if (k === "Enter") { e.preventDefault(); setCursor(ED.r + 1, ED.home); return; }
  if (k === "Home") { e.preventDefault(); setCursor(ED.r, 0); return; }
  if (k === "End") { e.preventDefault(); setCursor(ED.r, ED.cols - 1); return; }
  if (k === "Backspace") {
    e.preventDefault(); snapshot();
    const c = ED.c > 0 ? ED.c - 1 : ED.c;
    put(ED.r, c, null); setCursor(ED.r, c); editorChanged(); return;
  }
  if (k === "Delete") { e.preventDefault(); snapshot(); put(ED.r, ED.c, null); editorChanged(); return; }
  if (k.length === 1) {
    e.preventDefault(); snapshot();
    put(ED.r, ED.c, k === " " ? null : [k, ED.cur]);
    setCursor(ED.r, ED.c + 1);
    editorChanged();
  }
}

function brush(r, c) {
  const cell = ED.frames[ED.frame][r][c];
  if (ED.mode === "paint" && cell && cell[1] !== ED.cur) put(r, c, [cell[0], ED.cur]);
  if (ED.mode === "erase" && cell) put(r, c, null);
}

function buildGrid() {
  const pal = palette();
  const grid = h("div", {
    class: `ed-grid ${ED.mode}`, tabindex: "0", role: "grid", "aria-label": "Logo drawing grid: click a cell and type",
    style: { background: pal.bg, color: pal.fg },
    onkeydown: gridKey,
    onpaste: (e) => { e.preventDefault(); pasteText(e.clipboardData.getData("text"), false); },
    onmousedown: (e) => {
      const { r, c } = e.target.dataset;
      if (r === undefined) return;
      e.preventDefault();
      grid.focus();
      if (ED.mode === "type") { ED.home = Number(c); setCursor(Number(r), Number(c)); return; }
      snapshot();
      ED.drag = true;
      brush(Number(r), Number(c));
      editorChanged();
    },
    onmouseover: (e) => {
      const { r, c } = e.target.dataset;
      if (ED.drag && r !== undefined && e.buttons === 1) { brush(Number(r), Number(c)); editorChanged(); }
    },
  });
  grid.style.setProperty("--cols", ED.cols);
  ED.cells = [];
  for (let r = 0; r < ED.rows; r++) {
    ED.cells.push([]);
    for (let c = 0; c < ED.cols; c++) {
      const span = h("span", { dataset: { r, c } });
      ED.cells[r].push(span);
      grid.append(span);
    }
  }
  ED.gridEl = grid;
  for (let r = 0; r < ED.rows; r++) for (let c = 0; c < ED.cols; c++) drawCell(r, c);
  return grid;
}
window.addEventListener("mouseup", () => { ED.drag = false; });

function importDialog() {
  const area = h("textarea", { class: "form-control", placeholder: "Paste ASCII art here", spellcheck: "false" });
  const codes = h("input", { type: "checkbox" });
  dialog("Import text", [
    h("p", { class: "muted small", text: "It goes in at the cursor, in the selected colour. Only use art you're allowed to: credit the artist below." }),
    area,
    h("label", { class: "check", style: { marginTop: "8px" } }, codes, h("span", {}, "Uses fastfetch colour codes ($1 to $9)")),
  ], [{ label: "Cancel" }, { label: "Import", primary: true, onclick: () => pasteText(area.value, codes.checked) }]);
  setTimeout(() => area.focus(), 50);
}

function builtinDialog() {
  const names = S.meta.logos.map((l) => [l.name, `${l.name} (${l.source})`]);
  let chosen = names[0][0];
  const sel = select(names, () => chosen, (v) => { chosen = v; });
  dialog("Start from a built-in logo", [
    h("p", { class: "muted small", text: "Its credit comes along: keep it when you change the art." }), sel,
  ], [{ label: "Cancel" }, {
    label: "Load", primary: true, onclick: async () => {
      const res = await api("/api/builtin", { name: chosen, user: S.cfg.user, initials: S.cfg.initials, banner: S.cfg.banner });
      if (!res.ok) { flash(res.error); return; }
      editorFromSpec(`my-${chosen}`, { colors: res.colors, art: res.art, credit: `Based on ${chosen}: ${res.credit}`, accent: res.accent });
      ED.editing = null;
      refresh();
      editorChanged();
    },
  }]);
}

function editorSave() {
  const name = ED.name.trim();
  if (!/^[A-Za-z0-9_-]+$/.test(name)) { flash("Give the logo a name made of letters, digits, - or _."); return; }
  if (catalogEntry(name)) { flash(`“${name}” is a built-in logo; pick another name.`); return; }
  const spec = editorSpec();
  if (spec.error) { flash(spec.error); return; }
  const commit = () => {
    S.cfg.logo ||= {};
    if (ED.editing && ED.editing !== name) {
      delete S.cfg.logo[ED.editing];
      S.cfg.logos = S.cfg.logos.map((n) => (n === ED.editing ? name : n));
    }
    S.cfg.logo[name] = spec;
    if (!S.cfg.logos.includes(name)) S.cfg.logos.push(name);
    ED.editing = name;
    flash(`“${name}” is in your logos. Save writes it into readmefetch.toml.`, "success", 4000);
    refresh();
    changed();
  };
  if (S.cfg.logo?.[name] && ED.editing !== name) {
    dialog("Replace logo?", [h("p", { text: `You already have a logo called “${name}”.` })],
      [{ label: "Cancel" }, { label: "Replace", danger: true, onclick: commit }]);
  } else commit();
}

function editorTab() {
  const pal = palette();
  const colorRows = ED.colors.map((col, i) => h("div", { class: "ed-color" },
    h("button", {
      type: "button", class: "slot", "aria-pressed": String(ED.cur === i), title: `Use colour ${i + 1}`,
      style: { background: resolveColor(col) || pal.fg }, onclick: () => { ED.cur = i; refresh(); },
    }, String(i + 1)),
    colorField(() => ED.colors[i], (v) => { ED.colors[i] = v; for (let r = 0; r < ED.rows; r++) for (let c = 0; c < ED.cols; c++) drawCell(r, c); editorChanged(); }),
    iconButton("×", "Remove colour", ED.colors.length === 1, () => {
      snapshot();
      ED.colors.splice(i, 1);
      ED.frames = ED.frames.map((g) => g.map((row) => row.map((cell) => (cell ? [cell[0], cell[1] === i ? 0 : cell[1] > i ? cell[1] - 1 : cell[1]] : null))));
      ED.cur = Math.min(ED.cur, ED.colors.length - 1);
      refresh(); editorChanged();
    })));
  const frames = h("div", { class: "ed-frames" }, ED.frames.map((_, i) => h("div", { class: "ed-frame", "aria-current": String(i === ED.frame) },
    h("button", { type: "button", onclick: () => { ED.frame = i; refresh(); } }, i === 0 ? "Frame 1" : `Frame ${i + 1}`),
    ED.frames.length > 1 ? h("input", {
      type: "number", min: 0.05, step: 0.05, value: ED.durations[i], title: "Seconds this frame stays",
      oninput: (e) => { ED.durations[i] = Number(e.target.value) || 0.4; editorChanged(); },
    }) : null)),
  h("button", { type: "button", class: "btn btn-sm", onclick: () => {
    snapshot();
    ED.frames.splice(ED.frame + 1, 0, clone(ED.frames[ED.frame]));
    ED.durations.splice(ED.frame + 1, 0, ED.durations[ED.frame] || 0.4);
    ED.frame += 1; refresh(); editorChanged();
  } }, "+ Frame"),
  ED.frames.length > 1 ? h("button", { type: "button", class: "btn btn-sm btn-danger", onclick: () => {
    snapshot();
    ED.frames.splice(ED.frame, 1); ED.durations.splice(ED.frame, 1);
    ED.frame = Math.max(0, ED.frame - 1); refresh(); editorChanged();
  } }, "Delete frame") : null);

  const rows = h("input", { class: "form-control ed-size", type: "number", min: 1, max: 60, value: ED.rows,
    onchange: (e) => resize(Math.min(60, Math.max(1, Number(e.target.value) || ED.rows)), ED.cols) });
  const cols = h("input", { class: "form-control ed-size", type: "number", min: 1, max: 120, value: ED.cols,
    onchange: (e) => resize(ED.rows, Math.min(120, Math.max(1, Number(e.target.value) || ED.cols))) });

  setTimeout(editorPreview, 0);
  return [
    section("Draw a logo", "Click a cell and type. Arrows move, Enter goes down a line, Backspace erases, Ctrl+Z undoes. Paste works too.",
      h("div", { class: "ed-toolbar" },
        field("Name", h("input", { class: "form-control mono", value: ED.name, spellcheck: "false", oninput: (e) => { ED.name = e.target.value; } })),
        field("Rows", rows), field("Columns", cols)),
      h("div", { class: "row-actions", style: { marginBottom: "12px" } },
        h("button", { type: "button", class: "btn btn-sm", onclick: () => {
          Object.assign(ED, { name: "mine", frames: [blank(ED.rows, ED.cols)], durations: [0.4], frame: 0, editing: null, credit: "", accent: "", undo: [] });
          refresh(); editorChanged();
        } }, "New"),
        h("button", { type: "button", class: "btn btn-sm", onclick: importDialog }, "Import text…"),
        h("button", { type: "button", class: "btn btn-sm", onclick: builtinDialog }, "Start from a built-in…")),
      field("Tool", segmented([["type", "Type"], ["paint", "Paint"], ["erase", "Erase"]], () => ED.mode, (v) => {
        ED.mode = v; ED.gridEl.className = `ed-grid ${v}`; ED.gridEl.focus();
      }), ED.mode === "paint" ? "Drag over characters to give them the selected colour." : ED.mode === "erase" ? "Drag to clear cells." : "New characters use the selected colour."),
      field("Colours", h("div", {}, h("div", { class: "ed-colors" }, colorRows),
        ED.colors.length < 9 ? h("button", { type: "button", class: "btn btn-sm", style: { marginTop: "6px" }, onclick: () => {
          ED.colors.push("fg"); ED.cur = ED.colors.length - 1; refresh();
        } }, "Add colour") : null), "Click a number to draw with that colour."),
      h("span", { class: "label", style: { fontWeight: "600" } }, "Frames"),
      frames,
      h("p", { class: "hint", text: ED.frames.length > 1 ? "Highlighted cells differ from frame 1; only that part animates." : "Add a frame to animate part of the logo, like a blink." }),
      h("div", { class: "ed-wrap" }, buildGrid()),
      h("div", { class: "ed-preview" }, h("img", { id: "ed-preview-img", alt: "Animated preview of the logo", hidden: true }),
        h("p", { id: "ed-preview-note", class: "muted small" }))),
    section("Options", null,
      fieldRow(field("Entrance", select(S.meta.enters.map((e) => [e, e]), () => ED.enter, (v) => { ED.enter = v; })),
        h("div", { class: "align-input" }, checkbox("Hover (gentle bobbing)", () => ED.hover, (v) => { ED.hover = v; editorChanged(); }))),
      field("Info key colour", colorField(() => ED.accent, (v) => { ED.accent = v; }, { placeholder: ED.colors[0] })),
      field("Credit", h("input", { class: "form-control", value: ED.credit, placeholder: "art by …", oninput: (e) => { ED.credit = e.target.value; } }),
        "If you based it on someone's art, name them and the licence. It's kept in the SVG."),
      h("div", { class: "row-actions" },
        h("button", { type: "button", class: "btn btn-primary", onclick: editorSave }, ED.editing ? `Update “${ED.editing}”` : "Add to my logos"))),
  ];
}

// ---- badges -------------------------------------------------------------------------------

// data: URLs, not blob: ones, so an image still loading when the preview redraws can't lose its source.
function badgeImg(svg, alt) {
  return h("img", { src: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`, alt });
}

function drawBadgePreviews() {
  const list = S.last?.badges || [];
  const row = $("#preview-badges");
  row.replaceChildren(...list.map((b) => (b.link ? h("a", { href: b.link, target: "_blank", rel: "noopener" }, badgeImg(b.svg, b.text)) : badgeImg(b.svg, b.text))));
  row.hidden = !list.length;
  document.querySelectorAll("[data-badge-preview]").forEach((slot) => {
    const b = list[Number(slot.dataset.badgePreview)];
    slot.replaceChildren(b ? badgeImg(b.svg, b.text) : h("span", { class: "muted small", text: "…" }));
  });
  const copyBtn = $("#copy-badges");
  if (copyBtn) copyBtn.disabled = !list.length;
}

const PATH_RE = /^[MmLlHhVvCcSsQqTtAaZz0-9eE.,+\-\s]+$/;
function iconKind(icon) {
  if (!icon) return "";
  if (icon in S.meta.icons) return "builtin";
  if (/^[a-z0-9][a-z0-9_#+-]*$/.test(icon)) return "library";
  return PATH_RE.test(icon) ? "custom" : "library";
}

const sampleText = (s, def) => (s ? s.replace(/\{(\w+)\}/g, "128") : def);
function badgePreviewUrl(style, b = {}) {
  const d = S.cfg.badges || {};
  return `/api/badge?${new URLSearchParams({
    style, label: sampleText(b.label, "Label"), message: sampleText(b.message, "message"), color: resolveColor(b.color || d.color || "accent") || "#58a6ff",
    icon: b.icon && !PATH_RE.test(b.icon) ? b.icon : "star", theme: S.cfg.theme, window: S.cfg.window?.style || "macos",
  })}`;
}

// Mirrors badges.slug(): the file a badge is written to when it doesn't name one.
const badgeSlug = (s) => String(s || "").normalize("NFKD").replace(/[^\x00-\x7f]/g, "").toLowerCase()
  .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "badge";
const badgeFile = (b) => b.file || `${badgeSlug(b.label || b.message)}.svg`;

// Add a badge, naming its file so it can't collide with one already there (two "Website"s).
function addBadge(b) {
  const taken = new Set(S.cfg.badge.map(badgeFile));
  if (taken.has(badgeFile(b))) {
    const stem = badgeSlug(b.label || b.message);
    let n = 2;
    while (taken.has(`${stem}-${n}.svg`)) n++;
    b.file = `${stem}-${n}.svg`;
  }
  S.cfg.badge.push(b);
  S.openBadge = S.cfg.badge.length - 1;
  refresh(); changed();
}

function badgesTab() {
  const c = S.cfg;
  c.badges ||= {};
  c.badge ||= [];
  const d = c.badges;
  const defStyle = d.style || "flat";
  const builtins = Object.keys(S.meta.icons);
  const styleOptions = (def) => [["", `Default (${def})`], ...Object.keys(S.meta.badge_styles).map((k) => [k, k])];
  const set = (b, key, value) => { if (value === "" || value === undefined) delete b[key]; else b[key] = value; };
  const numbers = S.meta.github_keys.filter((n) => !S.meta.visuals.includes(n));

  const list = h("ol", { class: "list", "data-empty": "No badges yet." }, c.badge.map((b, i) => {
    const kind = iconKind(b.icon);
    const iconSel = select([["", "No icon"], ...builtins.map((k) => [k, `${k} (readmefetch)`]),
      ["library", kind === "library" ? `${b.icon} (icon library)` : "From the icon library…"], ["custom", "Custom SVG path…"]],
    () => (kind === "builtin" ? b.icon : kind), (v) => {
      if (v === "library") { pickIconDialog((ic) => { b.icon = ic.name; refresh(); changed(); }); return; }
      if (v === "custom") { b.icon = kind === "custom" ? b.icon : "M12 2L2 22h20z"; } else set(b, "icon", v);
      refresh();
    });
    const labelIn = text(b, "label", { placeholder: "Portfolio" });
    const messageIn = text(b, "message", { placeholder: "example.com or {stars}" });
    const liveChips = h("div", { class: "chips", style: { marginBottom: "10px" } },
      h("span", { class: "muted small", style: { alignSelf: "center" }, text: "Live numbers:" }),
      numbers.map((n) => h("button", {
        type: "button", class: "chip live", title: `${S.meta.placeholders[n]}. Goes in at your cursor in the label or message.`,
        onmousedown: (e) => e.preventDefault(),
        onclick: () => {
          if (S.focus !== labelIn && S.focus !== messageIn) S.focus = messageIn;
          insertAtFocus(`{${n}}`);
        },
      }, `{${n}}`)));
    return h("li", {},
      h("div", { class: "logo-head" },
        h("div", { class: "badge-slot", dataset: { badgePreview: i } }),
        h("span", { class: "spacer" }),
        iconButton("↑", "Earlier", i === 0, () => { move(c.badge, i, i - 1); refresh(); changed(); }),
        iconButton("↓", "Later", i === c.badge.length - 1, () => { move(c.badge, i, i + 1); refresh(); changed(); }),
        iconButton("×", "Remove", false, () => { c.badge.splice(i, 1); refresh(); changed(); })),
      h("details", { class: "badge-fields", open: c.badge.length <= 2 || S.openBadge === i, ontoggle: (e) => { if (e.target.open) S.openBadge = i; } },
        h("summary", { text: "Edit" }),
        h("div", { style: { marginTop: "10px" } },
          fieldRow(field("Label", labelIn), field("Message", messageIn)),
          liveChips,
          field("Link", text(b, "link", { placeholder: "https://…", type: "url" }), "Where it goes when clicked (in your README)"),
          fieldRow(field("Colour", colorField(() => b.color, (v) => set(b, "color", v), { placeholder: d.color || "accent" })),
            field("Label colour", colorField(() => b.label_color, (v) => set(b, "label_color", v), { placeholder: d.label_color || "auto" }))),
          fieldRow(field("Icon", iconSel), field("Style", select(styleOptions(defStyle), () => b.style || "", (v) => { set(b, "style", v); refresh(); }))),
          kind === "library" ? h("div", { class: "row-actions", style: { marginTop: "-6px" } },
            h("button", { type: "button", class: "btn btn-sm", onclick: () => pickIconDialog((ic) => { b.icon = ic.name; refresh(); changed(); }) }, "Change icon…")) : null,
          kind === "custom" ? field("SVG path (24×24)", text(b, "icon", { mono: true }), "The d attribute of a 24×24 icon (brand logos are trademarks)") : null,
          (b.style || defStyle) === "terminal" ? checkbox("Blinking cursor", () => b.cursor !== false, (v) => set(b, "cursor", v ? undefined : false)) : null,
          field("File", text(b, "file", { mono: true, placeholder: "from the label" }), `Written to ${d.dir || "badges"}/`))));
  }));

  const sample = c.badge[0] || {};
  const groups = [
    ["Classic", ["flat", "flat-square", "plastic", "for-the-badge", "pill", "terminal"]],
    ["Modern", ["outline", "gradient", "glow", "glass", "social", "window"]],
    ["Window styles", ["macos", "tahoe", "aqua", "platinum", "system7", "win11", "win7", "winxp", "win95"]],
  ];
  const gallery = groups.map(([g, names]) => h("div", { class: "picker-group" }, h("h3", { text: g }), h("div", { class: "style-grid" },
    names.filter((n) => n in S.meta.badge_styles).map((name) => h("button", {
      type: "button", class: "pick-card", "aria-pressed": String(defStyle === name), title: S.meta.badge_styles[name],
      onclick: () => { d.style = name; refresh(); changed(); },
    }, h("div", { class: "art" }, h("img", { src: badgePreviewUrl(name, sample), alt: "", loading: "lazy" })),
    h("strong", { text: name }), h("span", { class: "sub", text: S.meta.badge_styles[name] }))))));

  return [
    sectionWith("Badges", "Little buttons for your sites and contact, written as SVG files next to your config. Save writes them; the Action keeps them in sync.",
      h("button", { type: "button", class: "btn btn-sm", id: "copy-badges", disabled: !(S.last?.badges || []).length,
        onclick: () => copy(S.last.badge_snippet, "badge lines for your README") }, oct("copy"), "Copy README lines"),
      list,
      h("div", { class: "row-actions" },
        h("button", { type: "button", class: "btn btn-sm",
          onclick: () => addBadge({ label: "Website", message: "example.com", link: "https://example.com", icon: "globe" }) },
        oct("plus"), "Add badge"),
        S.cfg.github ? h("button", { type: "button", class: "btn btn-sm", onclick: () => addBadge({
          label: "Stars", message: "{stars}", link: `https://github.com/${S.cfg.github}?tab=repositories`, icon: "star", style: "social",
        }) }, oct("star"), "Add a live stars badge") : null)),
    section("Style", "Every badge that doesn't pick its own uses this. “window” follows the Window tab.", gallery),
    section("Defaults", null,
      fieldRow(field("Colour", colorField(() => d.color, (v) => set(d, "color", v), { placeholder: "accent" })),
        field("Folder", text(d, "dir", { mono: true, placeholder: "badges" }), "Next to the config file"))),
  ];
}

const TAB_VIEWS = { profile: profileTab, info: infoTab, logos: logosTab, motion: motionTab, look: lookTab, window: windowTab, badges: badgesTab, editor: editorTab };

// ---- preview and export --------------------------------------------------------------------

function setPreview(svgText) {
  URL.revokeObjectURL(S.url);
  S.url = URL.createObjectURL(new Blob([svgText], { type: "image/svg+xml" }));
  const img = $("#preview");
  img.src = S.url;
  img.hidden = false;
  $("#preview-empty").hidden = true;
}

async function renderPreview() {
  const seq = ++S.seq;
  let res;
  try {
    res = await api("/api/render", { config: S.cfg, live: S.live });
  } catch (e) {
    flash(`The readmefetch server stopped answering (${e.message}). Is \`readmefetch web\` still running?`);
    return;
  }
  if (seq !== S.seq) return;
  if (!res.ok) { flash(res.error); return; }
  if ($("#flash").classList.contains("error")) flash("");
  S.last = res;
  setPreview(res.svg);
  drawBadgePreviews();
  $("#copy-badge-lines").hidden = !(res.badges || []).length;
  const it = S.cfg.intro || {};
  const style = S.cfg.window?.style || "macos";
  $("#meta").replaceChildren(...[
    `${res.width} × ${res.height} px`,
    (S.meta.window_labels || {})[style] || style,
    `intro ${res.intro.toFixed(1)} s (${it.scope || "info"}${it.scope === "none" ? "" : `, ${it.direction || "left-to-right"}`})`,
    `${S.cfg.logos.length} logo${S.cfg.logos.length === 1 ? "" : "s"}, ${res.period.toFixed(0)} s per cycle`,
    `${(res.svg.length / 1024).toFixed(0)} KB`,
  ].map((x) => h("span", { text: x })), ...(res.note ? [h("span", { class: "note", text: res.note })] : []));
  $("#readme-title").textContent = `${S.cfg.github || S.cfg.user} / README.md`;
}

const baseName = (p) => String(p || "readmefetch.svg").split(/[\\/]/).pop();

function workflow() {
  const configName = baseName(S.meta.path);
  const extra = configName === "readmefetch.toml" ? "" : `\n        with:\n          config: ${configName}`;
  return `name: readmefetch
on:
  schedule: [{ cron: "0 4 * * *" }]   # daily, for {uptime} and the live numbers
  workflow_dispatch:
  push: { paths: [${configName}] }
permissions:
  contents: write
jobs:
  render:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aurelioochoa/readmefetch@v1${extra}
`;
}

function escapeAttr(s) {
  return String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

async function makeGif() {
  const btn = $("#gif-make");
  const status = $("#gif-status");
  btn.disabled = true;
  const started = Date.now();
  const tick = setInterval(() => { status.textContent = `Rendering every frame in a headless browser… ${Math.round((Date.now() - started) / 1000)} s`; }, 500);
  try {
    const res = await api("/api/gif", {
      config: S.cfg, live: S.live, fps: Number($("#gif-fps").value), scale: Number($("#gif-scale").value), intro: $("#gif-intro").checked,
    });
    if (!res.ok) { status.textContent = `GIF failed: ${res.error}`; return; }
    const url = URL.createObjectURL(res.blob);
    $("#gif-img").src = url;
    $("#gif-img").hidden = false;
    $("#gif-download").href = url;
    $("#gif-download").download = baseName(S.cfg.output).replace(/\.svg$/i, "") + ".gif";
    $("#gif-result").hidden = false;
    status.textContent = `Done: ${(res.blob.size / 1024).toFixed(0)} KB in ${Math.round((Date.now() - started) / 1000)} s.`;
  } catch (e) {
    status.textContent = `GIF failed: ${e.message}`;
  } finally {
    clearInterval(tick);
    btn.disabled = false;
  }
}

function save() {
  const target = S.meta.path;
  dialog("Save to disk", [
    h("p", {}, "This writes ", h("code", { text: target }), " and the SVG next to it (", h("code", { text: S.cfg.output }), ")."),
    S.meta.exists ? h("p", { class: "muted small", text: "The current file is copied to a .bak first. Comments in it aren't kept; the new file has short notes of its own." }) : null,
  ], [{ label: "Cancel" }, {
    label: "Save", primary: true, onclick: async () => {
      const res = await api("/api/save", { config: S.cfg, live: S.live });
      if (!res.ok) { flash(res.error); return; }
      setDirty(false);
      S.meta.exists = true;
      const extra = res.badges ? `, ${res.badges} badge${res.badges === 1 ? "" : "s"} in ${res.badge_dir}` : "";
      flash(`Saved ${res.config_path} and ${res.svg_path}${extra}${res.backup ? ` (old config in ${res.backup})` : ""}.`, "success", 8000);
      return true;
    },
  }]);
}

// ---- start -------------------------------------------------------------------------------

async function start() {
  const state = await api("/api/state");
  S.meta = state;
  if (state.api !== API_VERSION) flash(STALE_SERVER);
  S.cfg = state.config;
  S.cfg.logo ||= {};
  S.live = localStorage.getItem("readmefetch.live") === null ? Boolean(S.cfg.github) : localStorage.getItem("readmefetch.live") === "1";
  $("#live").checked = S.live;
  $("#live").addEventListener("change", (e) => { S.live = e.target.checked; localStorage.setItem("readmefetch.live", S.live ? "1" : "0"); renderPreview(); });
  $("#file-path-text").textContent = state.path;
  $("#file-path").prepend(oct("pencil"));
  $("#file-path").title = state.exists ? `Editing ${state.path}` : `${state.path} doesn't exist yet: Save creates it`;
  $("#version").textContent = `v${state.version}`;
  $("#footer-note").textContent = `readmefetch ${state.version}. Logo credits are listed in CREDITS.md and kept inside every SVG.`;

  const mode = localStorage.getItem("readmefetch.mode") || "dark";
  const applyMode = (m) => {
    document.documentElement.dataset.colorMode = m;
    const label = m === "dark" ? "Light page" : "Dark page";
    $("#color-mode").replaceChildren(oct(m === "dark" ? "sun" : "moon"));
    $("#color-mode").setAttribute("aria-label", label);
    $("#color-mode").title = `${label} (the editor and the README background)`;
    $("#color-mode").setAttribute("aria-pressed", String(m === "light"));
  };
  applyMode(mode);
  $("#color-mode").addEventListener("click", () => {
    const m = document.documentElement.dataset.colorMode === "dark" ? "light" : "dark";
    localStorage.setItem("readmefetch.mode", m);
    applyMode(m);
  });

  const names = h("datalist", { id: "color-names" }, Object.keys(state.themes["github-dark"]).map((k) => h("option", { value: k })));
  document.body.append(names);
  $("#tabs").replaceChildren(...TABS.map(([name, label, icon]) => h("button", {
    type: "button", class: "tab", role: "tab", dataset: { tab: name }, "aria-selected": String(name === S.tab), onclick: () => showTab(name),
  }, h("span", { class: "tab-inner" }, oct(icon), h("span", { text: label })))));

  $("#replay").prepend(oct("sync"));
  $("#replay").addEventListener("click", () => S.last && setPreview(S.last.svg));
  $("#zoom").prepend(oct("screen-full"));
  $("#zoom").addEventListener("click", () => {
    const on = $(".readme-body").classList.toggle("actual");
    $("#zoom").setAttribute("aria-pressed", String(on));
    $("#zoom").replaceChildren(oct(on ? "screen-normal" : "screen-full"), on ? "Fit" : "Actual size");
  });
  $("#save").addEventListener("click", save);
  $("#dl-svg").addEventListener("click", () => S.last && download(baseName(S.cfg.output), S.last.svg, "image/svg+xml"));
  $("#dl-toml").addEventListener("click", () => S.last && download("readmefetch.toml", S.last.toml, "application/toml"));
  $("#copy-snippet").addEventListener("click", () => S.last && copy(`<img src="${escapeAttr(S.cfg.output)}" alt="${escapeAttr(S.last.alt)}" width="100%">`, "README snippet"));
  $("#copy-workflow").addEventListener("click", () => copy(workflow(), "workflow (save it as .github/workflows/readmefetch.yml)"));
  $("#gif-make").addEventListener("click", makeGif);
  $("#copy-badge-lines").addEventListener("click", () => S.last && copy(S.last.badge_snippet, "badge lines for your README"));
  if (!state.gif.available) {
    $("#gif-make").disabled = true;
    $("#gif-status").textContent = state.gif.reason;
  } else {
    $("#gif-status").textContent = `Uses ${baseName(state.gif.browser)} in the background; a GIF takes 10 to 60 seconds.`;
  }
  window.addEventListener("beforeunload", (e) => { if (S.dirty) { e.preventDefault(); e.returnValue = ""; } });

  if (state.error) flash(state.error, "warn");
  showTab(S.tab);
  renderPreview();
}

// Anything that still throws (a click handler, a timer) shows up instead of doing nothing.
const oops = (message) => flash(S.meta && S.meta.api !== API_VERSION ? STALE_SERVER : `Something went wrong: ${message}`);
window.addEventListener("error", (e) => oops(e.message));
window.addEventListener("unhandledrejection", (e) => oops(e.reason?.message || e.reason));
start().catch((e) => flash(`Couldn't start: ${e.message}`));
