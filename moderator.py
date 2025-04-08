from datetime import datetime
from http import HTTPStatus
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from google_auth_oauthlib import flow

from evaluator import evaluate_msg

import logging
import argparse
import pickle
import time as tm
import json
import os
import re

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
TOKEN_FILE = "tokenfile"


def try_get_livechat_id(response):
    try:
        return response["items"][0]["liveStreamingDetails"]["activeLiveChatId"]
    except KeyError:
        return None


def handle_http_error(e: HttpError):
    if e.status_code == HTTPStatus.FORBIDDEN:
        if e.reason == "liveChatEnded":
            logging.info("Live chat ended")
            exit(0)
        logging.error(f"Forbidden due to: {e.reason}")
    logging.exception(e)


def save_credentials(credentials):
    with open(TOKEN_FILE, "wb") as file:
        pickle.dump(credentials, file)


def refresh_token(credentials):
    if not credentials.valid:
        if credentials.expired and credentials.refresh_token:
            logging.info("Credentials expired, need to refresh")
            credentials.refresh(Request())
            save_credentials(credentials)
        else:
            logging.info("Credentials are invalid, need to login anew ")
            return False
    return True


def try_load_token():
    if os.path.isfile(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, "rb") as f:
                credentials = pickle.load(f)
            if refresh_token(credentials):
                return discovery.build("youtube", "v3", credentials=credentials)
        except Exception as e:
            logging.exception(e)
            logging.info(f"Token file {TOKEN_FILE} error {str(e)}")

    return None


def build_youtube_client():
    youtube = try_load_token()

    if youtube:
        return youtube

    client_secrets_file = "client_secret.json"
    fl = flow.InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
    credentials = fl.run_local_server(port=0)

    save_credentials(credentials)

    return discovery.build("youtube", "v3", credentials=credentials)


def youtube_service():
    # Load service account credentials
    SERVICE_ACCOUNT_FILE = "youtube-moderator.json"
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    return discovery.build("youtube", "v3", credentials=credentials)


def get_playlist_list(youtube, channel_name):
    try:
        request = youtube.channels().list(
            part="contentDetails", channel_name=channel_name
        )
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error getting channel info: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error getting channel info: {e}")

    return None


def get_videos_list(youtube, video_id):
    try:
        request = youtube.videos().list(part="statistics", id=video_id)
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error getting the list of videos: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error getting the list of videos: {e}")
    return None


def get_video_livestream_info(youtube, video_id):
    try:
        request = youtube.videos().list(part="liveStreamingDetails", id=video_id)
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error getting livestream info: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error getting livestream info: {e}")

    return None


def get_livechat_msgs(youtube, chat_id, next_page_token, page_size=10):
    try:
        request = youtube.liveChatMessages().list(
            part="snippet,authorDetails",
            liveChatId=chat_id,
            pageToken=next_page_token,
            maxResults=page_size,
        )
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error getting livechat messages: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error getting livechat messages: {e}")

    return None


def get_video_comments(youtube, video_id, next_page_token, page_size=10):
    try:
        request = youtube.commentThreads().list(
            part="snippet,replies",
            videoId=video_id,
            maxResults=page_size,
            pageToken=next_page_token,
        )
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error getting livechat messages: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error getting livechat messages: {e}")

    return None


def get_video_id(youtube_uri: str) -> str | None:
    pattern = re.compile(
        r"(?:https?://)?(?:www\.)?(?:youtube\.com/(?:watch\?v=|embed/|shorts/|v/|.*[?&]v=)|youtu\.be/)([a-zA-Z0-9_-]{11})"
    )
    match = pattern.search(youtube_uri)
    return match.group(1) if match else None


def get_live_id(youtube_uri: str) -> str | None:
    pattern = re.compile(
        r"(?:https?://)?(?:www\.)?youtube\.com/live/([a-zA-Z0-9_-]{11})"
    )

    match = pattern.search(youtube_uri)
    return match.group(1) if match else None


def get_video_comments_complete(youtube, video_id, max_results=100):
    """
    Retrieve comments for a specific YouTube video.

    Args:
        youtube: Authenticated YouTube API service instance
        video_id (str): ID of the video to get comments from
        max_results (int): Maximum number of comments to retrieve

    Returns:
        list: List of comment objects
    """
    comments = []
    next_page_token = None

    try:
        while len(comments) < max_results:
            # Get comment threads (top-level comments)
            request = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                maxResults=min(100, max_results - len(comments)),
                pageToken=next_page_token,
            )

            try:
                response = request.execute()
            except HttpError as e:
                handle_http_error(e)
                continue

            # Process each comment thread
            for item in response["items"]:
                # Get the top-level comment
                top_level_comment = item["snippet"]["topLevelComment"]["snippet"]

                comment_data = {
                    "id": item["id"],
                    "author": top_level_comment["authorDisplayName"],
                    "author_channel_id": top_level_comment["authorChannelId"]["value"],
                    "text": top_level_comment["textDisplay"],
                    "like_count": top_level_comment["likeCount"],
                    "published_at": top_level_comment["publishedAt"],
                    "updated_at": top_level_comment["updatedAt"],
                    "reply_count": item["snippet"]["totalReplyCount"],
                    "replies": [],
                }

                # Get replies if they exist
                if item["snippet"]["totalReplyCount"] > 0 and "replies" in item:
                    for reply in item["replies"]["comments"]:
                        reply_snippet = reply["snippet"]
                        reply_data = {
                            "id": reply["id"],
                            "author": reply_snippet["authorDisplayName"],
                            "author_channel_id": reply_snippet["authorChannelId"][
                                "value"
                            ],
                            "text": reply_snippet["textDisplay"],
                            "like_count": reply_snippet["likeCount"],
                            "published_at": reply_snippet["publishedAt"],
                            "updated_at": reply_snippet["updatedAt"],
                        }
                        comment_data["replies"].append(reply_data)

                comments.append(comment_data)

            # Check if there are more comments
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

    except Exception as e:
        logging.exception(e)
        logging.error(f"Error retrieving comments: {e}")

    return comments


