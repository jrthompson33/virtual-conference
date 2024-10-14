import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any, List
import requests
import string
import secrets
import base64

from core.google_sheets import GoogleSheets
from core.auth import Authentication


def get_headers_with_access(auth: Authentication):
    client_id = auth.zoom["client_id"]
    account_id = auth.zoom["account_id"]
    client_secret = auth.zoom["client_secret"]

    credentials = base64.b64encode(
        f"{client_id}:{client_secret}".encode()).decode()

    # Create the Authorization header
    headers = {
        "Authorization": f"Basic {credentials}"
    }

    oauth_endpoint = f"https://zoom.us/oauth/token?grant_type=account_credentials&account_id={
        account_id}"

    payload = {}

    response = requests.request(
        "POST", oauth_endpoint, headers=headers, data=payload)

    if response.status_code == 200:
        access_token = response.json()["access_token"]
        access_headers = {
            "Authorization": f"Bearer {access_token}"
        }
        return access_headers
    else:
        None


def format_time_iso8601_utc(t: datetime):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for i in range(6))


def delete_meeting(auth: Authentication, meeting_id: str) -> requests.Response:
    """delete a scheduled Zoom meeting
    """
    headers = get_headers_with_access(auth)
    resp = requests.delete(
        f"https://api.zoom.us/v2/meetings/{meeting_id}", headers=headers).json()
    return resp


def schedule_zoom_webinar(auth: Authentication, title: str, password: str, start: datetime, end: datetime,
                          agenda: str, user_id: str, alternative_hosts: List[str] = []):
    # Compute the duration
    difference = start - end
    duration = divmod(difference.total_seconds(), 60)[0]

    webinar_info = {
        # Webinar description. Need to explain all sessions in Zoom Webinar.
        "agenda": agenda,
        # Webinar duration in minutes. Used for scheduled webinars only.
        "duration": duration,
        # Webinar passcode. Passcode may only contain the characters [a-z A-Z 0-9 @ - _ * !]. Maximum of 10 characters.
        "password": password,
        # Whether to generate a default passcode using the user's settings. This value defaults to false.
        "default_passcode": False,
        "settings": {
            "allow_multiple_devices": True,
            # Alternative host emails or IDs. Multiple values separated by comma.
            "alternative_hosts": ",".join(alternative_hosts),
            "alternative_host_update_polls": True,
            # The default value is 2. To enable registration required, set the approval type to 0 or 1.
            "approval_type": 2,
            # Send reminder email to attendees and panelists.
            "attendees_and_panelists_reminder_email_notification": {
                "enable": False,
                "type": 0
            },
            "auto_recording": "none",
            "contact_email": "ieeevistech@gmail.com",
            "contact_name": "IEEE VIS Tech Chairs",
            "email_language": "en-US",
            "follow_up_absentees_email_notification": {
                "enable": False,
            },
            "follow_up_attendees_email_notification": {
                "enable": False,
            },
            # Default to HD video.
            "hd_video": True,
            # Whether HD video for attendees is enabled.
            "hd_video_for_attendees": True,
            # Start video when host joins webinar.(
            "host_video": False,
            "language_interpretation": {
                "enable": False,
            },
            "sign_language_interpretation": {
                "enable": False,
            },
            # Require panelists to authenticate to join
            "panelist_authentication": False,
            # Only authenticated users can join meeting if the value of this field is set to true.
            "meeting_authentication": False,
            "add_watermark": False,
            "add_audio_watermark": False,
            "on_demand": False,
            "panelists_invitation_email_notification": False,
            "panelists_video": False,
            "post_webinar_survey": False,
            "practice_session": False,
            "question_and_answer": {
                "enable": False
            },
            # Send email notifications to registrants about approval, cancellation, denial of the registration.
            "registrants_email_notification": False,
            # Restrict number of registrants for a webinar. By default, it is set to 0. A 0 value means that the restriction option is disabled. Provide a number higher than 0 to restrict the webinar registrants by the that number.
            "registrants_restrict_number": 0,
            # Registration types. Only used for recurring webinars with a fixed time.
            "registration_type": 1,
            # Whether to always send 1080p video to attendees.
            "send_1080p_video_to_attendees": True,
            "show_share_button": False,
            # Whether the Webinar Session Branding setting is enabled. This setting lets hosts visually customize a webinar by setting a session background.
            "enable_session_branding": False
        },
        "start_time": start,
        # "timezone": "America/Los_Angeles",
        "topic": title,
        # Webinar types. 5 - Webinar.
        "type": 5,
        "is_simulive": False,
    }

    headers = get_headers_with_access(auth)
    zoom_info = requests.post(f"https://api.zoom.us/v2/users/{user_id}/webinars",
                              json=webinar_info, headers=headers).json()
    return zoom_info


