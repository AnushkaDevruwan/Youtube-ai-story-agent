import json
import pickle
import time
import argparse
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request


ROOT = Path(__file__).resolve().parents[1]

CLIENT_SECRET_FILE = ROOT / "client_secret.json"
TOKEN_FILE = ROOT / "youtube_token.pickle"

DEFAULT_VIDEO_FILE = ROOT / "output" / "final_short.mp4"
DEFAULT_METADATA_FILE = ROOT / "metadata" / "current_upload.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

RETRIABLE_STATUS_CODES = [500, 502, 503, 504]


def get_authenticated_service():
    credentials = None

    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as token:
            credentials = pickle.load(token)

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not CLIENT_SECRET_FILE.exists():
                raise FileNotFoundError(f"Missing OAuth client file: {CLIENT_SECRET_FILE}")

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRET_FILE),
                SCOPES
            )

            credentials = flow.run_local_server(
                port=0,
                prompt="consent"
            )

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(credentials, token)

    return build(API_SERVICE_NAME, API_VERSION, credentials=credentials)


def load_metadata(metadata_file):
    metadata_file = Path(metadata_file)

    if not metadata_file.exists():
        raise FileNotFoundError(f"Missing upload metadata file: {metadata_file}")

    return json.loads(metadata_file.read_text(encoding="utf-8"))


def resumable_upload(request):
    response = None
    error = None
    retry = 0
    max_retries = 5

    while response is None:
        try:
            print("Uploading video...")
            status, response = request.next_chunk()

            if response is not None:
                if "id" in response:
                    return response
                raise RuntimeError(f"Unexpected upload response: {response}")

        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"Retriable HTTP error {e.resp.status}: {e.content}"
            else:
                raise

        except Exception as e:
            error = f"Retriable error: {e}"

        if error:
            print(error)
            retry += 1

            if retry > max_retries:
                raise RuntimeError("Upload failed after max retries.")

            sleep_seconds = 2 ** retry
            print(f"Sleeping {sleep_seconds} seconds before retry...")
            time.sleep(sleep_seconds)


def upload_video(video_file, metadata_file, result_file=None):
    video_file = Path(video_file)
    metadata_file = Path(metadata_file)

    if not video_file.exists():
        raise FileNotFoundError(f"Missing final video: {video_file}")

    metadata = load_metadata(metadata_file)
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": metadata["title"],
            "description": metadata["description"],
            "tags": metadata.get("tags", []),
            "categoryId": metadata.get("categoryId", "27")
        },
        "status": {
            "privacyStatus": metadata.get("privacyStatus", "private"),
            "selfDeclaredMadeForKids": metadata.get("selfDeclaredMadeForKids", False)
        }
    }

    media = MediaFileUpload(
        str(video_file),
        chunksize=-1,
        resumable=True,
        mimetype="video/mp4"
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = resumable_upload(request)

    video_id = response.get("id")
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    upload_record = {
        "video_id": video_id,
        "video_url": video_url,
        "title": metadata["title"],
        "privacyStatus": body["status"]["privacyStatus"]
    }

    if result_file is None:
        result_file = ROOT / "output" / "youtube_upload_result.json"
    else:
        result_file = Path(result_file)

    result_file.write_text(
        json.dumps(upload_record, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Upload completed.")
    print(f"Video ID: {video_id}")
    print(f"Video URL: {video_url}")
    print(f"Upload result saved to: {result_file}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--video-file",
        default=str(DEFAULT_VIDEO_FILE),
        help="Path to video file"
    )

    parser.add_argument(
        "--metadata-file",
        default=str(DEFAULT_METADATA_FILE),
        help="Path to upload metadata JSON"
    )

    parser.add_argument(
        "--result-file",
        default=None,
        help="Where to save upload result JSON"
    )

    args = parser.parse_args()

    upload_video(
        video_file=args.video_file,
        metadata_file=args.metadata_file,
        result_file=args.result_file
    )


if __name__ == "__main__":
    main()