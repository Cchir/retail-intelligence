// Builds presentation/Retail-Intelligence-Stratum.pptx from deck_data.json (exported from the project's
// serving layer) and the dashboard screenshots.  Run:  node build_deck.js
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const lu = require("react-icons/lu");
const { applyTheme } = require("./apply_theme.js");

const DATA = JSON.parse(fs.readFileSync(path.join(__dirname, "deck_data.json"), "utf8"));
const FIG = path.join(__dirname, "..", "reports", "figures");
const OUT = path.join(__dirname, "Retail-Intelligence-Stratum.pptx");

// Stratum brand (stratumdata.org). Dark deck: lt1/lt2 carry text, dk1/dk2 carry background/surfaces.
const HEX = {
  ink: "0B0E13", surface: "141A24", hi: "EEF2F8", text: "C5CDDA",
  cobalt: "8AA0FF", amber: "F2B65C", teal: "58D6C2", muted: "8C97A8", deep: "5A6CF0", line: "242E3D",
};
const THEME = {
  name: "Stratum Dark",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: HEX.ink, lt1: HEX.hi, dk2: HEX.surface, lt2: HEX.text,
    accent1: HEX.cobalt, accent2: HEX.amber, accent3: HEX.teal, accent4: HEX.muted,
    accent5: HEX.deep, accent6: HEX.line, hlink: HEX.cobalt, folHlink: HEX.teal,
  },
};

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.author = "Stratum";
pres.company = "Stratum";
pres.title = "Retail Intelligence: a Stratum case study";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const INK = C.text1, SURFACE = C.text2, HI = C.background1, TEXT = C.background2;
const COBALT = C.accent1, AMBER = C.accent2, TEAL = C.accent3, MUTED = C.accent4, LINE = C.accent6;
const HEAD = "+mj-lt";

const W = 13.333, MX = 0.6;

// ---------------------------------------------------------------- layouts
const footer = [
  { text: { text: "stratum  ·  Retail Intelligence case study", options: { x: MX, y: 6.98, w: 6, h: 0.3, fontSize: 10, color: MUTED, margin: 0 } } },
];
pres.defineSlideMaster({
  title: "Title",
  background: { color: INK },
  objects: [
    { placeholder: { options: { name: "eyebrow", type: "body", x: MX + 0.4, y: 1.55, w: 9, h: 0.4, fontSize: 13, bold: true, color: COBALT, charSpacing: 4, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 2.1, w: 10.5, h: 2.2, fontSize: 60, bold: true, color: HI, margin: 0, valign: "top", align: "left" }, text: "" } },
    { placeholder: { options: { name: "body", type: "body", x: MX, y: 4.45, w: 9.8, h: 1.2, fontSize: 20, color: TEXT, margin: 0, valign: "top" }, text: "" } },
  ],
});
pres.defineSlideMaster({
  title: "Content",
  background: { color: INK },
  objects: [
    ...footer,
    { placeholder: { options: { name: "eyebrow", type: "body", x: MX + 0.3, y: 0.42, w: 10, h: 0.3, fontSize: 12, bold: true, color: COBALT, charSpacing: 4, margin: 0 }, text: "" } },
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.8, w: W - 2 * MX, h: 0.8, fontSize: 36, bold: true, color: HI, margin: 0, valign: "top", align: "left" }, text: "" } },
  ],
  slideNumber: { x: W - MX - 0.6, y: 6.98, w: 0.6, h: 0.3, fontSize: 10, color: MUTED, align: "right" },
});

// ---------------------------------------------------------------- helpers
const iconCache = {};
async function icon(name, hex) {
  const key = name + hex;
  if (!iconCache[key]) {
    const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(lu[name], { color: "#" + hex, size: 256, strokeWidth: 1.75 }));
    const png = await sharp(Buffer.from(svg)).resize(256, 256).png().toBuffer();
    iconCache[key] = "image/png;base64," + png.toString("base64");
  }
  return iconCache[key];
}

// The brand mark from the website: a small rounded square in cobalt beside the eyebrow.
function brandDot(slide, x, y) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: 0.14, h: 0.14, rectRadius: 0.03, fill: { color: COBALT }, line: { type: "none" }, objectName: "brand mark" });
}

function card(slide, x, y, w, h, name, fill = SURFACE) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.12, fill: { color: fill }, line: { color: LINE, width: 0.75 }, objectName: name,
  });
}

async function iconTile(slide, name, x, y, colorHex, size = 0.62) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w: size, h: size, rectRadius: 0.1, fill: { color: INK }, line: { color: LINE, width: 0.75 }, objectName: "icon tile " + name,
  });
  const pad = size * 0.22;
  slide.addImage({ data: await icon(name, colorHex), x: x + pad, y: y + pad, w: size - 2 * pad, h: size - 2 * pad, altText: name.replace("Lu", "") + " icon" });
}

function text(slide, t, opts) {
  slide.addText(t, { isTextBox: true, margin: 0, color: TEXT, fontSize: 15, valign: "top", ...opts });
}

function content(eyebrow, title, section) {
  const s = pres.addSlide({ masterName: "Content", sectionTitle: section });
  brandDot(s, MX, 0.5);
  s.addText(eyebrow.toUpperCase(), { placeholder: "eyebrow" });
  s.addText(title, { placeholder: "title" });
  return s;
}

