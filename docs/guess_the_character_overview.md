# Neural Character Oracle — Project Overview

## Executive summary

Neural Character Oracle is a browser-based character-guessing game built with Streamlit. The player thinks of a character from **One Piece** or **Haikyuu!!**, answers a sequence of factual yes/no questions, and receives the system's best matching character.

Although the interface uses a futuristic “neural oracle” theme, the prediction engine is deterministic. It does not call a generative-AI service. Instead, it narrows a curated local character dataset by selecting questions that efficiently separate the remaining candidates.

## Video demonstration

[Guess the Character demo](https://drive.google.com/file/d/17kcpr1GYMkoraQoTyxGjLmZ6Ji0nLlZo/view?usp=sharing)

## User experience

1. The welcome screen presents the supported character universes and starts a new scan.
2. The system asks one factual yes/no question at a time.
3. Each answer filters the remaining candidates according to their recorded traits.
4. Question selection adapts to the current candidate set.
5. When one candidate remains, the application displays the predicted character and series.
6. If the available facts cannot produce a unique match, the system presents the remaining possibilities instead of claiming false certainty.
7. The player can restart the experience and play again.

## Dataset

The verified dataset contains:

| Measure | Value |
|---|---:|
| Supported series | 2 |
| Playable characters | 300 |
| One Piece characters | 150 |
| Haikyuu!! characters | 150 |
| Character-trait records | 2,195 |
| Unique traits | 763 |

Each record links a character to a normalized trait and a human-readable question. The dataset also stores the series, category, difficulty, and supporting source note.

Representative categories include gender, affiliation, role, team, school, position, story or arc appearance, fighting style, Haki, Devil Fruit, species, and signature facts.

## Prediction logic

### Candidate filtering

At the beginning of a game, all 300 characters are possible candidates. A **Yes** answer keeps characters associated with the current trait; a **No** answer keeps characters without that trait.

### Adaptive question selection

For every unused trait, the engine calculates how many remaining candidates would answer Yes and how many would answer No. Traits that cannot reduce the candidate set are ignored.

The engine favors a question that divides the remaining candidates as evenly as possible. Easy and medium facts are preferred, while hard or highly specific clues are reserved for cases where broader facts are no longer useful. The opening question uses the dataset's common gender trait when it can divide the full set.

### Honest stopping behavior

- If one candidate remains, the system displays that character.
- If no unused trait can separate the remaining candidates, the system shows the possible matches rather than fabricating a result.
- If filtering removes every candidate, the interface explains that an answer may differ from the dataset or that the selected character may not be covered.

This behavior makes the outcome explainable: every prediction follows directly from the player's answers and the stored character facts.

## Technology and architecture

| Area | Technology or approach |
|---|---|
| User interface | Streamlit |
| Application language | Python |
| Dataset | UTF-8 CSV |
| State management | Streamlit session state |
| Selection algorithm | Deterministic candidate partitioning |
| Data loading | Cached CSV transformation |
| Visual design | Responsive custom theme and static artwork |

The application loads the long-form CSV into in-memory character and trait structures. Data loading is cached, while each player's candidates, question history, and current screen remain isolated in that user's Streamlit session.

## AI disclosure

The game does **not** use a large language model, external inference service, or model API key for its predictions. “Neural” is part of the visual concept and product presentation; the underlying engine uses deterministic rules and curated data.

This design provides several benefits:

- repeatable results for the same answer sequence;
- no inference cost;
- fast local decision-making;
- no transmission of player answers to an AI provider;
- predictions that can be traced to specific traits.

## Privacy and security

- No account or personal profile is required for the core game.
- Player answers are stored only in the active Streamlit session.
- The prediction process does not require an external API call.
- The application validates required dataset columns before starting.
- User-visible text derived from data is HTML-escaped before custom rendering.

Standard hosting logs and platform-level analytics may still be collected by the chosen deployment provider and should be covered by the deployment's privacy notice.

## Validation snapshot

The latest documentation review verified:

- successful Python syntax compilation;
- all required dataset columns are present;
- zero blank playable records;
- zero traits with conflicting question wording;
- 300 unique characters across two series;
- 763 unique traits across 2,195 records.

## Limitations

- Predictions are limited to the 300 characters represented in the dataset.
- Incorrect, ambiguous, or subjective answers can lead to the wrong candidate.
- Character facts and story status can change as the source series continues.
- Dataset completeness and source accuracy directly affect prediction quality.
- Binary questions cannot represent every nuanced or uncertain character attribute.
- The current release supports One Piece and Haikyuu!! only.

## Content and intellectual-property notice

Neural Character Oracle is an independent fan-made portfolio project. One Piece, Haikyuu!!, their characters, and related marks and artwork belong to their respective rights holders. The project is not affiliated with, sponsored by, or endorsed by those rights holders.

Before commercial distribution, the project owner should review permissions and licenses for every image, character fact, source reference, font, and third-party asset.

## Local execution

The current application implementation is maintained on the repository's [`dev` branch](https://github.com/AnasALAshi24/Guess-the-character/tree/dev). After checking out that branch, run:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

The application reads `character_game_data_arcs.csv` from the project directory and uses the configured Streamlit static-file support for its interface artwork.
