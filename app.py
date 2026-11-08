"""12·13주차 결핍 이론 실습: RPM 6문항 + 하트/꽃 20회.
Run: streamlit run app.py
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import pandas as pd
import streamlit as st
from streamlit.components.v1 import declare_component
from supabase import create_client

st.set_page_config(page_title="결핍 이론 실습실 · 12·13주차", page_icon="🧠", layout="wide")

CLASSES = ["인하대", "숙대1", "숙대2"]  # 기존 BQ(retire) 분반과 동일
EXPERIMENTS = {"rpm": "12주차 · RPM 미니테스트 (6문항)", "heartflower": "13주차 · 하트/꽃 공간 불일치 과제 (20회)"}
TRIAL_COUNT = {"rpm": 6, "heartflower": 20}
RPM_ANSWERS = [4, 2, 1, 4, 2, 1]
RPM_EXPLANATIONS = [
    ("Q1", 4, "점 5개", "오른쪽으로 한 칸 이동할 때마다 점이 1개씩 늘어나고, 아래로 한 칸 이동할 때도 1개씩 늘어납니다."),
    ("Q2", 2, "오른쪽 삼각형(▶)", "화살표 방향이 오른쪽 → 아래 → 왼쪽 → 위 순서로 회전합니다."),
    ("Q3", 1, "채워진 검은 사각형", "채워진 사각형과 속이 빈 사각형이 번갈아 나타납니다."),
    ("Q4", 4, "오른쪽 아래 칸에 점", "3×3 칸 안의 점이 위쪽 왼쪽부터 오른쪽으로 한 칸씩 이동합니다."),
    ("Q5", 2, "중간 크기 검은 사각형", "작은 사각형 → 중간 사각형 → 큰 사각형이 순환합니다."),
    ("Q6", 1, "오른쪽 아래 칸에 속이 빈 점", "마지막 행의 점 위치는 왼쪽 아래 → 아래 가운데 → 오른쪽 아래입니다. 검은색 채움이 아닌 빈 점입니다."),
]


def reaction_time_guide():
    st.markdown("**반응시간(rt_ms)의 의미**")
    st.write("**ms(밀리초)**는 1초의 1,000분의 1입니다. **1,000 ms = 1초**이며, **7,474 ms는 약 7.47초**입니다.")
    st.write("RPM은 각 문제 화면이 표시된 후 보기를 선택하기까지, 하트/꽃은 자극이 표시된 후 좌·우 버튼을 누르기까지의 시간입니다.")
    st.write("학생별 평균 반응시간은 **각 문항 반응시간을 합한 후 시행 수로 나눈 값**입니다. 교수 화면의 전체 평균은 **제출 완료 학생들의 개인별 평균을 다시 평균**한 값입니다.")
    st.caption("시간이 짧다고 항상 좋은 결과는 아닙니다. 정답률과 함께 해석해야 하며, 기기·네트워크·조작 방식 등의 차이도 영향을 줄 수 있습니다. 두 실습은 개인의 지능을 판정하는 검사가 아닙니다.")


def professor_answer_guide(exp: str, df: pd.DataFrame):
    """Only on authenticated professor screen; never depend on student-facing reveal."""
    if exp == "rpm":
        st.write("**RPM 미니테스트: 6문항, 문항당 6개 보기**")
        st.dataframe(pd.DataFrame(RPM_EXPLANATIONS, columns=["문항", "정답 번호", "정답 도형", "도형 규칙·해설"]),
                     use_container_width=True, hide_index=True)
        st.caption("정답 번호는 보기의 왼쪽 위부터 오른쪽으로 1·2·3, 그 아래가 4·5·6입니다. 작년 GitHub 원본의 정답과 동일합니다.")
    else:
        st.write("**하트/꽃 20회: 자극 종류와 나타나는 위치에 따라 정답 방향이 바뀝니다.**")
        st.dataframe(pd.DataFrame([
            ("❤️ 하트", "왼쪽", "왼쪽(1)", "나타난 쪽 선택"),
            ("❤️ 하트", "오른쪽", "오른쪽(2)", "나타난 쪽 선택"),
            ("🌸 꽃", "왼쪽", "오른쪽(2)", "반대쪽 선택"),
            ("🌸 꽃", "오른쪽", "왼쪽(1)", "반대쪽 선택"),
        ], columns=["자극", "출현 위치", "정답", "규칙"]), hide_index=True, use_container_width=True)
        st.caption("학생마다 하트/꽃과 좌우 위치가 매 시행 무작위이므로 HF_1~HF_20의 정답은 학생별로 다를 수 있습니다.")
        if not df.empty:
            names = sorted(df["student_name"].dropna().astype(str).unique().tolist())
            selected = st.selectbox("학생별 20회 정답·응답 확인", names, key="prof_trial_student")
            row = df.loc[df["student_name"].astype(str) == selected].iloc[0]
            records = [{
                "시행": t["qid"],
                "자극": "하트" if t.get("stimulus") == "heart" else "꽃",
                "위치": "왼쪽" if t.get("side") == "L" else "오른쪽",
                "정답 방향": "왼쪽" if t["correct_index"] == 1 else "오른쪽",
                "학생 응답": "왼쪽" if t["response"] == 1 else "오른쪽",
                "정답 여부": "정답" if t["correct"] else "오답",
                "반응시간(ms)": t["rt_ms"],
            } for t in row["trials"]]
            st.dataframe(pd.DataFrame(records), hide_index=True, use_container_width=True)
T_SESSIONS = "scarcity_lab_sessions"
T_STUDENTS = "scarcity_lab_students"
T_RESULTS = "scarcity_lab_results"

st.markdown("""<style>
.block-container{max-width:1060px;padding-top:2rem}
.stButton button{border-radius:10px}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# Runs locally in the student's browser. Only completed batch is sent to Python.
experiment_component = declare_component(
    "scarcity_experiment", path=str(Path(__file__).parent / "frontend")
)

