from __future__ import annotations

import csv
import html
from collections import defaultdict
from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "character_game_data_arcs.csv"
THINKING_IMAGE_URL = "app/static/oracle_thinking.png"
AWAKE_IMAGE_URL = "app/static/oracle_game_clean.png"


st.set_page_config(
    page_title="Neural Character Oracle",
    page_icon="🔮",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def normalize(text: str) -> str:
    """Normalize data values so comparisons remain reliable."""
    return " ".join((text or "").strip().lower().split())


def split_character_key(key: str) -> tuple[str, str]:
    anime, character = key.split("::", 1)
    return anime, character


def difficulty_rank(value: str) -> int:
    return {"easy": 0, "medium": 1, "hard": 2}.get(normalize(value), 1)


@st.cache_data(show_spinner=False)
def load_game_data(csv_path: str, data_version: int):
    """Load the long-form CSV into the structures used by the game engine."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot find the game data: {path.name}")

    characters: dict[str, set[str]] = {}
    questions: dict[str, str] = {}
    difficulties: dict[str, str] = {}
    categories: dict[str, str] = {}

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        required = {
            "anime_name",
            "character_name",
            "trait",
            "question",
            "category",
            "difficulty",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "The CSV is missing columns: " + ", ".join(sorted(missing))
            )

        for row_number, row in enumerate(reader, start=2):
            anime = (row.get("anime_name") or "").strip()
            character = (row.get("character_name") or "").strip()
            trait = normalize(row.get("trait") or "")
            question = (row.get("question") or "").strip()
            if not anime or not character or not trait or not question:
                continue

            key = f"{anime}::{character}"
            characters.setdefault(key, set()).add(trait)

            previous_question = questions.get(trait)
            if previous_question and previous_question != question:
                raise ValueError(
                    f"Trait '{trait}' has conflicting questions (near row {row_number})."
                )
            questions[trait] = question
            difficulties[trait] = normalize(row.get("difficulty") or "medium")
            categories[trait] = normalize(row.get("category") or "")

    if not characters:
        raise ValueError("The CSV contains no playable characters.")

    # Cached values are treated as immutable by the rest of the app.
    frozen_characters = {key: frozenset(value) for key, value in characters.items()}
    return frozen_characters, questions, difficulties, categories


def choose_best_trait(
    candidates: set[str],
    characters: dict[str, frozenset[str]],
    asked_traits: set[str],
    difficulties: dict[str, str],
) -> str | None:
    """Choose a factual question that divides the candidates as evenly as possible."""
    available = {
        trait
        for character in candidates
        for trait in characters[character]
        if trait not in asked_traits
    }

    choices: list[tuple[str, int, int, int]] = []
    for trait in available:
        yes_count = sum(trait in characters[key] for key in candidates)
        no_count = len(candidates) - yes_count
        # A shared trait cannot narrow the result: when every remaining
        # character has it (or none do), skip it and try another trait.
        if yes_count == 0 or yes_count == len(candidates):
            continue
        choices.append(
            (
                trait,
                difficulty_rank(difficulties.get(trait, "medium")),
                abs(yes_count - no_count),
                min(yes_count, no_count),
            )
        )

    if not choices:
        return None

    # The opening question should use the most common useful identity trait.
    # In this dataset that is gender male (261 of 300 characters), so every
    # game begins with the expected "Is your character male?" question.
    if not asked_traits:
        opening_trait = "gender male"
        if any(choice[0] == opening_trait for choice in choices):
            return opening_trait

    # Prefer easy/medium facts. Only use a hard clue when nothing else separates
    # the remaining characters.
    ordinary = [choice for choice in choices if choice[1] < 2]
    eligible = ordinary if ordinary else choices
    eligible.sort(key=lambda item: (item[2], item[1], -item[3], item[0]))
    return eligible[0][0]


def initialize_state(character_keys) -> None:
    defaults = {
        "screen": "welcome",
        "candidates": set(character_keys),
        "asked_traits": set(),
        "current_trait": None,
        "history": [],
        "question_number": 0,
        "last_answer": None,
    }
    for name, value in defaults.items():
        if name not in st.session_state:
            st.session_state[name] = value


def advance_game(characters, difficulties) -> None:
    candidates = st.session_state.candidates
    if not candidates:
        st.session_state.screen = "no_match"
        st.session_state.current_trait = None
        st.query_params["page"] = "no-match"
        return

    if len(candidates) == 1:
        st.session_state.screen = "guess"
        st.session_state.current_trait = None
        st.query_params["page"] = "result"
        return

    trait = choose_best_trait(
        candidates,
        characters,
        st.session_state.asked_traits,
        difficulties,
    )
    if trait is None:
        st.session_state.screen = "guess"
        st.session_state.current_trait = None
        st.query_params["page"] = "result"
        return

    st.session_state.current_trait = trait
    st.session_state.screen = "question"
    st.query_params["page"] = "game"


def start_game(character_keys, characters, difficulties) -> None:
    st.session_state.candidates = set(character_keys)
    st.session_state.asked_traits = set()
    st.session_state.current_trait = None
    st.session_state.history = []
    st.session_state.question_number = 0
    st.session_state.last_answer = None
    st.query_params["page"] = "game"
    advance_game(characters, difficulties)


def submit_answer(answer: bool | None, characters, difficulties) -> None:
    trait = st.session_state.current_trait
    if not trait:
        return

    st.session_state.history.append(
        {
            "trait": trait,
            "answer": answer,
            "candidates_before": set(st.session_state.candidates),
            "asked_before": set(st.session_state.asked_traits),
        }
    )
    st.session_state.asked_traits.add(trait)
    st.session_state.last_answer = "YES" if answer else "NO"

    if answer is True:
        st.session_state.candidates = {
            key
            for key in st.session_state.candidates
            if trait in characters[key]
        }
    elif answer is False:
        st.session_state.candidates = {
            key
            for key in st.session_state.candidates
            if trait not in characters[key]
        }

    st.session_state.question_number += 1
    advance_game(characters, difficulties)


def undo_answer() -> None:
    if not st.session_state.history:
        return
    previous = st.session_state.history.pop()
    st.session_state.candidates = previous["candidates_before"]
    st.session_state.asked_traits = previous["asked_before"]
    st.session_state.current_trait = previous["trait"]
    st.session_state.question_number = max(0, st.session_state.question_number - 1)
    st.session_state.screen = "question"


def install_theme(background_uri: str) -> None:
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700;800&family=Rajdhani:wght@500;600;700&display=swap');

        :root {{ color-scheme: dark; }}
        html, body, [data-testid="stAppViewContainer"], .stApp {{
            background-color: #010508;
        }}
        [data-testid="stAppViewContainer"] {{
            background-image:
                linear-gradient(90deg, #010508 0%, transparent 20%, transparent 80%, #010508 100%),
                url("{background_uri}");
            background-repeat: no-repeat;
            background-position: top center;
            /* Keep the artwork as a complete portrait instead of enlarging it
               to desktop width and cropping most of the character. */
            background-size: auto 100vh;
            background-attachment: fixed;
        }}
        [data-testid="stHeader"] {{
            background: transparent;
            height: 0;
        }}
        [data-testid="stMainBlockContainer"] {{
            max-width: 720px;
            padding: 0 16px 28px;
        }}
        #MainMenu, footer, [data-testid="stToolbar"],
        [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{
            display: none !important;
        }}
        .art-space {{
            height: 100vh;
        }}
        .st-key-game_panel {{
            position: fixed;
            z-index: 50;
            left: 50%;
            bottom: 8px;
            transform: translateX(-50%);
            width: min(88vw, 370px);
            padding: clamp(13px, 2vw, 17px) !important;
            border: 1px solid rgba(43, 230, 255, .86) !important;
            border-radius: 18px !important;
            background:
                linear-gradient(145deg, rgba(7, 30, 42, .98), rgba(2, 12, 22, .98)) !important;
            box-shadow:
                0 0 0 2px rgba(0, 91, 126, .55),
                inset 0 0 28px rgba(0, 190, 255, .13),
                0 0 35px rgba(0, 218, 255, .28) !important;
            overflow: hidden;
        }}
        .st-key-game_panel::before {{
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            background: linear-gradient(90deg, transparent, rgba(42, 232, 255, .07), transparent);
        }}
        .eyebrow {{
            color: #5eeaff;
            font: 700 12px/1.2 'Orbitron', sans-serif;
            letter-spacing: .18em;
            text-transform: uppercase;
            text-align: center;
            margin-bottom: 12px;
        }}
        .game-title {{
            color: #f5fcff;
            font: 800 clamp(27px, 6vw, 43px)/1.1 'Orbitron', sans-serif;
            letter-spacing: .02em;
            text-align: center;
            text-shadow: 0 0 16px rgba(36, 224, 255, .6);
            margin: 0 0 15px;
        }}
        .question {{
            color: #f8fbff;
            font: 700 clamp(18px, 2.8vw, 25px)/1.17 'Rajdhani', sans-serif;
            text-align: center;
            margin: 2px auto 12px;
            max-width: 620px;
        }}
        .answer-feedback {{
            width: fit-content;
            margin: 0 auto 9px;
            padding: 5px 12px;
            border-radius: 999px;
            font: 700 11px/1 'Orbitron', sans-serif;
            letter-spacing: .1em;
        }}
        .answer-feedback.yes {{
            color: #c7ffb1;
            border: 1px solid #7cff58;
            background: rgba(11, 131, 38, .55);
            box-shadow: 0 0 13px rgba(70, 255, 48, .35);
        }}
        .answer-feedback.no {{
            color: #ffd0c5;
            border: 1px solid #ff7657;
            background: rgba(151, 23, 16, .55);
            box-shadow: 0 0 13px rgba(255, 51, 32, .32);
        }}
        .intro {{
            color: #bcd1dd;
            font: 600 clamp(17px, 3.3vw, 22px)/1.45 'Rajdhani', sans-serif;
            text-align: center;
            max-width: 560px;
            margin: 0 auto 22px;
        }}
        .guess-name {{
            color: #8dffb1;
            font: 800 clamp(27px, 5vw, 41px)/1.08 'Orbitron', sans-serif;
            text-align: center;
            text-shadow: 0 0 20px rgba(64, 255, 138, .45);
            margin: 5px 0 9px;
        }}
        .series-name {{
            color: #66e9ff;
            font: 700 clamp(17px, 3vw, 21px)/1.3 'Rajdhani', sans-serif;
            text-align: center;
            letter-spacing: .08em;
            margin-bottom: 22px;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 9px;
            flex-wrap: wrap;
            margin: 0 0 17px;
        }}
        .chip {{
            color: #8feeff;
            background: rgba(0, 156, 198, .13);
            border: 1px solid rgba(44, 221, 255, .3);
            border-radius: 999px;
            padding: 6px 11px;
            font: 700 12px/1 'Orbitron', sans-serif;
            letter-spacing: .04em;
        }}
        .stButton > button {{
            min-height: 48px;
            border-radius: 8px;
            color: white;
            font: 800 clamp(17px, 2.5vw, 21px)/1 'Rajdhani', sans-serif;
            letter-spacing: .05em;
            transition: transform .15s ease, filter .15s ease, box-shadow .15s ease;
        }}
        .stButton > button:hover {{
            transform: translateY(-2px);
            filter: brightness(1.12);
        }}
        .st-key-start_button button, .st-key-confirm_guess button,
        .st-key-play_again button, .st-key-answer_yes button {{
            border: 1px solid #8dff4a !important;
            background: linear-gradient(135deg, #07822e, #13b51f) !important;
            box-shadow: inset 0 0 16px rgba(160, 255, 90, .35), 0 0 16px rgba(85, 255, 62, .25);
        }}
        .st-key-answer_no button, .st-key-reject_guess button {{
            border: 1px solid #ff705c !important;
            background: linear-gradient(135deg, #a41b18, #dc2d1f) !important;
            box-shadow: inset 0 0 16px rgba(255, 95, 70, .3), 0 0 16px rgba(255, 46, 30, .22);
        }}
        /* Beveled neon answer blocks matching the supplied HUD reference. */
        .st-key-answer_yes button, .st-key-answer_no button {{
            position: relative;
            min-height: 48px;
            border-radius: 0 !important;
            border-width: 2px !important;
            clip-path: polygon(
                12px 0, calc(100% - 12px) 0,
                100% 12px, 100% calc(100% - 12px),
                calc(100% - 12px) 100%, 12px 100%,
                0 calc(100% - 12px), 0 12px
            );
            overflow: hidden;
            font-size: 18px;
            text-transform: none;
        }}
        .st-key-answer_yes button {{
            border-color: #9dff32 !important;
            background:
                linear-gradient(180deg, rgba(13, 183, 45, .98), rgba(0, 91, 24, .98)) !important;
            box-shadow:
                inset 0 0 20px rgba(86, 255, 74, .55),
                inset 0 2px 0 rgba(217, 255, 130, .75) !important;
            filter: drop-shadow(0 0 7px rgba(71, 255, 45, .48));
        }}
        .st-key-answer_no button {{
            border-color: #ff713d !important;
            background:
                linear-gradient(180deg, rgba(211, 42, 28, .98), rgba(117, 8, 9, .98)) !important;
            box-shadow:
                inset 0 0 20px rgba(255, 66, 38, .52),
                inset 0 2px 0 rgba(255, 166, 97, .7) !important;
            filter: drop-shadow(0 0 7px rgba(255, 48, 28, .43));
        }}
        .st-key-answer_yes button::before,
        .st-key-answer_no button::before {{
            content: "";
            position: absolute;
            inset: 5px;
            border: 1px solid rgba(255, 255, 255, .42);
            clip-path: polygon(
                8px 0, calc(100% - 8px) 0,
                100% 8px, 100% calc(100% - 8px),
                calc(100% - 8px) 100%, 8px 100%,
                0 calc(100% - 8px), 0 8px
            );
            pointer-events: none;
        }}
        .st-key-answer_yes button p, .st-key-answer_no button p {{
            position: relative;
            z-index: 1;
        }}
        .st-key-answer_yes button:hover {{
            filter: brightness(1.12) drop-shadow(0 0 9px rgba(71, 255, 45, .62));
        }}
        .st-key-answer_no button:hover {{
            filter: brightness(1.12) drop-shadow(0 0 9px rgba(255, 48, 28, .58));
        }}
        .st-key-answer_skip button {{
            min-height: 30px;
            border: 1px solid #39d6ff !important;
            background: linear-gradient(135deg, #0b3e5b, #075c77) !important;
            font-size: 12px;
        }}
        .st-key-undo_button button, .st-key-restart_button button {{
            min-height: 30px;
            color: #a9cbd7 !important;
            border: 1px solid rgba(91, 202, 230, .28) !important;
            background: rgba(5, 28, 39, .78) !important;
            font-size: 12px;
        }}
        [data-testid="stExpander"] {{
            border-color: rgba(65, 219, 255, .25);
            background: rgba(0, 19, 29, .65);
        }}
        @media (max-width: 520px) {{
            [data-testid="stAppViewContainer"] {{ background-attachment: scroll; }}
            [data-testid="stMainBlockContainer"] {{ padding-left: 10px; padding-right: 10px; }}
            .st-key-game_panel {{
                width: min(88vw, 370px);
                padding: 13px 11px !important;
                border-radius: 13px !important;
                box-shadow: inset 0 0 14px rgba(0, 190, 255, .1), 0 0 14px rgba(0, 218, 255, .18) !important;
            }}
            .stButton > button {{ min-height: 46px; }}
            .stButton > button:hover {{ transform: none; }}
            .st-key-answer_yes button,
            .st-key-answer_no button,
            .st-key-answer_yes button:hover,
            .st-key-answer_no button:hover {{ filter: none; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def chips(*items: str) -> None:
    content = "".join(f'<span class="chip">{html.escape(item)}</span>' for item in items)
    st.markdown(f'<div class="stats">{content}</div>', unsafe_allow_html=True)


try:
    characters, questions, difficulties, categories = load_game_data(
        str(DATA_FILE), DATA_FILE.stat().st_mtime_ns
    )
except (FileNotFoundError, ValueError) as error:
    st.error(f"Game data error: {error}")
    st.stop()

character_keys = tuple(sorted(characters))
series_counts: dict[str, int] = defaultdict(int)
for character_key in character_keys:
    series_counts[split_character_key(character_key)[0]] += 1

initialize_state(character_keys)
background_url = (
    THINKING_IMAGE_URL
    if st.session_state.screen == "welcome"
    else AWAKE_IMAGE_URL
)
install_theme(background_url)

st.markdown('<div class="art-space"></div>', unsafe_allow_html=True)

with st.container(key="game_panel", border=True):
    screen = st.session_state.screen

    if screen == "welcome":
        st.markdown('<div class="eyebrow">Neural link ready</div>', unsafe_allow_html=True)
        st.markdown('<div class="game-title">CHARACTER ORACLE</div>', unsafe_allow_html=True)
        chips(f"{len(character_keys)} CHARACTERS", f"{len(series_counts)} UNIVERSES")
        st.markdown(
            '<div class="intro">Think of a character from <b>One Piece</b> or '
            '<b>Haikyuu!!</b>. I will read your answers and discover who it is.</div>',
            unsafe_allow_html=True,
        )
        st.button(
            "BEGIN THE SCAN",
            key="start_button",
            use_container_width=True,
            on_click=start_game,
            args=(character_keys, characters, difficulties),
        )

    elif screen == "question":
        trait = st.session_state.current_trait
        question = questions.get(trait, "Is this true for your character?")
        if st.session_state.last_answer:
            answer = st.session_state.last_answer
            feedback_class = "yes" if answer == "YES" else "no"
            st.markdown(
                f'<div class="answer-feedback {feedback_class}">{answer} SELECTED</div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            f'<div class="question">{html.escape(question)}</div>',
            unsafe_allow_html=True,
        )
        yes_col, no_col = st.columns(2, gap="medium")
        with yes_col:
            st.button(
                "Yes",
                key="answer_yes",
                use_container_width=True,
                on_click=submit_answer,
                args=(True, characters, difficulties),
            )
        with no_col:
            st.button(
                "No",
                key="answer_no",
                use_container_width=True,
                on_click=submit_answer,
                args=(False, characters, difficulties),
            )

    elif screen == "guess":
        remaining = sorted(st.session_state.candidates)
        chips(
            f"{st.session_state.question_number} ANSWERS ANALYZED",
            "MATCH FOUND" if len(remaining) == 1 else f"{len(remaining)} POSSIBLE MATCHES",
        )
        if len(remaining) == 1:
            anime, character = split_character_key(remaining[0])
            st.markdown('<div class="eyebrow">My prediction is</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="guess-name">{html.escape(character)}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div class="series-name">{html.escape(anime)}</div>',
                unsafe_allow_html=True,
            )
            st.button(
                "RESTART GAME",
                key="play_again",
                use_container_width=True,
                on_click=start_game,
                args=(character_keys, characters, difficulties),
            )
        else:
            st.markdown(
                '<div class="question">The signal is too close to separate.</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Show remaining characters", expanded=True):
                for key in remaining:
                    anime, character = split_character_key(key)
                    st.write(f"• {character} — {anime}")
            st.button(
                "PLAY AGAIN",
                key="play_again",
                use_container_width=True,
                on_click=start_game,
                args=(character_keys, characters, difficulties),
            )

    elif screen == "success":
        key = next(iter(st.session_state.candidates))
        anime, character = split_character_key(key)
        st.markdown('<div class="eyebrow">Identity confirmed</div>', unsafe_allow_html=True)
        st.markdown('<div class="game-title">NEURAL MATCH</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="guess-name">{html.escape(character)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="series-name">{html.escape(anime)} · '
            f'{st.session_state.question_number} questions</div>',
            unsafe_allow_html=True,
        )
        st.button(
            "PLAY AGAIN",
            key="play_again",
            use_container_width=True,
            on_click=start_game,
            args=(character_keys, characters, difficulties),
        )

    else:  # no_match
        st.markdown('<div class="eyebrow">Signal lost</div>', unsafe_allow_html=True)
        st.markdown('<div class="game-title">NO EXACT MATCH</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="intro">One answer may be different, or your character may not '
            'be in the current database. Undo the last answer or begin a new scan.</div>',
            unsafe_allow_html=True,
        )
        st.button(
            "START A NEW SCAN",
            key="play_again",
            use_container_width=True,
            on_click=start_game,
            args=(character_keys, characters, difficulties),
        )
