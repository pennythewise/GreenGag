# Product Requirement Document: GreenGag AI Dashboard

**System Classification:** High-Stakes Multi-Agent Deceptive Data Auditing Interface  
**Target Architecture:** Event-Driven Python Backend / Component-Driven React Frontend  
**Document Version:** V2.0 (Production Blueprint)

---

## 1. User Experience & Visual Design

The UI departs from traditional dark-themed, data-heavy developer consoles. It adopts a clean, trustworthy, human-centric aesthetic inspired by modern editorial, accessible, and community-driven web design.

- **Color Palette:** Soft, clean, and optimistic backgrounds (eggshell white, pale cream, muted canvas) paired with deep, authoritative editorial typography (dark navy, slate charcoal). Primary CTAs use accessible, high-contrast organic accents (sage greens, slate blues, terra cotta warm warnings).

- **Layout:** Asymmetric grid spacing, wide breathing margins, large humanized headers, smooth container corners (12–16px border-radius) with subtle elevation blurs. Data layers are grouped organically to reduce visual panic while maintaining dense information availability.

- **Animations:** Linear state transition fades (150ms) for data refreshes. Organic horizontal cascading slide animations when multi-agent workflow streams open on screen.

---

## 2. UI Blueprint: Agent Visibility & Explainable AI (XAI)

The core UI mandate is to make internal multi-agent graph computations fully transparent, conversational, and visual to the compliance auditor.

### 2.1 Live Agent Multi-Track Swimlanes

- A dedicated panel shows all live sub-agents running parallel operations simultaneously.
- Each agent is represented by a card component showing its current lifecycle state (**IDLE**, **PROCESSING**, **SUCCESS**, **ALERT**), active tool attachment, and an execution progress ring.

### 2.2 Explainable AI (XAI) Lineage Interface

Every audit score must be fully auditable via interactive **Data Triangulation Linkages**:

- **The Discrepancy Canvas:** An interactive side-by-side split viewport. Clicking any high-risk score highlight draws an SVG anchor line linking the suspicious block inside the corporate ESG PDF directly to the specific database line-item or anomalous satellite pixel cluster causing the system alarm.

- **Agent Thought Logs:** A clean Markdown terminal wrapper below each agent displaying its step-by-step rationalization trail, mapping the text prompt to its execution parameters and tool evaluation choices.

---

## 3. Backend Architecture & API Specifications

The backend is an asynchronous Python server using **FastAPI** to handle heavy spatial data processing and agent execution tracking without blocking web transactions.

### 3.1 Multi-Agent System — The 5 Agents

#### Agent 1: Orchestrator Agent (The Supervisor)
- **Role:** Central brain and traffic controller.
- **Task:** Coordinates state flow using a directional graph framework (e.g. LangGraph). Takes user input, passes data payloads to sub-agents sequentially, collects risk outputs, and applies the final **Weighted Integrity Index** (50% weight to physical/satellite data).
- **Frontend:** Rendered as a master status ring at the top center of the screen. Displays the aggregate **Global Greenwashing Risk Score** and a text-based "Executive Verdict Summary" compiling all agent findings.

#### Agent 2: Report Parser Agent (The Reader)
- **Role:** Translates unstructured corporate marketing text into structured data.
- **Task:** Ingests heavy corporate ESG PDFs, strips promotional fluff, and uses an LLM to extract concrete, measurable data points into a standardized JSON format.
- **Target Data:** Explicit carbon reduction claims (e.g. "30% reduction"), targeted facilities, geographical bounding boxes (GeoJSON), material classifications, and self-reported budgets.
- **Frontend/XAI:** Interactive PDF viewer widget. Identified claims are highlighted in light amber, showing the auditor exactly what raw data the system extracted.

#### Agent 3: Ledger Auditor Agent (The Accountant)
- **Role:** Financial truth-seeker tracking the real-world paper trail.
- **Task:** Runs deterministic tabular calculations directly over private corporate procurement ledgers, supplier invoices, and Bills of Materials (BOM). Calculates how much money was paid to verified eco-material vendors vs. standard high-carbon suppliers to detect "Bait-and-Switch" financial fraud.
- **Frontend/XAI:** Clean structured ledger timeline table. When a financial discrepancy is found, draws an **SVG connector line** from the flagged invoice row directly to the highlighted text box in the ESG report.