def find_session(cls: str) -> dict:
    rows = db().table(T_SESSIONS).select("*").eq("class_name", cls).execute().data
    if rows:
        return rows[0]
    # First-time initialization; upsert avoids concurrent first-access conflicts.
    db().table(T_SESSIONS).upsert({
        "class_name": cls, "experiment": "rpm", "is_open": False, "reveal": False,
    }, on_conflict="class_name").execute()
    return db().table(T_SESSIONS).select("*").eq("class_name", cls).single().execute().data


def save_session(cls: str, exp: str, opened: bool, reveal: bool) -> None:
    db().table(T_SESSIONS).upsert({
        "class_name": cls, "experiment": exp, "is_open": bool(opened), "reveal": bool(reveal),
    }, on_conflict="class_name").execute()


def get_result(cls: str, name: str, exp: str):
    rows = (db().table(T_RESULTS).select("*")
            .eq("class_name", cls).eq("student_name", name).eq("experiment", exp)
            .execute().data)
    return rows[0] if rows else None


def list_results(cls: str, exp: str) -> pd.DataFrame:
    rows = (db().table(T_RESULTS).select("*")
            .eq("class_name", cls).eq("experiment", exp).execute().data)
    return pd.DataFrame(rows)


def validate_payload(exp: str, payload: dict) -> list[dict]:
    """Ignore self-reported correct/score; check every answer against original rules."""
    if not isinstance(payload, dict) or payload.get("experiment") != exp:
        raise ValueError("실습 종류가 일치하지 않습니다.")
    trials = payload.get("results")
    if not isinstance(trials, list) or len(trials) != TRIAL_COUNT[exp]:
        raise ValueError("문항 수가 일치하지 않습니다.")
    cleaned = []
    for i, tr in enumerate(trials):
        if not isinstance(tr, dict):
            raise ValueError("응답 형식이 올바르지 않습니다.")
        qid = f"Q{i + 1}" if exp == "rpm" else f"HF_{i + 1}"
        if tr.get("qid") != qid:
            raise ValueError("문항 순서가 일치하지 않습니다.")
        response = tr.get("response")
        if type(response) is not int or response not in (range(1, 7) if exp == "rpm" else (1, 2)):
            raise ValueError("응답 범위가 올바르지 않습니다.")
        rt = tr.get("rt_ms")
        if type(rt) not in (int, float) or not 0 <= rt <= 600_000:
            raise ValueError("반응시간 데이터가 올바르지 않습니다.")
        if exp == "rpm":
            correct_index = RPM_ANSWERS[i]
            item = {}
        else:
            stimulus = tr.get("stimulus")
            side = tr.get("side")
            if stimulus not in ("heart", "flower") or side not in ("L", "R"):
                raise ValueError("자극 종류 또는 위치가 올바르지 않습니다.")
            correct_side = side if stimulus == "heart" else ("R" if side == "L" else "L")
            correct_index = 1 if correct_side == "L" else 2
            item = {"stimulus": stimulus, "side": side}
        cleaned.append({
            "qid": qid,
            "response": response,
            "correct_index": correct_index,
            "correct": response == correct_index,
            "rt_ms": round(rt),
            **item,
        })
    return cleaned


