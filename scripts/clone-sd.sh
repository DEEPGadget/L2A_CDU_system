#!/usr/bin/env bash
# 라즈베리파이 운용 SD를 USB SD 리더에 꽂힌 SD로 안전 복제.
# rpi-clone 의 boot 파티션 누락 + cmdline.txt PARTUUID 미치환 이슈를 자동 보정.
# 자세한 배경/수동 절차는 docs/SD_CLONE.md 참조.
#
# 사용: sudo ./clone-sd.sh sdX     (예: sudo ./clone-sd.sh sdb)

set -euo pipefail

DEST="${1:-}"
if [[ -z "$DEST" || "$DEST" != sd* ]]; then
    echo "Usage: sudo $0 sdX (e.g., sdb)" >&2
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

# rpi-clone 이 source /boot/firmware 를 unmount 해버리는 경우가 있어 재마운트
if ! findmnt -q /boot/firmware; then
    echo ">>> Re-mounting source /boot/firmware (rpi-clone left it unmounted)..."
    mount /boot/firmware
fi

# 대상 파티션 테이블 재인식
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

# boot 파티션 누락 보정 (rpi-clone 의 알려진 실패 모드)
BOOT_COUNT=$(find "$TMP_BOOT" -maxdepth 1 -mindepth 1 | wc -l)
if [[ "$BOOT_COUNT" -lt 5 ]]; then
    echo ">>> Dest boot partition is empty/incomplete ($BOOT_COUNT entries). Running manual rsync..."
    rsync -aHAX --delete /boot/firmware/ "$TMP_BOOT/"
    sync
fi

# cmdline.txt 의 root=PARTUUID 를 fstab 의 새 PARTUUID 와 정합
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
