# STUDENT-MARSK-ANALYZER
# 🎓 Student Performance Analyzer

An interactive Streamlit dashboard that lets teachers enter or upload student marks for multiple classes and sections, then automatically calculates totals, percentages, grades, class ranks and pass/fail results, with Plotly charts and downloadable CSV reports. Built as a beginner-friendly project: three files, no database, no paid APIs.

## Features

- Manual entry form and CSV upload (add to existing data or replace it)
- Multiple classes and sections, with class and section filters
- Dashboard: total students, class average %, highest %, lowest %, pass rate, top performer
- Sortable, searchable marks sheet filtered by class, section and result
- Student details: marks, percentage, grade, class rank, strengths, weaknesses, rule-based improvement suggestions
- Class analysis: subject averages, strongest/weakest subject, flagged students, class comparison
- Plotly charts: subject averages, student comparison, grade distribution, pass/fail, class comparison, individual vs class average
- Reports: CSV for the analysed marks sheet, an individual student, subject statistics and class summary
- Settings: subject names, maximum marks, pass marks and the grading scale
- Built-in **Validation** page with calculation checks (totals, percentages, grade boundaries, pass rule, ties, empty data, input validation)
- Fictional sample dataset loaded on start

## Grading and result rules (configurable examples)

These defaults are examples, **not universal academic rules**. Change them on the **Settings** page.

| Grade | Percentage |
|-------|-----------|
| A+ | 90 – 100 |
| A | 80 – 89.99 |
| B | 70 – 79.99 |
| C | 60 – 69.99 |
| D | 50 – 59.99 |
| F | below 50 |

- Default maximum per subject: 100. Default pass mark per subject: 50.
- Percentage = total obtained ÷ total possible × 100, **rounded to 2 decimals**; the rounded value is used for grading and ranking.
- **Pass**: at least the pass mark in every subject entered.
- **Needs Improvement**: below the pass mark in 1 or 2 subjects.
- **Fail**: below the pass mark in 3 or more subjects.
- Pass rate = students with result *Pass* ÷ students with marks.
- **Class rank** is calculated within each class (all sections together). Tied percentages share a rank (1, 2, 2, 4).
- A blank mark means "subject not taken": it is excluded from total possible and from the pass check. Students with no marks at all show result *No Marks* and are not ranked.
- Different maximum marks per subject are supported; totals use each subject's own maximum.

## CSV format

Required columns (names are case-insensitive): `Student ID`, `Full Name`, `Class`, `Section`, `Roll Number`, plus one column per configured subject (defaults: `Mathematics`, `Physics`, `Computer Science`, `English`, `Urdu`).

```csv
Student ID,Full Name,Class,Section,Roll Number,Mathematics,Physics,Computer Science,English,Urdu
S001,Ayesha Khan,Grade 9,A,1,88,76.5,91,69,72
S002,Bilal Ahmed,Grade 9,A,2,45,52,60,58,49
```

Rules: marks must be numbers from 0 to the subject's maximum; Student IDs must be unique **within a class** (the same ID may appear in different classes); invalid rows are skipped and reported with their row number. Missing required columns or an empty file produce a clear error. A sample CSV can be downloaded from **Manage Data → Upload CSV**.

## Installation and local run

Requires Python 3.9+ (3.10+ recommended).

```bash
cd student-performance-analyzer
python -m venv venv
# Windows: venv\Scripts\activate      macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. In VS Code, open the folder, open a terminal (Ctrl+`) and run the commands above.

## Testing the main features

1. Open **Validation** – all built-in checks should pass.
2. **Dashboard** – metrics and charts appear with the sample data; change the class filter.
3. **Marks Sheet** – search a name, sort, filter by result.
4. **Student Details** – pick a student and read the suggestions.
5. **Manage Data** – add a student, update marks, try a duplicate ID, negative marks and marks above the maximum (all should be rejected), then upload the sample CSV.
6. **Reports** – download each CSV and open it in a spreadsheet to check the values.

## Upload to GitHub

```bash
git init
git add app.py requirements.txt README.md
git commit -m "Student Performance Analyzer"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

Create the empty repository on github.com first (no README/licence), then use its URL above.

## Deploy on Streamlit Community Cloud

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. Click **Create app** → choose your repository and the `main` branch.
3. Set **Main file path** to `app.py`.
4. Click **Deploy**. Dependencies install from `requirements.txt` automatically.

## Data storage limitations

All data is held in Streamlit **session state**. There is no database: data is lost when the browser session resets, the app restarts or the cloud app sleeps and redeploys, and each visitor has their own separate data. Download the CSV reports (or re-upload your CSV) to keep your work. Do not enter real personal student data into a public deployment.

## Possible future improvements

- Persistent storage (SQLite or a hosted database) and teacher login
- Excel import/export and PDF report cards
- Term-by-term progress tracking and trend charts
- Per-subject weighting and custom grading scales per class
- Attendance data and parent-friendly report cards
- Automated unit tests in a separate test file (`pytest`)
