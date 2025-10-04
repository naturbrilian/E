import os
import json
import requests
import feedparser
from bs4 import BeautifulSoup
from atproto import Client

# Config
X_NITTER_BASE = "https://nitter.net"
X_USERNAME = "priconne_redive"

STATE_FILE = "state.json"

BSKY_HOST = "https://bsky.social"
BSKY_IDENTIFIER = os.environ.get("BSKY_IDENTIFIER")
BSKY_APP_PASSWORD = os.environ.get("BSKY_APP_PASSWORD")


def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE, "r"))
    return {"last_x_id": None}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def get_x_feed():
    url = f"{X_NITTER_BASE}/{X_USERNAME}/rss"
    resp = requests.get(url)
    if resp.status_code != 200:
        print("Gagal ambil RSS:", resp.status_code)
        return None
    return feedparser.parse(resp.text)


def download_media(url, filename):
    resp = requests.get(url)
    if resp.status_code == 200:
        with open(filename, "wb") as f:
            f.write(resp.content)
        return filename
    return None


def extract_images(entry):
    """Cari gambar dari entry.summary (HTML)"""
    media_files = []
    if hasattr(entry, "summary"):
        soup = BeautifulSoup(entry.summary, "html.parser")
        for i, img in enumerate(soup.find_all("img")):
            img_url = img.get("src")
            if img_url and img_url.startswith("http"):
                filename = f"media_{i}.jpg"
                path = download_media(img_url, filename)
                if path:
                    media_files.append(path)
    return media_files


def post_to_bsky(text, media_paths=None):
    client = Client(BSKY_HOST)
    client.login(BSKY_IDENTIFIER, BSKY_APP_PASSWORD)

    embed = None
    if media_paths:
        images = []
        for path in media_paths:
            with open(path, "rb") as f:
                blob = client.com.atproto.repo.upload_blob(f)
                images.append({"alt": "", "image": blob.blob})
        embed = {"$type": "app.bsky.embed.images", "images": images}

    client.com.atproto.repo.create_record(
        repo=client.me.did,
        collection="app.bsky.feed.post",
        record={
            "$type": "app.bsky.feed.post",
            "text": text,
            "embed": embed,
        },
    )
    print("✅ Posted to Bsky:", text[:50])


def main():
    state = load_state()
    feed = get_x_feed()

    if feed and "entries" in feed:
        for entry in reversed(feed.entries):
            x_id = entry.id
            if state["last_x_id"] is None or x_id > state["last_x_id"]:
                title = entry.title
                content = title

                # download gambar kalau ada
                media_paths = extract_images(entry)

                try:
                    post_to_bsky(content, media_paths)
                    state["last_x_id"] = x_id
                    save_state(state)
                except Exception as e:
                    print("❌ ERROR posting ke Bsky:", e)


if __name__ == "__main__":
    main()
