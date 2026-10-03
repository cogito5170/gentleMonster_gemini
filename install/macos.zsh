mkdir -p "$HOME/.gentlemonster/bin" "$HOME/.gentlemonster/cli"
npm install --prefix "$HOME/.gentlemonster/cli" --no-fund --no-audit @google/gemini-cli@0.60.0
"$HOME/.gentlemonster/cli/node_modules/.bin/gemini" extensions uninstall gentlemonster ; true
"$HOME/.gentlemonster/cli/node_modules/.bin/gemini" extensions install https://github.com/cogito5170/gentleMonster_gemini --ref PREVIEW_SHA --consent --skip-settings
cp "$HOME/.gemini/extensions/gentlemonster/install/gentlemonster" "$HOME/.gentlemonster/bin/gentlemonster"
chmod 755 "$HOME/.gentlemonster/bin/gentlemonster"
grep -qs 'gentlemonster/bin' "$HOME/.zshrc" || echo 'export PATH="$HOME/.gentlemonster/bin:$PATH"' | tee -a "$HOME/.zshrc"
export PATH="$HOME/.gentlemonster/bin:$PATH"
python3 -m venv "$HOME/.gentlemonster/venv"
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet --upgrade pip
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet "$HOME/.gemini/extensions/gentlemonster[render]"
"$HOME/.gentlemonster/venv/bin/python3" -m playwright install chromium
"$HOME/.gentlemonster/venv/bin/gmg" setup
if [ -n "$GEMINI_API_KEY" ]; then echo "GEMINI_API_KEY is set"; else echo "GEMINI_API_KEY is NOT set: see USAGE.md step 1"; fi
gentlemonster --version
"$HOME/.gentlemonster/venv/bin/gmg" doctor
