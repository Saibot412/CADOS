#!/bin/sh
set -eu
pid="$1"
dmg="$2"
target="$3"
version="$4"
mount_dir="$(mktemp -d /private/tmp/cados-mount.XXXXXX)"
stage=''
backup=''
installed=0
moved=0
cleanup() {
  if [ "$installed" -eq 0 ]; then
    if [ "$moved" -eq 1 ] && [ -d "$backup" ]; then
      if [ -e "$target" ]; then rm -rf "$target"; fi
      mv "$backup" "$target"
    fi
    /usr/bin/open "$dmg" || true
  fi
  /usr/bin/hdiutil detach "$mount_dir" -quiet || true
  rmdir "$mount_dir" || true
  if [ -n "$stage" ] && [ -d "$stage" ]; then rm -rf "$stage"; fi
}
trap cleanup EXIT
# Wait for BLE connections and recording workers to shut down first.
attempt=0
while kill -0 "$pid" 2>/dev/null; do
  attempt=$((attempt + 1))
  [ "$attempt" -le 60 ] || exit 1
  sleep 1
done
/usr/bin/hdiutil attach "$dmg" -readonly -nobrowse -mountpoint "$mount_dir" -quiet
source_app="$mount_dir/CADOS Connector.app"
[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$source_app/Contents/Info.plist")" = 'local.cados.connector' ]
[ "$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$source_app/Contents/Info.plist")" = "$version" ]
/usr/bin/codesign --verify --deep --strict "$source_app"
parent="$(dirname "$target")"
stage="$(mktemp -d "$parent/.cados-update.XXXXXX")"
/usr/bin/ditto "$source_app" "$stage/CADOS Connector.app"
/usr/bin/codesign --verify --deep --strict "$stage/CADOS Connector.app"
backup="$target.previous"
[ ! -e "$backup" ] || exit 1
mv "$target" "$backup"
moved=1
mv "$stage/CADOS Connector.app" "$target"
/usr/bin/open "$target"
installed=1
# The verified installation is in place; keep download and installer log for diagnosis.
rm -rf "$backup"