#### Agent 4: Media Sentinel Agent (The Public Watchdog)
- **Role:** External reputation monitor and whistleblower detector.
- **Task:** Runs web-scraping pipelines across news sites, local community message boards, and global environmental NGO databases (e.g. Greenpeace) using NLP text classification models.
- **Target Data:** Flags contradictions between public reports (illegal dumping, structural failures) and corporate claims (e.g. "Zero Environmental Incidents").
- **Frontend/XAI:** Editorial-style "Public Sentiment Track." Streams cards with scraped article clippings, headlines, and source links, each with an individual *Reputational Contradiction Score*.

#### Agent 5: Geospatial Truth Agent (The Ultimate Juror)
- **Role:** Physical verification anchor using planetary data science. **Holds absolute veto power in the final summary.**
- **Task:** Queries remote sensing satellite APIs (Sentinel-5P TROPOMI, Planet Labs) using coordinates from the Report Parser. Measures the physical state of atmosphere and terrain over a time-series interval.
- **Target Data:** Atmospheric gas column densities (NO₂, CH₄, CO₂) over factories; temporal phase-growth speeds of buildings to catch timeline fraud.
- **Frontend/XAI:** Interactive map canvas (Mapbox or Leaflet) with a color-coded heatmap overlay of actual gas emissions. Side-by-side time-series graph contrasting company's *claimed* emissions drop vs. satellite's *observed* flatline.

---

### 3.2 Primary State Payload Schema

```json
{
  "audit_id": "aud_2026_98x11",
  "meta": {
    "target_entity": "Malaya BuildCorp Group",
    "project_name": "KL Central Eco-Tower Expansion",
    "coordinates": {
      "type": "Polygon",
      "coordinates": [[[101.686, 3.139], [101.690, 3.139], [101.690, 3.143], [101.686, 3.143], [101.686, 3.139]]]
    }
  },
  "agent_states": {
    "ReportParserAgent": {
      "status": "COMPLETED",
      "risk_contribution": 0.10,
      "extracted_claims": {
        "claimed_reduction": 30.0,
        "material_class": "Cemex Vertua Low-Carbon Concrete",
        "stated_spend_usd": 1200000.0
      },
      "rationale_trail": [
        "Parsed PDF structure lines 112-140.",
        "Identified explicit emission reduction commitment clause."
      ]
    },
    "LedgerAuditorAgent": {
      "status": "COMPLETED",
      "risk_contribution": 0.85,
      "extracted_metrics": {
        "verified_green_spend_usd": 180000.0,
        "unverified_standard_spend_usd": 1020000.0
      },
      "rationale_trail": [
        "Cross-referenced vendor index against approved green material provider lists.",
        "Detected standard cement grade purchase order swap on invoice #INV-9981."
      ]
    },
    "GeospatialTruthAgent": {
      "status": "COMPLETED",
      "risk_contribution": 0.95,
      "metrics": {
        "satellite_source": "Sentinel-5P_TROPOMI",
        "observed_gas_variance_percentage": 0.40,
        "confidence_index": 0.92
      },
      "rationale_trail": [
        "Pulled time-series raster array values over polygon target.",
        "Calculated running mean of tropospheric NO2 vertical column density.",
        "Flatlined output indicates zero emissions reduction observed."
      ]
    }
  },
  "global_metrics": {
    "weighted_risk_score": 0.815,
    "confidence_score": 0.890,
    "final_verdict": "CRITICAL_RISK_FRAUD_DETECTED"
  }
}
```

---

### 3.3 Security & Environment Configuration

**No secrets or API keys are hardcoded anywhere in the codebase.**

- Backend initializes validation pipelines using strict `os.getenv()` bindings.
- A `.env.example` template is shipped at the root of the repo with empty placeholders.
- The app boot script verifies all env vars are populated on startup, prompting with explicit console errors if any key is missing.

```bash
# .env.example - Production Configuration Template
# Duplicate this file to .env and fill in your API keys. Never commit .env.

# Core System Orchestration
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Remote Sensing & Satellite APIs
PLANET_LABS_API_KEY=your_planet_labs_key_here
GOOGLE_EARTH_ENGINE_CREDENTIALS=your_gee_json_path_here
SENTINEL_HUB_CLIENT_ID=your_sentinel_hub_id_here
SENTINEL_HUB_CLIENT_SECRET=your_sentinel_hub_secret_here

# Financial & External Data
NEWS_API_KEY=your_news_api_key_here
INTERNAL_LEDGER_DB_URL=postgresql://user:password@localhost:5432/ledger_audit
```
