#!/usr/bin/env python3
"""Simple runner script for Media Toolkit."""

import sys
from pathlib import Path

def main():
    # Defaults
    data_dir = Path("./data")
    # Default to user requested directory (parent of GP_URL.md)
    source_dir = Path("/Users/joon/Documents/Obsidian/02_INBOX/_Hub/_Creative/GP/test") 
    port = 8080
    
    # Parse simple args
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print("""
Media Toolkit - 소셜 미디어 수집 + 범용 미디어 다운로더

사용법:
    python run.py [옵션]

옵션:
    --data DIR      데이터 저장 경로 (기본: ./data)
    --source DIR    MD 파일 경로 (기본: Obsidian 폴더)
    --port PORT     서버 포트 (기본: 8080)
    -h, --help      도움말 표시

예시:
    python run.py
    python run.py --data ./my_data --port 3000
""")
        return
    
    for i, arg in enumerate(args):
        if arg == "--data" and i + 1 < len(args):
            data_dir = Path(args[i + 1])
        elif arg == "--source" and i + 1 < len(args):
            source_dir = Path(args[i + 1])
        elif arg == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
    
    # Ensure data directory exists
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"""
╔══════════════════════════════════════════════════╗
║       Media Toolkit v0.2.0                       ║
╠══════════════════════════════════════════════════╣
║  데이터 경로: {str(data_dir):<35}║
║  소스 경로: {str(source_dir)[:35]:<37}║
║  서버: http://localhost:{port:<24}║
╚══════════════════════════════════════════════════╝
""")
    
    # Import and run
    try:
        from media_toolkit.viewer import run_server
        run_server(data_dir, source_dir=source_dir, host="0.0.0.0", port=port)
    except ImportError as e:
        print(f"❌ 모듈 import 실패: {e}")
        print("\n설치 명령어:")
        print("  pip install -e .")
        sys.exit(1)

if __name__ == "__main__":
    main()
