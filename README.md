# 3DGS vs Point Cloud Subjective Quality Study

This Streamlit app runs a method-blind A/B subjective video quality study comparing
3D Gaussian Splatting and point cloud rendered videos.

The current real stimulus set uses 5 complete sequences and 7 pairs per
sequence, for 35 saved trials per participant. StaticMannequin is reserved for
the practice/test phase and is not saved to the study results.

## Run

Researcher investigation version:

```bash
cd /gpfs/work3/0/prjs0839/data/IEEEVR2026/study_app
streamlit run app.py
```

This is the default version. It skips demographics and practice, fixes the trial
order, and keeps Video A as point cloud and Video B as 3DGS for quick checking.

Pilot study version:

```bash
cd /gpfs/work3/0/prjs0839/data/IEEEVR2026/study_app
STUDY_APP_VERSION=pilot streamlit run app.py
```

You can also open the app with `?version=pilot` in the browser URL. This version
uses only the real study sequences, skips practice trials, skips demographics,
and keeps randomized trial order and randomized Video A / Video B assignment.

Real participant testing version:

```bash
cd /gpfs/work3/0/prjs0839/data/IEEEVR2026/study_app
STUDY_APP_VERSION=participant streamlit run app.py
```

You can also open the app with `?version=participant` in the browser URL. This
version collects generic demographics, enables practice, randomizes trial order,
and randomizes which method appears as Video A or Video B.

Responses are appended to:

```text
results/responses.csv
```

Participant demographics are saved to:

```text
results/demographics.csv
results/by_participant/<participant_id>.json
```

## Stimuli

The participant sees only Video A and Video B. Method labels are randomized and
hidden in the interface, but the saved response records the hidden left/right
mapping for analysis.

Videos under `videos/` are symlinks to the generated render outputs. The
`stimuli.csv` file records both the relative app video path and the original
source MP4 path.
