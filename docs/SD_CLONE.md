# SD 카드 복제 (운용 SD → USB 리더 SD)

운용 중인 라즈베리파이의 시스템 SD를 USB SD 리더에 꽂힌 SD 카드로 안전하게 복제하는 절차.

## 사용법

```bash
# USB SD 리더에 빈(또는 덮어써도 되는) SD 카드를 꽂는다
lsblk                                    # 대상 디바이스 확인 (보통 sdb)
sudo /home/gadgetini/L2A_CDU_system/scripts/clone-sd.sh sdb
```

29GB SD 기준 14~16분 소요. 도중 사용자 확인 프롬프트 한 번 (`Proceed? [y/N]`).

## 스크립트가 자동으로 처리하는 것

1. **안전 가드** — 대상이 운용 중인 디스크면 거부.
2. **rpi-clone 실행** — `sudo rpi-clone sdX -f -U` (파티션 재구성 + 새 PARTUUID 부여 + rsync).
3. **source /boot/firmware 재마운트** — rpi-clone 이 도중에 unmount 하는 경우가 있어 명시적으로 다시 마운트.
4. **boot 파티션 누락 보정** — dest 의 `/dev/sdX1` 가 비어있으면(`< 5 entries`) 수동 `rsync -aHAX --delete /boot/firmware/ → 대상` 재실행.
5. **cmdline.txt PARTUUID 정합** — `cmdline.txt` 의 `root=PARTUUID=…` 를 대상 `/etc/fstab` 의 새 PARTUUID 와 일치하도록 `sed` 치환.
6. **검증 출력** — 최종 `cmdline.txt`, `fstab`, `lsblk`, plymouth 테마(`l2a-cdu`) 존재 여부.

## 왜 이 보정이 필요한가

`rpi-clone -f -U` 만으로는 이 시스템에서 두 가지 문제가 발생함 (2026-05-11 검증):

| 문제 | 결과 |
|---|---|
| rpi-clone 실행 도중 source `/boot/firmware` 가 unmount 됨 | dest 의 boot 파티션 rsync 의 source 가 빈 디렉토리가 되어 dest `/dev/sdX1` 가 **완전히 빈 상태**로 끝남 → 커널/dtb/cmdline 통째로 누락 → 부팅 실패 (커스텀 로고도 당연히 미표시) |
| rpi-clone 은 dest `/etc/fstab` 의 PARTUUID 만 자동 치환 | dest `cmdline.txt` 의 `root=PARTUUID=…` 는 원본 값 그대로 남음 → fstab 과 불일치 → 부팅 시 root 디스크 식별 실패 (원본 SD 가 같이 꽂혀 있으면 잘못된 디스크에서 부팅) |

스크립트는 이 두 가지를 자동 감지/보정한다.

## 복제 후 첫 부팅 체크리스트

복제한 SD 를 라즈베리파이에 꽂고 부팅 시:

1. 커스텀 부팅 로고(plymouth 테마 `l2a-cdu`)가 표시되는지
2. 720x1280 DSI 디스플레이가 90도 회전 상태로 나오는지 (`cmdline.txt` 의 `video=DSI-1:720x1280M@60,rotate=90`)
3. 로그인 후 `findmnt /` 로 root 가 `/dev/mmcblk0p2` 인지

## 스크립트가 실패했을 때 — 수동 절차

```bash
DEST=sdb                                       # 대상 디바이스
sudo rpi-clone $DEST -f -U                     # 1) clone

sudo blockdev --rereadpt /dev/$DEST            # 2) 파티션 테이블 재인식
sudo partprobe /dev/$DEST

sudo mkdir -p /mnt/v_boot /mnt/v_root          # 3) 검증 마운트
sudo mount /dev/${DEST}1 /mnt/v_boot
sudo mount /dev/${DEST}2 /mnt/v_root

ls /mnt/v_boot | wc -l                         # 4) boot 비어있는지 확인
# 비어있으면:
sudo mount /boot/firmware                      #    source 재마운트
sudo rsync -aHAX --delete /boot/firmware/ /mnt/v_boot/

# 5) cmdline.txt PARTUUID 치환 (예: 5ae84638 → a7cfe5ee)
sudo grep PARTUUID /mnt/v_root/etc/fstab        # 새 PARTUUID 확인
sudo sed -i 's/PARTUUID=<OLD>-02/PARTUUID=<NEW>-02/g' /mnt/v_boot/cmdline.txt

sudo umount /mnt/v_boot /mnt/v_root && sync     # 6) 마무리
sudo rmdir /mnt/v_boot /mnt/v_root
```