def get_webinar(auth: Authentication, webinar_id: str) -> requests.Response:
    """ get info of a scheduled Zoom webinar
    """
    headers = get_headers_with_access(auth)
    resp = requests.get(
        f"https://api.zoom.us/v2/webinars/{webinar_id}", headers=headers).json()
    return resp


def get_meeting(auth: Authentication, meeting_id: str) -> requests.Response:
    """get info of a scheduled Zoom meeting such as start_url
    """
    headers = get_headers_with_access(auth)
    resp = requests.get(
        f"https://api.zoom.us/v2/meetings/{meeting_id}", headers=headers).json()
    return resp


def schedule_zoom_meeting(headers: Any, title: str, password: str, start: datetime, end: datetime,
                          agenda: str, user_id: str, session_id: str):
    """Schedule a zoom meeting
    """
    # Max Zoom meeting topic length is 200 characters
    if len(title) > 200:
        title = title[0:199]
    # Max agenda length is 2000 characters
    if len(agenda) > 2000:
        agenda = agenda[0:1999]

    difference = end - start
    duration = divmod(difference.total_seconds(), 60)[0]

    meeting_info = {
        "agenda": agenda,
        "default_password": False,
        "duration": int(duration),
        "password": password,
        # Whether to create a prescheduled meeting via the GSuite app. This only supports the meeting type value of 2 (scheduled meetings) and 3 (recurring meetings with no fixed time).
        "pre_schedule": False,
        "settings": {
            "allow_multiple_devices": True,
            # Enable meeting registration approval. 2 - No registration required.
            "approval_type": 2,
            "audio": "both",
            "auto_recording": "none",
            "close_registration": False,
            "contact_email": "ieeevistech@gmail.com",
            "contact_name": "IEEE VIS Tech Chairs",
            "email_notification": False,
            "focus_mode": False,
            "host_video": False,
            "jbh_time": 0,
            "join_before_host": False,
            "meeting_authentication": True,
            "global_dial_in_countries": [],
            "mute_upon_entry": True,
            "participant_video": False,
            "private_meeting": False,
            "registrants_confirmation_email": False,
            "registrants_email_notification": False,
            "registration_type": 1,
            "use_pmi": False,
            "waiting_room": False,
            "watermark": False,
            "continuous_meeting_chat": {
                "enable": True,
                "auto_add_invited_external_users": True
            },
            "participant_focused_meeting": False,
        },
        "start_time": format_time_iso8601_utc(start),
        # https://developers.zoom.us/docs/api/rest/other-references/abbreviation-lists/
        "timezone": "America/New_York",
        "topic": title,
        "tracking_fields": [
            {
                "field": "session_id",
                "value": session_id
            }
        ],
        "type": 2
    }

    create_meeting_resp = requests.post(f"https://api.zoom.us/v2/users/{user_id}/meetings",
                                        json=meeting_info, headers=headers)
    print(create_meeting_resp)
    return create_meeting_resp.json()


