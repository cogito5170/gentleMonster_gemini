npm install -g @google/gemini-cli@0.60.0
gemini extensions uninstall gentlemonster ; true
gemini extensions install https://github.com/cogito5170/gentleMonster_gemini --ref PREVIEW_SHA --consent --skip-settings
python3 -m venv "$HOME/.gentlemonster/venv"
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet --upgrade pip
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet "$HOME/.gemini/extensions/gentlemonster[render]"
"$HOME/.gentlemonster/venv/bin/python3" -m playwright install chromium
"$HOME/.gentlemonster/venv/bin/gmg" setup
if [ -n "$GEMINI_API_KEY" ]; then echo "GEMINI_API_KEY is set"; else echo "GEMINI_API_KEY is NOT set: see USAGE.md step 1"; fi
"$HOME/.gentlemonster/venv/bin/gmg" doctor
