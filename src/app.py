"""Streamlit dashboard for JTVO — Scrum Dashboard (Figma-matched design)."""

from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src import database as db
from src import jira_client as jira
from src.auth import check_authentication, logout, get_current_user

_GEMINI_ENABLED = bool(os.getenv("GEMINI_API_KEY"))

TARGET_BOARDS = [
    {"id": 2, "name": "ICT開発ボード"},
    {"id": 135, "name": "AI/Analytics (NLTCS)"},
]

TEAMS = ["全チーム", "A Scrum", "B Scrum", "AI&Analytics"]
TEAM_ORDER = ["A Scrum", "B Scrum", "AI&Analytics"]
TEAM_COLORS = {
    "A Scrum": "#0031d8",      # ict-blue-800
    "B Scrum": "#6f23d0",      # ict-purple-700
    "AI&Analytics": "#259d63"  # ict-green-600
}
TEAM_ABBR = {"A Scrum": "A", "B Scrum": "B", "AI&Analytics": "AI"}

# ── Page config ─────────────────────────────────────────────────

st.set_page_config(
    page_title="Scrum Dashboard — JTVO",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Authentication ──────────────────────────────────────────────
# Password is set via APP_PASSWORD in .env or Streamlit secrets
if not check_authentication():
    st.stop()

db.init_db()

# ── CSS (ICT-DESIGN System) ─────────────────────────────────────

st.markdown("""
<style>
    /* ══════════════════════════════════════════════════════════════
       ICT-DESIGN System Variables (based on Digital Agency Design System)
       ══════════════════════════════════════════════════════════════ */
    :root {
        /* Primary Colors */
        --ict-blue-50: #e8f1fe;
        --ict-blue-100: #d9e6ff;
        --ict-blue-200: #c5d7fb;
        --ict-blue-600: #3460fb;
        --ict-blue-800: #0031d8;
        --ict-blue-1000: #00118f;

        /* Success / Green */
        --ict-green-50: #e6f5ec;
        --ict-green-100: #c2e5d1;
        --ict-green-600: #259d63;
        --ict-green-800: #197a4b;

        /* Warning / Yellow-Orange */
        --ict-yellow-100: #fff0b3;
        --ict-yellow-700: #b78f00;
        --ict-orange-50: #ffeee2;
        --ict-orange-600: #fb5b01;
        --ict-orange-800: #c74700;

        /* Error / Red */
        --ict-red-50: #fdeeee;
        --ict-red-100: #ffdada;
        --ict-red-800: #ec0000;
        --ict-red-900: #ce0000;

        /* Neutral */
        --ict-gray-50: #f2f2f2;
        --ict-gray-100: #e6e6e6;
        --ict-gray-200: #cccccc;
        --ict-gray-500: #7f7f7f;
        --ict-gray-700: #4d4d4d;
        --ict-gray-800: #333333;
        --ict-gray-900: #1a1a1a;
        --ict-white: #ffffff;
        --ict-black: #000000;

        /* Elevation */
        --ict-elevation-1: 0 2px 8px 1px rgba(0, 0, 0, 0.1), 0 1px 5px 0 rgba(0, 0, 0, 0.15);
        --ict-elevation-2: 0 2px 12px 2px rgba(0, 0, 0, 0.1), 0 1px 6px 0 rgba(0, 0, 0, 0.15);
        --ict-elevation-3: 0 4px 16px 3px rgba(0, 0, 0, 0.1), 0 1px 6px 0 rgba(0, 0, 0, 0.15);

        /* Typography */
        --ict-font-family: "Noto Sans JP", -apple-system, BlinkMacSystemFont, sans-serif;
        --ict-radius-sm: 0.25rem;
        --ict-radius-md: 0.5rem;
        --ict-radius-lg: 0.75rem;
    }

    /* ── Global ── */
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');

    .stApp, [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        background-color: var(--ict-gray-50) !important;
        font-family: var(--ict-font-family) !important;
    }
    .block-container {
        padding: 2rem 2rem 1rem 2rem;
        max-width: 1280px;
        font-family: var(--ict-font-family);
    }

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, [data-testid="stHeader"] { visibility: hidden; }

    /* ── Card title / desc (used inside st.container) ── */
    .card-title {
        font-size: 1rem;
        font-weight: 700;
        color: var(--ict-gray-900);
        margin: 0 0 0.25rem 0;
        letter-spacing: 0.02em;
    }
    .card-desc {
        font-size: 0.875rem;
        color: var(--ict-gray-500);
        margin: 0 0 1rem 0;
        line-height: 1.6;
    }

    /* ── Section heading ── */
    .section-heading {
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--ict-gray-900);
        margin: 1.5rem 0 1rem 0;
        letter-spacing: 0.01em;
    }

    /* ── Cards with ICT elevation ── */
    [data-testid="stVerticalBlock"] > div[data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid var(--ict-gray-100) !important;
        border-radius: var(--ict-radius-md) !important;
        box-shadow: var(--ict-elevation-1) !important;
        background: var(--ict-white) !important;
    }

    /* ── Velocity trend indicator cards ── */
    .trend-card {
        border-radius: var(--ict-radius-md);
        padding: 1rem;
        box-shadow: var(--ict-elevation-1);
    }
    .trend-card .team-label {
        font-size: 0.875rem;
        font-weight: 500;
        margin: 0 0 0.5rem 0;
    }
    .trend-card .trend-value {
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0;
    }
    .trend-card .trend-change {
        font-size: 0.75rem;
        margin: 0.25rem 0 0 0;
        opacity: 0.85;
    }

    /* ── Sprint status cards ── */
    .sprint-card {
        border-radius: var(--ict-radius-md);
        padding: 1rem;
        border: 1px solid;
        box-shadow: var(--ict-elevation-1);
    }
    .sprint-card .label { font-size: 0.75rem; opacity: 0.75; }
    .sprint-card .big { font-size: 1.25rem; font-weight: 700; }

    /* ── Progress bar ── */
    .pbar {
        background: var(--ict-gray-100);
        border-radius: var(--ict-radius-sm);
        height: 8px;
        overflow: hidden;
        margin: 6px 0;
    }
    .pbar-fill { height: 100%; border-radius: var(--ict-radius-sm); }

    /* ── Load indicator cards ── */
    .load-card {
        border-radius: var(--ict-radius-md);
        padding: 1rem;
        box-shadow: var(--ict-elevation-1);
    }

    /* ── Alert banners (ICT-DESIGN notification-banner style) ── */
    .alert-red {
        background: var(--ict-red-50);
        border: 1px solid var(--ict-red-100);
        border-left: 4px solid var(--ict-red-800);
        border-radius: var(--ict-radius-md);
        padding: 1rem 1.25rem;
        color: var(--ict-red-900);
        margin-bottom: 1rem;
    }
    .alert-yellow {
        background: var(--ict-orange-50);
        border: 1px solid var(--ict-yellow-100);
        border-left: 4px solid var(--ict-orange-600);
        border-radius: var(--ict-radius-md);
        padding: 1rem 1.25rem;
        color: var(--ict-orange-800);
        margin-bottom: 1rem;
    }
    .alert-green {
        background: var(--ict-green-50);
        border: 1px solid var(--ict-green-100);
        border-left: 4px solid var(--ict-green-600);
        border-radius: var(--ict-radius-md);
        padding: 1rem 1.25rem;
        color: var(--ict-green-800);
        margin-bottom: 1rem;
    }

    /* ── Info banner ── */
    .info-banner {
        background: var(--ict-blue-50);
        border: 1px solid var(--ict-blue-100);
        border-left: 4px solid var(--ict-blue-600);
        border-radius: var(--ict-radius-md);
        padding: 0.75rem 1rem;
        margin-top: 1rem;
    }
    .info-banner p {
        font-size: 0.875rem;
        color: var(--ict-blue-1000);
        margin: 0;
    }

    /* ── Stat summary pill (chip-label style) ── */
    .stat-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.25rem 0.75rem;
        border-radius: var(--ict-radius-sm);
        font-size: 0.75rem;
        font-weight: 500;
        border: 1px solid currentColor;
    }

    /* ── Team stat card ── */
    .team-stat {
        border-radius: var(--ict-radius-md);
        padding: 0.75rem;
        box-shadow: var(--ict-elevation-1);
    }
    .team-stat .ts-label { font-size: 0.75rem; margin: 0 0 0.25rem 0; }
    .team-stat .ts-value { font-size: 1rem; font-weight: 700; margin: 0; }

    /* ── Load legend bar ── */
    .legend-bar { height: 8px; border-radius: var(--ict-radius-sm); width: 100%; }

    /* ── Navigation pills (ICT button style) ── */
    [data-testid="stRadio"] > div { gap: 0.5rem !important; }
    [data-testid="stRadio"] > div > label {
        background: var(--ict-blue-50) !important;
        color: var(--ict-blue-800) !important;
        border-radius: var(--ict-radius-sm) !important;
        padding: 0.5rem 1rem !important;
        border: 1px solid var(--ict-blue-200) !important;
        font-size: 0.875rem !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
    }
    [data-testid="stRadio"] > div > label:hover {
        background: var(--ict-blue-100) !important;
        border-color: var(--ict-blue-600) !important;
    }
    [data-testid="stRadio"] > div > label[data-checked="true"],
    [data-testid="stRadio"] > div > label[aria-checked="true"] {
        background: var(--ict-blue-800) !important;
        color: var(--ict-white) !important;
        border-color: var(--ict-blue-800) !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: var(--ict-white) !important;
        border-right: 1px solid var(--ict-gray-100) !important;
    }
    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: var(--ict-gray-50) !important;
        border: 1px solid var(--ict-gray-100) !important;
        border-radius: var(--ict-radius-md) !important;
        padding: 0.75rem 1rem !important;
    }

    /* ── Buttons (ICT button style) ── */
    .stButton > button {
        background: var(--ict-blue-800) !important;
        color: var(--ict-white) !important;
        border: none !important;
        border-radius: var(--ict-radius-sm) !important;
        font-weight: 500 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        background: var(--ict-blue-600) !important;
    }
    .stButton > button[kind="secondary"] {
        background: var(--ict-white) !important;
        color: var(--ict-blue-800) !important;
        border: 1px solid var(--ict-blue-800) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: var(--ict-blue-50) !important;
    }

    /* ── Dataframe (ICT table style) ── */
    .stDataFrame {
        border-radius: var(--ict-radius-md);
        overflow: hidden;
        border: 1px solid var(--ict-gray-100);
    }
    .stDataFrame [data-testid="stDataFrameResizable"] {
        font-family: var(--ict-font-family) !important;
    }

    /* ── Select boxes ── */
    [data-testid="stSelectbox"] > div > div {
        border-radius: var(--ict-radius-sm) !important;
        border-color: var(--ict-gray-200) !important;
    }

    /* ── Focus states (ICT accessibility) ── */
    *:focus-visible {
        outline: 4px solid var(--ict-black) !important;
        outline-offset: 2px !important;
        border-radius: var(--ict-radius-sm) !important;
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════

with st.sidebar:
    # ICT-DESIGN sidebar header
    st.markdown("""
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
        <div style="width:40px;height:40px;border-radius:0.25rem;background:#0031d8;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px 1px rgba(0,0,0,0.1);">
            <span style="color:white;font-size:1.25rem;">📊</span>
        </div>
        <div>
            <p style="font-family:'Noto Sans JP',sans-serif;font-weight:700;color:#1a1a1a;margin:0;font-size:1rem;">Scrum Dashboard</p>
            <p style="font-family:'Noto Sans JP',sans-serif;font-size:0.75rem;color:#7f7f7f;margin:0;">開発チーム可視化</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    issue_count = db.get_issue_count()
    st.metric("DB Issues", issue_count)
    st.divider()

    _missing = [k for k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
                if not os.getenv(k) or os.getenv(k, "").startswith("your-")]
    if _missing:
        st.error("`.env` に Jira 認証情報を設定:\n\n" + "\n".join(f"- `{k}`" for k in _missing))
        st.stop()

    # ── Sync ──
    def _run_sync(full: bool = False):
        already_synced = set() if full else db.get_closed_sprint_ids()
        total_issues = total_comments = skipped = 0
        for board in TARGET_BOARDS:
            st.write(f"**{board['name']}** ...")
            try:
                sprints = jira.get_sprints(board["id"])
            except Exception as e:
                st.write(f"  Skip: {e}"); continue
            for s in sprints:
                sid, state = s["id"], s["state"]
                if state == "closed" and sid in already_synced: skipped += 1; continue
                if state not in ("active", "future", "closed"): continue
                st.write(f"  {s['name']} ({state})")
                try:
                    i_df, c_df, cl_df = jira.extract_sprint_data(board["name"], sid, s["name"])
                    db.upsert_issues(i_df); db.upsert_comments(c_df); db.upsert_changelog(cl_df)
                    db.mark_sprint_synced(sid, board["name"], s["name"], state)
                    total_issues += len(i_df); total_comments += len(c_df)
                except Exception as e:
                    st.write(f"    Error: {e}")
        db.rebuild_weekly_metrics()
        db.rebuild_sprint_issues()
        db.recalculate_priorities()
        future_sp = sum(jira.extract_future_sprint_sp(b["id"]) for b in TARGET_BOARDS if True)
        db.calculate_sufficiency(future_sp)
        return total_issues, total_comments, skipped

    c1, c2 = st.columns(2)
    if c1.button("Sync", type="primary", width="stretch"):
        with st.status("Syncing...", expanded=True) as s:
            ni, nc, ns = _run_sync(False)
            s.update(label=f"完了: {ni} issues ({ns} skipped)", state="complete")
        st.rerun()
    if c2.button("Full Sync", width="stretch"):
        with st.status("Full syncing...", expanded=True) as s:
            ni, nc, _ = _run_sync(True)
            s.update(label=f"完了: {ni} issues, {nc} comments", state="complete")
        st.rerun()

    # ── AI ──
    if _GEMINI_ENABLED:
        st.divider()
        if st.button("Run AI Analysis", width="stretch"):
            from src.analyzer import Analyzer
            all_issues = db.get_all_issues()
            if all_issues.empty:
                st.warning("データなし。先にSyncしてください。")
            else:
                analyzer = Analyzer()
                con = db._connect()
                comments_df = con.execute("SELECT * FROM issue_comments").fetchdf()
                con.close()
                progress = st.progress(0, text="Analyzing...")
                scores_df = analyzer.analyze_sprint_issues(
                    all_issues, comments_df,
                    progress_callback=lambda c, t: progress.progress(c / t, text=f"Analyzing {c}/{t}..."),
                )
                db.upsert_ai_scores(scores_df); db.rebuild_weekly_metrics()
                progress.progress(1.0, text="Complete!"); st.rerun()
        if st.button("Generate Feedback", width="stretch"):
            from src.analyzer import Analyzer
            lb = db.get_individual_leaderboard(); sc = db.get_all_issues_with_scores()
            if lb.empty: st.warning("先にAI Analysisを実行してください。")
            else:
                a = Analyzer()
                with st.spinner("Gemini is thinking..."):
                    fb = a.generate_weekly_feedback(sc.head(50).to_string(index=False), lb.to_string(index=False))
                st.session_state["feedback"] = fb
        if "feedback" in st.session_state:
            fb = st.session_state["feedback"]
            st.markdown("### Gemini's Verdict"); st.markdown(fb.feedback)
            st.markdown(f"**MVP:** {fb.mvp}")
    else:
        st.divider(); st.info("AI: GEMINI_API_KEY 未設定")


# ══════════════════════════════════════════════════════════════════
# MAIN DASHBOARD
# ══════════════════════════════════════════════════════════════════

# ── Header (ICT-DESIGN heading style) ───────────────────────────

st.markdown("""
<div style="background:var(--ict-white, #ffffff);border:1px solid var(--ict-gray-100, #e6e6e6);border-radius:0.5rem;padding:1.5rem;margin-bottom:1rem;box-shadow:var(--ict-elevation-2, 0 2px 12px 2px rgba(0,0,0,0.1));">
    <h1 style="font-family:'Noto Sans JP',sans-serif;font-size:1.75rem;font-weight:700;color:var(--ict-gray-900, #1a1a1a);margin:0 0 0.5rem 0;letter-spacing:0.01em;line-height:1.4;">Scrum Dashboard</h1>
    <p style="color:var(--ict-gray-500, #7f7f7f);font-size:0.875rem;margin:0;line-height:1.6;">開発チーム全体の可視化とKPI追跡</p>
</div>
""", unsafe_allow_html=True)

# ── Team filter + Period filter ─────────────────────────────────

fcol1, fcol2 = st.columns([3, 1])
with fcol1:
    selected_team = st.radio("team_filter", TEAMS, horizontal=True, label_visibility="collapsed")
with fcol2:
    DASHBOARD_START = date(2025, 12, 8)  # B Scrum発足日
    PERIODS = {"直近4週": 28, "直近8週": 56, "直近3ヶ月": 90, "直近6ヶ月": 180, "全期間": 0}
    period_label = st.selectbox("表示期間", list(PERIODS.keys()), index=4, label_visibility="collapsed")

team_filter = None if selected_team == "全チーム" else selected_team
date_from = max(date.today() - timedelta(days=PERIODS[period_label]), DASHBOARD_START) if PERIODS[period_label] > 0 else DASHBOARD_START

# ── Sufficiency alert ───────────────────────────────────────────

suf = db.get_sufficiency_alert()
if suf:
    pct = round(suf["sufficiency"], 1)
    if pct < 70:
        st.markdown(f'<div class="alert-red"><strong>⚠ Sufficiency Alert: {pct}%</strong> — Future SP ({suf["future_sp"]}) / Avg Velocity ({suf["avg_velocity"]:.1f}). バックログ補充が必要です。</div>', unsafe_allow_html=True)
    elif pct < 100:
        st.markdown(f'<div class="alert-yellow"><strong>Sufficiency: {pct}%</strong> — Future SP ({suf["future_sp"]}) / Avg Velocity ({suf["avg_velocity"]:.1f})</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alert-green"><strong>Sufficiency: {pct}%</strong> — バックログは健全です。</div>', unsafe_allow_html=True)

# ── Tab Navigation ──────────────────────────────────────────────

tab1, tab2 = st.tabs(["📊 チーム別ダッシュボード", "👤 個人別ベロシティ"])

with tab1:


    # ══════════════════════════════════════════════════════════════════
    # SECTION 0: Overall Velocity Summary
    # ══════════════════════════════════════════════════════════════════

    velocity_data = db.get_velocity_by_team(date_from)
    recent = db.get_recent_velocity_trend()
    team_summary = db.get_team_summary(date_from)

    if not team_summary.empty:
        all_total_sp = team_summary["total_sp"].sum()
        all_done_sp = team_summary["done_sp"].sum()
        all_completion = round(all_done_sp / all_total_sp * 100, 1) if all_total_sp > 0 else 0
        all_issues = team_summary["total_issues"].sum()
        # Compute weekly average velocity
        if not velocity_data.empty:
            weekly_total = velocity_data.groupby("week_start")["done_sp"].sum()
            avg_weekly_vel = weekly_total.mean()
        else:
            avg_weekly_vel = 0

        with st.container(border=True):
            st.markdown('<p class="card-title">チーム全体ベロシティサマリ</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">選択期間内の全チーム合算KPI。SP = Jira上の自己申告ストーリーポイント、達成率 = 完了SP / 計画SP</p>', unsafe_allow_html=True)

            kcols = st.columns(4)
            # ICT-DESIGN color scheme for KPI cards
            kpi_items = [
                ("合計 SP", f"{all_total_sp:.0f}", "#e8f1fe", "#00118f"),       # blue-50, blue-1000
                ("完了 SP", f"{all_done_sp:.0f}", "#e6f5ec", "#115a36"),        # green-50, green-900
                ("達成率", f"{all_completion:.1f}%", "#f1eafa", "#5c10be"),     # purple-50, purple-800
                ("平均ベロシティ/週", f"{avg_weekly_vel:.1f} SP", "#ffeee2", "#c74700"),  # orange-50, orange-800
            ]
            for i, (lbl, val, bg, fg) in enumerate(kpi_items):
                with kcols[i]:
                    st.markdown(f"""
                    <div style="background:{bg};border-radius:0.5rem;padding:1rem;text-align:center;">
                        <p style="font-size:0.75rem;color:{fg};margin:0 0 0.25rem 0;font-weight:500;">{lbl}</p>
                        <p style="font-size:1.5rem;font-weight:700;color:{fg};margin:0;">{val}</p>
                    </div>
                    """, unsafe_allow_html=True)

            # Per-team breakdown row
            tcols = st.columns(len(team_summary))
            for i, (_, row) in enumerate(team_summary.iterrows()):
                tn = row["team"]
                tc = TEAM_COLORS.get(tn, "#6b7280")
                pct = row["completion_pct"] if row["completion_pct"] is not None else 0
                with tcols[i]:
                    st.markdown(f"""
                    <div style="margin-top:0.75rem;padding:0.75rem;border-left:3px solid {tc};background:#f9fafb;border-radius:0 0.25rem 0.25rem 0;">
                        <p style="font-size:0.8rem;font-weight:600;color:#111827;margin:0 0 0.375rem 0;">{tn}</p>
                        <div style="display:flex;gap:1.5rem;font-size:0.75rem;color:#374151;">
                            <span>計画: <strong>{row['total_sp']:.0f} SP</strong></span>
                            <span>完了: <strong>{row['done_sp']:.0f} SP</strong></span>
                            <span>達成率: <strong>{pct:.0f}%</strong></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════
    # SECTION 1: Velocity Trend
    # ══════════════════════════════════════════════════════════════════

    with st.container(border=True):
        st.markdown('<p class="card-title">ベロシティトレンド分析</p>', unsafe_allow_html=True)
        st.markdown('<p class="card-desc">直近8週のSP推移から算出。直近3週平均 vs 前3週平均の変化率で改善/安定/低下を判定</p>', unsafe_allow_html=True)

        display_teams = [team_filter] if team_filter else [t for t in TEAM_ORDER if not recent.empty and t in recent["team"].values]

        if display_teams and not recent.empty:
            cols = st.columns(len(display_teams))
            for i, tn in enumerate(display_teams):
                td = recent[recent["team"] == tn].sort_values("week_start")
                if len(td) >= 2:
                    r_avg = td["done_sp"].tail(3).mean()
                    o_avg = td["done_sp"].head(3).mean()
                    chg = ((r_avg - o_avg) / o_avg * 100) if o_avg > 0 else 0
                else:
                    r_avg = td["done_sp"].mean() if not td.empty else 0
                    chg = 0

                # ICT-DESIGN colors for trend indicators
                if chg > 5:
                    bg, fg = "#e6f5ec", "#115a36"  # green-50, green-900
                    icon, label = "↑", "改善"
                elif chg < -5:
                    bg, fg = "#fdeeee", "#ce0000"  # red-50, red-900
                    icon, label = "↓", "低下"
                else:
                    bg, fg = "#f2f2f2", "#1a1a1a"  # gray-50, gray-900
                    icon, label = "→", "安定"

                # Build detail rows for recent and older 3 weeks
                recent_3 = td.tail(3)
                older_3 = td.head(3) if len(td) >= 4 else td.head(max(len(td) - 3, 0))

                detail_html = ""
                if not recent_3.empty:
                    detail_html += '<div style="margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid rgba(0,0,0,0.1);font-size:0.7rem;">'
                    detail_html += '<p style="margin:0 0 2px 0;font-weight:500;">直近3週:</p>'
                    for _, wr in recent_3.iterrows():
                        ws = str(wr["week_start"])[:10]
                        detail_html += f'<span style="margin-right:0.5rem;">{ws}: {wr["done_sp"]:.0f}SP</span>'
                    detail_html += f'<br/><strong>平均: {r_avg:.1f} SP</strong></div>'

                if not older_3.empty and len(td) >= 4:
                    detail_html += '<div style="margin-top:0.25rem;font-size:0.7rem;opacity:0.8;">'
                    detail_html += '<p style="margin:0 0 2px 0;font-weight:500;">前3週:</p>'
                    for _, wr in older_3.iterrows():
                        ws = str(wr["week_start"])[:10]
                        detail_html += f'<span style="margin-right:0.5rem;">{ws}: {wr["done_sp"]:.0f}SP</span>'
                    detail_html += f'<br/><strong>平均: {o_avg:.1f} SP</strong></div>'

                with cols[i]:
                    st.markdown(f"""
                    <div class="trend-card" style="background:{bg};color:{fg};">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <p class="team-label">{tn}</p>
                            <span style="font-size:1.25rem;">{icon}</span>
                        </div>
                        <div style="display:flex;align-items:baseline;gap:0.5rem;">
                            <p class="trend-value">{r_avg:.1f} SP</p>
                            <span style="font-size:0.875rem;">{chg:+.1f}%</span>
                        </div>
                        <p class="trend-change">直近3週平均・トレンド: {label}</p>
                        {detail_html}
                    </div>
                    """, unsafe_allow_html=True)

        # ── Row 2: Week-over-week comparison (前週 vs 前の前の週) ──
        st.markdown('<p class="card-desc" style="margin-top:1rem;">前週 vs 前の前の週の単週比較</p>', unsafe_allow_html=True)
        if display_teams and not recent.empty:
            cols2 = st.columns(len(display_teams))
            for i, tn in enumerate(display_teams):
                td = recent[recent["team"] == tn].sort_values("week_start")
                if len(td) >= 2:
                    last_w = td.iloc[-1]
                    prev_w = td.iloc[-2]
                    last_sp = last_w["done_sp"]
                    prev_sp = prev_w["done_sp"]
                    w_chg = ((last_sp - prev_sp) / prev_sp * 100) if prev_sp > 0 else 0
                    diff_sp = last_sp - prev_sp
                else:
                    last_w = td.iloc[-1] if not td.empty else None
                    prev_w = None
                    last_sp = last_w["done_sp"] if last_w is not None else 0
                    prev_sp = 0
                    w_chg = 0
                    diff_sp = 0

                # ICT-DESIGN colors for week-over-week comparison
                if w_chg > 10:
                    w_bg, w_fg = "#e6f5ec", "#115a36"  # green-50, green-900
                    w_icon = "↑"
                elif w_chg < -10:
                    w_bg, w_fg = "#fdeeee", "#ce0000"  # red-50, red-900
                    w_icon = "↓"
                else:
                    w_bg, w_fg = "#f2f2f2", "#1a1a1a"  # gray-50, gray-900
                    w_icon = "→"

                last_date = str(last_w["week_start"])[:10] if last_w is not None else "-"
                prev_date = str(prev_w["week_start"])[:10] if prev_w is not None else "-"

                with cols2[i]:
                    st.markdown(f"""
                    <div class="trend-card" style="background:{w_bg};color:{w_fg};">
                        <div style="display:flex;justify-content:space-between;align-items:center;">
                            <p class="team-label">{tn}</p>
                            <span style="font-size:1.25rem;">{w_icon}</span>
                        </div>
                        <div style="display:flex;align-items:baseline;gap:0.5rem;">
                            <p class="trend-value">{last_sp:.0f} SP</p>
                            <span style="font-size:0.875rem;">{w_chg:+.1f}% ({diff_sp:+.0f})</span>
                        </div>
                        <div style="margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid rgba(0,0,0,0.1);font-size:0.7rem;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
                                <span>前週 ({last_date}):</span>
                                <strong>{last_sp:.0f} SP</strong>
                            </div>
                            <div style="display:flex;justify-content:space-between;">
                                <span>前の前の週 ({prev_date}):</span>
                                <strong>{prev_sp:.0f} SP</strong>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════
    # SECTION 2: Velocity Chart
    # ══════════════════════════════════════════════════════════════════

    if not velocity_data.empty:
        with st.container(border=True):
            # Header with average velocity pills
            header_html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">'
            header_html += '<div><p class="card-title">チームベロシティ</p><p style="font-size:0.75rem;color:#6b7280;margin:0;">棒グラフ: 週別完了SP（完了日ベース）｜実線: 3週移動平均</p></div>'
            header_html += '<div style="display:flex;gap:0.5rem;">'
            for tn in (TEAM_ORDER if not team_filter else [team_filter]):
                vd = velocity_data[velocity_data["team"] == tn]
                if vd.empty:
                    continue
                avg = vd["done_sp"].mean()
                # ICT-DESIGN colors
                pill_bg = {"A Scrum": "#e8f1fe", "B Scrum": "#f1eafa", "AI&Analytics": "#e6f5ec"}.get(tn, "#f2f2f2")
                pill_fg = {"A Scrum": "#00118f", "B Scrum": "#5c10be", "AI&Analytics": "#115a36"}.get(tn, "#1a1a1a")
                header_html += f'<span class="stat-pill" style="background:{pill_bg};color:{pill_fg};">↑ {TEAM_ABBR.get(tn, tn)}: {avg:.1f} SP</span>'
            header_html += '</div></div>'
            st.markdown(header_html, unsafe_allow_html=True)

            MA_WINDOW = 3  # 3-week moving average

            fig = go.Figure()
            if team_filter:
                filt = velocity_data[velocity_data["team"] == team_filter].sort_values("week_start")
                tc = TEAM_COLORS.get(team_filter, "#6b7280")
                fig.add_trace(go.Bar(x=filt["week_start"], y=filt["done_sp"], name="完了 SP", marker_color=tc, opacity=0.8))
                if len(filt) >= MA_WINDOW:
                    ma = filt["done_sp"].rolling(MA_WINDOW).mean()
                    fig.add_trace(go.Scatter(x=filt["week_start"], y=ma, name=f"移動平均 ({MA_WINDOW}週)", mode="lines", line=dict(color=tc, width=3)))
            else:
                for tn in TEAM_ORDER:
                    td = velocity_data[velocity_data["team"] == tn].sort_values("week_start")
                    if td.empty: continue
                    fig.add_trace(go.Bar(x=td["week_start"], y=td["done_sp"], name=tn, marker_color=TEAM_COLORS.get(tn, "#6b7280"), opacity=0.85))
                for tn in TEAM_ORDER:
                    td = velocity_data[velocity_data["team"] == tn].sort_values("week_start")
                    if len(td) < MA_WINDOW: continue
                    ma = td["done_sp"].rolling(MA_WINDOW).mean()
                    fig.add_trace(go.Scatter(x=td["week_start"], y=ma, name=f"{TEAM_ABBR.get(tn, tn)} 移動平均", mode="lines", line=dict(color=TEAM_COLORS.get(tn, "#6b7280"), width=3)))

            # ICT-DESIGN chart styling
            fig.update_layout(
                barmode="group", height=400,
                margin=dict(t=10, b=40, l=50, r=20),
                plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                font=dict(family="Noto Sans JP, sans-serif"),
                xaxis=dict(gridcolor="#e6e6e6", title="", tickfont=dict(size=11, color="#4d4d4d")),
                yaxis=dict(gridcolor="#e6e6e6", title="ストーリーポイント", title_font=dict(size=12, color="#4d4d4d"), tickfont=dict(size=11, color="#4d4d4d")),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11, color="#4d4d4d")),
            )
            st.plotly_chart(fig, key="velocity_chart", theme=None)

            # Team stat summary cards
            stat_teams = TEAM_ORDER if not team_filter else [team_filter]
            scols = st.columns(len(stat_teams))
            for i, tn in enumerate(stat_teams):
                td = velocity_data[velocity_data["team"] == tn]
                if td.empty: continue
                total_sp = td["done_sp"].sum()
                avg_sp = td["done_sp"].mean()
                # ICT-DESIGN colors
                bg = {"A Scrum": "#e8f1fe", "B Scrum": "#f1eafa", "AI&Analytics": "#e6f5ec"}.get(tn, "#f2f2f2")
                fg = {"A Scrum": "#00118f", "B Scrum": "#5c10be", "AI&Analytics": "#115a36"}.get(tn, "#1a1a1a")
                fg2 = {"A Scrum": "#0031d8", "B Scrum": "#6f23d0", "AI&Analytics": "#259d63"}.get(tn, "#7f7f7f")
                tc = TEAM_COLORS.get(tn, "#6b7280")
                with scols[i]:
                    st.markdown(f"""
                    <div class="team-stat" style="background:{bg};color:{fg};">
                        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
                            <div style="width:12px;height:3px;background:{tc};border-radius:2px;"></div>
                            <span style="font-size:0.75rem;font-weight:500;">{tn}</span>
                        </div>
                        <div style="display:flex;gap:1rem;">
                            <div>
                                <p class="ts-label" style="color:{fg2};">合計 SP</p>
                                <p class="ts-value">{total_sp:.0f}</p>
                            </div>
                            <div>
                                <p class="ts-label" style="color:{fg2};">平均/週</p>
                                <p class="ts-value">{avg_sp:.1f}</p>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        # ── Achievement Rate Chart (separate) ──
        sprint_ach_tl = db.get_sprint_achievement_timeline(team_filter)
        if not sprint_ach_tl.empty:
            with st.container(border=True):
                st.markdown('<p class="card-title">スプリント達成率推移</p>', unsafe_allow_html=True)
                st.markdown('<p class="card-desc">完了SP / 計画SPの週別推移。キャリーオーバー（未完了のまま次スプリントに移動）を考慮した実質達成率</p>', unsafe_allow_html=True)

                fig_ach = go.Figure()
                RATE_DASH = {"A Scrum": "solid", "B Scrum": "dash", "AI&Analytics": "dashdot"}
                plot_teams = [team_filter] if team_filter else TEAM_ORDER
                for tn in plot_teams:
                    sa_t = sprint_ach_tl[sprint_ach_tl["team"] == tn].sort_values("week_start")
                    if sa_t.empty: continue
                    fig_ach.add_trace(go.Scatter(
                        x=sa_t["week_start"], y=sa_t["achievement_pct"],
                        name=f"{TEAM_ABBR.get(tn, tn)} 達成率",
                        mode="lines+markers",
                        line=dict(color=TEAM_COLORS.get(tn, "#6b7280"), width=2.5, dash=RATE_DASH.get(tn, "solid")),
                        marker=dict(size=6),
                    ))

                # 60% threshold line
                fig_ach.add_hline(y=60, line_dash="dot", line_color="#9ca3af", annotation_text="60% 基準", annotation_position="top left")

                # ICT-DESIGN chart styling
                fig_ach.update_layout(
                    height=300,
                    margin=dict(t=10, b=40, l=50, r=20),
                    plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                    font=dict(family="Noto Sans JP, sans-serif"),
                    xaxis=dict(gridcolor="#e6e6e6", title="", tickfont=dict(size=11, color="#4d4d4d")),
                    yaxis=dict(gridcolor="#e6e6e6", title="達成率 %", title_font=dict(size=12, color="#4d4d4d"), tickfont=dict(size=11, color="#4d4d4d"), range=[0, 105]),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11, color="#4d4d4d")),
                )
                st.plotly_chart(fig_ach, key="achievement_rate_chart", theme=None)

    else:
        st.info("ベロシティデータなし。Syncを実行してください。")


    # ══════════════════════════════════════════════════════════════════
    # SECTION 3: Current Sprint
    # ══════════════════════════════════════════════════════════════════

    sprint_progress = db.get_active_sprints_progress()

    with st.container(border=True):
        st.markdown('<p class="card-title">現在のスプリント進捗状況</p>', unsafe_allow_html=True)
        st.markdown('<p class="card-desc">Jira上でactiveなスプリントの完了SP / 計画SP。60%以上で「順調」、未満で「要注意」と判定</p>', unsafe_allow_html=True)

        if not sprint_progress.empty:
            sp = sprint_progress
            if team_filter:
                sp = sp[sp["team"] == team_filter]
            active = sp[sp["state"] == "active"]

            if not active.empty:
                acols = st.columns(min(len(active), 3))
                for i, (_, row) in enumerate(active.iterrows()):
                    pct = round(row["done_sp"] / row["total_sp"] * 100, 1) if row["total_sp"] > 0 else 0
                    on_track = pct >= 60
                    # ICT-DESIGN colors for sprint progress
                    if on_track:
                        bg, fg, bdr, bar_c = "#e6f5ec", "#115a36", "#c2e5d1", "#259d63"  # green palette
                        status_icon = "✓"
                    else:
                        bg, fg, bdr, bar_c = "#ffeee2", "#c74700", "#ffc199", "#fb5b01"  # orange palette
                        status_icon = "⚠"

                    with acols[i % len(acols)]:
                        st.markdown(f"""
                        <div class="sprint-card" style="background:{bg};color:{fg};border-color:{bdr};">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem;">
                                <span style="font-size:0.875rem;font-weight:500;">{row['team']}</span>
                                <span style="font-size:1.25rem;">{status_icon}</span>
                            </div>
                            <div>
                                <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:0.25rem;">
                                    <span class="label">完了率</span>
                                    <span class="big">{pct:.0f}%</span>
                                </div>
                                <div class="pbar"><div class="pbar-fill" style="width:{min(pct,100)}%;background:{bar_c};"></div></div>
                            </div>
                            <div style="display:flex;justify-content:space-between;margin-top:0.75rem;padding-top:0.5rem;border-top:1px solid {bdr};">
                                <div>
                                    <p class="label" style="margin:0 0 2px 0;">計画</p>
                                    <p style="font-size:1rem;font-weight:700;margin:0;">{row['total_sp']} SP</p>
                                </div>
                                <div>
                                    <p class="label" style="margin:0 0 2px 0;">完了</p>
                                    <p style="font-size:1rem;font-weight:700;margin:0;">{row['done_sp']} SP</p>
                                </div>
                            </div>
                            <div style="font-size:0.75rem;margin-top:0.5rem;opacity:0.8;">
                                {row['sprint_name']}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.markdown('<p style="color:#6b7280;font-size:0.875rem;">アクティブなスプリントがありません。</p>', unsafe_allow_html=True)

            st.markdown("""
            <div class="info-banner">
                <p><strong>判定基準:</strong> 完了率60%以上で「順調」と判定されます</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown('<p style="color:#6b7280;font-size:0.875rem;">スプリントデータなし。</p>', unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════
    # SECTION 3.5: Sprint Achievement & Carryover
    # ══════════════════════════════════════════════════════════════════

    sprint_achievement = db.get_sprint_achievement(team_filter)

    if not sprint_achievement.empty:
        with st.container(border=True):
            st.markdown('<p class="card-title">スプリント別達成率とキャリーオーバー</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">各スプリントの計画SP vs 完了SP。キャリーオーバー = 未完了のまま別スプリントに移動されたイシューのSP</p>', unsafe_allow_html=True)

            # Summary KPIs
            total_planned = sprint_achievement["planned_sp"].sum()
            total_done = sprint_achievement["done_sp"].sum()
            total_carry = sprint_achievement["carryover_sp"].sum()
            total_carry_count = sprint_achievement["carryover_count"].sum()
            true_rate = round(total_done / total_planned * 100, 1) if total_planned > 0 else 0

            kc = st.columns(4)
            # ICT-DESIGN color scheme
            carry_kpis = [
                ("計画 SP", f"{total_planned:.0f}", "#e8f1fe", "#00118f"),       # blue-50, blue-1000
                ("完了 SP", f"{total_done:.0f}", "#e6f5ec", "#115a36"),          # green-50, green-900
                ("キャリーオーバー SP", f"{total_carry:.0f}", "#fdeeee", "#ce0000"),  # red-50, red-900
                ("実質達成率", f"{true_rate:.1f}%", "#f1eafa", "#5c10be"),       # purple-50, purple-800
            ]
            for i, (lbl, val, bg, fg) in enumerate(carry_kpis):
                with kc[i]:
                    st.markdown(f"""
                    <div style="background:{bg};border-radius:0.5rem;padding:0.75rem;text-align:center;">
                        <p style="font-size:0.7rem;color:{fg};margin:0 0 0.25rem 0;font-weight:500;">{lbl}</p>
                        <p style="font-size:1.25rem;font-weight:700;color:{fg};margin:0;">{val}</p>
                    </div>
                    """, unsafe_allow_html=True)

            # Bar chart: per-sprint planned vs done vs carryover
            sa = sprint_achievement.groupby("sprint_name").agg({
                "planned_sp": "sum", "done_sp": "sum", "carryover_sp": "sum",
                "carryover_count": "sum", "achievement_pct": "mean"
            }).reset_index()
            # Sort by sprint name
            sa = sa.sort_values("sprint_name")

            # ICT-DESIGN colors for sprint achievement chart
            fig_carry = go.Figure()
            fig_carry.add_trace(go.Bar(x=sa["sprint_name"], y=sa["planned_sp"], name="計画 SP", marker_color="#c5d7fb", opacity=0.7))  # blue-200
            fig_carry.add_trace(go.Bar(x=sa["sprint_name"], y=sa["done_sp"], name="完了 SP", marker_color="#259d63"))  # green-600
            fig_carry.add_trace(go.Bar(x=sa["sprint_name"], y=sa["carryover_sp"], name="キャリーオーバー SP", marker_color="#ec0000"))  # red-800
            fig_carry.update_layout(
                barmode="group", height=350,
                margin=dict(t=10, b=60, l=50, r=20),
                plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                font=dict(family="Noto Sans JP, sans-serif"),
                xaxis=dict(tickangle=-45, tickfont=dict(size=9, color="#4d4d4d")),
                yaxis=dict(gridcolor="#e6e6e6", title="SP", title_font=dict(size=12, color="#4d4d4d"), tickfont=dict(size=11, color="#4d4d4d")),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=11, color="#4d4d4d")),
            )
            st.plotly_chart(fig_carry, key="sprint_achievement_chart", theme=None)

            # Detail table
            st.markdown('<p style="font-weight:600;color:#111827;margin:0.5rem 0 0.25rem 0;font-size:0.875rem;">スプリント別詳細</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">キャリーオーバー率 = キャリーオーバーSP / 計画SP。高いほどスプリント計画の精度に課題あり</p>', unsafe_allow_html=True)
            detail = sprint_achievement[["sprint_name", "team", "planned_sp", "done_sp", "carryover_sp", "carryover_count", "achievement_pct"]].copy()
            detail["carryover_pct"] = (detail["carryover_sp"] / detail["planned_sp"].replace(0, float("nan")) * 100).fillna(0).round(1)
            detail.columns = ["Sprint", "Team", "計画SP", "完了SP", "持越SP", "持越件数", "達成率%", "持越率%"]
            st.dataframe(detail, hide_index=True, height=min(len(detail) * 35 + 38, 400))


    # ══════════════════════════════════════════════════════════════════
    # SECTION 4: Team Load
    # ══════════════════════════════════════════════════════════════════

    load_data = db.get_assignee_load(team_filter)

    with st.container(border=True):
        if not load_data.empty:
            overall_sp = load_data["total_sp"].sum()
            overall_members = load_data["assignee"].nunique()
            overall_avg = overall_sp / overall_members if overall_members > 0 else 0

            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:1rem;">
                <div>
                    <p class="card-title">チーム負荷状況</p>
                    <p class="card-desc" style="margin:0;">直近4週間のアサイン済みイシューSP合計を人数で割った値。40SP/人以上で過負荷と判定</p>
                </div>
                <div style="text-align:right;">
                    <p style="font-size:1.5rem;font-weight:700;color:#111827;margin:0;">{overall_avg:.0f} SP</p>
                    <p style="font-size:0.75rem;color:#6b7280;margin:0;">平均負荷/人 (4週)</p>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Per-team load cards
            if not team_filter:
                tg = load_data.groupby("team").agg(total_sp=("total_sp", "sum"), members=("assignee", "nunique"), issues=("issue_count", "sum")).reset_index()
                lcols = st.columns(min(len(tg), 3))

                for i, (_, r) in enumerate(tg.iterrows()):
                    avg = r["total_sp"] / r["members"] if r["members"] > 0 else 0
                    # ICT-DESIGN colors for load levels
                    if avg >= 40:   bg, fg, bar_c, lbl = "#fdeeee", "#ce0000", "#ec0000", "過負荷"   # red
                    elif avg >= 30: bg, fg, bar_c, lbl = "#ffeee2", "#c74700", "#fb5b01", "高負荷"   # orange
                    elif avg >= 20: bg, fg, bar_c, lbl = "#e6f5ec", "#115a36", "#259d63", "最適"     # green
                    elif avg >= 10: bg, fg, bar_c, lbl = "#e8f1fe", "#00118f", "#0031d8", "適正"     # blue
                    else:           bg, fg, bar_c, lbl = "#f2f2f2", "#1a1a1a", "#7f7f7f", "低負荷"   # gray

                    load_pct = min(avg / 40 * 100, 100)

                    with lcols[i % len(lcols)]:
                        st.markdown(f"""
                        <div class="load-card" style="background:{bg};color:{fg};">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                                <span style="font-size:0.875rem;font-weight:500;">{r['team']}</span>
                                <span style="font-size:0.75rem;">{lbl}</span>
                            </div>
                            <div style="display:flex;align-items:baseline;gap:0.5rem;margin-bottom:0.5rem;">
                                <span style="font-size:1.5rem;font-weight:700;">{avg:.0f} SP</span>
                                <span style="font-size:0.75rem;opacity:0.75;">/ 人</span>
                            </div>
                            <div class="pbar"><div class="pbar-fill" style="width:{load_pct}%;background:{bar_c};"></div></div>
                            <div style="display:flex;justify-content:space-between;font-size:0.75rem;margin-top:0.5rem;">
                                <span style="opacity:0.75;">チーム人数</span>
                                <span style="font-weight:500;">{int(r['members'])}名</span>
                            </div>
                            <div style="display:flex;justify-content:space-between;font-size:0.75rem;">
                                <span style="opacity:0.75;">負荷</span>
                                <span style="font-weight:500;">{r['total_sp']:.0f} SP / {int(r['members'])}名</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            # Load legend (ICT-DESIGN colors)
            st.markdown("""
            <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:1rem;margin-top:1rem;padding-top:1rem;border-top:1px solid var(--ict-gray-100, #e6e6e6);">
                <div style="text-align:center;"><div class="legend-bar" style="background:#7f7f7f;"></div><span style="font-size:0.7rem;color:#7f7f7f;">0-9 低負荷</span></div>
                <div style="text-align:center;"><div class="legend-bar" style="background:#0031d8;"></div><span style="font-size:0.7rem;color:#7f7f7f;">10-19 適正</span></div>
                <div style="text-align:center;"><div class="legend-bar" style="background:#259d63;"></div><span style="font-size:0.7rem;color:#7f7f7f;">20-29 最適</span></div>
                <div style="text-align:center;"><div class="legend-bar" style="background:#fb5b01;"></div><span style="font-size:0.7rem;color:#7f7f7f;">30-39 高負荷</span></div>
                <div style="text-align:center;"><div class="legend-bar" style="background:#ec0000;"></div><span style="font-size:0.7rem;color:#7f7f7f;">40+ 過負荷</span></div>
            </div>
            """, unsafe_allow_html=True)

            # Member table
            st.markdown('<p style="font-weight:600;color:#111827;margin:1rem 0 0.25rem 0;font-size:0.875rem;">メンバー別負荷 (直近4週)</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">各メンバーのアサイン済みSP・イシュー数・完了数・進行中数。SP = Jira上の自己申告ストーリーポイント</p>', unsafe_allow_html=True)
            dl = load_data[["assignee", "team", "total_sp", "issue_count", "done_count", "in_progress_count"]].copy()
            dl.columns = ["Assignee", "Team", "SP", "Issues", "Done", "In Progress"]
            st.dataframe(dl, hide_index=True, height=min(len(dl) * 35 + 38, 350))
        else:
            st.markdown('<p class="card-title">チーム負荷状況</p>', unsafe_allow_html=True)
            st.markdown('<p style="color:#6b7280;font-size:0.875rem;">負荷データなし。</p>', unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════
    # SECTION 5: Leaderboard + Status
    # ══════════════════════════════════════════════════════════════════

    col_l, col_r = st.columns([1, 1])

    with col_l:
        with st.container(border=True):
            st.markdown('<p class="card-title">個人別 SP ランキング</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">期間別の完了SP順。前週・過去3週は完了日ベース、累計は12/8以降</p>', unsafe_allow_html=True)

            board_for_lb = None
            if team_filter in ("A Scrum", "B Scrum"):
                board_for_lb = "ICT開発ボード"
            elif team_filter == "AI&Analytics":
                board_for_lb = "AI/Analytics (NLTCS)"

            # Get all leaderboards
            leaderboard_total = db.get_individual_leaderboard(board_for_lb, date_from=DASHBOARD_START)
            leaderboard_periods = db.get_individual_leaderboard_by_period(board_for_lb)

            # Create tabs for different periods
            lb_tab1, lb_tab2, lb_tab3 = st.tabs(["📊 累計 (12/8~)", "📅 前週", "📈 過去3週"])

            with lb_tab1:
                if not leaderboard_total.empty:
                    st.dataframe(
                        leaderboard_total.rename(columns={"assignee": "担当者", "issue_count": "イシュー数", "total_sp": "合計SP"}),
                        hide_index=True, height=350,
                    )
                else:
                    st.markdown('<p style="color:#6b7280;">データなし。</p>', unsafe_allow_html=True)

            with lb_tab2:
                if not leaderboard_periods['last_week'].empty:
                    st.dataframe(
                        leaderboard_periods['last_week'].rename(columns={"assignee": "担当者", "issue_count": "イシュー数", "total_sp": "完了SP"}),
                        hide_index=True, height=350,
                    )
                else:
                    st.markdown('<p style="color:#6b7280;">データなし。</p>', unsafe_allow_html=True)

            with lb_tab3:
                if not leaderboard_periods['last_3_weeks'].empty:
                    st.dataframe(
                        leaderboard_periods['last_3_weeks'].rename(columns={"assignee": "担当者", "issue_count": "イシュー数", "total_sp": "完了SP"}),
                        hide_index=True, height=350,
                    )
                else:
                    st.markdown('<p style="color:#6b7280;">データなし。</p>', unsafe_allow_html=True)

    with col_r:
        with st.container(border=True):
            st.markdown('<p class="card-title">ステータス分布</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">Jiraステータスカテゴリ別のSP割合。完了/進行中/To Doの3区分</p>', unsafe_allow_html=True)

            status_df = db.get_status_breakdown(team_filter, date_from=DASHBOARD_START)
            if not status_df.empty:
                # ICT-DESIGN colors for status pie chart
                fig_s = go.Figure(data=[go.Pie(
                    labels=status_df["status_category"], values=status_df["sp"], hole=0.4,
                    marker_colors=[{"完了": "#259d63", "進行中": "#0031d8", "To Do": "#7f7f7f"}.get(s, "#999999") for s in status_df["status_category"]],
                    textinfo="label+percent", textfont_size=11,
                )])
                fig_s.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10), showlegend=False, paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font=dict(family="Noto Sans JP, sans-serif"))
                st.plotly_chart(fig_s, key="status_pie", theme=None)



    # ══════════════════════════════════════════════════════════════════
    # SECTION 6: Raw Data
    # ══════════════════════════════════════════════════════════════════

    issues_table = db.get_issues_for_table(team_filter, date_from=DASHBOARD_START)

    with st.container(border=True):
        rcol1, rcol2, rcol3 = st.columns([4, 1, 1])
        with rcol1:
            st.markdown('<p class="card-title">Rawデータ</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">Jiraから取得した全イシュー一覧。完了日はステータスが「完了」に変更された日付</p>', unsafe_allow_html=True)
        with rcol2:
            if not velocity_data.empty:
                st.download_button("ベロシティCSV", "\ufeff" + velocity_data.to_csv(index=False), "velocity.csv", "text/csv; charset=utf-8-sig", width="stretch")
        with rcol3:
            if not issues_table.empty:
                st.download_button("全イシューCSV", "\ufeff" + issues_table.to_csv(index=False), "issues.csv", "text/csv; charset=utf-8-sig", width="stretch")

        if not issues_table.empty:
            display_cols = ["key", "summary", "status", "priority", "team", "sprint_name", "assignee", "reported_sp", "created_date", "week_label", "completed_date"]
            available = [c for c in display_cols if c in issues_table.columns]
            st.dataframe(
                issues_table[available].rename(columns={"key": "Key", "summary": "概要", "status": "ステータス", "priority": "優先度", "team": "チーム", "sprint_name": "スプリント", "assignee": "担当者", "reported_sp": "SP", "created_date": "作成日", "week_label": "週", "completed_date": "完了日"}),
                hide_index=True, height=500,
            )
        else:
            st.markdown('<p style="color:#6b7280;">データなし。先にSyncしてください。</p>', unsafe_allow_html=True)


    # ══════════════════════════════════════════════════════════════════
    # TAB 2: Individual Velocity
    # ══════════════════════════════════════════════════════════════════

with tab2:
    st.markdown('<p class="card-title" style="margin-top:1rem;">個人別ベロシティ</p>', unsafe_allow_html=True)
    st.markdown('<p class="card-desc">担当者ごとの週別完了SP。複数チームで作業している場合はチーム別に分けて表示されます。担当者を選択してチーム平均・全体平均との比較が可能です。</p>', unsafe_allow_html=True)

    individual_velocity = db.get_individual_velocity(date_from)

    # Assignee multi-select filter
    if not individual_velocity.empty:
        # Sort assignees by total completed SP (descending)
        assignee_sp_totals = individual_velocity.groupby("assignee")["done_sp"].sum().sort_values(ascending=False)
        all_assignees = assignee_sp_totals.index.tolist()

        st.markdown("### フィルター")
        selected_assignees = st.multiselect(
            "担当者を選択（複数選択可）",
            options=all_assignees,
            default=[],
            help="担当者を選択してフィルタリング。未選択時は全員表示（完了SP順）"
        )

        # Filter data if assignees selected
        if selected_assignees:
            filtered_velocity = individual_velocity[individual_velocity["assignee"].isin(selected_assignees)]
        else:
            filtered_velocity = individual_velocity

        st.markdown("---")
    else:
        filtered_velocity = individual_velocity
        selected_assignees = []

    if not filtered_velocity.empty:
        # Calculate averages for comparison
        # Overall average (all assignees, all teams)
        overall_avg_sp = individual_velocity.groupby("assignee")["done_sp"].mean().mean()

        # Team averages
        team_avg_sp = individual_velocity.groupby(["assignee", "team"])["done_sp"].mean().groupby("team").mean()

        # Summary cards
        total_assignees = filtered_velocity["assignee"].nunique()
        total_sp = filtered_velocity["done_sp"].sum()
        avg_individual_velocity = filtered_velocity.groupby("assignee")["done_sp"].mean().mean()

        kcols = st.columns(4)
        kpi_items = [
            ("表示中アサイニー数", f"{total_assignees}", "#e8f1fe", "#00118f"),
            ("完了SP合計", f"{total_sp:.0f}", "#e6f5ec", "#115a36"),
            ("平均個人ベロシティ/週", f"{avg_individual_velocity:.1f} SP", "#ffeee2", "#c74700"),
            ("全体平均/週", f"{overall_avg_sp:.1f} SP", "#f1eafa", "#5c10be"),
        ]
        for i, (lbl, val, bg, fg) in enumerate(kpi_items):
            with kcols[i]:
                st.markdown(f"""
                <div style="background:{bg};border-radius:0.5rem;padding:1rem;text-align:center;">
                    <p style="font-size:0.75rem;color:{fg};margin:0 0 0.25rem 0;font-weight:500;">{lbl}</p>
                    <p style="font-size:1.5rem;font-weight:700;color:{fg};margin:0;">{val}</p>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Individual comparison view (when assignees selected)
        if selected_assignees:
            with st.container(border=True):
                st.markdown('<p class="card-title">選択された担当者の比較分析</p>', unsafe_allow_html=True)
                st.markdown('<p class="card-desc">各担当者の週平均ベロシティとチーム平均・全体平均との差分</p>', unsafe_allow_html=True)

                # Calculate individual stats with comparisons
                comparison_data = []
                for assignee in selected_assignees:
                    assignee_data = filtered_velocity[filtered_velocity["assignee"] == assignee]
                    if assignee_data.empty:
                        continue

                    # Get assignee's team(s)
                    assignee_teams = assignee_data.groupby("team").agg({
                        "done_sp": "sum",
                        "issue_count": "sum"
                    }).reset_index()

                    for _, team_row in assignee_teams.iterrows():
                        team = team_row["team"]
                        team_data = assignee_data[assignee_data["team"] == team]

                        # Calculate weekly average for this assignee-team combination
                        weekly_avg = team_data["done_sp"].mean()

                        # Get team average
                        team_avg = team_avg_sp.get(team, 0)

                        # Calculate differences
                        diff_from_team = weekly_avg - team_avg
                        diff_from_overall = weekly_avg - overall_avg_sp

                        comparison_data.append({
                            "担当者": assignee,
                            "チーム": team,
                            "週平均SP": round(weekly_avg, 1),
                            "チーム平均": round(team_avg, 1),
                            "差分(チーム比)": round(diff_from_team, 1),
                            "全体平均": round(overall_avg_sp, 1),
                            "差分(全体比)": round(diff_from_overall, 1),
                            "合計SP": team_row["done_sp"],
                            "イシュー数": int(team_row["issue_count"])
                        })

                if comparison_data:
                    comparison_df = pd.DataFrame(comparison_data)

                    # Color-coded display
                    def format_diff(val):
                        if val > 0:
                            return f"+{val:.1f}"
                        elif val < 0:
                            return f"{val:.1f}"
                        else:
                            return "±0.0"

                    # Create visual comparison
                    for _, row in comparison_df.iterrows():
                        assignee = row["担当者"]
                        team = row["チーム"]
                        weekly_avg = row["週平均SP"]
                        diff_team = row["差分(チーム比)"]
                        diff_overall = row["差分(全体比)"]

                        # Color based on performance
                        if diff_overall > 2:
                            bg, fg = "#e6f5ec", "#115a36"  # green
                            icon = "↑"
                        elif diff_overall < -2:
                            bg, fg = "#fdeeee", "#ce0000"  # red
                            icon = "↓"
                        else:
                            bg, fg = "#f2f2f2", "#1a1a1a"  # gray
                            icon = "→"

                        st.markdown(f"""
                        <div style="background:{bg};color:{fg};border-radius:0.5rem;padding:1rem;margin-bottom:0.75rem;">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.5rem;">
                                <span style="font-size:1rem;font-weight:600;">{assignee} ({team})</span>
                                <span style="font-size:1.5rem;">{icon}</span>
                            </div>
                            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin-top:0.75rem;">
                                <div>
                                    <p style="font-size:0.7rem;margin:0;opacity:0.75;">週平均</p>
                                    <p style="font-size:1.25rem;font-weight:700;margin:0;">{weekly_avg:.1f} SP</p>
                                </div>
                                <div>
                                    <p style="font-size:0.7rem;margin:0;opacity:0.75;">チーム平均比</p>
                                    <p style="font-size:1rem;font-weight:600;margin:0;">{format_diff(diff_team)} SP</p>
                                </div>
                                <div>
                                    <p style="font-size:0.7rem;margin:0;opacity:0.75;">全体平均比</p>
                                    <p style="font-size:1rem;font-weight:600;margin:0;">{format_diff(diff_overall)} SP</p>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    # Table view
                    st.markdown('<p style="font-weight:600;margin-top:1rem;">詳細データ</p>', unsafe_allow_html=True)
                    st.dataframe(
                        comparison_df,
                        hide_index=True,
                        height=min(len(comparison_df) * 35 + 38, 300),
                        use_container_width=True
                    )

        # Individual velocity chart
        with st.container(border=True):
            st.markdown('<p class="card-title">週別個人ベロシティ</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">完了日ベースの週別完了SP（担当者別）。フィルター選択時は選択された担当者のみ表示</p>', unsafe_allow_html=True)

            # Create pivot table for heatmap-style visualization
            pivot = filtered_velocity.pivot_table(
                index="assignee",
                columns="week_label",
                values="done_sp",
                aggfunc="sum",
                fill_value=0
            )

            # Sort by total SP descending
            pivot["total"] = pivot.sum(axis=1)
            pivot = pivot.sort_values("total", ascending=False)
            pivot = pivot.drop("total", axis=1)

            # Create bar chart grouped by assignee
            fig = go.Figure()

            # Get unique assignees sorted by total velocity
            assignee_totals = filtered_velocity.groupby("assignee")["done_sp"].sum().sort_values(ascending=False)
            sorted_assignees = assignee_totals.index.tolist()

            # Show selected assignees if filter applied, otherwise top 20
            display_assignees = selected_assignees if selected_assignees else sorted_assignees[:20]

            for assignee in display_assignees:
                assignee_data = filtered_velocity[filtered_velocity["assignee"] == assignee]
                if assignee_data.empty:
                    continue

                # Group by week and team
                weekly_data = assignee_data.groupby(["week_label", "team"]).agg({
                    "done_sp": "sum"
                }).reset_index()

                # If assignee works on multiple teams, show stacked bars
                for team in weekly_data["team"].unique():
                    team_data = weekly_data[weekly_data["team"] == team]
                    color = TEAM_COLORS.get(team, "#cccccc")

                    fig.add_trace(go.Bar(
                        x=team_data["week_label"],
                        y=team_data["done_sp"],
                        name=f"{assignee} ({team})",
                        marker_color=color,
                        hovertemplate="<b>%{fullData.name}</b><br>週: %{x}<br>完了SP: %{y:.1f}<extra></extra>"
                    ))

            fig.update_layout(
                barmode="group",
                height=600,
                showlegend=True,
                legend=dict(
                    orientation="v",
                    yanchor="top",
                    y=1,
                    xanchor="left",
                    x=1.01,
                    font=dict(size=10)
                ),
                xaxis=dict(
                    title="週",
                    tickangle=-45,
                    tickfont=dict(size=10)
                ),
                yaxis=dict(
                    title="完了SP",
                    gridcolor="#e6e6e6"
                ),
                plot_bgcolor="#ffffff",
                paper_bgcolor="#ffffff",
                margin=dict(l=50, r=250, t=30, b=100)
            )

            st.plotly_chart(fig, use_container_width=True)

        # Individual velocity table with team assignment
        with st.container(border=True):
            st.markdown('<p class="card-title">個人別ベロシティ詳細</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">担当者ごとの週別データ。チーム列は実際の作業チームで分類</p>', unsafe_allow_html=True)

            # Add summary row per assignee with comparisons
            assignee_summary = filtered_velocity.groupby(["assignee", "team"]).agg({
                "done_sp": "sum",
                "issue_count": "sum",
                "week_start": "count"
            }).reset_index()
            assignee_summary.columns = ["担当者", "チーム", "完了SP合計", "イシュー数", "アクティブ週数"]
            assignee_summary["週平均SP"] = (assignee_summary["完了SP合計"] / assignee_summary["アクティブ週数"]).round(1)

            # Add comparison columns
            assignee_summary["チーム平均"] = assignee_summary["チーム"].map(team_avg_sp).round(1)
            assignee_summary["差分(チーム比)"] = (assignee_summary["週平均SP"] - assignee_summary["チーム平均"]).round(1)
            assignee_summary["全体平均"] = round(overall_avg_sp, 1)
            assignee_summary["差分(全体比)"] = (assignee_summary["週平均SP"] - overall_avg_sp).round(1)

            assignee_summary = assignee_summary.sort_values("完了SP合計", ascending=False)

            st.dataframe(
                assignee_summary,
                hide_index=True,
                height=400,
                use_container_width=True
            )

            # Download button
            st.download_button(
                "個人別ベロシティCSV",
                "\ufeff" + filtered_velocity.to_csv(index=False),
                "individual_velocity.csv",
                "text/csv; charset=utf-8-sig",
                use_container_width=True
            )

        # Period-based leaderboards
        with st.container(border=True):
            st.markdown('<p class="card-title">期間別ランキング</p>', unsafe_allow_html=True)
            st.markdown('<p class="card-desc">前週・過去3週の完了SP順ランキング（完了日ベース）</p>', unsafe_allow_html=True)

            leaderboard_periods = db.get_individual_leaderboard_by_period()

            lb_col1, lb_col2 = st.columns(2)

            with lb_col1:
                st.markdown("**📅 前週**")
                if not leaderboard_periods['last_week'].empty:
                    st.dataframe(
                        leaderboard_periods['last_week'].rename(columns={"assignee": "担当者", "issue_count": "イシュー数", "total_sp": "完了SP"}),
                        hide_index=True,
                        height=350,
                        use_container_width=True
                    )
                else:
                    st.markdown('<p style="color:#6b7280;">データなし。</p>', unsafe_allow_html=True)

            with lb_col2:
                st.markdown("**📈 過去3週**")
                if not leaderboard_periods['last_3_weeks'].empty:
                    st.dataframe(
                        leaderboard_periods['last_3_weeks'].rename(columns={"assignee": "担当者", "issue_count": "イシュー数", "total_sp": "完了SP"}),
                        hide_index=True,
                        height=350,
                        use_container_width=True
                    )
                else:
                    st.markdown('<p style="color:#6b7280;">データなし。</p>', unsafe_allow_html=True)

        # Weekly detail view
        with st.container(border=True):
            st.markdown('<p class="card-title">週別個人ベロシティ生データ</p>', unsafe_allow_html=True)

            display_individual = filtered_velocity.copy()
            display_individual = display_individual.rename(columns={
                "week_start": "週開始日",
                "week_label": "週",
                "assignee": "担当者",
                "team": "チーム",
                "done_sp": "完了SP",
                "issue_count": "イシュー数"
            })

            st.dataframe(
                display_individual,
                hide_index=True,
                height=500,
                use_container_width=True
            )

    else:
        st.info("個人別ベロシティデータなし。Syncを実行してください。")