def schedule_meetings(args: argparse.Namespace):
    """Schedule meetings based on Sessions sheet in Data spreadsheet
    """
    auth = Authentication()
    headers = get_headers_with_access(auth)

    sessions_sheet = GoogleSheets()
    sessions_sheet.load_sheet("Sessions")
    tracks = GoogleSheets()
    tracks.load_sheet("Tracks")
    tracks_dict: dict[dict[str, Any], Any] = {}
    for row in tracks.data:
        tracks_dict[row["Track"]] = row
    events_sheet = GoogleSheets()
    events_sheet.load_sheet("Events")
    events = events_sheet.data
    events_dict = dict()
    for e in events:
        events_dict[e["Event Prefix"]] = e["Event"]

    # Filter out sessions that have not been scheduled yet and have a Track
    sessions = list(filter(lambda row: row["Track"] and len(row["Track"].strip()) > 0 and row["Track"].strip() != "various" and
                           (row["Zoom Meeting ID"] is None or len(row["Zoom Meeting ID"].strip()) == 0), sessions_sheet.data))

    # Filter for args event_prefix
    if args.event_prefix and len(args.event_prefix) > 0:
        sessions = list(
            filter(lambda it: it["Event Prefix"] == args.event_prefix, sessions))

    # Filter for args track id
    if args.track and len(args.track) > 0:
        sessions = list(filter(lambda it: it["Track"] == args.track, sessions))
    # Filter for day of the week e.g. mon1, tue1 for 1 block on Monday or Tuesday
    if args.dow:
        sessions = list(
            filter(lambda it: it["Day of Week"] == args.dow, sessions))

    num_to_schedule = len(sessions)
    if num_to_schedule > args.max_n_schedules:
        num_to_schedule = args.max_n_schedules

    print(f"{num_to_schedule} meetings will be scheduled")

    for i in range(num_to_schedule):
        session: dict[str, Any] = sessions[i]
        title = session["Session Title"]
        track = tracks_dict[session["Track"]]
        session_id = session["Session ID"]
        start = datetime.fromisoformat(
            session["DateTime Start"].replace('Z', '+00:00'))
        end = datetime.fromisoformat(
            session["DateTime End"].replace('Z', '+00:00'))
        start = start - timedelta(minutes=args.time_before)
        end = end + timedelta(minutes=args.time_after)
        room = track["Room Name"]
        host = track["Zoom Host ID"]
        password = generate_password()
        event_name = events_dict[session["Event Prefix"]]
        agenda = f"Event: {event_name}\n Session: {
            session["Session Title"]}\n Program: https://ieeevis.org/year/2024/program/session_{session["Session ID"]}.html"
        if host:
            print(
                f"\r\n{i+1}/{num_to_schedule}: {title} - {room} | {start} - {end} | {host}")
            resp = schedule_zoom_meeting(
                headers, f"IEEE VIS - {title}", password, start, end, agenda, host, session_id)
            print(f"\r\n{json.dumps(resp, indent=4)}")
            session["Zoom Meeting ID"] = str(resp["id"])
            session["Zoom Password"] = password
            session["Zoom URL"] = resp["join_url"]
            session["Zoom Host Start URL"] = resp["start_url"]
            session["Zoom Host Username"] = host
            session["Slido URL"] = track["Slido URL"]

            sessions_sheet.save()
        else:
            print(f"Zoom Host not found for session {session_id}")


def update_zoom_meeting_livestream(auth: Authentication, meeting_id: int, page_url: str, stream_key: str, stream_url: str, resolution: str = "720p"):
    livestream_info = {
        # The live stream page URL.
        "page_url": page_url,
        # Stream name and key.
        "stream_key": stream_key,
        # Streaming URL
        "stream_url": stream_url,
        "resolution": resolution
    }

    headers = get_headers_with_access(auth)
    response = requests.patch(f"https://api.zoom.us/v2/meetings/{
                              meeting_id}/livestream", headers=headers, json=livestream_info)
    return response


def update_session_zoom_livestreams(args: argparse.Namespace):
    auth = Authentication()
    session_sheet = GoogleSheets()
    session_sheet.load_sheet("Sessions")
    sessions = session_sheet.data
    streamkeys_sheet = GoogleSheets()
    streamkeys_sheet.load_sheet("StreamKeys")
    streamkeys = streamkeys_sheet.data
    streamkeys_dict = dict()
    for sk in streamkeys:
        streamkeys_dict[sk["Track"]] = sk

    print(f"{len(sessions)} sessions loaded")
    # Filter for day of the week e.g. mon1, tue1 for 1 block on Monday or Tuesday
    if args.dow:
        sessions = list(
            filter(lambda it: it["Day of Week"] == args.dow, sessions))
    # Filter for args event_prefix
    if args.event_prefix and len(args.event_prefix) > 0:
        sessions = list(
            filter(lambda it: it["Event Prefix"] == args.event_prefix, sessions))
    # Filter for args track id
    if args.track and len(args.track) > 0:
        sessions = list(filter(lambda it: it["Track"] == args.track, sessions))

    print(f"Updating livestream for {len(sessions)} Zoom Meetings")
    success = 0
    for s in sessions:
        id = s["Zoom Meeting ID"]
        sk = streamkeys_dict[s["Track"]]
        page_url = s["Session YouTube URL"]
        stream_key = sk["Stream Key"]
        stream_url = sk["Ingestion URL"]
        resp = update_zoom_meeting_livestream(
            auth, id, page_url, stream_key, stream_url, "720p")
        if resp.status_code != 204:
            print(resp.status_code, resp.text)
            print(f"{id} meeting not updated")
        else:
            success += 1
    print(f"{success} out of {len(sessions)} updated")


