"""Main CLI entry point for Media Toolkit."""

import asyncio
from pathlib import Path
from datetime import datetime

import hydra
from omegaconf import DictConfig
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from .parser import scan_directory, detect_duplicates
from .validator import URLValidator, URLStatus
from .scraper import scrape_url
from .downloader import MediaDownloader
from .storage import Database, Post, Platform
from .storage.models import PostStatus
from .viewer import run_server

console = Console()


@hydra.main(version_base=None, config_path="../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    """Main entry point."""
    console.print("[bold blue]Media Toolkit[/bold blue]")
    console.print()
    
    # Run the full pipeline
    asyncio.run(run_pipeline(cfg))


async def run_pipeline(cfg: DictConfig) -> None:
    """Run the full collection pipeline."""
    
    source_dir = Path(cfg.input.source_dir)
    data_dir = Path(cfg.output.data_dir)
    
    console.print(f"[cyan]Source directory:[/cyan] {source_dir}")
    console.print(f"[cyan]Data directory:[/cyan] {data_dir}")
    console.print()
    
    # Initialize components
    db = Database(data_dir)
    downloader = MediaDownloader(
        media_dir=data_dir / "media",
        thumbnails_dir=data_dir / "thumbnails",
        thumbnail_size=tuple(cfg.output.thumbnail_size),
    )
    validator = URLValidator(
        timeout=cfg.validator.timeout,
    )
    
    # Step 1: Parse MD files
    console.print("[bold]Step 1: Parsing MD files[/bold]")
    
    collection = scan_directory(
        source_dir,
        pattern=cfg.input.file_pattern,
        recursive=cfg.input.recursive,
    )
    
    console.print(f"  Found [green]{len(collection)}[/green] URLs in [green]{len(collection.source_files)}[/green] files")
    
    # Check for duplicates
    duplicates = detect_duplicates(collection.urls)
    if duplicates:
        console.print(f"  [yellow]Warning:[/yellow] Found {duplicates.total_duplicates} duplicate URLs")
    
    # Get unique URLs
    unique_urls = collection.unique_urls()
    console.print(f"  Processing [green]{len(unique_urls)}[/green] unique URLs")
    console.print()
    
    # Step 2: Filter already processed
    new_urls = [u for u in unique_urls if not db.exists(u.id)]
    console.print(f"[bold]Step 2: Filtering[/bold]")
    console.print(f"  Already in DB: {len(unique_urls) - len(new_urls)}")
    console.print(f"  New URLs: [green]{len(new_urls)}[/green]")
    console.print()
    
    if not new_urls:
        console.print("[yellow]No new URLs to process.[/yellow]")
        show_stats(db)
        return
    
    # Step 3: Validate URLs
    console.print("[bold]Step 3: Validating URLs[/bold]")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Validating...", total=len(new_urls))
        
        validation_results = {}
        for url_obj in new_urls:
            result = await validator.validate(url_obj.url)
            validation_results[url_obj.id] = result
            progress.advance(task)
            
            # Rate limiting
            await asyncio.sleep(cfg.scraper.delay_min)
    
    # Count by status
    status_counts = {}
    for result in validation_results.values():
        status = result.status.value
        status_counts[status] = status_counts.get(status, 0) + 1
    
    console.print(f"  Validation results: {status_counts}")
    console.print()
    
    # Step 4: Scrape accessible URLs
    console.print("[bold]Step 4: Scraping metadata[/bold]")
    
    accessible_urls = [
        u for u in new_urls 
        if validation_results[u.id].status == URLStatus.ACCESSIBLE
    ]
    
    console.print(f"  Scraping [green]{len(accessible_urls)}[/green] accessible URLs")
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping...", total=len(accessible_urls))
        
        for url_obj in accessible_urls:
            try:
                scrape_result = await scrape_url(
                    url_obj.url,
                    timeout=cfg.scraper.timeout,
                )
                
                # Create post object
                post = Post(
                    id=url_obj.id,
                    url=url_obj.url,
                    platform=Platform(url_obj.platform),
                    author=scrape_result.author,
                    author_url=scrape_result.author_url,
                    title=scrape_result.title,
                    content=scrape_result.content,
                    posted_at=scrape_result.posted_at,
                    status=PostStatus.ACCESSIBLE if scrape_result.success else PostStatus.FAILED,
                    scraped_at=datetime.now(),
                    validated_at=validation_results[url_obj.id].validated_at,
                    views=scrape_result.views,
                    likes=scrape_result.likes,
                    comments=scrape_result.comments,
                    shares=scrape_result.shares,
                    thumbnail_url=scrape_result.thumbnail_url,
                    media_urls=scrape_result.media_urls,
                    media_type=scrape_result.media_type,
                    source_file=str(url_obj.source_file),
                    source_context=url_obj.context,
                    error_message=scrape_result.error_message,
                )
                
                # Download thumbnail
                if cfg.output.download_media and scrape_result.thumbnail_url:
                    thumb_path = await downloader.download_thumbnail_only(
                        url_obj.url, 
                        url_obj.id,
                    )
                    if thumb_path:
                        post.thumbnail_path = thumb_path
                
                db.save_post(post)
                
            except Exception as e:
                console.print(f"  [red]Error scraping {url_obj.url}: {e}[/red]")
            
            progress.advance(task)
            await asyncio.sleep(cfg.scraper.delay_min)
    
    # Save inaccessible URLs too
    for url_obj in new_urls:
        if url_obj.id not in [u.id for u in accessible_urls]:
            validation = validation_results[url_obj.id]
            status_map = {
                URLStatus.PRIVATE: PostStatus.PRIVATE,
                URLStatus.DELETED: PostStatus.DELETED,
                URLStatus.LOGIN_REQUIRED: PostStatus.PRIVATE,
            }
            
            post = Post(
                id=url_obj.id,
                url=url_obj.url,
                platform=Platform(url_obj.platform),
                status=status_map.get(validation.status, PostStatus.FAILED),
                validated_at=validation.validated_at,
                source_file=str(url_obj.source_file),
                source_context=url_obj.context,
                error_message=validation.error_message,
            )
            db.save_post(post)
    
    console.print()
    show_stats(db)


def show_stats(db: Database) -> None:
    """Display collection statistics."""
    stats = db.get_stats()
    
    table = Table(title="Collection Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    
    table.add_row("Total Posts", str(stats.total_posts))
    table.add_row("Accessible", str(stats.accessible))
    table.add_row("Private", str(stats.private))
    table.add_row("Deleted", str(stats.deleted))
    table.add_row("Pending", str(stats.pending))
    
    console.print(table)
    
    if stats.by_platform:
        console.print()
        platform_table = Table(title="By Platform")
        platform_table.add_column("Platform", style="cyan")
        platform_table.add_column("Count", style="green")
        
        for platform, count in stats.by_platform.items():
            platform_table.add_row(platform, str(count))
        
        console.print(platform_table)


def run_viewer_command():
    """Run the web viewer."""
    import sys
    
    # Simple argument parsing for viewer
    data_dir = Path("./data")
    host = "localhost"
    port = 8080
    
    for i, arg in enumerate(sys.argv):
        if arg == "--data-dir" and i + 1 < len(sys.argv):
            data_dir = Path(sys.argv[i + 1])
        elif arg == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]
        elif arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
    
    console.print(f"[bold blue]Media Toolkit Viewer[/bold blue]")
    console.print(f"  Data directory: {data_dir}")
    console.print(f"  Server: http://{host}:{port}")
    console.print()
    
    run_server(data_dir, host, port)


if __name__ == "__main__":
    main()