const axis = () => ({
  catAxisLabelColor: HEX.muted, valAxisLabelColor: HEX.muted, catAxisLabelFontSize: 11, valAxisLabelFontSize: 11,
  catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt", catAxisLineShow: false, valAxisLineShow: false,
  valGridLine: { color: HEX.line, size: 0.75 }, catGridLine: { style: "none" },
  legendFontFace: "+mn-lt", legendFontSize: 12, legendColor: HEX.text, dataLabelFontFace: "+mn-lt",
  titleFontFace: "+mn-lt", titleColor: HEX.hi, titleFontSize: 14,
});

const gbpK = (v) => "£" + v.toLocaleString("en-GB") + "k";

// ---------------------------------------------------------------- slides
async function build() {
  // 1. Title ---------------------------------------------------------
  pres.addSection({ title: "Introduction" });
  let s = pres.addSlide({ masterName: "Title", sectionTitle: "Introduction" });
  brandDot(s, MX, 1.68);
  s.addText("STRATUM  ·  CASE STUDY", { placeholder: "eyebrow" });
  s.addText("Retail Intelligence", { placeholder: "title" });
  s.addText("From a million messy transactions to decisions a business owner can act on.", { placeholder: "body" });
  text(s, "Data engineering  ·  Statistics  ·  Machine learning  ·  Analytics", { x: MX, y: 6.55, w: 8, h: 0.35, fontSize: 13, color: MUTED });
  // Signature visual: a scatter resolving into a trend line, echoing the website hero.
  const pts = [];
  let seed = 7;
  const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
  for (let i = 0; i < 34; i++) {
    const t = i / 33;
    pts.push({ x: 10.0 + t * 2.6, y: 5.6 - t * 2.9 + (rnd() - 0.5) * 0.9 });
  }
  s.addShape(pres.shapes.LINE, { x: 10.0, y: 2.7, w: 2.6, h: 2.9, flipV: true, line: { color: TEAL, width: 2 }, objectName: "trend line" });
  pts.forEach((p, i) => {
    const out = i % 9 === 4;
    const r = out ? 0.11 : 0.08;
    s.addShape(pres.shapes.OVAL, { x: p.x - r / 2, y: p.y - r / 2, w: r, h: r, fill: { color: out ? AMBER : COBALT, transparency: out ? 0 : 15 }, line: { type: "none" }, objectName: "data point" });
  });
  s.addNotes("Retail Intelligence is an end-to-end data project on real transaction data: a UK online giftware wholesaler, two years, just over a million invoice lines. It shows the full path I take with a client: understand the data, engineer a pipeline you can trust, test what the business believes, build models that are checked against simple baselines, and hand over a dashboard people can use.");

  // 2. The brief ------------------------------------------------------
  s = content("The brief", "A wholesaler with data, but no answers", "Introduction");
  text(s, [
    { text: "A UK online giftware wholesaler selling mainly to small shops. Two years of sales exports: ", options: {} },
    { text: "1,067,371 invoice lines", options: { bold: true, color: HI } },
    { text: " in a spreadsheet, and four questions the owner couldn't answer.", options: {} },
  ], { x: MX, y: 1.75, w: 11.5, h: 0.75, fontSize: 17 });
  const qs = [
    ["LuTrendingUp", "Is the business growing?", "Revenue looks up on some charts and down on others."],
    ["LuUsers", "Who are our valuable customers?", "And which of them are quietly slipping away?"],
    ["LuPhoneCall", "Who should we call this quarter?", "The account team can't contact everyone."],
    ["LuCalendarRange", "What should we plan for?", "Stock and staffing for the next quarter."],
  ];
  for (let i = 0; i < 4; i++) {
    const x = MX + i * 3.06, y = 2.85, w = 2.82, h = 3.6;
    card(s, x, y, w, h, "question card " + (i + 1));
    await iconTile(s, qs[i][0], x + 0.3, y + 0.35, HEX.cobalt);
    text(s, "Q" + (i + 1), { x: x + 2.0, y: y + 0.45, w: 0.55, h: 0.4, fontSize: 14, bold: true, color: MUTED, align: "right" });
    text(s, qs[i][1], { x: x + 0.3, y: y + 1.25, w: w - 0.6, h: 1.0, fontSize: 19, bold: true, color: HI, fontFace: HEAD });
    text(s, qs[i][2], { x: x + 0.3, y: y + 2.35, w: w - 0.6, h: 1.0, fontSize: 14, color: TEXT });
  }
  s.addNotes("The data is the public UCI Online Retail II dataset. It's real transaction data, with all the mess that comes with it, which makes it a realistic stand-in for what an SMB client actually has. The four questions are typical of what owners ask.");

  // 3. Answers at a glance ---------------------------------------------
  s = content("The answers", "Four questions, four evidence-backed answers", "Introduction");
  const stats = [
    ["+2.2%", AMBER, "Is it growing?", "No: revenue is flat. The year-over-year change is not statistically significant."],
    ["69%", COBALT, "Who matters?", "of revenue comes from 22% of customers, the “Champions”."],
    ["2.1×", TEAL, "Who to call?", "more buyers reached by the model's top 10% than by random calling."],
    ["±10%", COBALT, "What to plan for?", "weekly error on a forecast that beats the standard benchmark."],
  ];
  for (let i = 0; i < 4; i++) {
    const x = MX + (i % 2) * 6.12, y = 1.85 + Math.floor(i / 2) * 2.5, w = 5.9, h = 2.3;
    card(s, x, y, w, h, "answer " + (i + 1));
    text(s, stats[i][0], { x: x + 0.35, y: y + 0.4, w: 2.6, h: 1.1, fontSize: 54, bold: true, color: stats[i][1], fontFace: HEAD, valign: "middle" });
    text(s, stats[i][2].toUpperCase(), { x: x + 3.05, y: y + 0.42, w: 2.6, h: 0.3, fontSize: 11, bold: true, color: MUTED, charSpacing: 2 });
    text(s, stats[i][3], { x: x + 3.05, y: y + 0.8, w: 2.6, h: 1.3, fontSize: 15, color: TEXT });
  }
  s.addNotes("The headline: the business is flat, value is concentrated in a small group, and there is a measurable way to focus the sales team. Every number on this slide is validated on data the model never saw, or formally tested.");

  // 4. Approach ------------------------------------------------------
  pres.addSection({ title: "How it was built" });
  s = content("The approach", "One pipeline, from raw export to decision", "How it was built");
  const steps = [
    ["LuSearch", "Profile", "Explore the raw data before writing any cleaning rule"],
    ["LuDatabase", "Engineer", "Layered ETL into a DuckDB star schema"],
    ["LuShieldCheck", "Verify", "15 automated data quality checks"],
    ["LuFlaskConical", "Analyse", "Hypothesis tests, segments, lifetime value, propensity, forecasts"],
    ["LuLayoutDashboard", "Deliver", "Interactive dashboard, notebooks and documentation"],
  ];
  for (let i = 0; i < 5; i++) {
    const x = MX + i * 2.45, y = 2.25, w = 2.15, h = 3.3;
    card(s, x, y, w, h, "step " + (i + 1));
    text(s, "0" + (i + 1), { x: x + 0.3, y: y + 0.3, w: 0.8, h: 0.35, fontSize: 13, bold: true, color: COBALT });
    await iconTile(s, steps[i][0], x + 0.3, y + 0.8, HEX.cobalt, 0.58);
    text(s, steps[i][1], { x: x + 0.3, y: y + 1.6, w: w - 0.5, h: 0.45, fontSize: 20, bold: true, color: HI, fontFace: HEAD });
    text(s, steps[i][2], { x: x + 0.3, y: y + 2.1, w: w - 0.5, h: 1.1, fontSize: 13.5, color: TEXT });
    if (i < 4) s.addImage({ data: await icon("LuArrowRight", HEX.muted), x: x + w + 0.07, y: y + h / 2 - 0.08, w: 0.16, h: 0.16, altText: "next step" });
  }
  text(s, "One command (uv run retail all) rebuilds everything from the public source in about a minute.", { x: MX, y: 5.95, w: 11.5, h: 0.4, fontSize: 14, color: MUTED, italic: true });
  s.addNotes("This mirrors the process on the Stratum website: scope, build, validate, hand over. The whole thing is reproducible with one command, has 18 automated tests, and runs in CI on every push.");

  // 5. Messy data ----------------------------------------------------
  s = content("Step 1 · Profile", "The raw data was messier than it looked", "How it was built");
  const issues = [
    ["23%", "of lines have no customer ID (guest checkouts)"],
    ["34,335", "exact duplicate lines"],
    ["19,494", "cancellation lines, plus postage and fees mixed in with products"],
    ["80,995", "units in one order (£168k), cancelled 12 minutes later"],
  ];
  issues.forEach(([n, l], i) => {
    const y = 1.85 + i * 1.18;
    card(s, MX, y, 5.4, 1.02, "issue " + (i + 1));
    text(s, n, { x: MX + 0.3, y: y + 0.16, w: 1.9, h: 0.7, fontSize: 30, bold: true, color: AMBER, fontFace: HEAD, valign: "middle" });
    text(s, l, { x: MX + 2.3, y: y + 0.16, w: 2.9, h: 0.7, fontSize: 14, color: TEXT, valign: "middle" });
  });
  card(s, 6.35, 1.85, 6.38, 4.56, "funnel card");
  const rs = DATA.row_status;
  const labels = rs.row_status.map((r) => r.replace(/_/g, " ").replace("zero or negative price", "zero / negative price"));
  s.addChart(pres.charts.BAR, [{ name: "rows", labels: labels.slice().reverse(), values: rs.n_rows.slice().reverse() }], {
    x: 6.55, y: 2.0, w: 6.0, h: 4.3, barDir: "bar", ...axis(),
    showTitle: true, title: "Every one of 1,067,371 rows accounted for (log scale)",
    valAxisLogScaleBase: 10, valAxisMinVal: 10, valAxisHidden: true, valGridLine: { style: "none" },
    chartColors: [HEX.amber, HEX.amber, HEX.amber, HEX.amber, HEX.amber, HEX.cobalt], invertedColors: [HEX.amber],
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#,##0", dataLabelColor: HEX.text, dataLabelFontSize: 11,
    barGapWidthPct: 45, showLegend: false,
  });
  s.addNotes("Every issue here became a documented cleaning rule. Rows are tagged with a status rather than deleted, so the path from the source file to the analysed data is fully auditable. 1,003,214 valid sale lines remain.");

  // 6. Pipeline ------------------------------------------------------
  s = content("Step 2 · Engineer & verify", "A pipeline built to be trusted", "How it was built");
  const layers = [
    ["LuFileSpreadsheet", "Bronze", "Untouched copy of the source", ["Checksum-verified download", "Lineage columns: sheet, row, load time", "Re-run without the network"]],
    ["LuLayers", "Silver", "Typed, standardised, tagged", ["Every row gets a status", "One canonical name per product", "Robust outlier flags"]],
    ["LuDatabase", "Gold", "DuckDB star schema", ["Date, product, customer dimensions", "Sales, returns, order facts", "KPI, cohort and country marts"]],
  ];
  for (let i = 0; i < 3; i++) {
    const x = MX + i * 4.1, y = 1.85, w = 3.85, h = 3.25;
    card(s, x, y, w, h, layers[i][1] + " layer");
    await iconTile(s, layers[i][0], x + 0.3, y + 0.3, i === 2 ? HEX.teal : HEX.cobalt);
    text(s, layers[i][1], { x: x + 1.1, y: y + 0.3, w: 2.4, h: 0.4, fontSize: 20, bold: true, color: HI, fontFace: HEAD });
    text(s, layers[i][2], { x: x + 1.1, y: y + 0.7, w: 2.6, h: 0.3, fontSize: 13, color: MUTED });
    text(s, layers[i][3].map((t, j) => ({ text: t, options: { bullet: { indent: 15 }, breakLine: j < 2 } })),
      { x: x + 0.3, y: y + 1.3, w: w - 0.6, h: 1.7, fontSize: 14.5, paraSpaceAfter: 8 });
  }
  const checks = [["15 / 15", "data quality checks pass"], ["100%", "of rows and revenue reconcile end to end"], ["< 1 min", "full rebuild with one command"]];
  checks.forEach(([n, l], i) => {
    const x = MX + i * 4.1;
    card(s, x, 5.3, 3.85, 1.15, "check stat " + (i + 1));
    text(s, n, { x: x + 0.3, y: 5.42, w: 1.7, h: 0.9, fontSize: 26, bold: true, color: TEAL, fontFace: HEAD, valign: "middle" });
    text(s, l, { x: x + 2.0, y: 5.42, w: 1.7, h: 0.9, fontSize: 13, color: TEXT, valign: "middle" });
  });
  s.addNotes("Bronze, silver and gold is the same layering used in modern warehouses. The quality checks are SQL tests in the spirit of dbt: uniqueness, referential integrity, reconciliation and range checks. If any error-level check fails, the pipeline stops, which is what 'pipelines that don't break' means in practice.");

  // 7. Finding: flat --------------------------------------------------
  pres.addSection({ title: "What the data says" });
  s = content("Finding 1 · Growth", "Revenue is flat. The monthly chart hides it", "What the data says");
  card(s, MX, 1.85, 8.1, 4.6, "monthly chart card");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"];
  s.addChart(pres.charts.LINE, [
    { name: "2010", labels: months, values: DATA.monthly["2010"] },
    { name: "2011", labels: months, values: DATA.monthly["2011"] },
  ], {
    x: MX + 0.2, y: 2.0, w: 7.7, h: 4.3, ...axis(), showTitle: true, title: "Monthly revenue, Jan to Nov (£k)",
    chartColors: [HEX.muted, HEX.cobalt], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 6,
    showLegend: true, legendPos: "b", valAxisLabelFormatCode: "£#,##0\"k\"",
  });
  card(s, 8.95, 1.85, 3.78, 4.6, "growth callout");
  text(s, "+2.2%", { x: 9.25, y: 2.15, w: 3.2, h: 1.0, fontSize: 54, bold: true, color: AMBER, fontFace: HEAD });
  text(s, "average daily revenue, Jan–Nov 2011 vs 2010", { x: 9.25, y: 3.15, w: 3.2, h: 0.6, fontSize: 14, color: TEXT });
  text(s, [
    { text: "95% CI includes zero (p = 0.58)", options: { bold: true, color: HI, breakLine: true } },
    { text: "Welch's t-test with a bootstrap interval. The busy monthly chart suggests momentum; the test shows the business is standing still.", options: {} },
  ], { x: 9.25, y: 4.05, w: 3.2, h: 2.2, fontSize: 13.5, paraSpaceAfter: 6 });
  s.addNotes("This is the most important finding for the owner, and it's easy to miss: month-to-month noise looks like growth. Formally testing it (with an effect size and confidence interval, not just a p-value) shows the 2011 lines sit on top of the 2010 lines.");

  // 8. Finding: concentration ------------------------------------------
  s = content("Finding 2 · Customers", "22% of customers drive 69% of revenue", "What the data says");
  card(s, MX, 1.85, 8.1, 4.6, "segment chart card");
  const sg = DATA.segments;
  s.addChart(pres.charts.BAR, [
    { name: "Share of customers", labels: sg.segment, values: sg.cust_share },
    { name: "Share of revenue", labels: sg.segment, values: sg.revenue_share },
  ], {
    x: MX + 0.2, y: 2.0, w: 7.7, h: 4.3, barDir: "col", barGrouping: "clustered", ...axis(),
    showTitle: true, title: "RFM segments: share of customers vs share of revenue",
    chartColors: [HEX.muted, HEX.cobalt], valAxisLabelFormatCode: "0%", valAxisMaxVal: 0.8,
    showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0%", dataLabelColor: HEX.text, dataLabelFontSize: 10,
    showLegend: true, legendPos: "b", barGapWidthPct: 60,
  });
  card(s, 8.95, 1.85, 3.78, 4.6, "concentration callout");
  const conc = [["69%", "of revenue from the Champions segment", COBALT], ["55%", "of next year's predicted value sits with the top 10% of customers", TEAL], ["0.74", "Gini coefficient of customer revenue", AMBER]];
  conc.forEach(([n, l, col], i) => {
    const y = 2.1 + i * 1.42;
    text(s, n, { x: 9.25, y, w: 3.2, h: 0.65, fontSize: 32, bold: true, color: col, fontFace: HEAD });
    text(s, l, { x: 9.25, y: y + 0.65, w: 3.2, h: 0.65, fontSize: 13.5, color: TEXT });
  });
  s.addNotes("RFM scores every customer on recency, frequency and monetary value. k-means on the same data confirms the structure. Retaining the Champions is the single biggest lever the business has; 'At risk' and 'Can't lose' are the win-back list.");

  // 9. Myths ---------------------------------------------------------
  s = content("Finding 3 · Assumptions, tested", "Two common beliefs that turned out to be wrong", "What the data says");
  const myths = [
    ["LuGift", "“Gift-season customers are one-off buyers”", "66%", "59%", "return within 180 days if first bought in Nov–Dec", "if first bought the rest of the year", "Two-proportion z-test, p < 0.001. Q4 acquisition is worth investing in, not discounting."],
    ["LuUndo2", "“Customers who return items are a problem”", "£2,072", "£479", "median lifetime spend of customers who return items", "for customers who never return anything", "Mann-Whitney U with bootstrap CI. Returns come with volume: don't deprioritise these accounts."],
  ];
  for (let i = 0; i < 2; i++) {
    const m = myths[i], x = MX + i * 6.12, y = 1.85, w = 5.9, h = 4.35;
    card(s, x, y, w, h, "myth " + (i + 1));
    await iconTile(s, m[0], x + 0.35, y + 0.35, HEX.amber);
    text(s, "BELIEF", { x: x + 1.15, y: y + 0.35, w: 2, h: 0.25, fontSize: 11, bold: true, color: MUTED, charSpacing: 2 });
    text(s, m[1], { x: x + 1.15, y: y + 0.62, w: w - 1.5, h: 0.7, fontSize: 17, bold: true, color: HI, fontFace: HEAD });
    text(s, m[2], { x: x + 0.35, y: y + 1.6, w: 2.5, h: 0.9, fontSize: 44, bold: true, color: TEAL, fontFace: HEAD });
    text(s, m[4], { x: x + 0.35, y: y + 2.5, w: 2.4, h: 0.85, fontSize: 13, color: TEXT });
    text(s, "vs", { x: x + 2.8, y: y + 1.85, w: 0.4, h: 0.5, fontSize: 16, color: MUTED });
    text(s, m[3], { x: x + 3.25, y: y + 1.6, w: 2.4, h: 0.9, fontSize: 44, bold: true, color: MUTED, fontFace: HEAD });
    text(s, m[5], { x: x + 3.25, y: y + 2.5, w: 2.3, h: 0.85, fontSize: 13, color: TEXT });
    text(s, m[6], { x: x + 0.35, y: y + 3.35, w: w - 0.7, h: 0.9, fontSize: 13.5, color: TEXT, italic: true });
  }
  text(s, "Also tested: international orders are larger (median £418 vs £299), and weekday strongly drives revenue. All five tests are Holm-corrected for multiple comparisons.", { x: MX, y: 6.55, w: 12.1, h: 0.35, fontSize: 12, color: MUTED });
  s.addNotes("Five hypothesis tests were run. Reporting effect sizes and confidence intervals, and correcting for multiple testing, is what separates evidence from anecdote. These two results directly change how the sales team should treat customers.");

  // 10. CLV ------------------------------------------------------------
  pres.addSection({ title: "Predictive models" });
  s = content("Model 1 · Customer lifetime value", "Predicting what each customer is worth", "Predictive models");
  card(s, MX, 1.85, 8.1, 4.6, "CLV chart card");
  const cal = DATA.clv_cal;
  const xl = cal.x_bucket.map((v) => (v === 10 ? "10+" : String(v)));
  s.addChart(pres.charts.LINE, [
    { name: "Actual", labels: xl, values: cal.x_holdout },
    { name: "BG/NBD model", labels: xl, values: cal.pred_holdout },
    { name: "Naive baseline", labels: xl, values: cal.baseline_holdout },
  ], {
    x: MX + 0.2, y: 2.0, w: 7.7, h: 4.3, ...axis(), showTitle: true,
    title: "Purchases in a 26-week holdout, by past purchase count",
    chartColors: [HEX.hi, HEX.cobalt, HEX.amber], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 6,
    showLegend: true, legendPos: "b", showCatAxisTitle: true, catAxisTitle: "repeat purchases before the holdout",
    catAxisTitleColor: HEX.muted, catAxisTitleFontSize: 11, catAxisTitleFontFace: "+mn-lt",
  });
  card(s, 8.95, 1.85, 3.78, 4.6, "CLV callout");
  text(s, "−1.7%", { x: 9.25, y: 2.1, w: 3.2, h: 0.8, fontSize: 44, bold: true, color: TEAL, fontFace: HEAD });
  text(s, "error in total predicted purchases, on six months the model never saw", { x: 9.25, y: 2.9, w: 3.2, h: 0.7, fontSize: 13.5, color: TEXT });
  text(s, "+69%", { x: 9.25, y: 3.75, w: 3.2, h: 0.8, fontSize: 44, bold: true, color: AMBER, fontFace: HEAD });
  text(s, "the naive “keep buying at your usual rate” baseline", { x: 9.25, y: 4.55, w: 3.2, h: 0.5, fontSize: 13.5, color: TEXT });
  text(s, "BG/NBD + Gamma-Gamma, implemented from the original papers.", { x: 9.25, y: 5.4, w: 3.2, h: 0.8, fontSize: 12.5, color: MUTED, italic: true });
  s.addNotes("The BG/NBD model treats each customer as buying at their own rate while 'alive', with a chance of silently leaving after each purchase, which suits businesses where customers never tell you they've left. I wrote the likelihoods by hand with scipy rather than using a library, and unit-tested that they recover known parameters from simulated data.");

  // 11. Propensity -----------------------------------------------------
  s = content("Model 2 · Purchase propensity", "Who to call: twice the buyers for the same effort", "Predictive models");
  card(s, MX, 1.85, 6.6, 4.6, "gains chart card");
  const dec = ["10%", "20%", "30%", "40%", "50%", "60%", "70%", "80%", "90%", "100%"];
  s.addChart(pres.charts.LINE, [
    { name: "Model", labels: dec, values: DATA.gains },
    { name: "Random", labels: dec, values: dec.map((_, i) => (i + 1) / 10) },
  ], {
    x: MX + 0.2, y: 2.0, w: 6.2, h: 4.3, ...axis(), showTitle: true, title: "Share of next quarter's buyers reached",
    chartColors: [HEX.cobalt, HEX.muted], lineSize: 2.5, lineDataSymbol: "none",
    valAxisLabelFormatCode: "0%", valAxisMaxVal: 1, showLegend: true, legendPos: "b",
    showCatAxisTitle: true, catAxisTitle: "share of customers contacted", catAxisTitleColor: HEX.muted, catAxisTitleFontSize: 11, catAxisTitleFontFace: "+mn-lt",
  });
  card(s, 7.45, 1.85, 5.28, 2.15, "campaign callout");
  text(s, "CALL 20% OF CUSTOMERS", { x: 7.75, y: 2.05, w: 4.6, h: 0.3, fontSize: 11, bold: true, color: MUTED, charSpacing: 2 });
  text(s, "889", { x: 7.75, y: 2.4, w: 2.0, h: 0.8, fontSize: 44, bold: true, color: COBALT, fontFace: HEAD });
  text(s, "buyers reached with the model", { x: 7.75, y: 3.2, w: 2.2, h: 0.6, fontSize: 13, color: TEXT });
  text(s, "457", { x: 10.25, y: 2.4, w: 2.0, h: 0.8, fontSize: 44, bold: true, color: MUTED, fontFace: HEAD });
  text(s, "buyers reached calling at random", { x: 10.25, y: 3.2, w: 2.3, h: 0.6, fontSize: 13, color: TEXT });
  card(s, 7.45, 4.2, 5.28, 2.25, "model comparison");
  const pr = DATA.prop;
  const rows = [[
    { text: "Model", options: { bold: true, color: MUTED } }, { text: "ROC-AUC", options: { bold: true, color: MUTED, align: "right" } },
    { text: "Lift @10%", options: { bold: true, color: MUTED, align: "right" } }]];
  pr.model.forEach((m, i) => rows.push([
    { text: m.charAt(0).toUpperCase() + m.slice(1), options: { color: i === 1 ? HI : TEXT, bold: i === 1 } },
    { text: pr.roc_auc[i].toFixed(3), options: { align: "right", color: i === 1 ? HI : TEXT, bold: i === 1 } },
    { text: pr.lift_top_decile[i].toFixed(2) + "×", options: { align: "right", color: i === 1 ? HI : TEXT, bold: i === 1 } },
  ]));
  s.addTable(rows, {
    x: 7.7, y: 4.35, w: 4.8, colW: [2.4, 1.2, 1.2], fontSize: 13, fontFace: "+mn-lt", color: TEXT,
    border: { type: "solid", pt: 0.5, color: HEX.line }, fill: { color: HEX.surface }, rowH: 0.36, margin: [0.04, 0.08, 0.04, 0.08],
  });
  text(s, "Out-of-time test. Simple logistic regression matched gradient boosting, so the explainable model ships.", { x: 7.7, y: 5.85, w: 4.8, h: 0.5, fontSize: 12, color: MUTED, italic: true });
  s.addNotes("Features use only data up to a cutoff date and the label is the following 90 days, so there's no leakage (this is unit-tested). Training stacks four quarterly snapshots and the test is the most recent quarter: an honest out-of-time evaluation. The headline business number is 889 vs 457 buyers when the team calls 20% of customers.");

  // 12. Forecast -------------------------------------------------------
  s = content("Model 3 · Forecasting", "A forecast that beats the standard benchmark", "Predictive models");
  card(s, MX, 1.85, 8.1, 4.6, "forecast chart card");
  const wk = DATA.weekly;
  // Label one week per quarter; LibreOffice and older PowerPoint ignore label-frequency settings.
  const allLabels = wk.dates.concat(wk.fdates).map((d, i) => (i % 13 === 0 ? d : " "));
  const nH = wk.rev.length, nF = wk.f.length;
  s.addChart(pres.charts.LINE, [
    { name: "Actual", labels: allLabels, values: wk.rev.concat(Array(nF).fill(null)) },
    { name: "Forecast", labels: allLabels, values: Array(nH - 1).fill(null).concat([wk.rev[nH - 1]], wk.f) },
  ], {
    x: MX + 0.2, y: 2.0, w: 7.7, h: 4.3, ...axis(), showTitle: true, title: "Weekly revenue (£k) and next-12-week forecast",
    chartColors: [HEX.text, HEX.cobalt], lineSize: 2, lineDataSymbol: "none", catAxisLabelFrequency: 13,
    valAxisLabelFormatCode: "£#,##0\"k\"", showLegend: true, legendPos: "b",
  });
  card(s, 8.95, 1.85, 3.78, 4.6, "forecast scores card");
  const fs_ = DATA.fscores;
  const short = { "ensemble (growth-naive + fourier)": "Ensemble", "seasonal naive": "Seasonal naive", "fourier regression": "Fourier regression", "seasonal naive + growth": "Naive + growth", "SARIMAX + fourier": "SARIMAX", "naive (last week)": "Last week" };
  s.addChart(pres.charts.BAR, [{ name: "MASE", labels: fs_.model.map((m) => short[m]).reverse(), values: fs_.mase.slice().reverse() }], {
    x: 9.05, y: 2.0, w: 3.58, h: 3.5, barDir: "bar", ...axis(), showTitle: true, title: "Backtest error (MASE, lower is better)",
    chartColors: [HEX.muted, HEX.muted, HEX.muted, HEX.muted, HEX.muted, HEX.cobalt], invertedColors: [HEX.muted],
    valAxisHidden: true, valGridLine: { style: "none" }, showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.00",
    dataLabelColor: HEX.text, dataLabelFontSize: 11, showLegend: false, barGapWidthPct: 40, valAxisMaxVal: 3.6, titleFontSize: 12,
  });
  text(s, "Below 1.0 beats “same week last year”. The most complex model (SARIMAX) did worst.", { x: 9.25, y: 5.5, w: 3.25, h: 0.8, fontSize: 12.5, color: MUTED, italic: true });
  s.addNotes("Six models were scored on the last 12 weeks, the 2011 peak season. A simple average of two different models wins, at about 10% weekly error and 3% error on the quarter total. Being upfront that the most complex model lost, and that the ensemble was chosen on the same holdout, is part of building trust.");

  // 13. Dashboard ------------------------------------------------------
  pres.addSection({ title: "Delivery" });
  s = content("Step 5 · Deliver", "An interactive dashboard the team can use", "Delivery");
  const shots = [["dashboard_overview.jpg", "Overview: KPIs with like-for-like YoY deltas and filters"],
    ["dashboard_predictive.jpg", "Predictive: model comparison and a campaign simulator"]];
  shots.forEach(([f, cap], i) => {
    const x = MX + i * 6.12, w = 5.9, h = w * 514 / 800;
    card(s, x, 1.85, w, h + 0.75, "screenshot card " + (i + 1));
    s.addImage({ path: path.join(FIG, f), x: x + 0.12, y: 1.97, w: w - 0.24, h: (w - 0.24) * 514 / 800, altText: cap, rounding: false });
    text(s, cap, { x: x + 0.3, y: 1.97 + (w - 0.24) * 514 / 800 + 0.18, w: w - 0.6, h: 0.35, fontSize: 13, color: TEXT });
  });
  text(s, "Five tabs: Overview · Customers · Predictive models · Statistical findings · Data pipeline (with live quality checks)", { x: MX, y: 6.52, w: 12.1, h: 0.35, fontSize: 12.5, color: MUTED });
  s.addNotes("The dashboard is built in Streamlit and reads only a 1 MB serving layer, so it deploys anywhere without the warehouse. The campaign simulator is the feature that sells: drag a slider and see how many buyers the team reaches. The pipeline tab shows the quality checks live, because trust in the numbers is the point.");

  // 14. Recommendations --------------------------------------------------
  s = content("Conclusions", "What I'd tell the business owner", "Delivery");
  const recs = [
    ["LuTarget", "Protect the Champions", "22% of customers bring 69% of revenue. Give them account management and early access to ranges."],
    ["LuPhoneCall", "Call by propensity score", "Each quarter, call the top-scored customers first: about twice the buyers per call."],
    ["LuGift", "Invest in Q4 acquisition", "Gift-season customers come back more often. Don't treat them as one-off buyers."],
    ["LuTrendingUp", "Plan for a flat year", "Stock and staff to the forecast; growth needs a deliberate plan, it isn't happening on its own."],
  ];
  for (let i = 0; i < 4; i++) {
    const x = MX + (i % 2) * 6.12, y = 1.85 + Math.floor(i / 2) * 2.4, w = 5.9, h = 2.2;
    card(s, x, y, w, h, "recommendation " + (i + 1));
    await iconTile(s, recs[i][0], x + 0.35, y + 0.4, HEX.teal);
    text(s, String(i + 1).padStart(2, "0"), { x: x + w - 0.95, y: y + 0.4, w: 0.6, h: 0.4, fontSize: 14, bold: true, color: MUTED, align: "right" });
    text(s, recs[i][1], { x: x + 1.2, y: y + 0.42, w: 3.8, h: 0.5, fontSize: 20, bold: true, color: HI, fontFace: HEAD });
    text(s, recs[i][2], { x: x + 1.2, y: y + 0.98, w: 4.4, h: 1.0, fontSize: 14.5, color: TEXT });
  }
  s.addNotes("Analysis is only useful if it changes a decision. Each recommendation maps to a finding: concentration, the propensity model, the gift-season test, and the flat-growth test plus forecast.");

  // 15. Rigour / toolkit -------------------------------------------------
  s = content("How it's built", "Production habits, not a notebook demo", "Delivery");
  const practices = [
    ["LuCircleCheck", "Validated against baselines", "Every model is tested against a simple alternative on data it never saw"],
    ["LuTestTube", "18 automated tests", "ETL rules, model correctness on simulated data, no-leakage checks, dashboard smoke test"],
    ["LuGitBranch", "CI on every push", "GitHub Actions lints, tests and rebuilds the full pipeline from source"],
    ["LuRepeat", "Reproducible end to end", "One command from the public download to the dashboard"],
  ];
  for (let i = 0; i < 4; i++) {
    const y = 1.85 + i * 1.17;
    card(s, MX, y, 7.3, 1.02, "practice " + (i + 1));
    await iconTile(s, practices[i][0], MX + 0.25, y + 0.2, HEX.cobalt, 0.6);
    text(s, practices[i][1], { x: MX + 1.1, y: y + 0.14, w: 5.9, h: 0.36, fontSize: 16, bold: true, color: HI, fontFace: HEAD });
    text(s, practices[i][2], { x: MX + 1.1, y: y + 0.5, w: 5.95, h: 0.42, fontSize: 13, color: TEXT });
  }
  card(s, 8.15, 1.85, 4.58, 4.53, "toolkit");
  text(s, "TOOLKIT", { x: 8.45, y: 2.1, w: 3, h: 0.3, fontSize: 11, bold: true, color: MUTED, charSpacing: 2 });
  const chips = ["Python", "SQL", "DuckDB", "pandas", "SciPy", "statsmodels", "scikit-learn", "Plotly", "Streamlit", "pytest", "GitHub Actions", "uv"];
  let cx = 8.45, cy = 2.55;
  chips.forEach((c) => {
    const cw = 0.28 + c.length * 0.105;
    if (cx + cw > 12.45) { cx = 8.45; cy += 0.58; }
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: cy, w: cw, h: 0.42, rectRadius: 0.08, fill: { color: INK }, line: { color: LINE, width: 0.75 }, objectName: "chip " + c });
    s.addText(c, { isTextBox: true, x: cx, y: cy, w: cw, h: 0.42, fontSize: 12.5, color: HI, align: "center", valign: "middle", margin: 0 });
    cx += cw + 0.14;
  });
  s.addNotes("This is how the work is handed over to a client: clean, tested code with documentation, so it keeps running whether or not I stay involved.");

  // 16. Close ----------------------------------------------------------
  s = pres.addSlide({ masterName: "Title", sectionTitle: "Delivery" });
  brandDot(s, MX, 1.68);
  s.addText("STRATUM", { placeholder: "eyebrow" });
  s.addText("Have data sitting unused?", { placeholder: "title" });
  s.addText("I'll take the messy data your business already has and turn it into pipelines, models and dashboards your team can actually use.", { placeholder: "body" });
  const contacts = [["LuGlobe", "stratumdata.org", "https://stratumdata.org"], ["LuMail", "stratumfreelance@gmail.com", "mailto:stratumfreelance@gmail.com"]];
  for (let i = 0; i < 2; i++) {
    const y = 5.75 + i * 0.55;
    s.addImage({ data: await icon(contacts[i][0], HEX.cobalt), x: MX, y: y + 0.04, w: 0.3, h: 0.3, altText: i ? "email" : "website" });
    text(s, [{ text: contacts[i][1], options: { hyperlink: { url: contacts[i][2] }, color: HI } }], { x: MX + 0.45, y, w: 5, h: 0.38, fontSize: 17, valign: "middle" });
  }
  s.addNotes("Close with the offer: the same process, applied to the client's own data. Every engagement starts with a short scoping call.");

  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
}

build().catch((e) => { console.error(e); process.exit(1); });
