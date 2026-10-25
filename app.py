"""
Multimodal Construction Intelligence Platform
Skill Wallet Capstone Project 1

Run locally:   streamlit run app.py
Deploy:        push app.py + requirements.txt to GitHub -> Streamlit Community Cloud
API key:       paste in the sidebar, or set GOOGLE_API_KEY in Streamlit secrets.
               With no key the app runs in demonstration mode.
"""

import io
import json
import urllib.parse
from datetime import datetime

import streamlit as st
from PIL import Image

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except Exception:  # library missing -> demo mode only
    GENAI_AVAILABLE = False

st.set_page_config(
    page_title="Construction Intelligence Platform",
    page_icon="🏗️",
    layout="wide",
)

# ------------------------------------------------------------------ styling
CSS = """
<style>
.block-container {padding-top: 1.6rem;}
.hero {background: linear-gradient(120deg,#0f2027,#203a43,#2c5364); color:#fff;
       padding: 1.4rem 1.8rem; border-radius: 14px; margin-bottom: 1rem;}
.hero h1 {margin:0; font-size: 1.8rem;}
.hero p {margin:.3rem 0 0 0; opacity:.85;}
.card {background: rgba(128,128,128,.08); border:1px solid rgba(128,128,128,.25);
       border-radius: 12px; padding: 1rem 1.2rem; margin-bottom:.8rem;}
.card h4 {margin:0 0 .4rem 0;}
.pill {display:inline-block; padding:.18rem .7rem; border-radius:999px;
       font-size:.78rem; font-weight:600; color:#fff;}
.p-low{background:#2e9e5b;} .p-medium{background:#d9a21b;}
.p-high{background:#e0701f;} .p-critical{background:#c62f2f;}
.p-ok{background:#2e9e5b;} .p-bad{background:#c62f2f;} .p-unk{background:#7a7a7a;}
.small {font-size:.85rem; opacity:.8;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ------------------------------------------------------------------ helpers
SEVERITY_CLASS = {"low": "p-low", "medium": "p-medium", "high": "p-high", "critical": "p-critical"}


def pill(text: str, css: str) -> str:
    return f'<span class="pill {css}">{text}</span>'


def sev_pill(sev: str) -> str:
    return pill(str(sev).title(), SEVERITY_CLASS.get(str(sev).lower(), "p-unk"))


def format_inr(amount: float) -> str:
    if amount >= 1e7:
        return f"₹{amount / 1e7:,.2f} Cr"
    if amount >= 1e5:
        return f"₹{amount / 1e5:,.2f} Lakh"
    return f"₹{amount:,.0f}"


def prepare_image(uploaded) -> Image.Image:
    img = Image.open(uploaded)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    return img


def image_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def clean_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def get_client():
    key = st.session_state.get("api_key", "")
    if not key:
        try:
            key = st.secrets.get("GOOGLE_API_KEY", "")
        except Exception:
            key = ""
    if key and GENAI_AVAILABLE:
        return genai.Client(api_key=key)
    return None


def call_vision(prompt: str, img: Image.Image) -> dict:
    client = get_client()
    model = st.session_state.get("model", "gemini-2.5-flash")
    part = types.Part.from_bytes(data=image_bytes(img), mime_type="image/jpeg")
    resp = client.models.generate_content(
        model=model,
        contents=[part, prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
    )
    return clean_json(resp.text)


def json_download(label: str, data: dict, name: str):
    st.download_button(label, json.dumps(data, indent=2), file_name=name, mime="application/json")


# ------------------------------------------------------------------ prompts
SAFETY_PROMPT = """You are a certified construction safety auditor following OSHA and Indian
IS 456 / BOCW site-safety practice. Analyze this construction site photo.
Check PPE for every visible worker: helmet, high-vis vest, steel-toe boots, safety harness
(harness only where work at height is visible). Identify site hazards (fall risk, exposed
rebar, electrical, housekeeping, scaffolding, machinery). Only report what is visible; use
"unknown" when unclear.

