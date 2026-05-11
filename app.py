import json
import os
import platform
import subprocess
import base64
import mimetypes
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="Пример рациона со сниженной калорийностью",
    page_icon="🥗",
    layout="wide",
)


DATA_FILE_NAME = "menu 1200 - 2000.json"
MEMO_TEMPLATE_NAME = "Шаблон памятки.html"
MEMO_OUTPUT_NAME = "patient_memo.html"

MEAL_TYPE_MAP = {
    "Офисное меню": "office",
    "Домашнее меню": "home",
    "Перекус в городе": "city_snack",
}

INDICATOR_COLORS = {
    "green": "#4CAF50",
    "yellow": "#F4B400",
    "red": "#DB4437",
}

SEX_OPTIONS = ["Женщина", "Мужчина"]
KCAL_OPTIONS = [1200, 1500, 1800, 2000]
MEAL_TYPE_OPTIONS = ["Офисное меню", "Домашнее меню", "Перекус в городе"]
FIBRAXIN_MESSAGE = (
    "Прием Фибраксина позволяет восполнить дефицит пищевых волокон и "
    "усвояемость железа и поможет легче себя чувствовать на низкокалорийной диете."
)


@st.cache_data
def load_data() -> dict:
    data_path = Path(__file__).parent / "data" / DATA_FILE_NAME
    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_scenario(data: dict, kcal: int, meal_type: str) -> dict | None:
    for scenario in data.get("scenarios", []):
        if scenario.get("kcal") == kcal and scenario.get("meal_type") == meal_type:
            return scenario
    return None


def _memo_meal_lines(items: list[str]) -> str:
    if not items:
        return "—"
    return "\n".join(f"• {x}" for x in items)


def build_patient_memo_html(data: dict, kcal: int) -> str:
    """Подставляет в шаблон меню для всех трёх типов на выбранную калорийность."""
    template_path = Path(__file__).resolve().parent / "data" / MEMO_TEMPLATE_NAME
    html = template_path.read_text(encoding="utf-8")

    # Важно: мы открываем HTML памятки внутри `iframe` через `data:` URL.
    # Поэтому относительные ссылки на изображения (типа `src="упаковка.webp"`)
    # не резолвятся. Инлайним нужные ассеты прямо в HTML как base64.
    data_dir = Path(__file__).resolve().parent / "data"

    def _data_url_from_file(path: Path) -> str:
        mime_type, _ = mimetypes.guess_type(str(path))
        if not mime_type:
            mime_type = "application/octet-stream"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{b64}"

    bg_expected_name = "fibra_section_bg.png"
    bg_path = data_dir / bg_expected_name
    if not bg_path.exists():
        bg_path = next(iter(data_dir.glob("*.png")), None)  # type: ignore[assignment]
    if bg_path and bg_path.exists():
        bg_data_url = _data_url_from_file(bg_path)
        html = html.replace(f'url("{bg_expected_name}")', f'url("{bg_data_url}")')
        html = html.replace(f"url('{bg_expected_name}')", f'url("{bg_data_url}")')

    pack_expected_name = "упаковка.webp"
    pack_path = data_dir / pack_expected_name
    if not pack_path.exists():
        pack_path = next(iter(data_dir.glob("*.webp")), None)  # type: ignore[assignment]
    if pack_path and pack_path.exists():
        pack_data_url = _data_url_from_file(pack_path)
        html = html.replace(f'src="{pack_expected_name}"', f'src="{pack_data_url}"')
        html = html.replace(f"src='{pack_expected_name}'", f'src="{pack_data_url}"')

    subs: dict[str, str] = {"KCAL": str(kcal)}
    for prefix, meal_type in (
        ("OFFICE", "office"),
        ("HOME", "home"),
        ("CITY", "city_snack"),
    ):
        scenario = find_scenario(data, kcal, meal_type)
        if scenario is None:
            for slot in ("BREAKFAST", "LUNCH", "SNACK", "DINNER"):
                subs[f"{prefix}_{slot}"] = "—"
            continue
        meals = scenario["meals"]
        subs[f"{prefix}_BREAKFAST"] = _memo_meal_lines(meals.get("breakfast", []))
        subs[f"{prefix}_LUNCH"] = _memo_meal_lines(meals.get("lunch", []))
        subs[f"{prefix}_SNACK"] = _memo_meal_lines(meals.get("snack", []))
        subs[f"{prefix}_DINNER"] = _memo_meal_lines(meals.get("dinner", []))
    for key, value in subs.items():
        html = html.replace("{{" + key + "}}", value)
    return html


