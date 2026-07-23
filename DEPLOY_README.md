# 2AFC 10-second Study App Deployment Package

Generated: 2026-07-20 13:29:14

This package contains the updated standard two-alternative forced-choice (2AFC) Streamlit study app.

## Contents

- `app.py`: updated app, no confidence field, no optional comment field, no tie option.
- `stimuli.csv`: 35 real-study trials using 10-second videos with relative paths.
- `practice_stimuli.csv`: 1 StaticMannequin practice/test trial using 10-second videos.
- `videos/real_sequences/`: 70 real-study MP4s.
- `videos/test_sequences/`: 2 StaticMannequin practice MP4s.
- `results/`: empty result folder initialized for deployment. I have put one results for you to check. Maybe you need re-write this part so how this info can be colleacted in your platform. The info that I collected should be correct, just save in the way you prefer like in the Google Sheet?
- `.streamlit/config.toml`: Streamlit config copied from the working app.
- `requirements.txt`: Python dependencies.

## Run

From this folder:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
STUDY_APP_VERSION=participant streamlit run app.py --server.address 0.0.0.0 --server.port 8502
```

For local testing only, use:

```bash
STUDY_APP_VERSION=researcher streamlit run app.py --server.port 8502
```

## Data Collected

The current app collects participant demographics, trial metadata, A/B choice, selected video/method, and response time. It does not collect confidence or comments.

## Trial Design

Real study: 5 sequences x 7 conditions = 35 pairs.
Practice: StaticMannequin same_NoP 4x pair.

Each trial requires full playback once before the response controls unlock. Participants can replay before submitting, but cannot go back after submission.