def store_result(cls: str, name: str, exp: str, trials: list[dict]):
    correct_count = sum(int(t["correct"]) for t in trials)
    mean_rt = round(sum(t["rt_ms"] for t in trials) / len(trials))
    # First submission wins, to avoid overwriting a completed attempt.
    db().table(T_RESULTS).insert({
        "class_name": cls,
        "student_name": name,
        "experiment": exp,
        "trials": trials,
        "correct_count": correct_count,
        "trial_count": len(trials),
        "accuracy": round(100 * correct_count / len(trials), 2),
        "mean_rt_ms": mean_rt,
    }).execute()


def summary_student(row: dict, revealed: bool):
    st.success("✅ 제출 및 저장 완료")
    c1, c2 = st.columns(2)
    c1.metric("내 정답률", f"{row['accuracy']:.1f}%")
    c2.metric("내 평균 반응시간", f"{row['mean_rt_ms']:,.0f} ms")
    st.caption(f"{row['correct_count']} / {row['trial_count']} 정답 · 개인 결과는 즉시 공개 · 문항별 해설은 교수자가 공개")
    if revealed:
        with st.expander("📖 교수자가 공개한 문항별 결과", expanded=True):
            if row["experiment"] == "rpm":
                st.write("RPM 정답 번호: ① 4번 · ② 2번 · ③ 1번 · ④ 4번 · ⑤ 2번 · ⑥ 1번")
            else:
                st.write("❤️ 하트는 같은 쪽, 🌸 꽃은 반대쪽이 정답입니다.")
            lines = []
            for t in row["trials"]:
                lines.append({"시행": t["qid"], "내 응답": t["response"], "정답": t["correct_index"],
                              "정오": "정답" if t["correct"] else "오답", "반응시간(ms)": t["rt_ms"]})
            st.dataframe(pd.DataFrame(lines), hide_index=True, use_container_width=True)


def student_screen():
    cls = st.session_state.student_class
    name = st.session_state.student_name
    session = find_session(cls)
    st.caption(f"{cls} · {name}")
    # 학생이 교수가 새 실습을 열었는지 직접 확인할 수 있도록 항상 표시합니다.
    # 진행 중 새로고침을 누르면 브라우저의 미제출 응답이 초기화될 수 있습니다.
    with st.container():
        if st.button("🔄 실습 상태 새로고침", key="student_status_refresh"):
            st.rerun()
    st.title("🧠 결핍 이론 실습실")
    st.info("본 활동은 인지 능력과 실행 제어의 체험입니다. 개인의 지능을 평가하거나 결핍의 효과를 직접 검증하는 검사는 아닙니다.")
    if not session["is_open"]:
        st.warning("교수님이 실습을 열면 참여할 수 있습니다. '새로고침'을 눌러 확인해 주세요.")
        return
    exp = session["experiment"]
    st.subheader(EXPERIMENTS[exp])
    existing = get_result(cls, name, exp)
    if existing:
        summary_student(existing, bool(session["reveal"]))
    else:
        st.warning("실습 진행 중에는 위의 '실습 상태 새로고침' 버튼을 누르지 마세요. 아직 제출하지 않은 답과 반응시간이 초기화될 수 있습니다.", icon="⚠️")
        st.caption("모든 문항을 마치면 서버에 한 번 저장됩니다.")
        # A stable component widget key keeps browser trial state across benign reruns.
        submitted = experiment_component(experiment=exp, key=f"lab_{cls}_{name}_{exp}", default=None)
        if submitted:
            try:
                trials = validate_payload(exp, submitted)
                # Make sure that classroom is still open for the same experiment.
                live = find_session(cls)
                if not live["is_open"] or live["experiment"] != exp:
                    st.error("실습이 종료되었거나 다른 실습으로 전환되어 저장할 수 없습니다. 교수님께 알려주세요.")
                    return
                if get_result(cls, name, exp) is None:
                    store_result(cls, name, exp, trials)
                st.rerun()
            except Exception as exc:
                # DB interruption: rerun component can retain submitted value.
                st.error(f"저장이 완료되지 않았습니다: {exc}. 화면을 유지하고 교수님께 알려주세요.")