def delete_comment(youtube, comment_id):
    try:
        request = youtube.comments().delete(id=comment_id)
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error deleting video comment: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error deleting video comment: {e}")

    return None


def delete_livechat_msg(youtube, message_id):
    try:
        request = youtube.liveChatMessages().delete(id=message_id)
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error deleting livechat message: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error deleting livechat message: {e}")

    return None


def post_livechat_msg(youtube, livechat_id, message):
    try:
        request = youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": livechat_id,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": message},
                }
            },
        )
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error posting livechat message: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error posting livechat message: {e}")

    return None


def ban_livechat_user(youtube, livechat_id, user_channel_id, ban_duration_seconds):
    try:
        request = youtube.liveChatBans().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": livechat_id,
                    "type": "permanent" if ban_duration_seconds == 0 else "temporary",
                    "bannedUserDetails": {"channelId": user_channel_id},
                    "banDurationSeconds": ban_duration_seconds,
                }
            },
        )
        return request.execute()
    except HttpError as e:
        handle_http_error(e)
        logging.error(f"Error banning livechat user: {e}")
    except Exception as e:
        logging.exception(e)
        logging.error(f"Error banning livechat user: {e}")

    return None


def start_livestream_moderation(youtube_uri: str):
    video_id = get_live_id(youtube_uri)
    if not video_id:
        video_id = get_video_id(youtube_uri)
    if not video_id:
        logging.info(f"Failed to extract video id fron the url: {youtube_uri}")
        exit(-1)
    logging.info(f"Video id: {video_id}")

    youtube = build_youtube_client()
    response = get_video_livestream_info(youtube, video_id)
    livechat_id = try_get_livechat_id(response)
    if not livechat_id:
        logging.info("Failed to get livechat id. Livechat may be unavailable.")

    next_page_token = None
    while True:
        response = get_livechat_msgs(youtube, livechat_id, next_page_token)

        items = response.get("items", []) if response else []

        for item in items:
            try:
                eventType = item["snippet"]["type"]
                if eventType in [
                    "newSponsorEvent",
                    "sponsorOnlyModeEndedEvent",
                    "userBannedEvent",
                ]:
                    logging.info(f"{eventType}:\n{json.dumps(item, indent=2)}")
                    continue
                logging.info(f"{eventType}:\n{json.dumps(item, indent=2)}")
                user_channel_id = item["authorDetails"]["channelId"]
                author = item["authorDetails"]["displayName"]
                # "textMessageEvent"
                message = item["snippet"]["textMessageDetails"]["messageText"]
                logging.info(f'{author}, "{message}"')
                continue
                test = evaluate_msg(message)
                logging.info(f"Evaluation result:\n{test}")
                js = json.loads(test[7:-3])
                verdict = js["verdict"]
                reasoning = js["reasoning"]
                if verdict:
                    logging.info(
                        f'Message violates the rules because "{reasoning}", will be deleted. User {user_channel_id} banned.'
                    )
                    delete_livechat_msg(youtube, item["id"])
                    ban_livechat_user(youtube, livechat_id, user_channel_id, 0)

            except KeyError as e:
                logging.exception(e)
                logging.error(json.dumps(item, indent=2))
            except Exception as e:
                logging.exception(e)

        tm.sleep(5)
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break


def run_comment_moderation(url):
    video_id = get_video_id(url)

    youtube = build_youtube_client()

    next_page_token = None

    count = 100
    while True:
        response = get_video_comments(youtube, video_id, next_page_token)
        items = response.get("items", []) if response else []

        for thread in items:
            try:
                toplevelcomment = thread["snippet"]["topLevelComment"]
                user_channel_id = toplevelcomment["snippet"]["authorChannelId"]["value"]
                comment = toplevelcomment["snippet"]["textOriginal"]
                test = evaluate_msg(comment)
                logging.info(f"Evaluation result:\n{test}")
                js = json.loads(test[7:-3])
                verdict = js["verdict"]
                reasoning = js["reasoning"]
                if verdict:
                    logging.info(
                        f'Message violates the rules because "{reasoning}", will be deleted. User {user_channel_id} banned.'
                    )
                    # delete_comment(youtube, item["id"])
                    # ban_user(youtube, livechat_id, user_channel_id, 0)
                count -= 1
                if count == 0:
                    return
            except KeyError as e:
                logging.exception(e)
                logging.error(json.dumps(item, indent=2))
            except Exception as e:
                logging.exception(e)

        tm.sleep(5)
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break


def get_log_name(logname):
    if not logname:
        current_time = datetime.now()
        logname = current_time.strftime("%Y-%m-%d_%H.log")
    return logname


def main():
    parser = argparse.ArgumentParser(description="Youtube moderation tool")

    parser.add_argument("url", type=str, help="Video url with valid lifechat")
    parser.add_argument(
        "--logname", type=int, help="Logfile name", required=False, default=None
    )

    args = parser.parse_args()

    logname = get_log_name(args.logname)
    logging.basicConfig(
        filename=logname, level=logging.INFO, format="%(asctime)s - %(message)s"
    )

    start_livestream_moderation(args.url)


if __name__ == "__main__":
    main()
