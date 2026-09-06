# Neural Character Oracle

A Streamlit character-guessing game using the supplied One Piece and Haikyuu!!
dataset and sci-fi artwork.

## Run it

Open PowerShell in this folder and run:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

The browser should open automatically. If it does not, open the local address
shown in the terminal (normally `http://localhost:8501`).

## Files

- `streamlit_app.py` — complete game logic and interface
- `character_game_data_arcs.csv` — 300-character game database
- `.streamlit/config.toml` — enables Streamlit's static-file server
- `static/oracle_thinking.png` — welcome-screen artwork
- `static/oracle_game_clean.png` — gameplay/result artwork
