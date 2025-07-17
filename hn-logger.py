# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx",
#     "rich",
#     "typer",
# ]
# ///
import csv
import json
import os
from datetime import datetime
import time
from typing import Set

import httpx
import typer
from rich.console import Console

app = typer.Typer()
console = Console()

HN_TOPSTORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{id}.json"
POLL_INTERVAL = 60  # seconds
CSV_HEADERS = ["id", "time_added", "title", "url", "score"]


def load_seen_ids(csv_file: str) -> Set[str]:
    seen = set()
    if os.path.exists(csv_file):
        with open(csv_file, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                seen.add(row["id"])
    return seen


def save_to_csv(csv_file: str, posts: list[dict]):
    file_exists = os.path.exists(csv_file)
    with open(csv_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(posts)


def fetch_top_ids(n: int) -> list[int]:
    with httpx.Client() as client:
        resp = client.get(HN_TOPSTORIES_URL)
        resp.raise_for_status()
        return resp.json()[:n]


def fetch_item(item_id: int) -> dict:
    with httpx.Client() as client:
        url = HN_ITEM_URL.format(id=item_id)
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


@app.command()
def main(n: int = typer.Option(10, "--n", help="Top n posts to monitor")):
    csv_file = f"hn_top_{n}.csv"
    seen_ids = load_seen_ids(csv_file)
    current_top_ids: Set[str] = set()

    while True:
        try:
            top_ids = fetch_top_ids(n)
            new_top_ids = set(map(str, top_ids)) - seen_ids
            if new_top_ids:
                new_posts = []
                now_ts = datetime.now().isoformat()
                for tid in new_top_ids:
                    item = fetch_item(int(tid))
                    post = {
                        "id": tid,
                        "time_added": now_ts,
                        "title": item.get("title", "Unknown"),
                        "url": item.get("url", f"https://news.ycombinator.com/item?id={tid}"),
                        "score": str(item.get("score", 0)),
                    }
                    new_posts.append(post)
                    console.print(
                        f"[bold green]{now_ts} New: {post['title']} (ID: {post['id']}, Score: {post['score']}, URL: {post['url']})[/]"
                    )

                save_to_csv(csv_file, new_posts)
                seen_ids.update(new_top_ids)

            current_top_ids = set(map(str, top_ids))
            time.sleep(POLL_INTERVAL)
        except Exception as e:
            console.print(f"[bold red]Error[/]: {str(e)}")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    app()