Return ONLY valid JSON with exactly this shape:
{
 "safety_score": <int 0-100>,
 "overall_status": "Compliant" | "Needs Improvement" | "Non-Compliant",
 "workers_detected": <int>,
 "ppe_detection": {"helmet": "yes|no|unknown", "high_vis_vest": "yes|no|unknown",
                   "steel_toe_boots": "yes|no|unknown", "safety_harness": "yes|no|unknown|not_required"},
 "hazards": [{"hazard": str, "severity": "Low|Medium|High|Critical", "remedy": str}],
 "summary": str
}"""

CRACK_PROMPT = """You are a structural engineer doing a preliminary visual assessment of a
concrete / masonry surface (Indian practice, IS 456). Classify the defect as one of:
Hairline, Settlement, Structural Shear, Thermal Expansion, Spalling, or No Defect.
Estimate crack width in mm, give likely root causes, recommended engineering repairs
(e.g. epoxy injection, structural re-grouting, jacketing, sealant) and urgency.
This is a screening, not a certified inspection; lower confidence for poor images.

Return ONLY valid JSON with exactly this shape:
{
 "defect_type": str,
 "estimated_width_mm": <number>,
 "severity": "Low|Medium|High|Critical",
 "severity_score": <int 0-100, higher = worse>,
 "root_causes": [str],
 "recommended_repairs": [str],
 "urgency": "Monitor" | "Repair within 3 months" | "Repair within 2 weeks" | "Immediate action",
 "structural_concern": <bool>,
 "confidence": <float 0-1>,
 "summary": str
}"""

# ------------------------------------------------------------------ demo data
DEMO_SAFETY = {
    "safety_score": 62, "overall_status": "Needs Improvement", "workers_detected": 4,
    "ppe_detection": {"helmet": "yes", "high_vis_vest": "yes", "steel_toe_boots": "unknown",
                      "safety_harness": "no"},
    "hazards": [
        {"hazard": "Worker at height on scaffold without harness", "severity": "Critical",
         "remedy": "Stop work at height; issue full-body harnesses and anchor points."},
        {"hazard": "Exposed rebar ends without caps", "severity": "High",
         "remedy": "Fit mushroom caps on all protruding rebar."},
        {"hazard": "Debris and material blocking walkway", "severity": "Medium",
         "remedy": "Clear walkways; assign daily housekeeping crew."},
    ],
    "summary": "DEMO OUTPUT. Most workers wear helmets and vests, but fall protection is missing.",
}

DEMO_CRACK = {
    "defect_type": "Settlement", "estimated_width_mm": 3.5, "severity": "High", "severity_score": 72,
    "root_causes": ["Differential foundation settlement", "Poor soil compaction", "Moisture ingress"],
    "recommended_repairs": ["Epoxy injection for crack sealing", "Structural re-grouting",
                            "Foundation assessment by a structural engineer"],
    "urgency": "Repair within 2 weeks", "structural_concern": True, "confidence": 0.78,
    "summary": "DEMO OUTPUT. Diagonal crack pattern suggests settlement; engineer inspection advised.",
}

# ------------------------------------------------------------------ cost model (INR)
# Construction cost per sq ft by structure type (Tier 2 baseline)
BASE_COST = {"Residential Apartment": 2000, "Independent House": 2400,
             "Commercial Building": 2900, "Industrial Warehouse": 1500}
# Market value per sq ft (Tier 2 baseline, completed asset)
BASE_MARKET = {"Residential Apartment": 5500, "Independent House": 6200,
               "Commercial Building": 8500, "Industrial Warehouse": 3500}
TIER_COST_MULT = {"Tier 1": 1.25, "Tier 2": 1.0, "Tier 3": 0.85}
TIER_MARKET_MULT = {"Tier 1": 1.9, "Tier 2": 1.0, "Tier 3": 0.6}
STEEL_KG_PER_SQFT = {"Residential Apartment": 4.0, "Independent House": 4.5,
                     "Commercial Building": 5.5, "Industrial Warehouse": 6.0}
CEMENT_BAGS_PER_SQFT = {"Residential Apartment": 0.40, "Independent House": 0.42,
                        "Commercial Building": 0.45, "Industrial Warehouse": 0.38}
MILESTONES = [(15, "Foundation"), (50, "Superstructure"), (70, "Masonry & MEP rough-in"),
              (90, "Finishing"), (100, "Handover")]
LAND_SHARE = 0.35  # share of market value that exists before construction starts

WEATHER = {
    "Normal": {"icon": "☀️", "level": "Low", "alerts": [
        "Proceed with the planned schedule and hold the daily toolbox talk.",
        "Keep hydration points stocked and check PPE at the gate."]},
    "High Wind": {"icon": "💨", "level": "Critical", "alerts": [
        "Suspend crane and hoisting operations when wind exceeds about 40 km/h.",
        "Secure loose sheets, formwork and scaffolding netting.",
        "Stop work on exposed edges and tall scaffolds; keep workers away from the building edge."]},
    "Heavy Rain": {"icon": "🌧️", "level": "High", "alerts": [
        "Electrical hazard: de-energize temporary wiring, use GFCI/ELCB, keep panels covered.",
        "Cover fresh concrete with tarpaulin; do not pour concrete in heavy rain.",
        "Inspect trench and excavation walls for collapse; pump out standing water.",
        "Slip risk: lay anti-skid boards on ramps and scaffold platforms."]},
    "Extreme Heat": {"icon": "🔥", "level": "High", "alerts": [
        "Shift heavy work to early morning and evening; enforce rest breaks in shade.",
        "Provide ORS and drinking water; watch for heat-stroke symptoms.",
        "Concrete curing: start curing immediately, cover with wet burlap, and cure for at least 7 days.",
        "Consider retarding admixtures and chilled mixing water for pours."]},
}

ASSISTANT_SYSTEM = """You are a senior construction engineering assistant for Indian building sites.
Give practical, concise answers on site safety, concrete and curing, IS codes (IS 456, IS 875,
IS 1893), scheduling, materials estimation and costs in INR. Mention when a licensed
structural engineer must be consulted. Current site weather: {weather}."""

DEMO_REPLIES = [
    (("curing", "cure"), "Cure concrete for at least 7 days (10 for blended cements) by keeping it continuously moist with wet burlap or ponding. Start within 12 hours of finishing, and protect it from direct sun and wind."),
    (("harness", "height", "scaffold"), "For work at height above 2 m, require full-body harnesses anchored to a rated point, inspected scaffolds with guardrails and toe boards, and a trained competent person on site."),
    (("cement", "steel", "material"), "A rough rule of thumb for residential work is about 0.4 bags of cement and 4 kg of steel per sq ft built-up. Use the Planning tab for a project-specific estimate."),
    (("crack",), "Hairline cracks under 0.3 mm are usually cosmetic; wider or diagonal cracks near beams, columns or foundations need a structural engineer. Use the Crack Diagnostics tab to screen a photo."),
    (("rain", "monsoon"), "In heavy rain, de-energize temporary electricals, cover fresh concrete, and inspect excavations before re-entry."),
]


def demo_chat_reply(msg: str) -> str:
    low = msg.lower()
    for keys, reply in DEMO_REPLIES:
        if any(k in low for k in keys):
            return reply + "\n\n*(Demonstration mode: add a Gemini API key for full answers.)*"
    return ("I can help with safety, concrete practice, materials and costs. "
            "Try asking about curing, working at height, or cement and steel quantities.\n\n"
            "*(Demonstration mode: add a Gemini API key for full answers.)*")


def gemini_chat(history: list, weather: str) -> str:
    client = get_client()
    model = st.session_state.get("model", "gemini-2.5-flash")
    contents = [
        types.Content(role="user" if m["role"] == "user" else "model",
                      parts=[types.Part.from_text(text=m["content"])])
        for m in history
    ]
    resp = client.models.generate_content(
        model=model, contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=ASSISTANT_SYSTEM.format(weather=weather), temperature=0.4),
    )
    return resp.text


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    st.text_input("Google Gemini API key", type="password", key="api_key",
                  help="Get a free key at aistudio.google.com/apikey. Leave empty for demo mode.")
    st.selectbox("Model", ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"], key="model")
    live = get_client() is not None
    st.markdown(pill("LIVE MODE", "p-ok") if live else pill("DEMO MODE", "p-medium"),
                unsafe_allow_html=True)
    if not GENAI_AVAILABLE:
        st.warning("google-genai is not installed; running in demo mode.")

    st.divider()
    st.subheader("🧭 Features")
    st.markdown("- 🦺 PPE safety audit\n- 🧱 Crack diagnostics\n- 💰 Planning & valuation (INR)\n- 🌦️ Weather-aware assistant")

    st.divider()
    st.subheader("🏛️ Architecture")
    st.markdown(
        "```\nImage / inputs\n   ↓\nStreamlit UI\n   ↓\nPrompt + JSON contract\n   ↓\nGemini multimodal model\n   ↓\nValidated JSON → UI + export\n```"
    )
    st.caption("No database. Session-only state.")

# ------------------------------------------------------------------ header
st.markdown(
    '<div class="hero"><h1>🏗️ Multimodal Construction Intelligence Platform</h1>'
    '<p>Site safety audit · crack diagnostics · cost & valuation · weather-aware advisory</p></div>',
    unsafe_allow_html=True,
)

tab1, tab2, tab3, tab4 = st.tabs(
    ["🦺 Site Safety & PPE", "🧱 Crack Diagnostics", "💰 Planning & Valuation", "🌦️ Site Assistant"])

# ------------------------------------------------------------------ tab 1
with tab1:
    st.subheader("Site Safety & PPE Audit")
    up = st.file_uploader("Upload a construction site photo", type=["jpg", "jpeg", "png"], key="safety_up")
    if up:
        try:
            img = prepare_image(up)
        except Exception as e:
            st.error(f"Could not read that image: {e}")
            img = None
        if img:
            c1, c2 = st.columns([1, 1.3])
            c1.image(img, caption="Uploaded photo", use_container_width=True)
            if c1.button("Run safety audit", type="primary", key="run_safety"):
                with st.spinner("Analyzing site photo..."):
                    try:
                        if get_client():
                            result = call_vision(SAFETY_PROMPT, img)
                        else:
                            result = DEMO_SAFETY
                        st.session_state["safety_result"] = result
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")
            res = st.session_state.get("safety_result")
            if res:
                with c2:
                    score = int(res.get("safety_score", 0))
                    status = res.get("overall_status", "Unknown")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Safety score", f"{score}/100")
                    m2.metric("Workers detected", res.get("workers_detected", "n/a"))
                    css = "p-ok" if score >= 80 else ("p-medium" if score >= 55 else "p-bad")
                    m3.markdown("**Status**<br>" + pill(status, css), unsafe_allow_html=True)
                    st.progress(min(max(score, 0), 100) / 100)

                    st.markdown("##### PPE checklist")
                    labels = {"helmet": "Helmet", "high_vis_vest": "High-vis vest",
                              "steel_toe_boots": "Steel-toe boots", "safety_harness": "Safety harness"}
                    cols = st.columns(4)
                    for col, (k, lab) in zip(cols, labels.items()):
                        v = str(res.get("ppe_detection", {}).get(k, "unknown")).lower()
                        pc = {"yes": "p-ok", "no": "p-bad"}.get(v, "p-unk")
                        col.markdown(f"{lab}<br>{pill(v.replace('_', ' ').title(), pc)}",
                                     unsafe_allow_html=True)

                st.markdown("##### Identified hazards")
                hazards = res.get("hazards", [])
                if not hazards:
                    st.success("No hazards identified.")
                for h in hazards:
                    st.markdown(
                        f'<div class="card"><h4>{h.get("hazard", "Hazard")} {sev_pill(h.get("severity", ""))}</h4>'
                        f'<span class="small">Remedy:</span> {h.get("remedy", "")}</div>',
                        unsafe_allow_html=True)
                st.info(res.get("summary", ""))
                json_download("⬇️ Download JSON report", res,
                              f"safety_report_{datetime.now():%Y%m%d_%H%M%S}.json")
    else:
        st.info("Upload a JPG or PNG to begin. With no API key, demo output is shown.")

# ------------------------------------------------------------------ tab 2
with tab2:
    st.subheader("Crack Diagnostics & Structural Integrity")
    up2 = st.file_uploader("Upload a concrete or wall surface photo", type=["jpg", "jpeg", "png"], key="crack_up")
    if up2:
        try:
            img2 = prepare_image(up2)
        except Exception as e:
            st.error(f"Could not read that image: {e}")
            img2 = None
        if img2:
            c1, c2 = st.columns([1, 1.3])
            c1.image(img2, caption="Uploaded surface", use_container_width=True)
            if c1.button("Diagnose defect", type="primary", key="run_crack"):
                with st.spinner("Analyzing surface..."):
                    try:
                        result = call_vision(CRACK_PROMPT, img2) if get_client() else DEMO_CRACK
                        st.session_state["crack_result"] = result
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")
            res = st.session_state.get("crack_result")
            if res:
                with c2:
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Defect type", res.get("defect_type", "n/a"))
                    m2.metric("Est. width", f"{res.get('estimated_width_mm', '?')} mm")
                    m3.markdown("**Severity**<br>" + sev_pill(res.get("severity", "")),
                                unsafe_allow_html=True)
                    st.progress(min(max(int(res.get("severity_score", 0)), 0), 100) / 100,
                                text=f"Severity score: {res.get('severity_score', 0)}/100")
                    st.markdown(f"**Urgency:** {res.get('urgency', 'n/a')}")
                    if res.get("structural_concern"):
                        st.error("Potential structural concern: consult a licensed structural engineer.")
                    else:
                        st.success("No immediate structural concern indicated.")
                    st.caption(f"Model confidence: {float(res.get('confidence', 0)):.0%}")
                k1, k2 = st.columns(2)
                k1.markdown("##### Root causes")
                for r in res.get("root_causes", []):
                    k1.markdown(f"- {r}")
                k2.markdown("##### Recommended repairs")
                for r in res.get("recommended_repairs", []):
                    k2.markdown(f"- {r}")
                st.info(res.get("summary", ""))
                st.caption("Screening only. This is not a certified structural inspection.")
                json_download("⬇️ Download JSON report", res,
                              f"crack_report_{datetime.now():%Y%m%d_%H%M%S}.json")
    else:
        st.info("Upload a close-up photo of the crack or damaged surface.")

# ------------------------------------------------------------------ tab 3
with tab3:
    st.subheader("Project Planning & Real Estate Valuation")
    i1, i2 = st.columns(2)
    stype = i1.selectbox("Structure type", list(BASE_COST))
    tier = i2.selectbox("Location tier", ["Tier 1", "Tier 2", "Tier 3"],
                        format_func=lambda t: {"Tier 1": "Tier 1 (Mumbai, Delhi, Bengaluru...)",
                                               "Tier 2": "Tier 2 (Indore, Pune, Jaipur...)",
                                               "Tier 3": "Tier 3 (smaller cities)"}[t], index=1)
    sqft = i1.number_input("Built-up area (sq ft)", min_value=200, max_value=500000, value=2000, step=100)
    pct = i2.slider("Completion (%)", 0, 100, 40)

    cost_sqft = BASE_COST[stype] * TIER_COST_MULT[tier]
    total_budget = cost_sqft * sqft
    capex = total_budget * pct / 100
    market_full = BASE_MARKET[stype] * TIER_MARKET_MULT[tier] * sqft
    market_now = market_full * (LAND_SHARE + (1 - LAND_SHARE) * pct / 100)
    steel_total = STEEL_KG_PER_SQFT[stype] * sqft / 1000  # tonnes
    cement_total = CEMENT_BAGS_PER_SQFT[stype] * sqft

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total project budget", format_inr(total_budget), f"₹{cost_sqft:,.0f}/sq ft")
    m2.metric("Capex incurred", format_inr(capex), f"{pct}% complete")
    m3.metric("Current asset valuation", format_inr(market_now))
    m4.metric("Valuation at completion", format_inr(market_full))

    n1, n2, n3, n4 = st.columns(4)
    n1.metric("Steel required", f"{steel_total:,.1f} t")
    n2.metric("Steel consumed", f"{steel_total * pct / 100:,.1f} t")
    n3.metric("Cement required", f"{cement_total:,.0f} bags")
    n4.metric("Cement consumed", f"{cement_total * pct / 100:,.0f} bags")

    st.markdown("##### Milestone progress")
    st.progress(pct / 100)
    current = next((name for limit, name in MILESTONES if pct <= limit), "Handover")
    cols = st.columns(len(MILESTONES))
    for col, (limit, name) in zip(cols, MILESTONES):
        done = pct >= limit
        col.markdown(f"{'✅' if done else ('🔨' if name == current else '⬜')} **{name}**<br>"
                     f"<span class='small'>up to {limit}%</span>", unsafe_allow_html=True)
    st.caption("Estimates use indicative per-sq-ft rates and a 35% land-value share. "
               "Replace the rate tables in the code with your local data for real use.")

    st.markdown("##### Conceptual 3D rendering")
    default_prompt = (f"Photorealistic architectural 3D render of a modern {stype.lower()} in an Indian "
                      f"{tier.lower()} city, about {sqft:,} sq ft, {pct}% constructed, golden hour, "
                      "high detail")
    prompt = st.text_area("Rendering prompt", value=default_prompt, key=f"render_prompt_{stype}_{tier}_{pct}")
    if st.button("Generate rendering", key="gen_render"):
        url = ("https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt)
               + "?width=1024&height=640&nologo=true")
        st.session_state["render_url"] = url
    if st.session_state.get("render_url"):
        st.image(st.session_state["render_url"], caption="Generated via Pollinations AI",
                 use_container_width=True)

# ------------------------------------------------------------------ tab 4
with tab4:
    st.subheader("Daily Site Assistant & Weather-Aware Advisory")
    weather = st.radio("Today's weather", list(WEATHER), horizontal=True, key="weather")
    w = WEATHER[weather]
    st.markdown(f"### {w['icon']} {weather} {sev_pill(w['level'])}", unsafe_allow_html=True)
    for a in w["alerts"]:
        (st.error if w["level"] in ("Critical", "High") else st.success)(a)

    st.divider()
    st.markdown("##### Engineering assistant")
    if "chat" not in st.session_state:
        st.session_state["chat"] = [{"role": "assistant",
                                     "content": "Hello! Ask me about site safety, concrete, materials, or schedules."}]
    for m in st.session_state["chat"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_msg = st.chat_input("Ask a construction question...")
    if user_msg:
        st.session_state["chat"].append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    if get_client():
                        reply = gemini_chat(st.session_state["chat"], f"{weather} ({w['level']} risk)")
                    else:
                        reply = demo_chat_reply(user_msg)
                except Exception as e:
                    reply = f"Sorry, the assistant hit an error: {e}"
            st.markdown(reply)
        st.session_state["chat"].append({"role": "assistant", "content": reply})
    if st.button("Clear chat"):
        st.session_state.pop("chat", None)
        st.rerun()