def update_livestream_status(auth: Authentication, meeting_id: int, action: str, layout: str, close_caption: str):
    livestream_info = {
        # "start" - Start a livestream. "stop" - Stop an ongoing livestream. "mode" - Control a livestream view at runtime.
        "action": action,
        "settings": {
            #   The layout of the meeting's livestream. Use this field if you pass the start or mode value for the action field.
            # follow_host - Follow host view. gallery_view - Gallery view. speaker_view - Speaker view.
            "layout": layout,
            # burnt-in - Burnt in captions. embedded - Embedded captions. off - Turn off captions.
            "close_caption": close_caption
        }
    }

    headers = get_headers_with_access(auth)
    response = requests.patch(f"https://api.zoom.us/v2/meetings/{
                              meeting_id}/livestream/status", headers=headers, json=livestream_info)
    return response


def start_livestreams(args: argparse.Namespace):
    update_status_for_livestreams(args, "start")


def stop_livestreams(args: argparse.Namespace):
    update_status_for_livestreams(args, "stop")


def update_status_for_livestreams(args: argparse.Namespace, action: str):
    auth = Authentication()
    session_sheet = GoogleSheets()
    session_sheet.load_sheet("Sessions")
    sessions = session_sheet.data

    print(f"{len(sessions)} sessions loaded")
    # Filter for day of the week e.g. mon1, tue1 for 1 block on Monday or Tuesday
    if args.dow:
        sessions = list(
            filter(lambda it: it["Day of Week"] == args.dow, sessions))
    # Filter for args event_prefix
    if args.event_prefix and len(args.event_prefix) > 0:
        sessions = list(
            filter(lambda it: it["Event Prefix"] == args.event_prefix, sessions))
    # Filter for args track id
    if args.track and len(args.track) > 0:
        sessions = list(filter(lambda it: it["Track"] == args.track, sessions))

    print(f"Updating livestream status for {len(sessions)} Zoom Meetings")
    success = 0
    for s in sessions:
        id = s["Zoom Meeting ID"]
        resp = update_livestream_status(
            auth, id, action, "follow_host", "embedded")
        if resp.status_code != 204:
            print(resp.status_code, resp.text)
            print(f"{id} meeting not updated")
        else:
            success += 1
    print(f"{success} out of {len(sessions)} updated")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Schedule zoom meetings')
    parser.add_argument('--schedule', action="store_true",
                        help='schedule zoom meetings for sessions in sheet')
    parser.add_argument('--delete', action="store_true",
                        help='delete specified meeting')
    parser.add_argument('--get', action="store_true",
                        help='get info of specified meeting')
    parser.add_argument('--update_livestream', action="store_true",
                        help='update the livestream for all sessions based on streamkeys to YouTube')
    parser.add_argument('--start_livestream', action="store_true",
                        help="update status of livestreams to start and use embedded captions")
    parser.add_argument('--stop_livestream', action="store_true",
                        help="update status of livestreams to stop")
    parser.add_argument('--start_url', action="store_true",
                        help='retrieve start url of a meeting')

    parser.add_argument("--max_n_schedules", default=200, type=int,
                        help='Maximum number of meetings to schedule in a call')
    parser.add_argument("--time_before", default=15, type=int,
                        help='Time to start meeting earlier than session time, in minutes')
    parser.add_argument("--time_after", default=5, type=int,
                        help='Scheduled end time of meeting after official session end, in minutes')

    parser.add_argument("--id", default=None, type=str, help='meeting id')
    parser.add_argument("--dow", default=None, type=str,
                        help='Day of Week and Session Block Number (e.g., mon1 = Monday First Block, tue3 = Tuesday Third Block)')
    parser.add_argument("--event_prefix", default=None,
                        type=str, help='Event prefix to filter for')
    parser.add_argument("--track", default=None, type=str,
                        help='Track id to filter for')
    parser.add_argument("--disable_dialin", action="store_true", default=True,
                        help='Enable dial-in for meetings (requires Pro account)')

    args = parser.parse_args()

    if args.schedule:
        schedule_meetings(args)
    elif args.delete:
        resp = delete_meeting(Authentication(), args.id)
        print(resp)
    elif args.get:
        resp = get_meeting(Authentication(), args.id)
        print(json.dumps(resp, indent=4))
    elif args.update_livestream:
        update_session_zoom_livestreams(args)
    elif args.start_livestream:
        start_livestreams(args)
    elif args.stop_livestream:
        stop_livestreams(args)
    
