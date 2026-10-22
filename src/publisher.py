"""Publish Reels with the Instagram API (Instagram Login), using a resumable upload of a local file."""
import time
from pathlib import Path

import requests

GRAPH = "https://graph.instagram.com"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload"


class InstagramError(RuntimeError):
    pass


def _check(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise InstagramError(f"HTTP {resp.status_code}: {resp.text[:500]}")
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error", data)
        raise InstagramError(f"HTTP {resp.status_code}: {err.get('message', err)}")
    return data


class Instagram:
    def __init__(self, user_id: str, token: str, api_version: str = "v21.0"):
        self.user_id = user_id
        self.token = token
        self.version = api_version
        self.base = f"{GRAPH}/{api_version}"

    def me(self) -> dict:
        return _check(requests.get(
            f"{self.base}/me",
            params={"fields": "user_id,username,account_type", "access_token": self.token},
            timeout=30,
        ))

    def publish_reel(self, video_path: Path, caption: str, share_to_feed: bool = True, timeout_s: int = 600) -> dict:
        # 1) create a container that expects a resumable upload
        container = _check(requests.post(f"{self.base}/{self.user_id}/media", data={
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": caption,
            "share_to_feed": "true" if share_to_feed else "false",
            "access_token": self.token,
        }, timeout=60))
        container_id = container["id"]
        print(f"Created container {container_id}")

        # 2) upload the file bytes
        size = video_path.stat().st_size
        with open(video_path, "rb") as f:
            _check(requests.post(
                f"{RUPLOAD}/{self.version}/{container_id}",
                headers={"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(size)},
                data=f,
                timeout=600,
            ))
        print(f"Uploaded {size / 1_000_000:.1f} MB")

        # 3) wait for Instagram to process the video
        deadline = time.time() + timeout_s
        while True:
            status = _check(requests.get(
                f"{self.base}/{container_id}",
                params={"fields": "status_code,status", "access_token": self.token},
                timeout=30,
            ))
            code = status.get("status_code")
            print(f"Processing status: {code}")
            if code == "FINISHED":
                break
            if code in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Video processing failed: {status.get('status', code)}")
            if time.time() > deadline:
                raise InstagramError("Timed out waiting for Instagram to process the video.")
            time.sleep(10)

        # 4) publish
        published = _check(requests.post(
            f"{self.base}/{self.user_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.token},
            timeout=60,
        ))
        media_id = published["id"]
        info = _check(requests.get(
            f"{self.base}/{media_id}",
            params={"fields": "permalink", "access_token": self.token},
            timeout=30,
        ))
        return {"media_id": media_id, "permalink": info.get("permalink")}


def refresh_token(token: str) -> dict:
    """Extend a long-lived token by 60 days. The token must be at least 24 hours old."""
    return _check(requests.get(
        f"{GRAPH}/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
        timeout=30,
    ))
