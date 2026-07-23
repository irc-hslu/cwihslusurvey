import base64
import html
import os
import random
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import google_storage


STIMULI_CSV = "stimuli.csv"
PRACTICE_STIMULI_CSV = "practice_stimuli.csv"
APP_VERSIONS = {
    "researcher": "Researcher investigation",
    "pilot": "Pilot study",
    "participant": "Participant testing",
}
DEMOGRAPHICS_EXPERTISE_FIELDS = [
    ("expertise_3d_representation", "3D representation / computer graphics"),
    ("expertise_3d_processing", "3D processing, reconstruction, or compression"),
    ("expertise_qoe", "Quality of Experience (QoE) or user studies"),
    ("expertise_quality_assessment", "Visual quality assessment"),
]
ANALYSIS_COLUMNS = [
    "app_version",
    "participant_id",
    "index",
    "sequence",
    "video_a",
    "video_b",
    "choice",
    "selected_video",
    "time_used_seconds",
    "timestamp",
]


def page_title_from_env():
    if os.environ.get("STUDY_APP_VERSION", "").lower() == "pilot":
        return "Pilot Study - Subjective Visual Quality Assessment"
    return "Subjective Visual Quality Assessment"


st.set_page_config(
    page_title=page_title_from_env(),
    layout="wide",
)


def get_app_version():
    query_version = st.query_params.get("version")
    env_version = os.environ.get("STUDY_APP_VERSION")
    requested_version = (query_version or env_version or "researcher").lower()
    if requested_version not in APP_VERSIONS:
        requested_version = "researcher"
    return requested_version


APP_VERSION = get_app_version()
DETERMINISTIC_TEST_MODE = APP_VERSION == "researcher"
COLLECT_DEMOGRAPHICS = APP_VERSION == "participant"
RUN_PRACTICE = APP_VERSION == "participant"
STUDY_TITLE = (
    "Pilot Study - Subjective Visual Quality Assessment"
    if APP_VERSION == "pilot"
    else "Subjective Visual Quality Assessment"
)


@st.cache_data
def load_stimuli(stimuli_mtime):
    df = pd.read_csv(STIMULI_CSV)

    required_cols = [
        "trial_id",
        "sequence",
        "criterion",
        "regime",
        "pc_factor",
        "gs_factor",
        "pc_video",
        "gs_video",
        "pc_size_mb",
        "gs_size_mb",
        "pc_primitive_count",
        "gs_primitive_count",
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"Missing columns in stimuli.csv: {missing}")
        st.stop()

    missing_videos = []
    for _, row in df.iterrows():
        if not os.path.exists(row["pc_video"]):
            missing_videos.append(row["pc_video"])
        if not os.path.exists(row["gs_video"]):
            missing_videos.append(row["gs_video"])

    if missing_videos:
        st.error("Missing video files:")
        st.write(missing_videos)
        st.stop()

    return df


@st.cache_data
def load_practice_stimuli(stimuli_mtime):
    df = load_stimuli(stimuli_mtime) if PRACTICE_STIMULI_CSV == STIMULI_CSV else pd.read_csv(PRACTICE_STIMULI_CSV)

    required_cols = [
        "trial_id",
        "sequence",
        "criterion",
        "regime",
        "pc_factor",
        "gs_factor",
        "pc_video",
        "gs_video",
        "pc_size_mb",
        "gs_size_mb",
        "pc_primitive_count",
        "gs_primitive_count",
    ]

    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"Missing columns in practice_stimuli.csv: {missing}")
        st.stop()

    missing_videos = []
    for _, row in df.iterrows():
        if not os.path.exists(row["pc_video"]):
            missing_videos.append(row["pc_video"])
        if not os.path.exists(row["gs_video"]):
            missing_videos.append(row["gs_video"])

    if missing_videos:
        st.error("Missing practice video files:")
        st.write(missing_videos)
        st.stop()

    return df


def generate_participant_id():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if google_storage.is_configured():
        participant_index = google_storage.next_participant_index()
    else:
        participant_index = random.randint(1000, 9999)
    return f"{timestamp}_{participant_index}"


def participant_record():
    if "participant_record" not in st.session_state:
        st.session_state.participant_record = {
            "participant_id": st.session_state.participant_id,
            "app_version": APP_VERSION,
            "demographics": st.session_state.get("demographics"),
            "responses": [],
        }
    return st.session_state.participant_record


def persist_study_data(
    *,
    responses_row=None,
    responses_columns=None,
    analysis_row=None,
    demographics_row=None,
    demographics_columns=None,
    participant_data=None,
):
    if not google_storage.is_configured():
        raise RuntimeError(
            "Google Sheets is not configured. Add secrets before collecting study data "
            "on Streamlit Cloud (see GOOGLE_SHEETS_SETUP.md)."
        )

    if responses_row is not None:
        google_storage.append_row(
            google_storage.WORKSHEET_RESPONSES,
            responses_row,
            responses_columns,
        )
    if analysis_row is not None:
        google_storage.append_row(
            google_storage.WORKSHEET_ANALYSIS,
            analysis_row,
            ANALYSIS_COLUMNS,
        )
    if demographics_row is not None:
        google_storage.append_row(
            google_storage.WORKSHEET_DEMOGRAPHICS,
            demographics_row,
            demographics_columns,
        )
    if participant_data is not None:
        google_storage.save_participant_json(
            participant_data["participant_id"],
            participant_data,
        )


