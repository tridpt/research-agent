"""Visual theme for the Streamlit UI.

``THEME_CSS`` is a pure string so it can be unit-tested and reused. ``app.py``
injects it once via ``st.markdown(..., unsafe_allow_html=True)``. Selectors are
defensive: if a Streamlit internal class changes, unmatched rules are simply
ignored and the app keeps working.
"""
from __future__ import annotations

# Brand palette (indigo -> violet gradient with a warm accent).
PRIMARY = "#4f46e5"
PRIMARY_DARK = "#4338ca"
ACCENT = "#7c3aed"

THEME_CSS = f"""
:root {{
  --ra-primary: {PRIMARY};
  --ra-primary-dark: {PRIMARY_DARK};
  --ra-accent: {ACCENT};
  --ra-gradient: linear-gradient(135deg, {PRIMARY} 0%, {ACCENT} 100%);
}}

/* Roomier, centered content column. */
.block-container {{
  max-width: 1100px;
  padding-top: 2.2rem;
}}

/* Gradient, bolder page title. */
h1 {{
  font-weight: 800 !important;
  letter-spacing: -0.02em;
  background: var(--ra-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}}

/* Decorative hero banner injected above the title. */
.ra-hero {{
  border-radius: 18px;
  padding: 1px;
  background: var(--ra-gradient);
  margin-bottom: 1.1rem;
  box-shadow: 0 10px 30px rgba(79, 70, 229, 0.18);
}}
.ra-hero-inner {{
  border-radius: 17px;
  padding: 1.1rem 1.4rem;
  background: rgba(255, 255, 255, 0.92);
}}
.ra-hero-badge {{
  display: inline-block;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--ra-primary-dark);
  background: rgba(79, 70, 229, 0.10);
  border: 1px solid rgba(79, 70, 229, 0.20);
  padding: 0.18rem 0.6rem;
  border-radius: 999px;
}}
.ra-hero-tag {{
  margin: 0.5rem 0 0 0;
  color: #475569;
  font-size: 0.98rem;
}}
.ra-hero-chips {{
  margin-top: 0.7rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}}
.ra-chip {{
  font-size: 0.8rem;
  color: #3730a3;
  background: rgba(124, 58, 237, 0.08);
  border: 1px solid rgba(124, 58, 237, 0.16);
  padding: 0.22rem 0.6rem;
  border-radius: 999px;
}}
@media (prefers-color-scheme: dark) {{
  .ra-hero-inner {{ background: rgba(17, 24, 39, 0.88); }}
  .ra-hero-tag {{ color: #e2e8f0; }}
  .ra-hero-badge {{
    color: #c7d2fe;
    background: rgba(129, 140, 248, 0.18);
    border-color: rgba(129, 140, 248, 0.45);
  }}
  .ra-chip {{
    color: #ddd6fe;
    background: rgba(167, 139, 250, 0.16);
    border-color: rgba(167, 139, 250, 0.40);
  }}
}}

/* Primary action buttons: gradient, rounded, subtle lift on hover. */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {{
  background: var(--ra-gradient);
  border: none;
  color: #fff;
  font-weight: 700;
  border-radius: 12px;
  padding: 0.55rem 1rem;
  transition: transform 0.06s ease, box-shadow 0.2s ease;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.22);
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {{
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(79, 70, 229, 0.30);
}}

/* Secondary buttons: soft outline. */
.stButton > button:not([kind="primary"]) {{
  border-radius: 12px;
  border: 1px solid rgba(79, 70, 229, 0.28);
}}

/* Tab bar: pill-style with a highlighted active tab. */
.stTabs [data-baseweb="tab-list"] {{
  gap: 0.4rem;
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 10px 10px 0 0;
  padding: 0.5rem 0.9rem;
  font-weight: 600;
}}
.stTabs [aria-selected="true"] {{
  background: rgba(79, 70, 229, 0.10);
  color: var(--ra-primary-dark) !important;
}}

/* Source cards / expanders: rounded with a soft border. */
[data-testid="stExpander"] {{
  border-radius: 12px;
  border: 1px solid rgba(79, 70, 229, 0.14);
  overflow: hidden;
}}

/* Text inputs: rounded and clearer focus. */
.stTextInput input, .stTextArea textarea {{
  border-radius: 10px;
}}

/* Sidebar: gentle tinted background. */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, rgba(79,70,229,0.05) 0%, rgba(124,58,237,0.02) 100%);
}}
"""


def hero_html(title: str, subtitle: str, badge: str, chips: list[str]) -> str:
    """Build the decorative hero banner shown above the page title.

    Pure string builder (no Streamlit) so it can be unit-tested. The caller is
    responsible for passing already-trusted, localized copy.
    """
    chip_html = "".join(f'<span class="ra-chip">{c}</span>' for c in chips)
    return (
        '<div class="ra-hero"><div class="ra-hero-inner">'
        f'<span class="ra-hero-badge">{badge}</span>'
        f'<p class="ra-hero-tag">{title} — {subtitle}</p>'
        f'<div class="ra-hero-chips">{chip_html}</div>'
        "</div></div>"
    )
