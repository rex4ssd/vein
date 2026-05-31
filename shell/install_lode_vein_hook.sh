#!/usr/bin/env bash
# install_lode_vein_hook.sh
# 在 Lode 專案裝 post-commit hook，每次 commit 後問要不要 vein log
set -euo pipefail

LODE_DIR="/Users/lion/Documents/lode"
HOOK_PATH="$LODE_DIR/.git/hooks/post-commit"

if [ ! -d "$LODE_DIR/.git" ]; then
  echo "❌ 找不到 $LODE_DIR/.git — 確認 Lode 路徑正確"
  exit 1
fi

cat > "$HOOK_PATH" << 'EOF'
#!/usr/bin/env bash
# post-commit: prompt to log to .vein/ via vein
LODE_DIR="/Users/lion/Documents/lode"
MSG=$(git log -1 --pretty=%B | head -1)

echo ""
echo "📝 vein log? [d]ecision / [l]ore / [p]itfall / Enter=skip"
printf "   %s\n" "$MSG"
read -r -p "> " CHOICE </dev/tty

case "$CHOICE" in
  d) cd "$LODE_DIR" && vein log decision "$MSG" --no-polish --yes ;;
  l) cd "$LODE_DIR" && vein log lore "$MSG" --no-polish --yes ;;
  p) cd "$LODE_DIR" && vein log pitfall "$MSG" --no-polish --yes ;;
  *) ;;
esac
EOF

chmod +x "$HOOK_PATH"
echo "✓ Hook installed: $HOOK_PATH"
echo "  下次 git commit 後會看到 vein log 提示"
