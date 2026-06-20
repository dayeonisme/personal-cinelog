# CINELOG 배포 (GCP Always Free VM + Tailscale)

Mac 가 꺼져 있어도, 다른 와이파이/셀룰러에서도 휴대폰으로 접속하기 위한 배포 방법.
GCP 무료 e2-micro VM 에 올리고, **Tailscale 사설망으로 내 기기에서만** 접근한다.
공개 인터넷에는 노출하지 않으므로 별도 로그인/HTTPS 가 필요 없다.

## 1. VM (기존 것 재사용)

이미 굴리는 Always Free e2-micro `cinelog-vm`(<ZONE>) 에 **함께 올린다.**
- **새 VM 만들지 말 것** — GCP Always Free 는 계정당 e2-micro 1대만 무료. 두 번째는 과금.
- existing-service 와 포트 충돌 없음(cinelog=5001). swap 으로 RAM 1GB 보호(아래 setup-vm.sh 가 자동).
- 방화벽: **5001 을 열지 않는다.** 앱은 Tailscale IP 에만 바인딩하므로 외부 IP 로는 애초에 안 뜸(이중 안전장치).

## 2. VM 안에서 Tailscale 설치 (3번보다 먼저!)

서비스가 Tailscale IP 에만 바인딩하므로, 이걸 먼저 올려야 3번 서비스가 뜬다.

```bash
gcloud compute ssh cinelog-vm --zone=<ZONE>   # Mac 에서 VM 접속
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up          # 출력된 링크를 브라우저에서 열어 로그인
tailscale ip -4            # 이 VM 의 100.x.x.x 주소 확인 (나중에 폰에서 사용)
```

## 3. 앱 배포

```bash
# VM 안에서
sudo apt-get install -y git
git clone <이 레포 URL> ~/movie-review
cd ~/movie-review
bash deploy/setup-vm.sh    # venv + 의존성 + swap + systemd 서비스(자동시작/재시작) 등록
```

`.env` 도 필요하다(TMDb 토큰). Mac 에서 복사:

```bash
# Mac 에서
gcloud compute scp .env cinelog-vm:~/movie-review/.env --zone=<ZONE>
```

## 4. 데이터(평가 DB + 업로드 이미지) 전송

DB·이미지는 `.gitignore` 라 clone 으로 안 따라온다. Mac 에서:

```bash
# Mac 에서, 레포 루트에서
deploy/push-data.sh cinelog-vm <ZONE>
# 그 뒤 VM 에서
sudo systemctl restart cinelog
```

## 5. 휴대폰에서 접속

1. App Store / Play 스토어에서 **Tailscale** 앱 설치 → VM 과 **같은 계정**으로 로그인
2. 브라우저에서 `http://<VM의 tailscale IP>:5001` 접속
   - 셀룰러든 다른 와이파이든 어디서나 접속됨
3. Safari → 공유 → "홈 화면에 추가" 하면 앱처럼 사용

## 보안 체크리스트 (내 기기끼리만 — 위험 차단)

앱에 로그인 기능이 없다. 그래서 "Tailscale 안에서만 보이게" 가 곧 보안이다. 아래 다 지켜야 안전:

1. **Tailscale IP 바인딩** — 서비스가 `100.x.x.x:5001` 에만 바인딩(외부 IP 에 안 뜸). 코드 손댈 필요 없음, [cinelog.service](cinelog.service) 에 반영됨.
2. **5001 방화벽 열지 않기** — GCP 방화벽에 5001 인바운드 규칙 만들지 말 것. 확인:
   ```bash
   # Mac 에서: 혹시 5001/전체개방 규칙 있는지 점검 (있으면 안 됨)
   gcloud compute firewall-rules list --format='table(name,allowed[].map().firewall_rule().list(),sourceRanges.list())'
   ```
3. **Tailscale 계정 2FA 켜기** — 이 계정이 사실상 유일한 열쇠. 뚫리면 끝. login.tailscale.com → Settings → 2FA.
4. (선택) **Tailscale ACL** 로 5001 접근을 내 기기 태그로만 더 좁힐 수 있음.

## 운영 메모

- **데이터 정본은 VM 한 곳.** Mac 로컬에서도 따로 실행하면 DB 가 갈라져 평가가 따로 쌓인다. Mac 에서도 위 tailscale 주소로 접속할 것.
- 서비스 관리: `sudo systemctl {status|restart|stop} cinelog`, 로그: `journalctl -u cinelog -f`
- 코드 업데이트: VM 에서 `git pull` 후 `sudo systemctl restart cinelog`
- gunicorn 이 Flask debug 없이 구동 → 디버거 노출 위험 없음.
- 부팅 직후 잠깐 cinelog 가 죽어있을 수 있음(Tailscale 올라오기 전엔 fail-closed 로 종료 후 재시도). 몇 초 뒤 자동 복구.
- RAM 부족(OOM) 시: swap 자동 생성됨. 그래도 모자라면 `journalctl -u cinelog` 에서 OOM 확인 → 최후수단 머신 e2-small 업그레이드(Always Free 깨짐).
