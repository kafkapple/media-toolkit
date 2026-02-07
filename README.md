# Media Toolkit

소셜 미디어 수집 파이프라인 + 범용 미디어 다운로더를 통합한 도구.

## Features

### Mode 1: Social Media Collection Pipeline
- **URL Parsing**: Obsidian MD 파일에서 소셜 미디어 URL 자동 추출
- **Validation**: URL 접근 가능 여부 확인 (공개/비공개/삭제 분류)
- **Scraping**: 게시물 메타데이터 추출 (게시자, 날짜, 내용, 조회수 등)
- **Download**: 멀티미디어 파일 다운로드 (yt-dlp 활용)
- **Storage**: Markdown frontmatter 기반 로컬 데이터베이스
- **Viewer**: 인터랙티브 웹 뷰어 (FastAPI, 포트 8080)

### Mode 2: General Media Downloader
- **Video Extraction**: yt-dlp 기반 1000+ 사이트 비디오 추출
- **Image Extraction**: cloudscraper + BeautifulSoup 웹 이미지 스크래핑
- **Streamlit UI**: 브라우저 기반 미디어 다운로드 인터페이스
- **Bot Protection Bypass**: Cloudflare 등 자동 우회

## Supported Platforms

| Platform  | Status | Notes |
|-----------|--------|-------|
| Instagram | ✅     | Reels, Posts, Stories |
| Facebook  | ✅     | Videos, Reels, Shares |
| Threads   | ✅     | Posts |
| LinkedIn  | ✅     | Posts, Pulse |
| YouTube   | ✅     | Videos, Playlists (via yt-dlp) |
| 1000+ sites | ✅  | Any yt-dlp supported site |

## Installation

### Prerequisites

- Python 3.10+
- [Conda](https://docs.conda.io/en/latest/) (recommended)

### Setup

```bash
# Clone repository
git clone https://github.com/yourusername/media-toolkit.git
cd media-toolkit

# Create conda environment
conda env create -f environment.yaml
conda activate media-toolkit

# Or use pip
pip install -e .
```

## Quick Start

### Social Media Collection (FastAPI)

```bash
pip install -e .
python run.py
```

브라우저에서 **http://localhost:8080** 접속 후:
1. **Step 1**: 소스 경로 설정 (MD 파일 폴더)
2. **Step 2**: MD 파일 스캔
3. **Step 3**: 정보 조회 시작

### General Media Downloader (Streamlit)

```bash
streamlit run src/media_toolkit/app/streamlit_app.py
```

URL 입력 → Analyze → 항목 선택 → Download

### 옵션 지정

```bash
python run.py --data ./my_data --source /path/to/md/files --port 3000
```

## Configuration

Configuration is managed via [Hydra](https://hydra.cc/). Edit `conf/config.yaml`:

```yaml
input:
  source_dir: /path/to/your/md/files
  file_pattern: "*.md"

output:
  data_dir: ./data
  download_media: true

scraper:
  timeout: 30
  concurrent_requests: 5
```

## Project Structure

```
media-toolkit/
├── conf/                        # Hydra configuration
├── src/media_toolkit/
│   ├── parser/                  # MD file parsing
│   ├── validator/               # URL validation
│   ├── scraper/                 # Platform-specific metadata
│   ├── extractor/               # General media extraction (yt-dlp, web images)
│   ├── downloader/              # Media download (social + general)
│   ├── storage/                 # Data persistence (Pydantic + Markdown)
│   ├── viewer/                  # FastAPI web interface
│   ├── app/                     # Streamlit UI
│   └── utils/                   # Common utilities
├── data/                        # Generated data (gitignored)
├── tests/                       # Unit tests
└── docs/                        # Documentation
```

## License

MIT License