def prepare_trial_rows(trial_rows, shuffle_rows):
    trial_rows = [dict(row) for row in trial_rows]
    if shuffle_rows and not DETERMINISTIC_TEST_MODE:
        random.shuffle(trial_rows)

    prepared_trials = []
    for row in trial_rows:
        if DETERMINISTIC_TEST_MODE:
            row["left_method"] = "PC"
            row["right_method"] = "3DGS"
            row["left_video"] = row["pc_video"]
            row["right_video"] = row["gs_video"]
        elif random.random() < 0.5:
            row["left_method"] = "PC"
            row["right_method"] = "3DGS"
            row["left_video"] = row["pc_video"]
            row["right_video"] = row["gs_video"]
        else:
            row["left_method"] = "3DGS"
            row["right_method"] = "PC"
            row["left_video"] = row["gs_video"]
            row["right_video"] = row["pc_video"]

        prepared_trials.append(row)

    return prepared_trials


def init_session():
    if st.session_state.get("app_version") not in (None, APP_VERSION):
        st.session_state.clear()
    st.session_state.app_version = APP_VERSION

    if "participant_id" not in st.session_state:
        st.session_state.participant_id = generate_participant_id()

    if "trial_index" not in st.session_state:
        st.session_state.trial_index = 0

    if "trials" not in st.session_state:
        stimuli_mtime = os.path.getmtime(STIMULI_CSV)
        stimuli = load_stimuli(stimuli_mtime)
        st.session_state.trials = prepare_trial_rows(stimuli.to_dict("records"), shuffle_rows=True)
        st.session_state.stimuli_mtime = stimuli_mtime
        practice_mtime = os.path.getmtime(PRACTICE_STIMULI_CSV)
        practice_rows = load_practice_stimuli(practice_mtime).to_dict("records")
        st.session_state.practice_trials = prepare_trial_rows(practice_rows, shuffle_rows=False)
        st.session_state.practice_stimuli_mtime = practice_mtime
    elif st.session_state.get("stimuli_mtime") != os.path.getmtime(STIMULI_CSV):
        del st.session_state.trials
        st.session_state.trial_index = 0
        st.session_state.phase = "instructions"
        st.session_state.practice_runs = 0
        st.session_state.trial_start_time = time.time()
        init_session()
    elif st.session_state.get("practice_stimuli_mtime") != os.path.getmtime(PRACTICE_STIMULI_CSV):
        practice_mtime = os.path.getmtime(PRACTICE_STIMULI_CSV)
        practice_rows = load_practice_stimuli(practice_mtime).to_dict("records")
        st.session_state.practice_trials = prepare_trial_rows(practice_rows, shuffle_rows=False)
        st.session_state.practice_stimuli_mtime = practice_mtime

    if st.session_state.practice_trials and "left_video" not in st.session_state.practice_trials[0]:
        st.session_state.practice_trials = prepare_trial_rows(
            st.session_state.practice_trials,
            shuffle_rows=False,
        )

    if "trial_start_time" not in st.session_state:
        st.session_state.trial_start_time = time.time()


def save_response(response):
    analysis_response = compact_analysis_response(response)
    record = participant_record()
    record["app_version"] = response["app_version"]
    if st.session_state.get("demographics"):
        record["demographics"] = st.session_state.demographics
    record["responses"].append(analysis_response)

    try:
        persist_study_data(
            responses_row=response,
            responses_columns=list(response.keys()),
            analysis_row=analysis_response,
            participant_data=record,
        )
    except Exception as exc:
        st.error(f"Failed to save response to Google Sheets: {exc}")
        st.stop()


def save_demographics(demographics):
    demographic_row = {
        "timestamp": datetime.now().isoformat(),
        "participant_id": st.session_state.participant_id,
        "app_version": APP_VERSION,
        **demographics,
    }
    record = participant_record()
    record["app_version"] = APP_VERSION
    record["demographics"] = demographics

    try:
        persist_study_data(
            demographics_row=demographic_row,
            demographics_columns=list(demographic_row.keys()),
            participant_data=record,
        )
    except Exception as exc:
        st.error(f"Failed to save demographics to Google Sheets: {exc}")
        st.stop()


def compact_analysis_response(response):
    return {
        "app_version": response["app_version"],
        "participant_id": response["participant_id"],
        "index": response["global_trial_index"],
        "sequence": response["sequence"],
        "video_a": response["video_a_name"],
        "video_b": response["video_b_name"],
        "choice": response["choice_compact"],
        "selected_video": response["selected_name"],
        "time_used_seconds": response["time_used_seconds"],
        "timestamp": response["timestamp"],
    }


