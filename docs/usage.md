# Media Toolkit 사용 가이드

## 빠른 시작

### 1. 설치 및 실행

```bash
# 프로젝트 디렉토리로 이동
cd /Users/joon/dev/media-toolkit

# Conda 환경 생성 (최초 1회)
conda env create -f environment.yaml
conda activate media-toolkit
pip install -e .

# 뷰어 실행
python run.py
```

브라우저에서 **http://localhost:8080** 접속

---

## 워크플로우 (3단계)

### Step 1. 소스 경로 설정

사이드바 상단에서 MD 파일이 있는 폴더 경로를 입력합니다.

- 기본값: `/Users/joon/Documents/Obsidian/02_INBOX/_Hub/_Creative/GP`
- 경로 입력 후 **[저장]** 버튼 클릭

### Step 2. MD 파일 스캔

**[📥 MD 파일 스캔]** 버튼을 클릭합니다.

- MD 파일에서 Instagram, Facebook 등 소셜 미디어 URL 추출
- 새로 발견된 URL 수 표시
- 중복 URL 자동 필터링

### Step 3. URL 정보 조회

**[🔍 정보 조회 시작]** 버튼을 클릭합니다.

1. **URL 검증**: 각 URL의 접근 가능 여부 확인
2. **메타데이터 수집**: 게시자, 조회수, 좋아요 등 정보 추출

---

## 접근 불가 URL 관리

비공개/삭제된 URL이 발견되면 사이드바에 **⚠️ 접근 불가 URL** 알림이 표시됩니다.

- **[📋 목록 보기]**: 상세 목록 확인
- **[📥 CSV 내보내기]**: 파일로 저장하여 정리

상단 통계 바에서 **비공개/삭제됨** 숫자를 클릭하면 해당 상태로 필터링됩니다.

---

## 필터 및 검색

| 필터 | 설명 |
|------|------|
| **상태** | 접근가능 / 비공개 / 삭제됨 / 대기중 |
| **플랫폼** | Instagram / Facebook 등 |
| **게시자** | 특정 계정별 필터 |
| **검색** | 내용, URL, 제목 검색 |

---

## 파일 구조

```
data/
├── posts/            # 각 게시물 JSON 데이터
├── media/            # 다운로드된 미디어
│   └── [게시자명]/    # 게시자별 폴더 자동 생성
│       └── [제목-ID].jpg
├── thumbnails/       # 썸네일 이미지
├── index.json        # 빠른 검색용 인덱스
└── stats.json        # 통계 정보
```

## 고급 기능

### 🔐 인증 설정 (Facebook/Instagram 등)
로그인이 필요한 게시물(비공개 그룹, 친구 공개 등)을 다운로드하려면:
1. 웹 뷰어 우측 상단 **[⚙️ 설정]** 클릭.
2. **인증 방식**을 `Browser Cookies`로 선택.
3. 로그인된 브라우저(Chrome 등) 선택 후 저장.
4. 서버 재시작 필수.

### 📊 통계 및 정렬
- 좌측 상단 **[📊]** 버튼으로 게시자별 랭킹 및 플랫폼 통계 확인.
- 리스트 뷰 헤더 클릭으로 **날짜/조회수/좋아요** 정렬 가능.

### 📂 로컬 파일 관리
- 게시자별 필터: 검색 및 다중 선택 지원.
- 다운로드 완료된 항목은 **[📂]** 버튼을 눌러 내 컴퓨터의 폴더를 바로 열 수 있습니다.

---

## CLI 사용

### 개별 명령어

```bash
# URL 스캔만 실행
python -m media_toolkit.cli scan /path/to/md/files

# URL 검증
python -m media_toolkit.cli validate

# 메타데이터 수집
python -m media_toolkit.cli scrape

# 전체 파이프라인
python -m media_toolkit.cli process-all
```

---

## 문제 해결

### yt-dlp 오류
```bash
pip install --upgrade yt-dlp
```

### 인코딩 오류
MD 파일이 UTF-8 형식인지 확인하세요.

### 권한 오류
data 디렉토리에 쓰기 권한이 있는지 확인하세요.
