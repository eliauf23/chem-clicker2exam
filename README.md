# get shell working  
```bash
    python3 -m venv .venv
    source .venv/bin/activate
    python3 -m pip install -r requirements.txt
```

# save packages
```bash

    pip freeze > requirements.txt
```
# Run app

```bash
streamlit run app.py                   
```

# Preprocess clicker slides script:
python3 scripts/preprocess_clicker_pdf.py data/allclickerslides_only_questions.pdf  -o data/allclickerslides_clean.pdf --summary-json allclickerslides_summary.json

# Find duplicates script
python3 scripts/find_duplicates.py allclickerslides_summary.json
