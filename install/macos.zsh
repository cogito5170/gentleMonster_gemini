mkdir -p "$HOME/.gentlemonster/bin" "$HOME/.gentlemonster/cli" "$HOME/.gentlemonster/cli-home"
npm install --prefix "$HOME/.gentlemonster/cli" --no-fund --no-audit @google/gemini-cli@0.62.0
GEMINI_CLI_HOME="$HOME/.gentlemonster/cli-home" "$HOME/.gentlemonster/cli/node_modules/.bin/gemini" extensions uninstall gentlemonster ; true
GEMINI_CLI_HOME="$HOME/.gentlemonster/cli-home" "$HOME/.gentlemonster/cli/node_modules/.bin/gemini" extensions install https://github.com/cogito5170/gentleMonster_gemini --ref d0854c8c74c107c7aabc15fadb7aeaf779a43406 --consent --skip-settings
cp "$HOME/.gentlemonster/cli-home/.gemini/extensions/gentlemonster/install/gentlemonster" "$HOME/.gentlemonster/bin/gentlemonster"
chmod 755 "$HOME/.gentlemonster/bin/gentlemonster"
grep -qs 'gentlemonster/bin' "$HOME/.zshrc" || echo 'export PATH="$HOME/.gentlemonster/bin:$PATH"' | tee -a "$HOME/.zshrc"
export PATH="$HOME/.gentlemonster/bin:$PATH"
python3 -m venv "$HOME/.gentlemonster/venv"
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet --upgrade pip
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet "$HOME/.gentlemonster/cli-home/.gemini/extensions/gentlemonster[render]"
"$HOME/.gentlemonster/venv/bin/python3" -m playwright install chromium
"$HOME/.gentlemonster/venv/bin/gmg" setup
if [ -n "$GEMINI_API_KEY" ]; then echo "GEMINI_API_KEY is set"; else echo "GEMINI_API_KEY is NOT set: see USAGE.md step 1"; fi
gentlemonster --version
"$HOME/.gentlemonster/venv/bin/gmg" doctor
