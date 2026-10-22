"""Student Performance Analyzer - single-file Streamlit app.

Data lives in st.session_state only (no database). Marks, passing rules and the
grading scale are configurable EXAMPLE settings, not universal academic rules.
"""
import math
import random

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Student Performance Analyzer", page_icon="🎓", layout="wide")
st.markdown(
    """<style>
    [data-testid="stMetric"]{background:rgba(128,128,128,.08);border:1px solid rgba(128,128,128,.25);
    padding:12px 16px;border-radius:10px}
    .block-container{padding-top:2rem}
    </style>""",
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------- constants
ID_COL, NAME_COL, CLASS_COL, SECTION_COL, ROLL_COL = "Student ID", "Full Name", "Class", "Section", "Roll Number"
INFO_COLS = [ID_COL, NAME_COL, CLASS_COL, SECTION_COL, ROLL_COL]
DEFAULT_SUBJECTS = ["Mathematics", "Physics", "Computer Science", "English", "Urdu"]
DEFAULT_MAX_MARKS = 100
DEFAULT_PASS_MARK = 50
DEFAULT_GRADES = [("A+", 90.0), ("A", 80.0), ("B", 70.0), ("C", 60.0), ("D", 50.0)]  # below the lowest -> F
FAIL_SUBJECT_COUNT = 3  # failing this many subjects (or more) -> "Fail"; 1-2 -> "Needs Improvement"
STRONG_PCT, WEAK_PCT = 80.0, 60.0
RESULT_COLORS = {"Pass": "#2e9e5b", "Needs Improvement": "#f0a030", "Fail": "#d64545", "No Marks": "#999999"}
STAT_COLS = ["Total Obtained", "Total Possible", "Percentage", "Grade", "Rank", "Failed Subjects",
             "Failed Subject Names", "Result"]
FIRST_NAMES = ["Ayesha", "Bilal", "Hira", "Usman", "Zainab", "Hamza", "Maryam", "Ali", "Fatima", "Omar",
               "Sana", "Daniyal", "Iqra", "Saad", "Noor", "Taha", "Laiba", "Hassan", "Mahnoor", "Zain"]
LAST_NAMES = ["Khan", "Ahmed", "Malik", "Hussain", "Raza", "Sheikh", "Qureshi", "Butt", "Iqbal", "Siddiqui"]


# ------------------------------------------------------------- core logic
def default_config():
    return {
        "subjects": {s: {"max": DEFAULT_MAX_MARKS, "pass": DEFAULT_PASS_MARK} for s in DEFAULT_SUBJECTS},
        "grades": list(DEFAULT_GRADES),
    }


def grade_for(percentage, grades):
    """Return the grade whose minimum percentage is the highest one not above `percentage`."""
    for grade, minimum in sorted(grades, key=lambda g: -g[1]):
        if percentage >= minimum:
            return grade
    return "F"


def grade_order(config):
    return [g for g, _ in sorted(config["grades"], key=lambda g: -g[1])] + ["F"]


def result_status(failed_count):
    if failed_count == 0:
        return "Pass"
    return "Needs Improvement" if failed_count < FAIL_SUBJECT_COUNT else "Fail"


def analyze(raw, config):
    """Add totals, percentage, grade, class rank, failed subjects and result to raw marks."""
    subjects = list(config["subjects"])
    columns = INFO_COLS + subjects + STAT_COLS
    if raw is None or raw.empty:
        return pd.DataFrame(columns=columns)
    df = raw.copy()
    for s in subjects:
        df[s] = pd.to_numeric(df[s], errors="coerce") if s in df.columns else float("nan")
    marks = df[subjects]
    max_marks = pd.Series({s: float(config["subjects"][s]["max"]) for s in subjects})
    pass_marks = pd.Series({s: float(config["subjects"][s]["pass"]) for s in subjects})
    # Blank marks = subject not taken: excluded from both obtained and possible totals.
    df["Total Obtained"] = marks.sum(axis=1, skipna=True)
    df["Total Possible"] = marks.notna().mul(max_marks, axis=1).sum(axis=1)
    has_marks = df["Total Possible"] > 0
    percentage = (df["Total Obtained"] / df["Total Possible"].where(has_marks) * 100).fillna(0.0)
    df["Percentage"] = percentage.round(2)  # grade and rank both use the 2-decimal value
    df["Grade"] = [grade_for(p, config["grades"]) if ok else "N/A" for p, ok in zip(df["Percentage"], has_marks)]
    failed = marks.notna() & marks.lt(pass_marks, axis=1)
    df["Failed Subjects"] = failed.sum(axis=1)
    df["Failed Subject Names"] = failed.apply(lambda r: ", ".join(r.index[r]), axis=1)
    df["Result"] = [result_status(n) if ok else "No Marks" for n, ok in zip(df["Failed Subjects"], has_marks)]
    ranks = df[has_marks].groupby(CLASS_COL)["Percentage"].rank(method="min", ascending=False)
    df["Rank"] = ranks.reindex(df.index).astype("Int64")  # tied percentages share a rank
    return df[columns].reset_index(drop=True)


def subject_statistics(df, config):
    rows = []
    for s, c in config["subjects"].items():
        values = pd.to_numeric(df[s], errors="coerce").dropna() if (not df.empty and s in df) else pd.Series(dtype=float)
        if values.empty:
            rows.append({"Subject": s, "Maximum": c["max"], "Pass Mark": c["pass"], "Average": None,
                         "Average %": None, "Highest": None, "Lowest": None, "Pass Rate %": None})
        else:
            rows.append({"Subject": s, "Maximum": c["max"], "Pass Mark": c["pass"],
                         "Average": round(values.mean(), 2), "Average %": round(values.mean() / c["max"] * 100, 2),
                         "Highest": values.max(), "Lowest": values.min(),
                         "Pass Rate %": round((values >= c["pass"]).mean() * 100, 2)})
    return pd.DataFrame(rows)


def class_summary(df):
    columns = [CLASS_COL, "Students", "Average %", "Highest %", "Lowest %", "Pass Rate %", "Top Student"]
    rows = []
    for cls, group in df.groupby(CLASS_COL):
        graded = group[group["Total Possible"] > 0]
        row = {CLASS_COL: cls, "Students": len(group)}
        if not graded.empty:
            best = graded["Percentage"].max()
            row.update({"Average %": round(graded["Percentage"].mean(), 2), "Highest %": best,
                        "Lowest %": graded["Percentage"].min(),
                        "Pass Rate %": round((graded["Result"] == "Pass").mean() * 100, 2),
                        "Top Student": ", ".join(graded.loc[graded["Percentage"] == best, NAME_COL])})
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def student_insights(student, class_df, config):
    """Transparent rule-based strengths/weaknesses and suggestions for one student."""
    stats = subject_statistics(class_df, config).set_index("Subject")
    rows, tips = [], []
    for s, c in config["subjects"].items():
        mark = student[s]
        if pd.isna(mark):
            continue
        pct = mark / c["max"] * 100
        class_avg = stats.at[s, "Average %"]
        if mark < c["pass"]:
            status = "Below pass mark"
            tips.append(f"**{s}**: {mark:g} is below the pass mark of {c['pass']:g}. Gain at least "
                        f"{c['pass'] - mark:g} more marks - revise core topics, redo class exercises and ask your teacher for help.")
        elif pct < WEAK_PCT:
            status = "Needs work"
            tips.append(f"**{s}**: passed but under {WEAK_PCT:.0f}%. Practise past questions weekly and review mistakes.")
        elif pct >= STRONG_PCT:
            status = "Strong"
        else:
            status = "Good"
        if status in ("Good", "Strong") and pd.notna(class_avg) and pct < class_avg - 10:
            tips.append(f"**{s}** is more than 10 points below the class average; a little extra revision would help.")
        rows.append({"Subject": s, "Marks": mark, "Maximum": c["max"], "Pass Mark": c["pass"],
                     "Percentage": round(pct, 2), "Class Average %": class_avg, "Status": status})
    detail = pd.DataFrame(rows, columns=["Subject", "Marks", "Maximum", "Pass Mark", "Percentage",
                                         "Class Average %", "Status"])
    if not detail.empty:
        strong = detail.loc[detail["Status"] == "Strong", "Subject"].tolist()
        if strong:
            tips.append("Keep up the strong work in " + ", ".join(strong) + ".")
        if not tips:
            weakest = detail.loc[detail["Percentage"].idxmin(), "Subject"]
            tips.append(f"Balanced performance. To improve further, give a little more time to {weakest}.")
    return detail, tips


def lowest_subjects(student, config, count=2):
    scored = [(student[s] / c["max"], s) for s, c in config["subjects"].items() if pd.notna(student[s])]
    return ", ".join(s for _, s in sorted(scored)[:count])


# -------------------------------------------------------------- validation
def normalise_name(text):
    return " ".join(str(text).replace("_", " ").strip().lower().split())


def clean_text(value):
    return "" if pd.isna(value) else str(value).strip()


def check_mark(value, subject, maximum):
    if value < 0:
        return f"{subject} marks cannot be negative ({value:g})"
    if value > maximum:
        return f"{subject} marks {value:g} exceed the maximum of {maximum:g}"
    return None


def existing_keys(raw):
    return {(clean_text(c).lower(), clean_text(i).lower()) for c, i in zip(raw[CLASS_COL], raw[ID_COL])}


def validate_records(incoming, config, known_keys=None, show_row_numbers=True):
    """Return (valid_rows_df, error_messages, warning_messages). Bad rows are skipped, never guessed."""
    errors, warnings = [], []
    subjects = config["subjects"]
    empty = pd.DataFrame(columns=INFO_COLS + list(subjects))
    aliases = {normalise_name(c): c for c in INFO_COLS + list(subjects)}
    aliases.update({"id": ID_COL, "name": NAME_COL, "student name": NAME_COL, "roll": ROLL_COL, "roll no": ROLL_COL})
    df = incoming.rename(columns={c: aliases[normalise_name(c)] for c in incoming.columns if normalise_name(c) in aliases})
    df = df.loc[:, ~df.columns.duplicated()]
    missing = [c for c in INFO_COLS if c not in df.columns]
    if missing:
        return empty, ["Missing required column(s): " + ", ".join(missing) + ". See the CSV format on this page."], warnings
    present = [s for s in subjects if s in df.columns]
    if not present:
        return empty, ["No subject columns found. Expected at least one of: " + ", ".join(subjects) + "."], warnings
    absent = [s for s in subjects if s not in present]
    if absent:
        warnings.append("No column found for " + ", ".join(absent) + " - those marks are left blank (treated as not taken).")
    unknown = [c for c in df.columns if c not in INFO_COLS and c not in subjects]
    if unknown:
        warnings.append("Ignored unrecognised column(s): " + ", ".join(map(str, unknown)) + ".")
    if df.empty:
        return empty, ["The file has no data rows."], warnings
    seen = set(known_keys or [])
    valid = []
    for position, (_, row) in enumerate(df.iterrows()):
        prefix = f"Row {position + 2}: " if show_row_numbers else ""  # +2 = header line + 1-based
        record = {c: clean_text(row[c]) for c in INFO_COLS}
        problems = [f"{c} is empty" for c in (ID_COL, NAME_COL, CLASS_COL) if not record[c]]
        record[SECTION_COL] = record[SECTION_COL] or "-"
        for s in present:
            text = clean_text(row[s])
            if text == "":
                record[s] = float("nan")
                continue
            try:
                value = float(text)
            except ValueError:
                problems.append(f"{s} marks '{text}' is not a number")
                continue
            if not math.isfinite(value):
                problems.append(f"{s} marks '{text}' is not a valid number")
                continue
            message = check_mark(value, s, subjects[s]["max"])
            if message:
                problems.append(message)
            record[s] = value
        key = (record[CLASS_COL].lower(), record[ID_COL].lower())
        if record[ID_COL] and record[CLASS_COL] and key in seen:
            problems.append(f"Student ID '{record[ID_COL]}' already exists in class '{record[CLASS_COL]}'")
        if problems:
            errors.append(prefix + "; ".join(problems) + ".")
            continue
        seen.add(key)
        valid.append(record)
    out = pd.DataFrame(valid, columns=INFO_COLS + present).reindex(columns=INFO_COLS + list(subjects))
    return out, errors, warnings


def validate_settings(editor_df, grades, raw):
    errors, subjects = [], {}
    for _, row in editor_df.iterrows():
        name = clean_text(row.get("Subject"))
        maximum, pass_mark = pd.to_numeric(row.get("Maximum Marks"), errors="coerce"), pd.to_numeric(row.get("Pass Mark"), errors="coerce")
        if not name:
            errors.append("Every subject needs a name (delete empty rows).")
        elif name in subjects:
            errors.append(f"Duplicate subject name: {name}.")
        elif pd.isna(maximum) or maximum <= 0:
            errors.append(f"{name}: maximum marks must be a positive number.")
        elif pd.isna(pass_mark) or not 0 <= pass_mark <= maximum:
            errors.append(f"{name}: pass mark must be between 0 and the maximum marks.")
        else:
            subjects[name] = {"max": float(maximum), "pass": float(pass_mark)}
            if name in raw.columns and (pd.to_numeric(raw[name], errors="coerce") > maximum).any():
                errors.append(f"{name}: existing marks exceed the new maximum ({maximum:g}). Fix those marks first.")
    if not subjects and not errors:
        errors.append("At least one subject is required.")
    minimums = [m for _, m in grades]
    if any(a <= b for a, b in zip(minimums, minimums[1:])):
        errors.append("Grade minimums must strictly decrease from A+ down to D.")
    return errors, {"subjects": subjects, "grades": grades}


def run_self_tests():
    """Built-in checks of key calculations; returns a list of (check, passed)."""
    results = []

    def check(label, condition):
        results.append((label, bool(condition)))

    try:
        cfg = {"subjects": {"Maths": {"max": 100, "pass": 50}, "Science": {"max": 50, "pass": 25},
                            "Art": {"max": 20, "pass": 10}}, "grades": list(DEFAULT_GRADES)}
        nan = float("nan")
        base = lambda sid, name, cls, m, s, a: {ID_COL: sid, NAME_COL: name, CLASS_COL: cls, SECTION_COL: "A",
                                               ROLL_COL: sid, "Maths": m, "Science": s, "Art": a}
        raw = pd.DataFrame([base("1", "Ann", "X", 90, 45, 18), base("2", "Bob", "X", 50, 25, 10),
                            base("3", "Cara", "X", 49, 25, 10), base("4", "Dan", "X", 60, 15, 10),
                            base("5", "Eve", "Y", 80, 40, nan), base("6", "Fay", "Y", 10, 5, 2)])
        r = analyze(raw, cfg).set_index(NAME_COL)
        check("Totals handle different maximum marks (Ann 153/170)", r.at["Ann", "Total Obtained"] == 153 and r.at["Ann", "Total Possible"] == 170)
        check("Percentage rounds to 2 decimals (Cara 49.41)", r.at["Cara", "Percentage"] == 49.41)
        check("Blank mark excluded from total possible (Eve 120/150)", r.at["Eve", "Total Possible"] == 150 and r.at["Eve", "Percentage"] == 80.0)
        for pct, expected in [(100, "A+"), (90, "A+"), (89.99, "A"), (80, "A"), (79.99, "B"), (70, "B"), (69.99, "C"),
                              (60, "C"), (59.99, "D"), (50, "D"), (49.99, "F"), (0, "F")]:
            check(f"Grade boundary {pct}% -> {expected}", grade_for(pct, DEFAULT_GRADES) == expected)
        check("Exactly the pass mark counts as passing (Bob)", r.at["Bob", "Result"] == "Pass")
        check("One failed subject -> Needs Improvement (Cara)", r.at["Cara", "Result"] == "Needs Improvement")
        check("Three failed subjects -> Fail (Fay)", r.at["Fay", "Result"] == "Fail")
        check("Passing overall % but failing a subject is not Pass (Dan)", r.at["Dan", "Percentage"] == 50.0 and r.at["Dan", "Result"] != "Pass")
        check("Tied percentages share a rank (Bob & Dan = 2, next = 4)", r.at["Bob", "Rank"] == 2 and r.at["Dan", "Rank"] == 2 and r.at["Cara", "Rank"] == 4)
        check("Ranks are per class (Eve = 1 in class Y)", r.at["Eve", "Rank"] == 1 and r.at["Fay", "Rank"] == 2)
        check("Empty dataset analyses without error", analyze(raw.iloc[0:0], cfg).empty)
        sub = {"subjects": {"Maths": {"max": 100, "pass": 50}}, "grades": DEFAULT_GRADES}
        frame = lambda rows: pd.DataFrame(rows, columns=INFO_COLS + ["Maths"], dtype=str)
        ok, err, _ = validate_records(frame([["1", "A", "X", "A", "1", "50"]]), sub)
        check("Valid row accepted", len(ok) == 1 and not err)
        check("Negative marks rejected", validate_records(frame([["1", "A", "X", "A", "1", "-1"]]), sub)[1] != [])
        check("Marks above maximum rejected", validate_records(frame([["1", "A", "X", "A", "1", "101"]]), sub)[1] != [])
        check("Non-numeric marks rejected", validate_records(frame([["1", "A", "X", "A", "1", "abc"]]), sub)[1] != [])
        check("Duplicate ID in same class rejected", len(validate_records(frame([["1", "A", "X", "A", "1", "5"], ["1", "B", "X", "A", "2", "6"]]), sub)[0]) == 1)
        check("Same ID in a different class allowed", len(validate_records(frame([["1", "A", "X", "A", "1", "5"], ["1", "B", "Y", "A", "2", "6"]]), sub)[0]) == 2)
        check("Missing required column handled", validate_records(pd.DataFrame({"Maths": ["5"]}), sub)[1] != [])
    except Exception as exc:  # a crash is itself a failed check
        check(f"Self-tests crashed: {exc}", False)
    return results


# ------------------------------------------------------------ data helpers
def sample_data(config):
    rng = random.Random(2024)
    rows, number = [], 1
    for cls, section, count in [("Grade 8", "A", 6), ("Grade 9", "A", 6), ("Grade 9", "B", 6), ("Grade 10", "A", 6)]:
        for roll in range(1, count + 1):
            row = {ID_COL: f"S{number:03d}", NAME_COL: f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                   CLASS_COL: cls, SECTION_COL: section, ROLL_COL: str(roll)}
            ability = rng.gauss(68, 15)
            for s, c in config["subjects"].items():
                row[s] = round(min(max(rng.gauss(ability, 10), 0), 100) * c["max"] / 100 * 2) / 2
            rows.append(row)
            number += 1
    return pd.DataFrame(rows)


def init_state():
    if "config" not in st.session_state:
        st.session_state.config = default_config()
    if "raw" not in st.session_state:
        st.session_state.raw = sample_data(st.session_state.config)


def to_csv(df):
    return df.to_csv(index=False).encode("utf-8")


def filter_controls(df, key, with_section=True):
    classes = sorted(df[CLASS_COL].unique()) if not df.empty else []
    left, right = st.columns(2)
    chosen = left.selectbox("Class", ["All classes"] + classes, key=f"{key}_class", help="Show one class or all classes.")
    view = df if chosen == "All classes" else df[df[CLASS_COL] == chosen]
    if with_section:
        sections = sorted(view[SECTION_COL].unique()) if not view.empty else []
        picked = right.multiselect("Section (empty = all)", sections, key=f"{key}_sec_{chosen}")
        if picked:
            view = view[view[SECTION_COL].isin(picked)]
    return view


def student_picker(df, key):
    pos = st.selectbox("Student", list(df.index), key=key,
                       format_func=lambda i: f"{df.at[i, NAME_COL]} · {df.at[i, ID_COL]} · {df.at[i, CLASS_COL]}-{df.at[i, SECTION_COL]}")
    return df.loc[pos]


def show_table(df):
    st.dataframe(df, hide_index=True, use_container_width=True,
                 column_config={"Percentage": st.column_config.NumberColumn(format="%.2f")})


def show_messages(errors, warnings, limit=30):
    for w in warnings:
        st.warning(w)
    if errors:
        with st.expander(f"{len(errors)} problem(s) found - affected rows were skipped", expanded=True):
            for e in errors[:limit]:
                st.error(e)
            if len(errors) > limit:
                st.caption(f"...and {len(errors) - limit} more.")


# ------------------------------------------------------------------ charts
def chart_subject_averages(df, config):
    stats = subject_statistics(df, config).dropna(subset=["Average %"])
    fig = px.bar(stats, x="Subject", y="Average %", text_auto=".1f", range_y=[0, 100],
                 hover_data=["Average", "Maximum", "Pass Rate %"], title="Class average by subject (% of maximum)")
    return fig.update_layout(template="plotly_white")


def chart_grades(df, config):
    counts = df["Grade"].value_counts().reindex(grade_order(config), fill_value=0)
    fig = px.bar(x=counts.index, y=counts.values, labels={"x": "Grade", "y": "Students"}, text=counts.values,
                 title="Grade distribution")
    return fig.update_layout(template="plotly_white")


def chart_results(df):
    counts = df["Result"].value_counts()
    fig = px.pie(names=counts.index, values=counts.values, hole=0.4, color=counts.index,
                 color_discrete_map=RESULT_COLORS, title="Pass / fail distribution")
    return fig.update_layout(template="plotly_white")


def chart_students(df):
    ordered = df.sort_values("Percentage", ascending=False)
    fig = px.bar(ordered, x=NAME_COL, y="Percentage", color="Result", color_discrete_map=RESULT_COLORS,
                 range_y=[0, 100], hover_data=[CLASS_COL, "Grade", "Rank"], title="Student performance comparison")
    return fig.update_layout(template="plotly_white", xaxis_title="")


def chart_classes(summary):
    long = summary.melt(id_vars=CLASS_COL, value_vars=["Average %", "Pass Rate %"], var_name="Measure", value_name="Percent")
    fig = px.bar(long, x=CLASS_COL, y="Percent", color="Measure", barmode="group", range_y=[0, 100],
                 text_auto=".1f", title="Class comparison")
    return fig.update_layout(template="plotly_white")


def chart_individual(detail):
    long = detail.melt(id_vars="Subject", value_vars=["Percentage", "Class Average %"], var_name="Measure", value_name="Percent")
    long["Measure"] = long["Measure"].replace({"Percentage": "Student %"})
    fig = px.bar(long, x="Subject", y="Percent", color="Measure", barmode="group", range_y=[0, 100],
                 text_auto=".1f", title="Student vs class average (% of maximum)")
    return fig.update_layout(template="plotly_white")


def plot(fig):
    st.plotly_chart(fig, use_container_width=True)


# ------------------------------------------------------------------- pages
def page_dashboard(analyzed, config):
    st.header("📊 Dashboard")
    if analyzed.empty:
        st.info("No student data yet. Add students or upload a CSV under **Manage Data**.")
        return
    view = filter_controls(analyzed, "dash")
    graded = view[view["Total Possible"] > 0]
    if graded.empty:
        st.info("No students with marks match the selected filters.")
        return
    best = graded["Percentage"].max()
    names = graded.loc[graded["Percentage"] == best, NAME_COL].tolist()
    top = ", ".join(names[:2]) + (f" +{len(names) - 2} more" if len(names) > 2 else "")
    a, b, c = st.columns(3)
    a.metric("Total students", len(view))
    b.metric("Class average %", f"{graded['Percentage'].mean():.2f}%", help="Mean of student percentages.")
    c.metric("Overall pass rate", f"{(graded['Result'] == 'Pass').mean() * 100:.1f}%",
             help="Share of students who passed EVERY subject.")
    d, e, f = st.columns(3)
    d.metric("Highest %", f"{best:.2f}%")
    e.metric("Lowest %", f"{graded['Percentage'].min():.2f}%")
    f.metric("Top performer", top, f"{best:.2f}%", delta_color="off")
    left, right = st.columns(2)
    with left:
        plot(chart_grades(graded, config))
    with right:
        plot(chart_results(graded))
    plot(chart_subject_averages(view, config))
    plot(chart_students(graded))


def page_marks_sheet(analyzed, config):
    st.header("📋 Marks Sheet")
    if analyzed.empty:
        st.info("No student data yet.")
        return
    view = filter_controls(analyzed, "sheet")
    c1, c2, c3 = st.columns([2, 2, 1])
    search = c1.text_input("Search", placeholder="Name, ID or roll number", help="Case-insensitive match.")
    results = c2.multiselect("Result status (empty = all)", ["Pass", "Needs Improvement", "Fail", "No Marks"])
    ascending = c3.checkbox("Ascending", value=False)
    sort_by = st.selectbox("Sort by", list(view.columns), index=list(view.columns).index("Rank"),
                           help="You can also click any column header in the table to sort.")
    if search.strip():
        text = search.strip()
        mask = pd.Series(False, index=view.index)
        for col in (NAME_COL, ID_COL, ROLL_COL):
            mask |= view[col].astype(str).str.contains(text, case=False, regex=False)
        view = view[mask]
    if results:
        view = view[view["Result"].isin(results)]
    st.caption(f"{len(view)} student(s) shown")
    show_table(view.sort_values(sort_by, ascending=ascending, kind="stable"))


def page_student(analyzed, config):
    st.header("🧑‍🎓 Student Details")
    if analyzed.empty:
        st.info("No student data yet.")
        return
    pool = filter_controls(analyzed, "stu", with_section=False)
    if pool.empty:
        st.info("No students in this class.")
        return
    student = student_picker(pool, "stu_pick")
    class_df = analyzed[analyzed[CLASS_COL] == student[CLASS_COL]]
    ranked = int((class_df["Total Possible"] > 0).sum())
    st.subheader(f"{student[NAME_COL]}  ·  {student[CLASS_COL]}-{student[SECTION_COL]}")
    a, b, c, d = st.columns(4)
    a.metric("Marks", f"{student['Total Obtained']:g} / {student['Total Possible']:g}")
    b.metric("Percentage", f"{student['Percentage']:.2f}%")
    c.metric("Grade", student["Grade"])
    d.metric("Class rank", "-" if pd.isna(student["Rank"]) else f"{student['Rank']} of {ranked}")
    st.markdown(f"**Result:** {student['Result']}" + (f" - below pass mark in: {student['Failed Subject Names']}" if student["Failed Subject Names"] else ""))
    detail, tips = student_insights(student, class_df, config)
    if detail.empty:
        st.warning("This student has no marks entered.")
        return
    plot(chart_individual(detail))
    show_table(detail)
    left, right = st.columns(2)
    left.success("**Strengths:** " + (", ".join(detail.loc[detail["Status"] == "Strong", "Subject"]) or "none above " + f"{STRONG_PCT:.0f}% yet"))
    weak = detail.loc[detail["Status"].isin(["Below pass mark", "Needs work"]), "Subject"]
    right.warning("**Weaknesses:** " + (", ".join(weak) or "none"))
    st.subheader("Improvement suggestions")
    for tip in tips:
        st.markdown("- " + tip)


def page_class_analysis(analyzed, config):
    st.header("🏫 Class Analysis")
    if analyzed.empty:
        st.info("No student data yet.")
        return
    view = filter_controls(analyzed, "cls")
    graded = view[view["Total Possible"] > 0]
    if graded.empty:
        st.info("No students with marks match the selected filters.")
        return
    stats = subject_statistics(view, config)
    show_table(stats)
    valid = stats.dropna(subset=["Average %"])
    if not valid.empty:
        strongest, weakest = valid.loc[valid["Average %"].idxmax()], valid.loc[valid["Average %"].idxmin()]
        a, b = st.columns(2)
        a.success(f"**Strongest subject:** {strongest['Subject']} ({strongest['Average %']:.1f}% average)")
        b.error(f"**Weakest subject:** {weakest['Subject']} ({weakest['Average %']:.1f}% average)")
        st.info(f"Recommendation: schedule extra revision or practice sessions for **{weakest['Subject']}**, "
                f"and review what is working in **{strongest['Subject']}**.")
    plot(chart_subject_averages(view, config))
    plot(chart_students(graded))
    summary = class_summary(analyzed)
    st.subheader("Class comparison (all classes)")
    show_table(summary)
    if summary["Average %"].notna().any():
        plot(chart_classes(summary.dropna(subset=["Average %"])))
    st.subheader("Students below the passing threshold")
    flagged = graded[graded["Failed Subjects"] > 0].copy()
    if flagged.empty:
        st.success("No student is below the pass mark in any subject.")
    else:
        flagged["Study Focus (lowest-scoring subjects)"] = flagged.apply(lambda r: lowest_subjects(r, config), axis=1)
        show_table(flagged[[ID_COL, NAME_COL, CLASS_COL, SECTION_COL, "Percentage", "Result", "Failed Subject Names",
                            "Study Focus (lowest-scoring subjects)"]])
        st.caption("Practical advice: revise the lowest-scoring subjects first, 30-45 minutes daily, with past questions and teacher feedback.")


def page_manage(analyzed, config):
    st.header("✏️ Manage Data")
    st.warning("Data is kept in Streamlit **session state** only - there is no database. It is lost when the session "
               "resets or the app restarts. Download your reports (Reports page) to keep results.")
    raw, subjects = st.session_state.raw, config["subjects"]
    tab_add, tab_update, tab_upload, tab_other = st.tabs(["Add student", "Update marks", "Upload CSV", "Other"])

    with tab_add:
        with st.form("add_student"):
            c1, c2 = st.columns(2)
            sid, name = c1.text_input("Student ID *"), c2.text_input("Full name *")
            cls, section = c1.text_input("Class *", help="e.g. Grade 9"), c2.text_input("Section")
            roll = c1.text_input("Roll number")
            st.markdown("**Marks**")
            cols, marks = st.columns(3), {}
            for i, (s, c) in enumerate(subjects.items()):
                marks[s] = cols[i % 3].number_input(f"{s} (max {c['max']:g})", 0.0, float(c["max"]), 0.0, 0.5,
                                                    key=f"add_{s}_{c['max']}")
            blanks = st.multiselect("Subjects not taken (leave blank)", list(subjects))
            if st.form_submit_button("Add student", type="primary"):
                record = {ID_COL: sid, NAME_COL: name, CLASS_COL: cls, SECTION_COL: section, ROLL_COL: roll}
                record.update({s: ("" if s in blanks else str(v)) for s, v in marks.items()})
                new, errors, _ = validate_records(pd.DataFrame([record]), config, existing_keys(raw), False)
                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    st.session_state.raw = pd.concat([raw, new], ignore_index=True)
                    st.success(f"Added {name.strip()} to {cls.strip()}.")

    with tab_update:
        if raw.empty:
            st.info("No students to update.")
        else:
            idx = st.selectbox("Student", list(raw.index), key="upd_pick",
                               format_func=lambda i: f"{raw.at[i, NAME_COL]} · {raw.at[i, ID_COL]} · {raw.at[i, CLASS_COL]}-{raw.at[i, SECTION_COL]}")
            with st.form("update_marks"):
                cols, new_marks = st.columns(3), {}
                for i, (s, c) in enumerate(subjects.items()):
                    current = pd.to_numeric(raw.at[idx, s], errors="coerce") if s in raw.columns else float("nan")
                    new_marks[s] = cols[i % 3].number_input(f"{s} (max {c['max']:g})", 0.0, float(c["max"]),
                                                            0.0 if pd.isna(current) else float(current), 0.5,
                                                            key=f"upd_{idx}_{s}_{c['max']}")
                blanks = st.multiselect("Subjects not taken (leave blank)", list(subjects), key=f"upd_blank_{idx}",
                                        default=[s for s in subjects if s in raw.columns and pd.isna(pd.to_numeric(raw.at[idx, s], errors="coerce"))])
                if st.form_submit_button("Save marks", type="primary"):
                    problems = [m for s, v in new_marks.items() if s not in blanks and (m := check_mark(v, s, subjects[s]["max"]))]
                    if problems:
                        for p in problems:
                            st.error(p)
                    else:
                        for s, v in new_marks.items():
                            raw.at[idx, s] = float("nan") if s in blanks else v
                        st.session_state.raw = raw
                        st.success("Marks updated.")

    with tab_upload:
        st.markdown("**Required columns:** `Student ID, Full Name, Class, Section, Roll Number` plus one column per subject "
                    f"({', '.join(subjects)}). Blank marks mean 'not taken'. Column names are case-insensitive.")
        st.download_button("Download sample CSV", to_csv(sample_data(default_config())), "sample_marks.csv", "text/csv")
        uploaded = st.file_uploader("Upload marks CSV", type=["csv"])
        mode = st.radio("Import mode", ["Add to existing records", "Replace all records"], horizontal=True)
        if uploaded is not None and st.button("Import CSV", type="primary"):
            try:
                incoming = pd.read_csv(uploaded, dtype=str, keep_default_na=False, skipinitialspace=True, encoding="utf-8-sig")
            except pd.errors.EmptyDataError:
                st.error("The file is empty.")
                return
            except (pd.errors.ParserError, UnicodeDecodeError) as exc:
                st.error(f"Could not read the file as CSV: {exc}")
                return
            known = set() if mode.startswith("Replace") else existing_keys(raw)
            new, errors, warnings = validate_records(incoming, config, known)
            show_messages(errors, warnings)
            if new.empty:
                st.error("No valid rows were imported.")
            else:
                st.session_state.raw = new if mode.startswith("Replace") else pd.concat([raw, new], ignore_index=True)
                st.success(f"Imported {len(new)} student(s)" + (f"; skipped {len(errors)} invalid row(s)." if errors else "."))

    with tab_other:
        st.write(f"Current records: **{len(st.session_state.raw)}**")
        if not raw.empty:
            idx = st.selectbox("Student to delete", list(raw.index), key="del_pick",
                               format_func=lambda i: f"{raw.at[i, NAME_COL]} · {raw.at[i, ID_COL]} · {raw.at[i, CLASS_COL]}")
            if st.checkbox("I understand this cannot be undone") and st.button("Delete student"):
                st.session_state.raw = raw.drop(index=idx).reset_index(drop=True)
                st.success("Student deleted. Re-select a student if the list looks stale.")
        c1, c2 = st.columns(2)
        if c1.button("Reload sample data"):
            st.session_state.raw = sample_data(config)
            st.success("Sample data restored.")
        if c2.button("Clear all records"):
            st.session_state.raw = pd.DataFrame(columns=INFO_COLS + list(subjects))
            st.success("All records cleared.")


def page_reports(analyzed, config):
    st.header("📥 Reports")
    if analyzed.empty:
        st.info("No student data yet.")
        return
    view = filter_controls(analyzed, "rep")
    if view.empty:
        st.info("No students match the selected filters.")
        return
    c1, c2, c3 = st.columns(3)
    c1.download_button("Complete analysed marks sheet", to_csv(view), "marks_sheet_analysed.csv", "text/csv")
    c2.download_button("Subject-wise statistics", to_csv(subject_statistics(view, config)), "subject_statistics.csv", "text/csv")
    c3.download_button("Class summary", to_csv(class_summary(view)), "class_summary.csv", "text/csv")
    st.subheader("Individual student result")
    student = student_picker(view, "rep_pick")
    class_df = analyzed[analyzed[CLASS_COL] == student[CLASS_COL]]
    detail, _ = student_insights(student, class_df, config)
    summary = {ID_COL: student[ID_COL], NAME_COL: student[NAME_COL], CLASS_COL: student[CLASS_COL],
               SECTION_COL: student[SECTION_COL], "Total Obtained": student["Total Obtained"],
               "Total Possible": student["Total Possible"], "Overall %": student["Percentage"],
               "Grade": student["Grade"], "Rank": student["Rank"], "Result": student["Result"]}
    for key in reversed(list(summary)):
        detail.insert(0, key, summary[key])
    show_table(detail)
    st.download_button("Download this student's result", to_csv(detail), f"result_{student[ID_COL]}.csv", "text/csv")


def page_settings(config):
    st.header("⚙️ Settings")
    st.caption("These are configurable EXAMPLE settings, not universal academic rules. Adjust them to your school.")
    table = pd.DataFrame([{"Subject": s, "Maximum Marks": c["max"], "Pass Mark": c["pass"]} for s, c in config["subjects"].items()])
    edited = st.data_editor(table, num_rows="dynamic", hide_index=True, use_container_width=True, key="subject_editor",
                            help="Add, rename or remove subjects. Renaming creates a new, empty subject.")
    st.markdown("**Grading scale** (minimum percentage; below D is F)")
    cols, grades = st.columns(len(config["grades"])), []
    for col, (grade, minimum) in zip(cols, config["grades"]):
        grades.append((grade, col.number_input(f"{grade} from %", 0.0, 100.0, float(minimum), 1.0, key=f"grade_{grade}")))
    if st.button("Apply settings", type="primary"):
        errors, new_config = validate_settings(edited, grades, st.session_state.raw)
        if errors:
            for e in errors:
                st.error(e)
        else:
            st.session_state.config = new_config
            st.session_state.raw = st.session_state.raw.reindex(columns=INFO_COLS + list(new_config["subjects"]))
            st.success("Settings applied. Marks for removed subjects were dropped; new subjects start blank.")
    st.markdown(f"""**Result rule:** *Pass* = at least the pass mark in every subject entered; *Needs Improvement* = below the pass mark in
1-{FAIL_SUBJECT_COUNT - 1} subject(s); *Fail* = below the pass mark in {FAIL_SUBJECT_COUNT} or more. Percentages are rounded to 2 decimals before grading and ranking.""")


def page_validation(analyzed, config):
    st.header("✅ Validation Checks")
    results = run_self_tests()
    passed = sum(ok for _, ok in results)
    (st.success if passed == len(results) else st.error)(f"{passed} of {len(results)} built-in calculation checks passed.")
    st.dataframe(pd.DataFrame({"Check": [r[0] for r in results], "Passed": ["✅" if r[1] else "❌" for r in results]}),
                 hide_index=True, use_container_width=True)
    st.subheader("Live data consistency")
    if analyzed.empty:
        st.info("No data loaded.")
        return
    subjects = list(config["subjects"])
    live = [
        ("Totals equal the sum of subject marks", ((analyzed[subjects].sum(axis=1) - analyzed["Total Obtained"]).abs() < 1e-9).all()),
        ("Percentages are between 0 and 100", analyzed["Percentage"].between(0, 100).all()),
        ("Every 'Pass' student has no failed subject", (analyzed.loc[analyzed["Result"] == "Pass", "Failed Subjects"] == 0).all()),
        ("Every class has a rank-1 student", all((g["Rank"] == 1).any() for _, g in analyzed[analyzed["Total Possible"] > 0].groupby(CLASS_COL))),
        ("No duplicate Student ID within a class", not analyzed.duplicated([CLASS_COL, ID_COL]).any()),
    ]
    for label, ok in live:
        st.write(("✅ " if ok else "❌ ") + label)


# -------------------------------------------------------------------- main
def main():
    init_state()
    config = st.session_state.config
    analyzed = analyze(st.session_state.raw, config)
    pages = {
        "📊 Dashboard": lambda: page_dashboard(analyzed, config),
        "📋 Marks Sheet": lambda: page_marks_sheet(analyzed, config),
        "🧑‍🎓 Student Details": lambda: page_student(analyzed, config),
        "🏫 Class Analysis": lambda: page_class_analysis(analyzed, config),
        "✏️ Manage Data": lambda: page_manage(analyzed, config),
        "📥 Reports": lambda: page_reports(analyzed, config),
        "⚙️ Settings": lambda: page_settings(config),
        "✅ Validation": lambda: page_validation(analyzed, config),
    }
    st.sidebar.title("🎓 Performance Analyzer")
    choice = st.sidebar.radio("Navigate", list(pages), label_visibility="collapsed")
    st.sidebar.caption("Data is stored in session state only and is lost when the app restarts.")
    pages[choice]()


main()
