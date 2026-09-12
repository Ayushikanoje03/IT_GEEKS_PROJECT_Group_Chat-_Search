"""ConvoLens — Realistic Group Chat Search UI.

Design: WhatsApp/Telegram-inspired chat bubbles, sender avatars, read receipts,
glassmorphism shell, live accuracy dashboard with animated gauges.
"""

from __future__ import annotations

import html
import os
from datetime import datetime
from typing import Any

import requests
import streamlit as st

APP_NAME = "ConvoLens"
APP_SUBTITLE = "Group Chat Search"
DEFAULT_API_URL = "http://127.0.0.1:8000"
SEARCH_RESULT_COUNT = 5
MAX_RELEVANT_RESULTS = 50
REQUEST_TIMEOUT_SECONDS = 60

EXAMPLE_QUERIES = (
    "When did we decide on the trip?",
    "What did Priya say about the budget?",
    "Who said hills jaana chahiye?",
    "Who gave health advice about altitude sickness?",
)

INTENT_META = {
    "SEMANTIC": {"icon": "🔍", "label": "Semantic", "color": "#6366F1"},
    "PERSON":   {"icon": "👤", "label": "Person",   "color": "#22D3EE"},
    "TEMPORAL": {"icon": "📅", "label": "Temporal", "color": "#F59E0B"},
}

# Consistent avatar colors keyed by sender name
AVATAR_PALETTE = {
    "Priya":  "#EC4899",
    "Rahul":  "#6366F1",
    "Sneha":  "#10B981",
    "Arjun":  "#F59E0B",
    "Kavya":  "#8B5CF6",
    "Dev":    "#14B8A6",
    "Mehak":  "#EF4444",
    "Rohan":  "#F97316",
}
DEFAULT_COLOR = "#64748B"

# ─── API helpers ──────────────────────────────────────────────────────────────

def api_url() -> str:
    return os.getenv("GROUP_CHAT_API_URL", DEFAULT_API_URL).rstrip("/")


def request_api(method: str, path: str, **kwargs: Any) -> tuple[dict[str, Any] | None, str | None]:
    try:
        response = requests.request(method, f"{api_url()}{path}", timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
        payload = response.json()
    except requests.RequestException:
        return None, "Backend unavailable. Start FastAPI, then try again."
    except ValueError:
        return None, "Backend returned an unexpected response."
    if response.ok and isinstance(payload, dict):
        return payload, None
    if isinstance(payload, dict):
        detail = payload.get("detail", "Search failed.")
        if isinstance(detail, list):
            messages = [str(item.get("msg", "Invalid request.")) for item in detail if isinstance(item, dict)]
            return None, " ".join(messages) or "Invalid request."
        return None, str(detail)
    return None, "Search failed."


def format_timestamp(timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return timestamp


def format_date(timestamp: str) -> str:
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%d %B %Y")
    except ValueError:
        return ""


def avatar_color(sender: str) -> str:
    return AVATAR_PALETTE.get(sender, DEFAULT_COLOR)


def avatar_initials(sender: str) -> str:
    parts = sender.strip().split()
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else parts[0][1])).upper()


# ─── CSS injection ─────────────────────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@400;500;600&display=swap');