def open_html_file_default(html_path: Path) -> None:
    """Открывает локальный HTML в приложении по умолчанию (надёжнее, чем webbrowser + file://)."""
    path = html_path.resolve()
    try:
        if platform.system() == "Windows":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            subprocess.run(["open", str(path)], check=False, timeout=30)
        else:
            subprocess.run(["xdg-open", str(path)], check=False, timeout=30)
    except OSError:
        pass


@st.dialog("Памятка для пациента")
def patient_memo_dialog(memo_html: str) -> None:
    """Открывает памятку поверх интерфейса (оверлей) и корректно закрывается кнопкой в UI."""
    # В `st.dialog` контейнер может быть уже по умолчанию, поэтому принудительно
    # задаём ширину компонента, чтобы HTML памятки не превращался в "узкую ленту".
    st.components.v1.html(memo_html, width=1100, height=900, scrolling=True)
    st.download_button(
        "Скачать памятку (HTML)",
        data=memo_html.encode("utf-8"),
        file_name=MEMO_OUTPUT_NAME,
        mime="text/html",
        use_container_width=True,
    )


def render_intake_item(name: str, percent: int, indicator: str) -> None:
    color = INDICATOR_COLORS.get(indicator, "#9CA3AF")
    st.markdown(
        f"""
        <div style="margin-bottom:12px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:2px;">
                <span style="font-weight:600; color:#111827;">{name}</span>
                <span style="display:flex; align-items:center; gap:10px; font-weight:700; color:#111827; font-size:1.4rem;">
                    {percent}%
                    <span style="
                        width:12px;
                        height:12px;
                        border-radius:50%;
                        display:inline-block;
                        background:{color};
                    "></span>
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


st.markdown(
    """
    <style>
    .block-container {
        max-width: 1100px;
        padding-top: 1.2rem;
        padding-bottom: 2rem;
    }
    .section-title {
        margin-top: 0.1rem;
        margin-bottom: 0.5rem;
    }
    .intake-vertical-center {
        display: flex;
        flex-direction: column;
        justify-content: center;
        gap: 8px;
    }
    .memo-btn-wrap {
        margin-top: 14px;
    }
    .memo-btn-wrap .stButton > button {
        font-weight: 700;
        font-size: 1rem;
        padding: 0.62rem 1.2rem;
        border-radius: 12px;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.18);
        width: 100%;
    }
    .summary-box {
        background: #e8f2ff;
        border: 1px solid #bfdbfe;
        border-radius: 10px;
        padding: 14px 16px;
        color: #0f172a;
        font-size: 1.08rem;
        line-height: 1.55;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Пример рациона со сниженной калорийностью")

data = load_data()

if "applied_sex" not in st.session_state:
    st.session_state.applied_sex = "Женщина"
if "applied_kcal" not in st.session_state:
    st.session_state.applied_kcal = 1500
if "applied_meal_type" not in st.session_state:
    st.session_state.applied_meal_type = "office"
if "show_result" not in st.session_state:
    st.session_state.show_result = False
with st.container():
    st.markdown("<h3 class='section-title'>Параметры</h3>", unsafe_allow_html=True)
    input_col1, input_col2, input_col3, input_col4 = st.columns([1.0, 1.0, 1.2, 0.8])

    with input_col1:
        selected_sex = st.radio(
            "Пол",
            options=SEX_OPTIONS,
            index=SEX_OPTIONS.index(st.session_state.applied_sex),
            horizontal=True,
        )

    with input_col2:
        kcal_label_options = [f"{k} ккал" for k in KCAL_OPTIONS]
        selected_kcal_label = st.selectbox(
            "Дневная калорийность",
            kcal_label_options,
            index=KCAL_OPTIONS.index(st.session_state.applied_kcal),
        )
        selected_kcal = int(selected_kcal_label.split()[0])

    with input_col3:
        default_meal_type_label = next(
            label for label, value in MEAL_TYPE_MAP.items() if value == st.session_state.applied_meal_type
        )
        selected_meal_type_label = st.selectbox(
            "Тип питания",
            MEAL_TYPE_OPTIONS,
            index=MEAL_TYPE_OPTIONS.index(default_meal_type_label),
        )
        selected_meal_type = MEAL_TYPE_MAP[selected_meal_type_label]

    with input_col4:
        st.write("")
        st.write("")
        show_button = st.button("Показать рацион", type="primary", use_container_width=True)

if show_button:
    st.session_state.applied_sex = selected_sex
    st.session_state.applied_kcal = selected_kcal
    st.session_state.applied_meal_type = selected_meal_type
    st.session_state.show_result = True

if st.session_state.show_result:
    scenario = find_scenario(
        data,
        st.session_state.applied_kcal,
        st.session_state.applied_meal_type,
    )

    if scenario is None:
        st.error("Сценарий с такими параметрами не найден.")
    else:
        sex_key = "female" if st.session_state.applied_sex == "Женщина" else "male"
        deficits = scenario["deficits"]

        left_col, right_col = st.columns([1.2, 1])

        with left_col:
            with st.container(border=True):
                st.subheader("Примерное меню на день")
                st.markdown(f"**Калорийность:** {st.session_state.applied_kcal} ккал")

                st.markdown("**Завтрак**")
                for item in scenario["meals"]["breakfast"]:
                    st.markdown(f"- {item}")

                st.markdown("**Обед**")
                for item in scenario["meals"]["lunch"]:
                    st.markdown(f"- {item}")

                st.markdown("**Перекус**")
                for item in scenario["meals"]["snack"]:
                    st.markdown(f"- {item}")

                st.markdown("**Ужин**")
                for item in scenario["meals"]["dinner"]:
                    st.markdown(f"- {item}")

        with right_col:
            with st.container(border=True):
                st.subheader("Дефицит микронутриентов")
                st.markdown("Поступление микронутриентов - % от суточной нормы")
                fiber_percent = deficits["fiber"][f"{sex_key}_percent"]
                fiber_indicator = deficits["fiber"][f"{sex_key}_indicator"]
                iron_percent = deficits["iron"][f"{sex_key}_percent"]
                iron_indicator = deficits["iron"][f"{sex_key}_indicator"]

                st.markdown('<div class="intake-vertical-center">', unsafe_allow_html=True)
                render_intake_item("Пищевые волокна", fiber_percent, fiber_indicator)
                render_intake_item("Железо", iron_percent, iron_indicator)
                st.markdown("</div>", unsafe_allow_html=True)

            with st.container(border=True):
                summary_text = scenario["summary"][sex_key]
                main_summary_text = summary_text.replace(FIBRAXIN_MESSAGE, "").strip()
                if main_summary_text.endswith("."):
                    main_summary_text = main_summary_text[:-1].strip()
                st.markdown(
                    f"<div class='summary-box'>{main_summary_text}.</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<div class='summary-box' style='margin-top:10px;'>{FIBRAXIN_MESSAGE}</div>",
                    unsafe_allow_html=True,
                )

            st.markdown('<div class="memo-btn-wrap">', unsafe_allow_html=True)
            memo_clicked = st.button("Памятка для пациента", type="primary", key="memo_patient")
            st.markdown("</div>", unsafe_allow_html=True)

            if memo_clicked:
                kcal = st.session_state.applied_kcal
                memo_html = build_patient_memo_html(data, kcal)
                patient_memo_dialog(memo_html)
