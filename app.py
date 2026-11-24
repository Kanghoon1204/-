import streamlit as st

from utils.model_loader import ROOT, load_model


@st.cache_resource
def current_model(signature):
    return load_model()


def file_signature(path):
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


st.set_page_config(page_title="PIPEGUARD AI", page_icon=":material/monitoring:", layout="wide")
paths = [ROOT / "models" / name for name in ("rf_model.joblib", "model_metadata.json", "preprocessor.joblib")]
signature = tuple(file_signature(path) for path in paths)
st.session_state.model, st.session_state.model_detail = current_model(signature)

page = st.navigation([
    st.Page("pages/dashboard.py", title="대시보드", icon=":material/dashboard:", default=True),
    st.Page("pages/mat_playback.py", title="MAT 순차 재생·알림", icon=":material/play_circle:"),
    st.Page("pages/live_monitor.py", title="실시간 진동·알림", icon=":material/notifications_active:"),
    st.Page("pages/manual_diagnosis.py", title="수동 진단", icon=":material/sensors:"),
    st.Page("pages/csv_analysis.py", title="CSV 분석 및 신호", icon=":material/monitoring:"),
    st.Page("pages/capstone_ocsvm.py", title="캡스톤 OCSVM", icon=":material/analytics:"),
    st.Page("pages/history.py", title="진단 기록", icon=":material/history:"),
])
st.sidebar.divider()
st.sidebar.markdown("**PIPEGUARD AI**")
if st.session_state.model is None:
    st.sidebar.caption("기존 수동·CSV 진단용 단일 RF 미연결 · 진동 번들은 ‘실시간 진동·알림’에서 사용")
else:
    model = st.session_state.model
    st.sidebar.success(f"{model.name} · {model.version}")
st.title("PIPEGUARD AI — 지하배관 지능형 이상 진단 시스템")
page.run()
