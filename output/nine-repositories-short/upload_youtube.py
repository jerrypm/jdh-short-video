"""Private YouTube upload for this short — prepared, NOT executed.

There is no authorized API connection in this workspace, so this file has never
been run: no token exists, no scope was requested, and no upload was attempted.
See youtube-setup.md for the one-time setup. Running it without --client-secret
fails immediately with a clear message.

What it does when it can run:
  1. verifies the authorized channel is UCRig_f5P4QyB_kilUs2PN8Q
  2. reuses a recorded video id instead of uploading a second copy
  3. resumable upload of final.mp4 with privacyStatus=private,
     selfDeclaredMadeForKids=false, containsSyntheticMedia=true
  4. reads the processing/visibility state back and writes youtube-upload.json
"""

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHANNEL_ID = "UCRig_f5P4QyB_kilUs2PN8Q"
CHANNEL_NAME = "JR DEV | SWIFT | FLUTTER"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
RESULT = HERE / "youtube-upload.json"


def fail(message):
    print(json.dumps({"uploaded": False, "reason": message}, indent=2))
    raise SystemExit(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-secret", default=os.environ.get("JDH_YOUTUBE_CLIENT_SECRET"),
                        help="Desktop-app OAuth client JSON for the channel owner")
    parser.add_argument("--file", default=str(HERE / "final.mp4"))
    arguments = parser.parse_args()

    metadata = json.loads((HERE / "upload-metadata.json").read_text())
    video = Path(arguments.file)
    if not video.is_file():
        fail(f"video not found: {video}")
    if RESULT.exists():
        existing = json.loads(RESULT.read_text())
        if existing.get("videoId"):
            print(json.dumps({"uploaded": True, "reused": True,
                              "videoId": existing["videoId"],
                              "url": existing.get("url")}, indent=2))
            return

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as error:
        fail(f"missing client library ({error}); install google-api-python-client and "
             f"google-auth-oauthlib as described in youtube-setup.md")

    if not arguments.client_secret or not Path(arguments.client_secret).is_file():
        fail("no --client-secret file; see youtube-setup.md. Nothing was requested or uploaded.")

    token = Path(arguments.client_secret).with_name("youtube-token.json")
    credentials = None
    if token.is_file():
        credentials = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            credentials = InstalledAppFlow.from_client_secrets_file(
                arguments.client_secret, SCOPES).run_local_server(port=0)
        token.write_text(credentials.to_json())
        os.chmod(token, 0o600)

    youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    channels = youtube.channels().list(part="id,snippet", mine=True).execute()
    items = channels.get("items", [])
    found = [item for item in items if item["id"] == CHANNEL_ID]
    if not found:
        fail(f"authorized account(s) {[item['id'] for item in items]} do not include {CHANNEL_ID}; "
             f"refusing to upload to the wrong channel")

    body = {
        "snippet": {
            "title": metadata["title"][:100],
            "description": metadata["description"][:5000],
            "tags": metadata["tags"],
            "categoryId": metadata["category_id"],
            "defaultLanguage": metadata["language"],
            "defaultAudioLanguage": metadata["default_audio_language"],
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }
    request = youtube.videos().insert(
        part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True))
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print(json.dumps({"uploaded_bytes": progress.resumable_progress,
                              "total_bytes": progress.total_size}), flush=True)

    video_id = response["id"]
    observed = youtube.videos().list(
        part="status,processingDetails,snippet", id=video_id).execute()["items"][0]
    record = {
        "uploaded": True,
        "videoId": video_id,
        "url": f"https://youtube.com/shorts/{video_id}",
        "channelId": CHANNEL_ID,
        "channelName": found[0]["snippet"]["title"] or CHANNEL_NAME,
        "requestedPrivacy": "private",
        "observedPrivacy": observed["status"].get("privacyStatus"),
        "uploadStatus": observed["status"].get("uploadStatus"),
        "processingStatus": observed.get("processingDetails", {}).get("processingStatus"),
        "containsSyntheticMedia": observed["status"].get("containsSyntheticMedia"),
        "selfDeclaredMadeForKids": observed["status"].get("selfDeclaredMadeForKids"),
        "title": observed["snippet"]["title"],
        "sourceFile": str(video),
        "checkedAt": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
    }
    RESULT.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    sys.exit(main())
