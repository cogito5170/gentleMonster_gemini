command -v agy || curl -fsSL https://antigravity.google/cli/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
agy --version
agy -p "/usage"
mkdir -p "$HOME/.gentlemonster/bin"
test -d "$HOME/.gentlemonster/ext/.git" || git clone -q https://github.com/cogito5170/gentleMonster_gemini "$HOME/.gentlemonster/ext"
git -C "$HOME/.gentlemonster/ext" fetch -q --depth 1 origin 62af1a5d85ef026e8c83036441a2369ef587f78d
git -C "$HOME/.gentlemonster/ext" checkout -q 62af1a5d85ef026e8c83036441a2369ef587f78d
python3 -m venv "$HOME/.gentlemonster/venv"
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet --upgrade pip
"$HOME/.gentlemonster/venv/bin/python3" -m pip install --quiet -e "$HOME/.gentlemonster/ext[render]"
"$HOME/.gentlemonster/venv/bin/python3" -m playwright install chromium
"$HOME/.gentlemonster/venv/bin/gmg" setup
cp "$HOME/.gentlemonster/ext/install/gentlemonster-agy" "$HOME/.gentlemonster/bin/gentlemonster-agy"
chmod 755 "$HOME/.gentlemonster/bin/gentlemonster-agy"
grep -qs 'gentlemonster/bin' "$HOME/.zshrc" || echo 'export PATH="$HOME/.gentlemonster/bin:$PATH"' | tee -a "$HOME/.zshrc"
export PATH="$HOME/.gentlemonster/bin:$PATH"
gentlemonster-agy --version
"$HOME/.gentlemonster/venv/bin/gmg" doctor --host agy
gentlemonster-agy --check
