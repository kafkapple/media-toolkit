
import json
import shutil
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.media_toolkit.storage.db import Database
from src.media_toolkit.storage.models import Post

def migrate():
    root_dir = Path("data")
    if not root_dir.exists():
        print("Data directory not found!")
        return

    posts_dir = root_dir / "posts"
    backup_dir = root_dir / "posts_json_backup"
    
    print(f"Migrating posts from {posts_dir}...")
    
    # 1. Create backup directory
    backup_dir.mkdir(exist_ok=True)
    
    # 2. Find all JSON files
    json_files = list(posts_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found to migrate.")
        return

    print(f"Found {len(json_files)} JSON files. Backing up...")
    
    # 3. Process each file
    db = Database(root_dir.parent) # Database expects root of the project (or wherever data dir is relative to)
    # Actually Database constructor takes data_dir directly? 
    # Let's check db.py: def __init__(self, data_dir: Path): self.data_dir = Path(data_dir) self.posts_dir = ...
    # So if we pass the project root, it expects data usually to be passed in. 
    # But usually in main.py it's initialized with `Path("data")` or something.
    # In db.py: self.posts_dir = self.data_dir / "posts".
    # So if we pass `Path("data")`, posts_dir is `data/posts`. Correct.
    
    db = Database(root_dir) 
    
    count = 0
    for json_file in json_files:
        try:
            # Read JSON
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate Post
            post = Post.model_validate(data)
            
            # Save as MD (this handles frontmatter conversion)
            db.save_post(post)
            
            # Move JSON to backup
            shutil.move(str(json_file), str(backup_dir / json_file.name))
            
            count += 1
            print(f"Migrated {post.id}")
            
        except Exception as e:
            print(f"Failed to migrate {json_file.name}: {e}")
    
    print(f"\nMigration complete. {count} posts migrated.")
    print(f"Original JSON files moved to {backup_dir}")
    
    # Force static data export just in case
    db.export_static_data()
    print("Static data exported to data/data.js")

if __name__ == "__main__":
    migrate()