def response_video_name(method, trial):
    video_path = trial["pc_video"] if method == "PC" else trial["gs_video"]
    return os.path.basename(video_path)


def selected_response_name(choice, video_a_name, video_b_name):
    if choice == "Video A is better":
        return video_a_name
    if choice == "Video B is better":
        return video_b_name
    return choice


def compact_choice_label(choice):
    if choice == "Video A is better":
        return "A"
    if choice == "Video B is better":
        return "B"
    return ""


def get_chosen_method(choice, left_method, right_method):
    if choice in ("A is better", "Video A is better"):
        return left_method
    if choice in ("B is better", "Video B is better"):
        return right_method
    return ""


def get_preference_3dgs(chosen_method):
    if chosen_method == "3DGS":
        return 1
    if chosen_method == "PC":
        return 0
    return ""


def show_transition_screen(title, body, primary_label, primary_phase, secondary_label=None, secondary_phase=None):
    st.markdown(
        """
        <style>
          .transition-screen {
            min-height: 58vh;
            background: #f2f4f7;
            border: 1px solid #d0d5dd;
            border-radius: 8px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 48px 28px;
            margin-top: 24px;
          }
          .transition-screen h2 {
            margin: 0 0 12px;
            font-size: 32px;
            line-height: 1.2;
            color: #111827;
          }
          .transition-screen p {
            margin: 0;
            max-width: 720px;
            font-size: 18px;
            line-height: 1.55;
            color: #374151;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="transition-screen">
          <h2>{html.escape(title)}</h2>
          <p>{html.escape(body)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button(primary_label, type="primary", use_container_width=True):
            st.session_state.phase = primary_phase
            st.session_state.trial_start_time = time.time()
            st.rerun()
        if secondary_label and secondary_phase:
            if st.button(secondary_label, use_container_width=True):
                st.session_state.phase = secondary_phase
                st.session_state.trial_start_time = time.time()
                st.rerun()


@st.cache_data(show_spinner=False)
def video_data_uri(video_path, video_mtime):
    with open(video_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:video/mp4;base64,{encoded}"


def render_synced_videos(left_video, right_video, trial_id, participant_id):
    left_uri = video_data_uri(left_video, os.path.getmtime(left_video))
    right_uri = video_data_uri(right_video, os.path.getmtime(right_video))
    left_label = html.escape("Video A")
    right_label = html.escape("Video B")
    trial_key = html.escape(f"{participant_id}_{trial_id}")

    components.html(
        f"""
        <style>
          .sync-wrap {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          }}
          .sync-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            align-items: start;
          }}
          .sync-label {{
            font-size: 18px;
            font-weight: 650;
            margin: 0 0 6px;
            color: #262730;
          }}
          .sync-video {{
            display: none;
          }}
          .sync-canvas {{
            width: 100%;
            height: 100%;
            background: #000;
            display: block;
          }}
          .video-crop {{
            width: 100%;
            aspect-ratio: 4 / 3;
            overflow: hidden;
            background: #000;
          }}
          .sync-controls {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin: 8px 0 0;
          }}
          .sync-button {{
            border: 1px solid #d0d5dd;
            background: #ffffff;
            color: #111827;
            border-radius: 6px;
            font-size: 16px;
            font-weight: 600;
            padding: 9px 18px;
            cursor: pointer;
            min-width: 104px;
          }}
          .sync-button:hover {{
            background: #f3f4f6;
          }}
          .timeline-wrap {{
            display: grid;
            grid-template-columns: 58px minmax(0, 1fr) 58px;
            align-items: center;
            gap: 10px;
            margin: 7px auto 0;
            max-width: 780px;
          }}
          .time-label {{
            color: #475467;
            font-size: 13px;
            font-variant-numeric: tabular-nums;
            text-align: center;
          }}
          .timeline {{
            width: 100%;
            accent-color: #2563eb;
            cursor: pointer;
          }}
          .timeline:disabled {{
            cursor: not-allowed;
            opacity: 0.45;
          }}
          .sync-status {{
            text-align: center;
            color: #7f1d1d;
            font-size: 14px;
            font-weight: 600;
            margin-top: 3px;
            margin-bottom: 0;
          }}
          .sync-status.ready {{
            color: #166534;
          }}
          @media (max-width: 900px) {{
            .sync-grid {{
              grid-template-columns: 1fr;
            }}
          }}
        </style>
        <div class="sync-wrap">
          <div class="sync-grid">
            <div>
              <div class="sync-label">{left_label}</div>
              <div class="video-crop">
                <video id="video-a" class="sync-video" src="{left_uri}" preload="auto" playsinline></video>
                <canvas id="canvas-a" class="sync-canvas"></canvas>
              </div>
            </div>
            <div>
              <div class="sync-label">{right_label}</div>
              <div class="video-crop">
                <video id="video-b" class="sync-video" src="{right_uri}" preload="auto" playsinline></video>
                <canvas id="canvas-b" class="sync-canvas"></canvas>
              </div>
            </div>
          </div>
          <div class="sync-controls">
            <button id="play-pause" class="sync-button" type="button" aria-label="Play both videos">
              <span id="play-pause-icon">▶</span>
              <span id="play-pause-text">Play</span>
            </button>
          </div>
          <div class="timeline-wrap">
            <span id="elapsed-time" class="time-label">0:00</span>
            <input
              id="video-timeline"
              class="timeline"
              type="range"
              min="0"
              max="1000"
              value="0"
              step="1"
              disabled
              aria-label="Video playback position"
            />
            <span id="duration-time" class="time-label">0:00</span>
          </div>
          <div id="watch-status" class="sync-status">
            Please watch both videos to the end at least once. The preference controls will unlock after full playback.
          </div>
        </div>
        <script>
          const a = document.getElementById("video-a");
          const b = document.getElementById("video-b");
          const canvasA = document.getElementById("canvas-a");
          const canvasB = document.getElementById("canvas-b");
          const ctxA = canvasA.getContext("2d", {{ willReadFrequently: true }});
          const ctxB = canvasB.getContext("2d", {{ willReadFrequently: true }});
          const playPause = document.getElementById("play-pause");
          const playPauseIcon = document.getElementById("play-pause-icon");
          const playPauseText = document.getElementById("play-pause-text");
          const timeline = document.getElementById("video-timeline");
          const elapsedTime = document.getElementById("elapsed-time");
          const durationTime = document.getElementById("duration-time");
          const status = document.getElementById("watch-status");
          const trialKey = "watched_full_trial_{trial_key}";
          let syncing = false;
          let watchedA = window.localStorage.getItem(trialKey) === "1";
          let watchedB = window.localStorage.getItem(trialKey) === "1";
          let renderLoop = null;
          let scrubbing = false;

          function resizeCanvas(canvas) {{
            const rect = canvas.getBoundingClientRect();
            const scale = Math.min(window.devicePixelRatio || 1, 1.5);
            const width = Math.max(1, Math.round(rect.width * scale));
            const height = Math.max(1, Math.round(rect.height * scale));
            if (canvas.width !== width || canvas.height !== height) {{
              canvas.width = width;
              canvas.height = height;
            }}
          }}

          function drawVideo(video, canvas, ctx) {{
            resizeCanvas(canvas);
            const width = canvas.width;
            const height = canvas.height;
            ctx.fillStyle = "#000";
            ctx.fillRect(0, 0, width, height);

            if (!video.videoWidth || !video.videoHeight) return;

            const scale = Math.max(width / video.videoWidth, height / video.videoHeight);
            const drawWidth = Math.round(video.videoWidth * scale);
            const drawHeight = Math.round(video.videoHeight * scale);
            const x = Math.round((width - drawWidth) / 2);
            const y = Math.round((height - drawHeight) / 2);
            ctx.drawImage(video, x, y, drawWidth, drawHeight);

            const image = ctx.getImageData(0, 0, width, height);
            const data = image.data;
            for (let i = 0; i < data.length; i += 4) {{
              const r = data[i];
              const g = data[i + 1];
              const bValue = data[i + 2];
              const maxValue = Math.max(r, g, bValue);
              const minValue = Math.min(r, g, bValue);
              if (maxValue <= 42 && maxValue - minValue <= 10) {{
                data[i] = 0;
                data[i + 1] = 0;
                data[i + 2] = 0;
              }}
            }}
            ctx.putImageData(image, 0, 0);
          }}

          function renderVideos() {{
            drawVideo(a, canvasA, ctxA);
            drawVideo(b, canvasB, ctxB);
          }}

          function startRenderLoop() {{
            if (renderLoop) return;
            const tick = () => {{
              renderVideos();
              if (!a.paused || !b.paused) {{
                renderLoop = window.requestAnimationFrame(tick);
              }} else {{
                renderLoop = null;
              }}
            }};
            renderLoop = window.requestAnimationFrame(tick);
          }}

          function setButton(isPlaying) {{
            playPauseIcon.textContent = isPlaying ? "■" : "▶";
            playPauseText.textContent = isPlaying ? "Stop" : "Play";
            playPause.setAttribute("aria-label", isPlaying ? "Stop both videos" : "Play both videos");
          }}

          function formatTime(seconds) {{
            if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
            const totalSeconds = Math.floor(seconds);
            const minutes = Math.floor(totalSeconds / 60);
            const remainder = String(totalSeconds % 60).padStart(2, "0");
            return `${{minutes}}:${{remainder}}`;
          }}

          function duration() {{
            const values = [a.duration, b.duration].filter(Number.isFinite);
            return values.length ? Math.min(...values) : 0;
          }}

          function updateTimeline() {{
            const d = duration();
            const t = Math.min(a.currentTime || 0, b.currentTime || 0);
            durationTime.textContent = formatTime(d);
            elapsedTime.textContent = formatTime(t);
            if (!scrubbing && d > 0) {{
              timeline.value = String(Math.round((t / d) * 1000));
            }}
            timeline.disabled = !(watchedA && watchedB);
            timeline.title = timeline.disabled
              ? "The timeline is available after the first full playback."
              : "Drag to replay or inspect a specific moment.";
          }}

          function submitButtons() {{
            const buttons = Array.from(window.parent.document.querySelectorAll("button"));
            return buttons.filter((button) =>
              button.innerText && (
                button.innerText.includes("Save answer and go to next trial") ||
                button.innerText.includes("Complete practice trial")
              )
            );
          }}

          function ratingForms() {{
            return submitButtons()
              .map((button) =>
                button.closest("form") ||
                button.closest('[data-testid="stForm"]') ||
                button.parentElement?.parentElement?.parentElement
              )
              .filter(Boolean);
          }}

          function setRatingVisible(visible) {{
            ratingForms().forEach((form) => {{
              form.style.display = visible ? "" : "none";
            }});
          }}

          function setSubmitEnabled(enabled) {{
            setRatingVisible(enabled);
            submitButtons().forEach((button) => {{
              button.disabled = !enabled;
              button.style.opacity = enabled ? "1" : "0.45";
              button.style.cursor = enabled ? "pointer" : "not-allowed";
              button.title = enabled ? "" : "Please watch both full videos once before submitting.";
            }});
          }}

          const formObserver = new MutationObserver(() => {{
            setSubmitEnabled(watchedA && watchedB);
          }});
          formObserver.observe(window.parent.document.body, {{
            childList: true,
            subtree: true,
          }});

          function markWatchedIfDone() {{
            if (watchedA && watchedB) {{
              window.localStorage.setItem(trialKey, "1");
              status.textContent = "Playback completed. You can replay or scrub the timeline before saving.";
              status.classList.add("ready");
              setSubmitEnabled(true);
            }} else {{
              setSubmitEnabled(false);
            }}
            updateTimeline();
          }}

          function setTime(t) {{
            syncing = true;
            a.currentTime = t;
            b.currentTime = t;
            updateTimeline();
            window.setTimeout(() => {{ syncing = false; }}, 80);
          }}

          function bothVideosEnded() {{
            return a.ended && b.ended;
          }}

          function syncFrom(source, target) {{
            if (syncing) return;
            if (Math.abs(source.currentTime - target.currentTime) > 0.25) {{
              target.currentTime = source.currentTime;
            }}
            updateTimeline();
          }}

          a.addEventListener("seeked", () => syncFrom(a, b));
          b.addEventListener("seeked", () => syncFrom(b, a));
          a.addEventListener("seeked", renderVideos);
          b.addEventListener("seeked", renderVideos);
          a.addEventListener("loadeddata", renderVideos);
          b.addEventListener("loadeddata", renderVideos);
          a.addEventListener("loadedmetadata", () => {{
            renderVideos();
            updateTimeline();
          }});
          b.addEventListener("loadedmetadata", () => {{
            renderVideos();
            updateTimeline();
          }});
          a.addEventListener("timeupdate", updateTimeline);
          b.addEventListener("timeupdate", updateTimeline);
          window.addEventListener("resize", renderVideos);

          timeline.addEventListener("input", () => {{
            if (timeline.disabled) return;
            scrubbing = true;
            const d = duration();
            const t = d * (Number(timeline.value) / 1000);
            elapsedTime.textContent = formatTime(t);
            a.pause();
            b.pause();
            setButton(false);
            setTime(t);
            renderVideos();
          }});

          timeline.addEventListener("change", () => {{
            scrubbing = false;
            updateTimeline();
            renderVideos();
          }});

          playPause.addEventListener("click", async () => {{
            if (a.paused && b.paused) {{
              const t = bothVideosEnded() ? 0 : Math.min(a.currentTime || 0, b.currentTime || 0);
              setTime(t);
              await Promise.allSettled([a.play(), b.play()]);
              setButton(true);
              startRenderLoop();
              updateTimeline();
            }} else {{
              a.pause();
              b.pause();
              setButton(false);
              renderVideos();
              updateTimeline();
            }}
          }});

          function updateButton() {{
            if (a.paused && b.paused) {{
              setButton(false);
              updateTimeline();
            }}
          }}
          a.addEventListener("ended", updateButton);
          b.addEventListener("ended", updateButton);
          a.addEventListener("ended", () => {{
            watchedA = true;
            renderVideos();
            markWatchedIfDone();
          }});
          b.addEventListener("ended", () => {{
            watchedB = true;
            renderVideos();
            markWatchedIfDone();
          }});

          window.setInterval(() => {{
            if (window.localStorage.getItem(trialKey) === "1") {{
              setSubmitEnabled(true);
            }} else {{
              setSubmitEnabled(false);
            }}
          }}, 500);
          renderVideos();
          updateTimeline();
          markWatchedIfDone();
        </script>
        """,
        height=680,
    )


def render_rating_form(trial, button_label, key_prefix):
    widget_key = f"{key_prefix}_{trial['trial_id']}"
    with st.form(key=f"trial_form_{widget_key}"):
        choice = st.radio(
            "Which video has better overall visual quality?",
            [
                "Video A is better",
                "Video B is better",
            ],
            index=None,
            horizontal=True,
            key=f"choice_{widget_key}",
        )

        submitted = st.form_submit_button(button_label, type="primary")

    artifact_tags = []
    return choice, artifact_tags, submitted


def pilot_method_label(trial, method):
    regime = "NoP" if trial["regime"] == "same_NoP" else "BitRate"
    if method == "PC":
        return f"{regime}_{trial['pc_factor']}_point cloud"
    return f"{regime}_{trial['gs_factor']}_3DGS"


def format_asset_metadata(trial, method):
    if method == "PC":
        primitive_count = trial.get("pc_primitive_count")
        size_mb = trial.get("pc_size_mb")
        count_label = "points"
    else:
        primitive_count = trial.get("gs_primitive_count")
        size_mb = trial.get("gs_size_mb")
        count_label = "primitives"

    parts = []
    try:
        count = int(primitive_count)
        if count > 0:
            parts.append(f"{count:,} {count_label}")
    except (TypeError, ValueError):
        pass

    try:
        size_value = float(size_mb)
        if size_value > 0:
            parts.append(f"{size_value:.2f} MB")
    except (TypeError, ValueError):
        pass

    return " | ".join(parts)


def source_asset_path(trial, method):
    if method == "PC":
        return trial.get("source_pc_ply") or trial.get("source_pc_video")
    return trial.get("source_gs_ply") or trial.get("source_gs_video")


def render_pilot_trial_labels(trial):
    if APP_VERSION == "participant":
        return
    st.caption(trial.get("pair_description", ""))
    left_label = pilot_method_label(trial, trial["left_method"])
    right_label = pilot_method_label(trial, trial["right_method"])
    left_metadata = format_asset_metadata(trial, trial["left_method"])
    right_metadata = format_asset_metadata(trial, trial["right_method"])
    left_source = source_asset_path(trial, trial["left_method"])
    right_source = source_asset_path(trial, trial["right_method"])
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"**Video A:** `{left_label}`")
        if left_metadata:
            st.caption(left_metadata)
        if left_source:
            st.caption(f"source: {left_source}")
    with col_b:
        st.markdown(f"**Video B:** `{right_label}`")
        if right_metadata:
            st.caption(right_metadata)
        if right_source:
            st.caption(f"source: {right_source}")


def render_demographics_form():
    st.subheader("Participant information")
    st.markdown(
        """
        Please answer the following questions. Your responses will only be used
        for demographic analysis of the study results.
        """
    )

    age_options = [
        "Under 18",
        "18-24",
        "25-34",
        "35-44",
        "45-54",
        "55-64",
        "65 or above",
        "Prefer not to say",
    ]
    sex_options = [
        "Female",
        "Male",
        "Other",
        "Prefer not to say",
    ]
    occupation_options = [
        "Student",
        "Researcher / Academic staff",
        "Engineer / Developer",
        "Designer / Artist",
        "Industry professional",
        "Other",
        "Prefer not to say",
    ]
    expertise_options = [
        "Expert",
        "Advanced",
        "Intermediate",
        "Basic",
        "Not an expert",
    ]
    nationality_region_options = [
        "Africa",
        "Australia",
        "Canada",
        "China",
        "France",
        "Germany",
        "India",
        "Italy",
        "Japan",
        "Netherlands",
        "Other Asian country",
        "Other European country",
        "South Korea",
        "Spain",
        "South America",
        "United Kingdom",
        "United States",
        "Other",
        "Prefer not to say",
    ]

    with st.form("demographics_form"):
        age_group = st.radio("1. What is your age?", age_options, index=None)
        sex = st.radio("2. What is your sex?", sex_options, index=None)
        occupation = st.radio("3. What is your occupation?", occupation_options, index=None)
        expertise_level = st.radio(
            "4. What is your level of expertise in 3D representation, visual quality assessment, or 3D processing?",
            expertise_options,
            index=None,
        )
        nationality_region = st.selectbox(
            "5. What is your nationality or region?",
            ["Select one"] + nationality_region_options,
            help="Click the menu and type to search.",
        )

        submitted = st.form_submit_button("Save participant information", type="primary")

    if nationality_region == "Select one":
        nationality_region = None

    demographics = {
        "age_group": age_group,
        "sex": sex,
        "occupation": occupation,
        "expertise_level": expertise_level,
        "country_region": nationality_region,
        "nationality_or_region": nationality_region,
    }
    return demographics, submitted


init_session()

st.markdown(
    """
    <style>
      .block-container {
        max-width: 1560px;
        padding-top: 3.7rem;
        padding-bottom: 1.5rem;
        padding-left: 1rem;
        padding-right: 1rem;
      }
      div[data-testid="stVerticalBlock"] {
        gap: 0.45rem;
      }
      h2, h3 {
        margin-top: 0.25rem;
        margin-bottom: 0.4rem;
      }
      div[data-testid="stForm"] {
        margin-top: 0;
      }
      div[data-testid="stForm"] fieldset {
        padding-top: 0.35rem;
      }
      .study-title {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 100;
        background: #ffffff;
        border-bottom: 1px solid #d0d5dd;
        box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08);
        font-size: 1.8rem;
        line-height: 1.35;
        font-weight: 700;
        margin: 0;
        padding: 0.55rem 1rem;
        color: #262730;
      }
    </style>
    <div class="study-title">{study_title}</div>
    """.replace("{study_title}", html.escape(STUDY_TITLE)),
    unsafe_allow_html=True,
)

if "phase" not in st.session_state:
    st.session_state.phase = "instructions"
if "practice_runs" not in st.session_state:
    st.session_state.practice_runs = 0
if APP_VERSION == "researcher":
    st.sidebar.markdown("### App version")
    selected_label = st.sidebar.radio(
        "Version",
        list(APP_VERSIONS.values()),
        index=list(APP_VERSIONS).index(APP_VERSION),
        help=(
            "Researcher mode is fixed and fast. Pilot mode uses real randomized trials only. "
            "Participant mode adds demographics and practice."
        ),
    )
    selected_version = next(
        key for key, label in APP_VERSIONS.items() if label == selected_label
    )
    if selected_version != APP_VERSION:
        st.session_state.clear()
        st.query_params["version"] = selected_version
        st.rerun()

trials = st.session_state.trials
trial_index = st.session_state.trial_index
num_trials = len(trials)

if st.session_state.phase == "instructions":
    if DETERMINISTIC_TEST_MODE:
        st.info(
            "Researcher investigation mode: practice is skipped, trial order is fixed, "
            "Video A is always point cloud, and Video B is always 3DGS."
        )
        st.dataframe(
            pd.DataFrame(st.session_state.trials)[
                ["trial_id", "sequence", "pair_description", "pc_factor", "gs_factor"]
            ],
            hide_index=True,
            use_container_width=True,
        )
    elif APP_VERSION == "pilot":
        st.info(
            "Pilot study mode: only the real study sequences are shown. "
            "Practice trials and demographic information collection are skipped."
        )

    st.markdown(
        """
        In each trial, you will see two videos: **Video A** and **Video B**.

        Please choose which video has better overall visual quality. You
        **MUST** choose either Video A or Video B. You may replay the videos
        multiple times by pressing the **Play** button before submitting your
        choice. After you submit your choice, you can **NOT** go back to the
        previous pair.

        Please use a laptop or desktop screen, not a phone or tablet. The
        recommended setup is a 13-inch or larger laptop display with at least
        1366 x 768 resolution, browser zoom at 100%, and the browser window
        maximized or full screen.

        The two videos may differ in sharpness, holes, noise, floating artifacts,
        edge stability, color, texture, geometry, or overall realism.

        Please judge only the visual quality. The method names are intentionally hidden.
        """
    )

    st.caption(f"Current version: {APP_VERSIONS[APP_VERSION]}")
    if not google_storage.is_configured():
        st.warning(
            "Google Sheets is not configured. Add Streamlit secrets before collecting "
            "responses on Streamlit Cloud (see GOOGLE_SHEETS_SETUP.md)."
        )
    st.text_input(
        "Participant ID",
        value=st.session_state.participant_id,
        disabled=True,
    )

    if DETERMINISTIC_TEST_MODE:
        start_label = "Start investigation trials"
    elif COLLECT_DEMOGRAPHICS:
        start_label = "Continue to participant information"
    else:
        start_label = "Start pilot study"

    if st.button(start_label, type="primary"):
        if DETERMINISTIC_TEST_MODE:
            st.session_state.phase = "real"
        elif COLLECT_DEMOGRAPHICS and st.session_state.get("demographics"):
            st.session_state.phase = "practice"
        elif COLLECT_DEMOGRAPHICS:
            st.session_state.phase = "demographics"
        elif RUN_PRACTICE:
            st.session_state.phase = "practice"
        else:
            st.session_state.phase = "real"
        st.session_state.practice_runs = 0
        st.session_state.trial_start_time = time.time()
        st.rerun()

    st.stop()

if st.session_state.phase == "demographics":
    if not COLLECT_DEMOGRAPHICS:
        st.session_state.phase = "instructions"
        st.rerun()

    demographics, submitted = render_demographics_form()
    if submitted:
        required_demographic_fields = [
            "age_group",
            "sex",
            "occupation",
            "expertise_level",
            "nationality_or_region",
        ]
        if any(not demographics[field] for field in required_demographic_fields):
            st.warning("Please answer all participant information questions before continuing.")
            st.stop()

        st.session_state.demographics = demographics
        save_demographics(demographics)
        st.session_state.phase = "practice"
        st.session_state.trial_start_time = time.time()
        st.rerun()

    st.stop()

if st.session_state.phase == "practice_transition":
    practice_total = len(st.session_state.practice_trials)
    has_next_practice = st.session_state.practice_runs < practice_total
    show_transition_screen(
        "Practice completed",
        (
            f"You have completed practice trial {st.session_state.practice_runs} / {practice_total}. "
            "The next screen will show the next practice trial."
            if has_next_practice
            else "You have completed the practice phase. The next screen starts the real experiment."
        ),
        "Continue practice" if has_next_practice else "Start real experiment",
        "practice" if has_next_practice else "real",
    )
    st.stop()

if st.session_state.phase == "real_transition":
    if trial_index >= num_trials:
        show_transition_screen(
            "Study complete",
            "Your final response has been saved. Thank you for completing the study.",
            "Show completion message",
            "done",
        )
    else:
        show_transition_screen(
            f"Response saved",
            f"The next screen will show Trial {trial_index + 1} / {num_trials}.",
            "Continue to next trial",
            "real",
        )
    st.stop()

if st.session_state.phase == "done":
    st.success("Thank you. You have completed the study.")
    if google_storage.is_configured():
        spreadsheet_name = st.secrets["spreadsheet_name"]
        st.write(f"Your responses have been saved to the Google Sheet **{spreadsheet_name}**.")
    else:
        st.warning(
            "Google Sheets is not configured. Responses from this session were not persisted."
        )
    st.stop()

if st.session_state.phase == "practice":
    practice_total = len(st.session_state.practice_trials)
    practice_index = min(st.session_state.practice_runs, practice_total - 1)
    practice_trial = dict(st.session_state.practice_trials[practice_index])
    st.info("Practice trial. This response will **NOT** be saved in the study results.")
    st.subheader(f"Practice trial {practice_index + 1} / {practice_total}")

    render_synced_videos(
        practice_trial["left_video"],
        practice_trial["right_video"],
        f"practice_{st.session_state.practice_runs + 1}_{practice_trial['trial_id']}",
        st.session_state.participant_id,
    )

    choice, artifact_tags, submitted = render_rating_form(
        practice_trial,
        "Complete practice trial",
        f"practice_{st.session_state.practice_runs + 1}",
    )

    if submitted:
        if choice is None:
            st.warning("Please select an answer before continuing.")
            st.stop()

        st.session_state.practice_runs += 1
        st.session_state.phase = "practice_transition"
        st.session_state.trial_start_time = time.time()
        st.rerun()

    st.stop()

if trial_index >= num_trials:
    st.session_state.phase = "done"
    st.rerun()

trial = trials[trial_index]

st.progress((trial_index + 1) / num_trials)
st.subheader(f"Trial {trial_index + 1} / {num_trials}")

render_pilot_trial_labels(trial)

render_synced_videos(
    trial["left_video"],
    trial["right_video"],
    trial["trial_id"],
    st.session_state.participant_id,
)

choice, artifact_tags, submitted = render_rating_form(
    trial,
    "Save answer and go to next trial",
    "real",
)

if submitted:
    if choice is None:
        st.warning("Please select an answer before continuing.")
        st.stop()

    time_used = time.time() - st.session_state.trial_start_time
    chosen_method = get_chosen_method(
        choice,
        trial["left_method"],
        trial["right_method"],
    )
    preference_3dgs = get_preference_3dgs(chosen_method)
    sequence_trial_index = sum(
        1 for previous_trial in trials[:trial_index] if previous_trial["sequence"] == trial["sequence"]
    ) + 1
    video_a_name = response_video_name(trial["left_method"], trial)
    video_b_name = response_video_name(trial["right_method"], trial)
    selected_name = selected_response_name(choice, video_a_name, video_b_name)
    choice_compact = compact_choice_label(choice)

    response = {
        "timestamp": datetime.now().isoformat(),
        "app_version": APP_VERSION,
        "participant_id": st.session_state.participant_id,
        "global_trial_index": trial_index + 1,
        "sequence_trial_index": sequence_trial_index,
        "trial_id": trial["trial_id"],
        "sequence": trial["sequence"],
        "criterion": trial["criterion"],
        "regime": trial["regime"],
        "pair_description": trial["pair_description"],
        "pc_factor": trial["pc_factor"],
        "gs_factor": trial["gs_factor"],
        "pc_size_mb": trial["pc_size_mb"],
        "gs_size_mb": trial["gs_size_mb"],
        "pc_primitive_count": trial["pc_primitive_count"],
        "gs_primitive_count": trial["gs_primitive_count"],
        "left_method": trial["left_method"],
        "right_method": trial["right_method"],
        "left_video": trial["left_video"],
        "right_video": trial["right_video"],
        "video_a_name": video_a_name,
        "video_b_name": video_b_name,
        "choice_raw": choice,
        "choice_compact": choice_compact,
        "selected_name": selected_name,
        "chosen_method": chosen_method,
        "preference_3dgs": preference_3dgs,
        "artifact_tags": ";".join(artifact_tags),
        "time_used_seconds": round(time_used, 2),
    }

    save_response(response)

    st.session_state.trial_index += 1
    st.session_state.trial_start_time = time.time()
    st.session_state.phase = "real_transition"
    st.rerun()