def prof_screen():
    cls = st.session_state.prof_class
    st.title("🧠 12·13주차 실습 · 교수 통제소")
    st.caption(f"현재 분반: {cls} · RPM 및 하트/꽃 실습 공용")
    session = find_session(cls)
    with st.container(border=True):
        exp = st.selectbox("실습 선택", list(EXPERIMENTS),
                           index=list(EXPERIMENTS).index(session["experiment"]),
                           format_func=lambda x: EXPERIMENTS[x])
        opened = st.toggle("학생 실습 허용", value=bool(session["is_open"]))
        if st.button("✅ 선택한 실습과 열림 상태 적용", type="primary"):
            save_session(cls, exp, opened, reveal=False if exp != session["experiment"] else bool(session["reveal"]))
            st.rerun()
        st.caption("실습을 바꿔 적용하면 교수 정답 공개 상태는 자동으로 닫힙니다. 학생의 기존 제출은 유지됩니다.")
        st.info(f"현재 실제 송출: **{EXPERIMENTS[session['experiment']]}** · {'🟢 열림' if session['is_open'] else '⚪ 닫힘'}")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 최신 집계 불러오기", use_container_width=True):
            st.rerun()
    with col2:
        if st.button("🙈 정답·해설 닫기" if session["reveal"] else "📖 정답·해설 공개",
                     use_container_width=True):
            save_session(cls, session["experiment"], bool(session["is_open"]), not bool(session["reveal"]))
            st.rerun()

    st.subheader("결과 현황")
    view_exp = st.selectbox("집계할 실습", list(EXPERIMENTS), format_func=lambda x: EXPERIMENTS[x],
                            index=list(EXPERIMENTS).index(session["experiment"]))
    df = list_results(cls, view_exp)
    st.info("**평균 반응시간의 단위:** ms(밀리초). 예를 들어 7,474 ms는 약 7.47초입니다. 아래 '반응시간 설명'에서 계산 방법과 해석상 주의사항을 확인할 수 있습니다.")
    with st.expander("⏱ 반응시간(ms) 설명 · 계산 방식", expanded=False):
        reaction_time_guide()
    if df.empty:
        st.warning("아직 제출한 학생이 없습니다. 문항별 정답은 아래에서 확인할 수 있습니다.")
        with st.expander("🔐 교수 전용 문항별 정답·해설 보기", expanded=False):
            professor_answer_guide(view_exp, df)
        return
    student_rows = db().table(T_STUDENTS).select("student_name").eq("class_name", cls).execute().data
    registered = len(student_rows)
    done = len(df)
    cc1, cc2, cc3, cc4 = st.columns(4)
    cc1.metric("제출 완료", f"{done}명")
    cc2.metric("등록 학생", f"{registered}명")
    cc3.metric("전체 평균 정답률", f"{df['accuracy'].mean():.1f}%")
    cc4.metric("전체 평균 반응시간", f"{df['mean_rt_ms'].mean():,.0f} ms")
    st.caption("등록 학생 수는 앱에서 이름을 입력한 인원이며 실제 수강 인원과 다를 수 있습니다.")
    if registered:
        st.progress(min(done / registered, 1.0), text=f"완료율 {done}/{registered} (등록 학생 기준)")
    tab1, tab2, tab3 = st.tabs(["학생별 결과", "분포 및 문항별 통계", "문항·규칙(교수 전용)"])
    with tab1:
        columns = ["student_name", "correct_count", "trial_count", "accuracy", "mean_rt_ms", "submitted_at"]
        show = df[[c for c in columns if c in df.columns]].copy()
        show = show.rename(columns={"student_name":"학생", "correct_count":"정답 수", "trial_count":"시행 수", "accuracy":"정답률(%)", "mean_rt_ms":"평균 반응시간(ms)", "submitted_at":"제출 시각"})
        st.dataframe(show, hide_index=True, use_container_width=True)
        st.download_button("CSV 다운로드", data=show.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{cls}_{view_exp}_results.csv", mime="text/csv")
    with tab2:
        st.bar_chart(df["accuracy"].round(0).value_counts().sort_index().rename("학생 수"), x_label="정답률(%)", y_label="학생 수")
        all_trials = []
        for _, row in df.iterrows():
            for t in row["trials"]:
                all_trials.append({"문항": t["qid"], "정답": int(t["correct"]), "반응시간(ms)": t["rt_ms"],
                                   "자극": t.get("stimulus", "")})
        if all_trials:
            trials_df = pd.DataFrame(all_trials)
            stats = trials_df.groupby("문항", sort=False).agg(응답수=("정답", "size"), 정답률=("정답", "mean"), 평균반응시간_ms=("반응시간(ms)", "mean")).reset_index()
            stats["정답률"] = (stats["정답률"] * 100).round(1)
            stats["평균반응시간_ms"] = stats["평균반응시간_ms"].round(0)
            st.dataframe(stats, hide_index=True, use_container_width=True)
            if view_exp == "heartflower":
                by_stim = trials_df.groupby("자극").agg(응답수=("정답", "size"), 정답률=("정답", "mean"), 평균반응시간_ms=("반응시간(ms)", "mean"))
                by_stim["정답률"] = (100 * by_stim["정답률"]).round(1)
                st.write("하트/꽃 유형별 통계")
                st.dataframe(by_stim, use_container_width=True)
    with tab3:
        st.info("교수 전용 정답·해설입니다. **학생에게 공개하려면** 화면 상단의 '정답·해설 공개' 버튼을 눌러야 합니다. 이 탭은 교수 화면에서만 표시됩니다.")
        professor_answer_guide(view_exp, df)


def home():
    st.title("🧠 결핍 이론 실습실")
    st.caption("은퇴와 상속설계 · 12·13주차")
    role = st.radio("접속 유형", ["학생", "교수"], horizontal=True)
    if role == "학생":
        active = db().table(T_SESSIONS).select("class_name").eq("is_open", True).execute().data
        active_names = [r["class_name"] for r in active if r["class_name"] in CLASSES]
        if not active_names:
            st.warning("현재 열려 있는 실습이 없습니다. 교수님이 시작하면 다시 접속해 주세요.")
            return
        cls = st.radio("분반", active_names, index=None)
        name = st.text_input("이름 또는 수업에서 정한 별명", max_chars=60)
        if st.button("학생 입장", type="primary"):
            if not cls or not name.strip():
                st.error("분반과 이름(별명)을 입력해 주세요.")
            else:
                name = name.strip()
                db().table(T_STUDENTS).upsert({"class_name":cls, "student_name":name}, on_conflict="class_name,student_name").execute()
                st.session_state.update(role="student", student_class=cls, student_name=name)
                st.rerun()
    else:
        cls = st.selectbox("분반", CLASSES)
        pw = st.text_input("교수 비밀번호", type="password")
        if st.button("교수 통제소 입장", type="primary"):
            configured = st.secrets.get("PROF_PASSWORD", "")
            if not configured:
                st.error("Secrets에 PROF_PASSWORD를 먼저 설정해 주세요.")
            elif pw and pw == configured:
                st.session_state.update(role="professor", prof_class=cls)
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")


def main():
    if st.session_state.get("role") in ("student", "professor"):
        if st.button("← 로그아웃"):
            st.session_state.clear()
            st.rerun()
    if st.session_state.get("role") == "student":
        student_screen()
    elif st.session_state.get("role") == "professor":
        prof_screen()
    else:
        home()

if __name__ == "__main__":
    main()