/* ── Reset & base ── */
html, body, [class*="css"], .stApp {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  background: #0B0E17 !important;
  color: #E2E8F0;
}
.stApp { background: #0B0E17 !important; }
#MainMenu, footer, .stDeployButton { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; border: none; }
.block-container { max-width: 1080px; padding: 1.5rem 1.25rem 5rem; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  background: #0F1220 !important;
  border-right: 1px solid rgba(255,255,255,0.06) !important;
}
section[data-testid="stSidebar"] * { color: #CBD5E1 !important; }
section[data-testid="stSidebar"] > div { padding: 0; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  gap: 0; background: rgba(255,255,255,0.03);
  border-radius: 14px; padding: 4px;
  border: 1px solid rgba(255,255,255,0.07);
  margin-bottom: 1.5rem;
}
.stTabs [data-baseweb="tab"] {
  color: #64748B !important; font-family: 'Manrope', sans-serif;
  font-weight: 600; font-size: 0.875rem;
  padding: 0.55rem 1.5rem; border-radius: 10px;
  transition: all 0.2s ease;
}
.stTabs [aria-selected="true"] {
  background: linear-gradient(135deg, #6366F1 0%, #818CF8 100%) !important;
  color: #fff !important;
  box-shadow: 0 4px 14px rgba(99,102,241,0.4);
}

/* ── Sidebar: Group chat header ── */
.sb-chat-header {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 1rem 1rem 0.75rem;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.sb-group-icon {
  width: 42px; height: 42px; border-radius: 50%;
  background: linear-gradient(135deg, #6366F1, #8B5CF6);
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; flex-shrink: 0;
}
.sb-group-name { font-family: 'Manrope', sans-serif; font-size: 1rem; font-weight: 800; color: #F1F5F9 !important; }
.sb-group-meta { font-size: 0.7rem; color: #475569 !important; margin-top: 0.1rem; }
.sb-online-dot { width: 7px; height: 7px; border-radius: 50%; background: #22C55E; display: inline-block; margin-right: 4px; }

/* Sidebar status bar */
.sb-status-bar {
  padding: 0.6rem 1rem; font-size: 0.73rem; color: #64748B !important;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  display: flex; align-items: center; gap: 0.5rem;
}
.pulse-dot {
  width: 7px; height: 7px; border-radius: 50%; background: #22C55E; flex-shrink: 0;
  animation: pulse-ring 2s ease-in-out infinite;
}
.pulse-dot.offline { background: #EF4444; animation: none; }
@keyframes pulse-ring {
  0%   { box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
  70%  { box-shadow: 0 0 0 5px rgba(34,197,94,0); }
  100% { box-shadow: 0 0 0 0 rgba(34,197,94,0); }
}

/* Sidebar members list */
.sb-section { padding: 0.75rem 1rem 0.5rem; }
.sb-section-title {
  font-family: 'Manrope', sans-serif; font-size: 0.63rem; font-weight: 700;
  letter-spacing: 0.12em; text-transform: uppercase; color: #334155 !important;
  margin-bottom: 0.6rem;
}
.sb-member-row {
  display: flex; align-items: center; gap: 0.6rem;
  padding: 0.45rem 0.25rem; border-bottom: 1px solid rgba(255,255,255,0.03);
}
.sb-member-avatar {
  width: 32px; height: 32px; border-radius: 50%; position: relative;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.7rem; font-weight: 800; color: #fff; flex-shrink: 0;
  font-family: 'Manrope', sans-serif;
}
.sb-member-online::after {
  content: ''; position: absolute; bottom: 1px; right: 1px;
  width: 8px; height: 8px; border-radius: 50%;
  background: #22C55E; border: 1.5px solid #0F1220;
}
.sb-member-name { font-size: 0.8rem; font-weight: 600; color: #CBD5E1 !important; }
.sb-member-status { font-size: 0.67rem; color: #475569 !important; }
.sb-stat-section { padding: 0.75rem 1rem 1rem; border-top: 1px solid rgba(255,255,255,0.05); margin-top: 0.5rem; }
.sb-stat-row { display: flex; justify-content: space-between; padding: 0.3rem 0; }
.sb-stat-label { font-size: 0.75rem; color: #475569 !important; }
.sb-stat-val { font-size: 0.75rem; font-weight: 700; color: #94A3B8 !important; font-family: 'Manrope', sans-serif; }

/* ── Hero ── */
.hero-eyebrow {
  font-family: 'Manrope', sans-serif; font-size: 0.68rem; font-weight: 700;
  letter-spacing: 0.16em; text-transform: uppercase;
  background: linear-gradient(90deg, #6366F1, #22D3EE);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  margin-bottom: 0.4rem;
}
.hero-title {
  font-family: 'Manrope', sans-serif; font-size: 2.2rem; font-weight: 800;
  background: linear-gradient(135deg, #F1F5F9 40%, #94A3B8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  letter-spacing: -0.035em; line-height: 1.1; margin: 0 0 0.4rem;
}
.hero-sub { color: #64748B; font-size: 0.9rem; margin-bottom: 1.25rem; line-height: 1.6; }

/* ── Example query chips ── */
.stButton > button {
  background: rgba(99,102,241,0.07) !important;
  border: 1px solid rgba(99,102,241,0.2) !important;
  border-radius: 999px !important; color: #A5B4FC !important;
  font-size: 0.78rem !important; font-weight: 500 !important;
  transition: all 0.2s ease !important;
}
.stButton > button:hover {
  background: rgba(99,102,241,0.18) !important;
  border-color: rgba(99,102,241,0.45) !important;
  transform: translateY(-1px) !important;
}

/* ── Search input ── */
.stTextInput label { display: none !important; }
.stTextInput input {
  background: rgba(255,255,255,0.04) !important;
  border: 1.5px solid rgba(255,255,255,0.1) !important;
  border-radius: 14px !important;
  color: #F1F5F9 !important;
  padding: 0.85rem 1.1rem !important;
  font-size: 0.95rem !important;
  transition: all 0.25s ease;
}
.stTextInput input:focus {
  border-color: rgba(99,102,241,0.6) !important;
  box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
  background: rgba(255,255,255,0.06) !important;
}
.stTextInput input::placeholder { color: #334155 !important; }
.stFormSubmitButton > button {
  background: linear-gradient(135deg, #6366F1 0%, #818CF8 100%) !important;
  border: none !important; border-radius: 12px !important;
  color: #FFF !important; font-weight: 700 !important;
  font-family: 'Manrope', sans-serif !important;
  min-height: 46px !important; font-size: 0.9rem !important;
  box-shadow: 0 4px 15px rgba(99,102,241,0.4) !important;
  transition: all 0.2s ease !important;
}
.stFormSubmitButton > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 8px 24px rgba(99,102,241,0.5) !important;
}
.stSelectbox label { color: #64748B !important; font-size: 0.78rem !important; }
.stSelectbox > div > div {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(255,255,255,0.09) !important;
  border-radius: 12px !important; color: #F1F5F9 !important;
}

/* ── Intent badge ── */
.intent-row { display: flex; align-items: center; gap: 0.5rem; margin: 1.25rem 0 0.75rem; flex-wrap: wrap; }
.intent-badge {
  display: inline-flex; align-items: center; gap: 0.3rem;
  padding: 0.28rem 0.7rem; border-radius: 999px;
  font-size: 0.72rem; font-weight: 700; font-family: 'Manrope', sans-serif;
}
.intent-badge.semantic { background: rgba(99,102,241,0.14); border: 1px solid rgba(99,102,241,0.3); color: #A5B4FC; }
.intent-badge.person   { background: rgba(34,211,238,0.1); border: 1px solid rgba(34,211,238,0.3); color: #67E8F9; }
.intent-badge.temporal { background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.3); color: #FCD34D; }
.filter-chip {
  padding: 0.25rem 0.6rem; border-radius: 999px;
  background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1);
  color: #94A3B8; font-size: 0.72rem;
}
.result-count { font-size: 0.75rem; color: #475569; margin-left: auto; }
.result-header {
  font-family: 'Manrope', sans-serif; font-size: 0.65rem; font-weight: 700;
  letter-spacing: 0.1em; text-transform: uppercase; color: #334155;
  margin: 0 0 0.85rem;
}

/* ── Realistic chat card ── */
.chat-card {
  border-radius: 18px; overflow: hidden; margin-bottom: 1.4rem;
  width: 100%; box-sizing: border-box;
  border: 1px solid rgba(255,255,255,0.07);
  background: #111827;
  box-shadow: 0 6px 28px rgba(0,0,0,0.35);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}
.chat-card:hover { box-shadow: 0 10px 36px rgba(99,102,241,0.12); }

/* Chat header (like WhatsApp group header) */
.chat-header {
  display: flex; align-items: center; gap: 0.65rem;
  padding: 0.65rem 0.9rem;
  background: #1A2236;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.chat-header-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, #6366F1, #8B5CF6);
  display: flex; align-items: center; justify-content: center;
  font-size: 0.8rem; color: #fff; font-weight: 800; flex-shrink: 0;
  font-family: 'Manrope', sans-serif;
}
.chat-header-info { flex: 1; }
.chat-header-name { font-family: 'Manrope', sans-serif; font-weight: 700; font-size: 0.85rem; color: #E2E8F0; }
.chat-header-sub { font-size: 0.68rem; color: #475569; margin-top: 0.05rem; }
.chat-header-rank {
  font-family: 'Manrope', sans-serif; font-size: 0.7rem; font-weight: 700;
  background: rgba(99,102,241,0.15); border: 1px solid rgba(99,102,241,0.3);
  color: #A5B4FC; padding: 0.2rem 0.6rem; border-radius: 999px;
}
.chat-header-score {
  font-size: 0.7rem; color: #475569; margin-left: 0.5rem;
}

/* Messages area */
.messages-wrap {
  padding: 0.6rem 0.8rem 0.5rem;
  background: #0F1824;
  background-image:
    radial-gradient(rgba(255,255,255,0.012) 1px, transparent 1px);
  background-size: 18px 18px;
  min-height: 80px;
  overflow: hidden;
}

/* Date separator */
.date-sep {
  text-align: center; margin: 0.4rem 0 0.6rem;
  display: flex; align-items: center; gap: 0.5rem;
}
.date-sep span {
  font-size: 0.65rem; font-weight: 600; color: #334155;
  background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.07);
  padding: 0.18rem 0.7rem; border-radius: 999px; white-space: nowrap;
}
.date-sep::before, .date-sep::after {
  content: ''; flex: 1; height: 1px; background: rgba(255,255,255,0.05);
}

/* Context divider */
.ctx-divider {
  text-align: center; margin: 0.5rem 0 0.3rem;
  display: flex; align-items: center; gap: 0.4rem;
}
.ctx-divider span {
  font-size: 0.62rem; font-weight: 700; color: #6366F1;
  letter-spacing: 0.08em; text-transform: uppercase;
  padding: 0.15rem 0.55rem;
  background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.25);
  border-radius: 999px;
}
.ctx-divider::before, .ctx-divider::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(99,102,241,0.25), transparent);
}

/* ── Realistic chat bubbles ── */
.msg-row {
  display: flex; align-items: flex-end; gap: 0.45rem;
  margin: 0.3rem 0;
}
.msg-row.me { flex-direction: row-reverse; }

/* Avatar circle */
.msg-avatar {
  width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 0.6rem; font-weight: 800; color: #fff;
  font-family: 'Manrope', sans-serif;
  position: relative; align-self: flex-end; margin-bottom: 2px;
}
.msg-avatar.online-av::after {
  content: ''; position: absolute; bottom: 0; right: 0;
  width: 7px; height: 7px; border-radius: 50%;
  background: #22C55E; border: 1.5px solid #0F1824;
}

/* Bubble */
.bubble {
  max-width: calc(100% - 38px);
  padding: 0.5rem 0.7rem 0.35rem;
  border-radius: 14px;
  position: relative; word-break: break-word;
}
/* Other person */
.bubble.other {
  background: #1E2A3A;
  border: 1px solid rgba(255,255,255,0.07);
  border-bottom-left-radius: 4px;
}
/* Target / highlighted message */
.bubble.target {
  background: linear-gradient(135deg, rgba(99,102,241,0.22) 0%, rgba(139,92,246,0.18) 100%);
  border: 1px solid rgba(99,102,241,0.4);
  border-bottom-left-radius: 4px;
  box-shadow: 0 0 14px rgba(99,102,241,0.12);
}
/* "Me" bubble (right side) */
.bubble.me-bubble {
  background: linear-gradient(135deg, #1d4a2a, #16382d);
  border: 1px solid rgba(34,197,94,0.15);
  border-bottom-right-radius: 4px;
}
.bubble-sender {
  font-size: 0.68rem; font-weight: 700; margin-bottom: 0.18rem;
  font-family: 'Manrope', sans-serif;
}
.bubble-text { font-size: 0.875rem; color: #CBD5E1; line-height: 1.5; }
.bubble-footer {
  display: flex; justify-content: flex-end; align-items: center;
  gap: 0.3rem; margin-top: 0.25rem;
}
.bubble-time { font-size: 0.6rem; color: #475569; }
.bubble-ticks { font-size: 0.65rem; color: #60A5FA; }
.bubble-reaction {
  position: absolute; bottom: -10px; right: 8px;
  background: #1A2236; border: 1px solid rgba(255,255,255,0.1);
  border-radius: 999px; padding: 0.08rem 0.35rem;
  font-size: 0.7rem; white-space: nowrap;
}
.target-marker {
  font-size: 0.58rem; font-weight: 700; color: #818CF8;
  background: rgba(99,102,241,0.15); border-radius: 3px;
  padding: 0.1rem 0.3rem; margin-bottom: 0.15rem; display: inline-block;
}

/* ── Empty / error states ── */
.empty-state {
  text-align: center; padding: 3rem 1.5rem;
  border: 1px dashed rgba(255,255,255,0.07); border-radius: 18px;
  background: rgba(255,255,255,0.015); margin-top: 1rem;
}
.empty-icon { font-size: 2.4rem; margin-bottom: 0.6rem; }
.empty-title { font-family: 'Manrope', sans-serif; font-weight: 700; font-size: 1.05rem; color: #475569; margin-bottom: 0.35rem; }
.empty-sub { font-size: 0.83rem; color: #334155; }

/* ── Evaluation ── */
.eval-hero {
  padding: 1.6rem; border-radius: 18px; margin-bottom: 1.5rem;
  background: linear-gradient(135deg, rgba(99,102,241,0.1) 0%, rgba(34,211,238,0.05) 100%);
  border: 1px solid rgba(99,102,241,0.2);
}
.eval-hero-title {
  font-family: 'Manrope', sans-serif; font-size: 1.65rem; font-weight: 800;
  background: linear-gradient(135deg, #F1F5F9, #A5B4FC);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.eval-hero-sub { color: #64748B; font-size: 0.87rem; margin-top: 0.3rem; }
.metric-glass {
  padding: 1.2rem 0.8rem; border-radius: 16px;
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07);
  text-align: center; position: relative; overflow: hidden;
  transition: all 0.2s ease;
}
.metric-glass:hover { border-color: rgba(99,102,241,0.3); background: rgba(99,102,241,0.06); transform: translateY(-2px); }
.metric-glass::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, #6366F1, #22D3EE);
}
.metric-label { color: #64748B; font-size: 0.73rem; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase; }
.metric-sub { color: #475569; font-size: 0.68rem; margin-top: 0.22rem; }
.metric-trend { font-size: 0.73rem; font-weight: 700; margin-top: 0.25rem; }
.metric-trend.up { color: #22C55E; }
.metric-trend.mid { color: #F59E0B; }
.gap-banner {
  padding: 0.9rem 1.1rem; border-radius: 12px; margin: 1.1rem 0;
  background: rgba(99,102,241,0.07); border-left: 3px solid #6366F1;
  display: flex; align-items: center; gap: 0.7rem;
}
.gap-banner-text { font-size: 0.83rem; color: #94A3B8; line-height: 1.5; }
.gap-banner-text strong { color: #A5B4FC; }
.query-grid { display: grid; grid-template-columns: repeat(8, 1fr); gap: 5px; margin-top: 0.85rem; }
.query-cell {
  aspect-ratio: 1; border-radius: 6px; display: flex; align-items: center; justify-content: center;
  font-size: 0.54rem; font-weight: 700; cursor: default;
  transition: transform 0.15s ease;
}
.query-cell:hover { transform: scale(1.35); z-index: 10; }
.query-cell.hit      { background: rgba(34,197,94,0.22); border: 1px solid rgba(34,197,94,0.4); color: #22C55E; }
.query-cell.miss     { background: rgba(239,68,68,0.18); border: 1px solid rgba(239,68,68,0.32); color: #EF4444; }
.query-cell.hard-hit { background: rgba(99,102,241,0.28); border: 1px solid rgba(99,102,241,0.5); color: #A5B4FC; }
.query-cell.hard-miss{ background: rgba(249,115,22,0.18); border: 1px solid rgba(249,115,22,0.32); color: #FB923C; }
.legend-row { display: flex; gap: 1rem; margin-top: 0.6rem; flex-wrap: wrap; }
.legend-item { display: flex; align-items: center; gap: 0.4rem; font-size: 0.7rem; color: #64748B; }
.legend-dot { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
.stSpinner > div { border-top-color: #6366F1 !important; }
</style>
""", unsafe_allow_html=True)
    if st.session_state.get("light_theme", False):
        st.markdown(
            """
<style>
html, body, [class*="css"], .stApp { background:#F6F8FB !important; color:#172033 !important; }
header[data-testid="stHeader"] { background:#F6F8FB !important; }
.stTabs [data-baseweb="tab-list"] { background:#FFFFFF; border-color:#E2E8F0; }
.stTabs [data-baseweb="tab"] { color:#64748B !important; }
.stTabs [aria-selected="true"] { background:#172033 !important; color:#FFFFFF !important; box-shadow:none !important; }
.hero-title { background:none; -webkit-text-fill-color:#172033; color:#172033; }
.hero-eyebrow { background:none; -webkit-text-fill-color:#475569; color:#475569; }
.hero-sub, .result-count, .filter-chip { color:#64748B !important; }
.stTextInput input, .stSelectbox > div > div { background:#FFFFFF !important; color:#172033 !important; border-color:#CBD5E1 !important; }
.stTextInput input::placeholder { color:#94A3B8 !important; }
.stFormSubmitButton > button { background:#172033 !important; box-shadow:none !important; }
.stButton > button { background:#FFFFFF !important; color:#334155 !important; border-color:#CBD5E1 !important; }
.chat-card { background:#FFFFFF; border-color:#E2E8F0; box-shadow:0 6px 22px rgba(15,23,42,.08); }
.chat-header { background:#FFFFFF; border-bottom-color:#E2E8F0; }
.chat-header-name { color:#172033; }.chat-header-sub, .chat-header-score { color:#64748B; }
.messages-wrap { background:#EEF2F5; background-image:radial-gradient(rgba(15,23,42,.04) 1px, transparent 1px); }
.bubble.other { background:#FFFFFF; border-color:#E2E8F0; }.bubble.target { background:#E8F1FF; border-color:#93C5FD; }
.bubble-text { color:#172033; }.bubble-time { color:#64748B; }
.date-sep span { color:#64748B; background:#FFFFFF; border-color:#E2E8F0; }
.ctx-divider span { color:#1D4ED8; background:#DBEAFE; border-color:#BFDBFE; }
.empty-state, .metric-glass { background:#FFFFFF; border-color:#E2E8F0; }
.empty-title, .eval-hero-title { color:#172033 !important; -webkit-text-fill-color:#172033; background:none; }
.empty-sub, .eval-hero-sub, .metric-label, .metric-sub { color:#64748B !important; }
.eval-hero { background:#FFFFFF; border-color:#E2E8F0; }.gap-banner { background:#EFF6FF; border-left-color:#2563EB; }
.intent-badge.semantic { color:#3730A3 !important; background:#EEF2FF; border-color:#C7D2FE; }
.intent-badge.person { color:#0E7490 !important; background:#ECFEFF; border-color:#A5F3FC; }
.intent-badge.temporal { color:#92400E !important; background:#FFFBEB; border-color:#FDE68A; }
.result-header, .sb-section-title { color:#475569 !important; }
.chat-header-rank { color:#4338CA !important; background:#EEF2FF !important; border-color:#C7D2FE !important; }
.target-marker { color:#4338CA !important; background:#EEF2FF !important; }
.filter-chip { background:#EEF2F7 !important; border-color:#E2E8F0 !important; }
.gap-banner-text { color:#475569 !important; }
.gap-banner-text strong { color:#1E3A8A !important; }
.legend-item { color:#475569 !important; }
.stSelectbox label, .stTextInput label, .stToggle label { color:#475569 !important; }
[data-baseweb="popover"], [data-baseweb="menu"] { background:#FFFFFF !important; }
[data-baseweb="menu"] *, [data-baseweb="popover"] * { color:#172033 !important; }
.stAlert, [data-testid="stAlert"] { background:#FFF7ED !important; color:#9A3412 !important; border-color:#FED7AA !important; }
.stExpander { background:#FFFFFF !important; border-color:#E2E8F0 !important; }
.stExpander summary, .stExpander summary * { color:#334155 !important; }
.stDataFrame, [data-testid="stDataFrame"] { border-color:#E2E8F0 !important; }
.bubble-ticks { color:#2563EB !important; }
</style>
            """,
            unsafe_allow_html=True,
        )


# ─── Sidebar ─────────────────────────────────────────────────────────────────

def render_sidebar(stats: dict[str, Any] | None) -> None:
    with st.sidebar:
        st.toggle("Light theme", key="light_theme")
        # Group header
        participants = stats.get("participants", []) if stats else []
        member_count = len(participants) or 8
        st.markdown(
            f'<div class="sb-chat-header">'
            f'<div class="sb-group-icon">C</div>'
            f'<div>'
            f'<div class="sb-group-name">ConvoLens</div>'
            f'<div class="sb-group-meta">'
            f'Group Chat Search · {member_count} members'
            f'</div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        # Backend status
        health, err = request_api("GET", "/health")
        is_online = health and not err
        dot_cls = "pulse-dot" if is_online else "pulse-dot offline"
        status_text = "API connected" if is_online else "API offline"
        st.markdown(
            f'<div class="sb-status-bar">'
            f'<span class="{dot_cls}"></span>{status_text}'
            f'</div>',
            unsafe_allow_html=True,
        )

        if not is_online:
            return

        # Members list
        st.markdown('<div class="sb-section"><div class="sb-section-title">Members</div>', unsafe_allow_html=True)
        for name in participants:
            color = avatar_color(name)
            initials = avatar_initials(name)
            st.markdown(
                f'<div class="sb-member-row">'
                f'<div class="msg-avatar" style="background:{color};width:32px;height:32px;font-size:0.65rem">{initials}</div>'
                f'<div>'
                f'<div class="sb-member-name">{html.escape(name)}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # Stats
        if stats:
            dates = stats.get("date_range", {})
            st.markdown('<div class="sb-stat-section"><div class="sb-section-title">Archive</div>', unsafe_allow_html=True)
            for label, val in [
                ("Messages", f"{int(stats.get('total_messages', 0)):,}"),
                ("Date range", f"{str(dates.get('start',''))[:7]} – {str(dates.get('end',''))[:7]}"),
                ("Model", str(stats.get("embedding_model", "")).split("/")[-1]),
            ]:
                st.markdown(
                    f'<div class="sb-stat-row"><span class="sb-stat-label">{label}</span>'
                    f'<span class="sb-stat-val">{val}</span></div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)


# ─── Bubble renderer ─────────────────────────────────────────────────────────

REACTIONS = ["🔥", "👍", "❤️", "😮", "🎉", "✅"]


def bubble_html(message: dict[str, Any], is_target: bool, show_date_sep: bool = False) -> str:
    sender = html.escape(str(message.get("sender", "Unknown")))
    text = html.escape(str(message.get("text", "")))
    ts = str(message.get("timestamp", ""))
    time_str = format_timestamp(ts)
    date_str = format_date(ts)
    color = avatar_color(sender)
    initials = avatar_initials(sender)

    parts: list[str] = []

    if show_date_sep:
        parts.append(
            f'<div class="date-sep"><span>{html.escape(date_str)}</span></div>'
        )

    avatar = (
        f'<div class="msg-avatar" style="background:{color};width:28px;height:28px">'
        f'{html.escape(initials)}</div>'
    )

    bubble_cls = "target" if is_target else "other"
    sender_label = ""
    if not is_target:
        sender_label = f'<div class="bubble-sender" style="color:{color}">{sender}</div>'

    target_marker = ""
    if is_target:
        target_marker = '<div class="target-marker">🔎 Matched message</div>'

    reaction_html = ""
    if is_target:
        rx = REACTIONS[abs(hash(text)) % len(REACTIONS)]
        reaction_html = f'<div class="bubble-reaction">{rx} 2</div>'

    ticks = '<span class="bubble-ticks">✓✓</span>' if is_target else '<span style="color:#475569;font-size:0.65rem">✓</span>'

    bubble_inner = (
        f'<div class="bubble {bubble_cls}" style="position:relative">'
        f'{target_marker}'
        f'{sender_label}'
        f'<div class="bubble-text">{text}</div>'
        f'<div class="bubble-footer">'
        f'<span class="bubble-time">{html.escape(time_str)}</span>'
        f'{ticks}'
        f'</div>'
        f'{reaction_html}'
        f'</div>'
    )

    row = (
        f'<div class="msg-row">'
        f'{avatar}{bubble_inner}'
        f'</div>'
    )
    parts.append(row)
    return "".join(parts)


def render_result(result: dict[str, Any]) -> None:
    rank = int(result.get("rank", 0))
    similarity = float(result.get("retrieval_similarity", 0.0))
    context_msgs = list(result.get("context", {}).get("messages", []))
    if not context_msgs:
        context_msgs = [dict(result, is_target=True)]

    # Build messages HTML
    html_parts: list[str] = []
    prev_date = ""
    divider_inserted = False

    for msg in context_msgs:
        is_target = bool(msg.get("is_target"))
        ts = str(msg.get("timestamp", ""))
        date_str = format_date(ts)
        show_sep = date_str != prev_date
        prev_date = date_str

        if is_target and not divider_inserted:
            html_parts.append(
                '<div class="ctx-divider"><span>Matched Message</span></div>'
            )
            divider_inserted = True

        html_parts.append(bubble_html(msg, is_target, show_date_sep=show_sep))

    # Participants in context
    senders_in_ctx = list(dict.fromkeys(
        str(m.get("sender", "")) for m in context_msgs
    ))
    avatars_html = "".join(
        f'<div class="msg-avatar" style="background:{avatar_color(s)};width:20px;height:20px;'
        f'font-size:0.5rem;margin-right:-4px">{html.escape(avatar_initials(s))}</div>'
        for s in senders_in_ctx[:4]
    )

    st.markdown(
        f'<div class="chat-card">'
        # Card header
        f'<div class="chat-header">'
        f'<div class="chat-header-avatar">C</div>'
        f'<div class="chat-header-info">'
        f'<div class="chat-header-name">ConvoLens</div>'
        f'<div class="chat-header-sub" style="display:flex;align-items:center;gap:4px">'
        f'{avatars_html}'
        f'<span style="margin-left:6px">{", ".join(html.escape(s) for s in senders_in_ctx[:3])}'
        f'{"…" if len(senders_in_ctx) > 3 else ""}</span>'
        f'</div></div>'
        f'<span class="chat-header-rank">#{rank}</span>'
        f'<span class="chat-header-score">{similarity:.0%}</span>'
        f'</div>'
        # Messages
        f'<div class="messages-wrap">{"".join(html_parts)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─── Search tab ───────────────────────────────────────────────────────────────

def submit_search(query: str) -> None:
    requested_count = st.session_state.get("result_count", SEARCH_RESULT_COUNT)
    payload, error = request_api(
        "POST", "/search",
        json={"query": query, "top_k": requested_count},
    )
    if payload is None and requested_count > 20 and error and "less than or equal to 20" in error:
        payload, error = request_api("POST", "/search", json={"query": query, "top_k": 20})
    st.session_state.search_payload = payload
    st.session_state.search_error = error
    st.session_state.last_query = query


def render_search() -> None:
    st.markdown('<div class="hero-eyebrow">Hinglish · Semantic Search · RAG Pipeline</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title">Find any chat moment,<br>instantly.</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-sub">Search by meaning, person, or time across 4,200 messages. '
        'Every result shows the full conversation context.</p>',
        unsafe_allow_html=True,
    )

    # Example chips
    cols = st.columns(len(EXAMPLE_QUERIES))
    selected_example: str | None = None
    for col, ex in zip(cols, EXAMPLE_QUERIES):
        if col.button(ex, key=f"chip_{ex}", use_container_width=True):
            selected_example = ex
    if selected_example:
        with st.spinner("Searching…"):
            submit_search(selected_example)
        st.rerun()

    with st.form("search_form", clear_on_submit=False):
        result_options = [5, 10, 20, MAX_RELEVANT_RESULTS]
        selected_count = st.session_state.get("result_count", SEARCH_RESULT_COUNT)
        if selected_count not in result_options:
            selected_count = SEARCH_RESULT_COUNT
        q_col, n_col = st.columns([5, 1])
        with q_col:
            query = st.text_input(
                "Search",
                value=st.session_state.get("last_query", ""),
                placeholder="What did Priya say about the budget?",
                label_visibility="collapsed",
            )
        with n_col:
            result_count = st.selectbox(
                "Results",
                options=result_options,
                index=result_options.index(selected_count),
                format_func=lambda count: "All relevant" if count == MAX_RELEVANT_RESULTS else str(count),
            )
        submitted = st.form_submit_button("🔍  Search", use_container_width=True)

    if submitted:
        st.session_state.result_count = result_count
        if query.strip():
            with st.spinner("Searching…"):
                submit_search(query.strip())
        else:
            st.session_state.search_payload = None
            st.session_state.search_error = "Enter a search question."

    error = st.session_state.get("search_error")
    payload = st.session_state.get("search_payload")

    if error:
        st.error(error)
        return

    if not payload:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-icon">💬</div>'
            '<div class="empty-title">Start searching</div>'
            '<div class="empty-sub">Ask a question or tap one of the example chips above.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Intent + filter row
    intent_raw = str(payload.get("intent", "semantic")).upper()
    intent_info = INTENT_META.get(intent_raw, {"icon": "🔍", "label": intent_raw.title()})
    parsed = payload.get("parsed_query", {})
    intent_cls = intent_raw.lower()

    filter_chips = ""
    if parsed.get("sender"):
        filter_chips += f'<span class="filter-chip">👤 {html.escape(str(parsed["sender"]))}</span>'
    if parsed.get("time_expression"):
        filter_chips += f'<span class="filter-chip">📅 {html.escape(str(parsed["time_expression"]))}</span>'

    results = list(payload.get("results", []))
    st.markdown(
        f'<div class="intent-row">'
        f'<span class="intent-badge {intent_cls}">{intent_info["icon"]} {intent_info["label"]}</span>'
        f'{filter_chips}'
        f'<span class="result-count">{len(results)} result{"s" if len(results) != 1 else ""}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if not results:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-icon">🔍</div>'
            '<div class="empty-title">No relevant conversations found</div>'
            '<div class="empty-sub">This topic doesn\'t appear in the chat archive. '
            'Try different phrasing or ask about trip planning, budget, dates, or accommodation.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="result-header">Search Results</div>', unsafe_allow_html=True)
    for result in results:
        render_result(result)


# ─── Evaluation tab ───────────────────────────────────────────────────────────

def _gauge_svg(pct: float, color_start: str, color_end: str, size: int = 110) -> str:
    r = 40
    cx = cy = size // 2
    circumference = 2 * 3.14159 * r
    arc_fraction = (pct / 100) * 0.75
    dash = arc_fraction * circumference
    gap = circumference - dash
    grad_id = f"g{abs(hash(color_start)) % 9999}"
    return f"""
<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{color_start}"/>
      <stop offset="100%" stop-color="{color_end}"/>
    </linearGradient>
  </defs>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="8"
          stroke-dasharray="{0.75*circumference:.1f} {0.25*circumference:.1f}"
          stroke-dashoffset="{-0.625*circumference:.1f}" stroke-linecap="round"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#{grad_id})" stroke-width="8"
          stroke-dasharray="{dash:.1f} {gap:.1f}"
          stroke-dashoffset="{-0.625*circumference:.1f}" stroke-linecap="round"/>
  <text x="{cx}" y="{cy+5}" text-anchor="middle" font-family="Manrope,sans-serif"
        font-size="14" font-weight="800" fill="#F1F5F9">{pct:.0f}%</text>
</svg>"""


def render_evaluation() -> None:
    st.markdown(
        '<div class="eval-hero">'
        '<div class="eval-hero-title">Evaluation Dashboard</div>'
        '<div class="eval-hero-sub">Live accuracy benchmarks across 40 ground-truth queries · Hit@5 metric</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.button("▶  Run Evaluation", key="run_evaluation"):
        with st.spinner("Running 40 queries through the full pipeline…"):
            payload, error = request_api("GET", "/evaluate")
        st.session_state.evaluation_payload = payload
        st.session_state.evaluation_error = error

    error = st.session_state.get("evaluation_error")
    payload = st.session_state.get("evaluation_payload")

    if error:
        st.error(error)
        return

    if not payload:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-icon">📊</div>'
            '<div class="empty-title">No evaluation data yet</div>'
            '<div class="empty-sub">Click "Run Evaluation" to benchmark the search pipeline.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    overall = float(payload.get("overall_accuracy_at_5", 0))
    hard    = float(payload.get("hard_accuracy_at_5", 0))
    easy    = float(payload.get("easy_accuracy_at_5", 0))
    o_at1   = float(payload.get("overall_accuracy_at_1", 0))

    overall_pct = round(overall * 100, 1)
    hard_pct    = round(hard * 100, 1)
    easy_pct    = round(easy * 100, 1)
    at1_pct     = round(o_at1 * 100, 1)

    gauges = [
        ("Overall Hit@5", overall_pct, "#6366F1", "#8B5CF6", "All 40 queries"),
        ("Easy Hit@5",    easy_pct,    "#22D3EE", "#10B981", "32 paraphrase queries"),
        ("Hard Hit@5",    hard_pct,    "#F59E0B", "#EC4899", "8 zero-overlap queries"),
        ("Hit@1",         at1_pct,     "#10B981", "#22D3EE", "Top-1 precision"),
    ]
    cols = st.columns(4)
    for col, (label, pct, c1, c2, sub) in zip(cols, gauges):
        trend_cls = "up" if pct >= 88 else "mid"
        trend_icon = "▲" if pct >= 88 else "◆"
        col.markdown(
            f'<div class="metric-glass">'
            f'{_gauge_svg(pct, c1, c2)}'
            f'<div class="metric-label">{label}</div>'
            f'<div class="metric-sub">{sub}</div>'
            f'<div class="metric-trend {trend_cls}">{trend_icon} {pct:.1f}%</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    gap = easy - hard
    st.markdown(
        f'<div class="gap-banner">'
        f'<span style="font-size:1.1rem">⚡</span>'
        f'<div class="gap-banner-text">'
        f'<strong>Easy–Hard gap: {gap:.0%}</strong> — '
        f'A smaller gap means semantic search handles paraphrase-only (zero-overlap) queries reliably. '
        f'Overall Hit@5 of <strong>{overall_pct:.1f}%</strong> across all 40 benchmark queries.'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    try:
        import plotly.graph_objects as go

        segments = ["Overall", "Easy-32", "Hard-8"]
        hit5_vals = [overall_pct, easy_pct, hard_pct]
        hit1_vals = [at1_pct,
                     round(float(payload.get("easy_accuracy_at_1", 0)) * 100, 1),
                     round(float(payload.get("hard_accuracy_at_1", 0)) * 100, 1)]

        # Radar
        cats = ["Overall Hit@5", "Easy Hit@5", "Hard Hit@5", "Hit@1", "Overall Hit@5"]
        vals = [overall_pct, easy_pct, hard_pct, at1_pct, overall_pct]
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=vals, theta=cats, fill="toself",
            fillcolor="rgba(99,102,241,0.14)",
            line=dict(color="#6366F1", width=2),
            marker=dict(color="#6366F1", size=6),
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(visible=True, range=[0, 100],
                                tickfont=dict(color="#475569", size=10),
                                gridcolor="rgba(255,255,255,0.06)", ticksuffix="%"),
                angularaxis=dict(tickfont=dict(color="#94A3B8", size=11),
                                 gridcolor="rgba(255,255,255,0.07)"),
            ),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False, margin=dict(l=40, r=40, t=30, b=30), height=270,
        )

        # Bar
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            name="Hit@5", x=segments, y=hit5_vals,
            marker=dict(color=["#6366F1", "#22D3EE", "#F59E0B"], line=dict(width=0)),
            text=[f"{v:.1f}%" for v in hit5_vals], textposition="outside",
            textfont=dict(color="#A5B4FC", size=11, family="Manrope"),
        ))
        fig_bar.add_trace(go.Bar(
            name="Hit@1", x=segments, y=hit1_vals,
            marker=dict(color="rgba(245,158,11,0.5)", line=dict(width=0)),
            text=[f"{v:.1f}%" for v in hit1_vals], textposition="outside",
            textfont=dict(color="#FCD34D", size=11, family="Manrope"),
        ))
        fig_bar.update_layout(
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94A3B8", family="Inter"),
            xaxis=dict(gridcolor="rgba(255,255,255,0.04)", zeroline=False,
                       tickfont=dict(color="#94A3B8", size=12)),
            yaxis=dict(range=[0, 115], gridcolor="rgba(255,255,255,0.05)", zeroline=False,
                       tickfont=dict(color="#475569"), ticksuffix="%"),
            legend=dict(font=dict(color="#94A3B8"), bgcolor="rgba(0,0,0,0)",
                        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            bargap=0.22, bargroupgap=0.06,
            margin=dict(l=20, r=20, t=40, b=20), height=290,
        )

        r_col, b_col = st.columns([1, 1.35])
        with r_col:
            st.markdown('<div style="color:#334155;font-size:0.72rem;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;margin-bottom:0.4rem">Accuracy Radar</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_radar, use_container_width=True, config={"displayModeBar": False})
        with b_col:
            st.markdown('<div style="color:#334155;font-size:0.72rem;font-weight:700;letter-spacing:0.09em;text-transform:uppercase;margin-bottom:0.4rem">Hit@1 vs Hit@5 by Segment</div>', unsafe_allow_html=True)
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

    except ImportError:
        pass

    # Per-query heatmap
    results_rows = payload.get("results", [])
    if results_rows:
        st.markdown(
            '<div style="margin-top:1.4rem;color:#334155;font-size:0.72rem;font-weight:700;'
            'letter-spacing:0.09em;text-transform:uppercase;margin-bottom:0.65rem">'
            'Per-Query Hit Map (40 queries)</div>',
            unsafe_allow_html=True,
        )
        cells = []
        for row in results_rows:
            is_hard = bool(row.get("is_hard"))
            hit = bool(row.get("hit_at_5"))
            qid = str(row.get("query_id", "?"))[-2:]
            cls = ("hard-hit" if is_hard and hit else
                   "hard-miss" if is_hard else
                   "hit" if hit else "miss")
            cells.append(
                f'<div class="query-cell {cls}" title="Query {qid} · {"hit" if hit else "miss"}">{qid}</div>'
            )
        st.markdown(
            f'<div class="query-grid">{"".join(cells)}</div>'
            '<div class="legend-row">'
            '<div class="legend-item"><div class="legend-dot" style="background:rgba(34,197,94,0.35)"></div>Easy hit</div>'
            '<div class="legend-item"><div class="legend-dot" style="background:rgba(239,68,68,0.3)"></div>Easy miss</div>'
            '<div class="legend-item"><div class="legend-dot" style="background:rgba(99,102,241,0.45)"></div>Hard hit</div>'
            '<div class="legend-item"><div class="legend-dot" style="background:rgba(249,115,22,0.3)"></div>Hard miss</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown('<div style="margin-top:1.25rem"></div>', unsafe_allow_html=True)
        with st.expander("📋 Detailed per-query breakdown"):
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Query ID": row.get("query_id"),
                    "Query": str(row.get("query", ""))[:65] + ("…" if len(str(row.get("query", ""))) > 65 else ""),
                    "Intent": row.get("intent", ""),
                    "Type": "Hard" if row.get("is_hard") else "Easy",
                    "Hit@1": "✅" if row.get("hit_at_1") else "❌",
                    "Hit@5": "✅" if row.get("hit_at_5") else "❌",
                }
                for row in results_rows
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="ConvoLens · Group Chat Search",
        page_icon="💬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

    stats, _ = request_api("GET", "/stats")
    render_sidebar(stats or {})

    search_tab, eval_tab = st.tabs(["💬  Search", "📊  Evaluation"])
    with search_tab:
        render_search()
    with eval_tab:
        render_evaluation()


if __name__ == "__main__":
    main()
