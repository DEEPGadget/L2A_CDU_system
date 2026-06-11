#!/usr/bin/env bash
# Safely clone the running Raspberry Pi SD to an SD in a USB SD reader.
# Auto-fixes rpi-clone's missing boot partition + unsubstituted cmdline.txt PARTUUID.
# See docs/SD_CLONE.md for background and the manual procedure.
#
# Usage: sudo ./clone-sd.sh sdX     (e.g. sudo ./clone-sd.sh sdb)

set -euo pipefail

DEST="${1:-}"
# Accept a disk name only (sda, sdb, ...). Reject partition names like sdb1.
if [[ -z "$DEST" || ! "$DEST" =~ ^sd[a-z]+$ ]]; then
    if [[ "$DEST" =~ ^sd[a-z]+[0-9]+$ ]]; then
        echo "ERROR: '$DEST' is a partition name. Use the whole disk (e.g., ${DEST%%[0-9]*})." >&2
    else
        echo "Usage: sudo $0 sdX (e.g., sdb)" >&2
    fi
    exit 1
fi
if [[ $EUID -ne 0 ]]; then
    echo "Must run as root (use sudo)." >&2
    exit 1
fi

DEST_DEV="/dev/${DEST}"
DEST_P1="${DEST_DEV}1"
DEST_P2="${DEST_DEV}2"

ROOT_SRC=$(findmnt -no SOURCE /)
BOOT_SRC=$(findmnt -no SOURCE /boot/firmware)
ROOT_DISK=$(lsblk -no PKNAME "$ROOT_SRC")
if [[ "$DEST" == "$ROOT_DISK" ]]; then
    echo "ERROR: $DEST_DEV is the running disk ($ROOT_DISK). Refusing." >&2
    exit 1
fi
if [[ ! -b "$DEST_DEV" ]]; then
    echo "ERROR: $DEST_DEV is not a block device." >&2
    exit 1
fi

echo "Source : $ROOT_SRC (/) + $BOOT_SRC (/boot/firmware)"
echo "Dest   : $DEST_DEV"
lsblk "$DEST_DEV"
echo
read -rp "All data on $DEST_DEV will be ERASED. Proceed? [y/N] " ans
[[ "$ans" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 1; }

echo ">>> Running rpi-clone (force init, unattended)..."
/usr/local/sbin/rpi-clone "$DEST" -f -U

# rpi-clone sometimes unmounts the source /boot/firmware — re-mount it.
# (findmnt has no -q on this build; `|| true` so an already-mounted source
#  doesn't abort the script under `set -e` before the cmdline.txt fix below.)
if ! findmnt /boot/firmware >/dev/null 2>&1; then
    echo ">>> Re-mounting source /boot/firmware (rpi-clone left it unmounted)..."
    mount /boot/firmware || true
fi

# Re-read the destination partition table.
blockdev --rereadpt "$DEST_DEV" || true
partprobe "$DEST_DEV" || true
sleep 1

TMP_BOOT=$(mktemp -d)
TMP_ROOT=$(mktemp -d)
cleanup() {
    umount -q "$TMP_BOOT" 2>/dev/null || true
    umount -q "$TMP_ROOT" 2>/dev/null || true
    rmdir "$TMP_BOOT" "$TMP_ROOT" 2>/dev/null || true
}
trap cleanup EXIT

mount "$DEST_P1" "$TMP_BOOT"
mount "$DEST_P2" "$TMP_ROOT"

# Fix the missing boot partition (a known rpi-clone failure mode).
BOOT_COUNT=$(find "$TMP_BOOT" -maxdepth 1 -mindepth 1 | wc -l)
if [[ "$BOOT_COUNT" -lt 5 ]]; then
    echo ">>> Dest boot partition is empty/incomplete ($BOOT_COUNT entries). Running manual rsync..."
    rsync -aHAX --delete /boot/firmware/ "$TMP_BOOT/"
    sync
fi

# Align cmdline.txt's root=PARTUUID with fstab's new PARTUUID.
NEW_UUID=$(grep -oE 'PARTUUID=[a-f0-9]{8}' "$TMP_ROOT/etc/fstab" | head -1 | cut -d= -f2)
OLD_UUID=$(grep -oE 'PARTUUID=[a-f0-9]{8}' "$TMP_BOOT/cmdline.txt" | head -1 | cut -d= -f2)
if [[ -n "$NEW_UUID" && -n "$OLD_UUID" && "$OLD_UUID" != "$NEW_UUID" ]]; then
    echo ">>> Fixing cmdline.txt PARTUUID: $OLD_UUID -> $NEW_UUID"
    sed -i "s/PARTUUID=${OLD_UUID}/PARTUUID=${NEW_UUID}/g" "$TMP_BOOT/cmdline.txt"
    sync
fi

echo
echo "=== final cmdline.txt ==="
cat "$TMP_BOOT/cmdline.txt"
echo
echo "=== final fstab (PARTUUID lines) ==="
grep PARTUUID "$TMP_ROOT/etc/fstab"
echo
echo "=== dest layout ==="
lsblk -o NAME,SIZE,FSTYPE,LABEL,PARTUUID "$DEST_DEV"
echo
echo "=== plymouth custom theme check ==="
if [[ -d "$TMP_ROOT/usr/share/plymouth/themes/l2a-cdu" ]]; then
    echo "OK: l2a-cdu theme present on dest rootfs"
else
    echo "WARN: l2a-cdu theme NOT found on dest rootfs"
fi
echo
echo ">>> Clone complete. Safe to remove $DEST_DEV after this script exits."
