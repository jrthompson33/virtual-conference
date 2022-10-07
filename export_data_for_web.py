import sys
import shutil
import os
import json
import ics
from PIL import Image
from datetime import timezone, datetime, timedelta
import argparse

from core.auth import Authentication
from core.google_sheets import GoogleSheets


def parse_time(t: str):
    return datetime.fromisoformat(t.replace("Z", "+00:00"))


def format_time_slot(start: datetime, end: datetime):
    return start.strftime("%H%M") + "-" + end.strftime("%H%M")


def format_time(t: datetime):
    return t.strftime("%a %b %d %H:%M %Z")


def format_time_iso8601_utc(t: datetime):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def create_data_for_web(auth: Authentication, output_dir: str, export_ics: bool, export_img: bool, export_pdf: bool):
    """create data for virtual website.
    authentication: Authentication instance in which aws ses client, & google sheets was authenticated
    conference_db: Google Sheet identifier for Conference Database Sheet. TODO add more info about that sheet
    output_dir: output directory for data

    """
    # Check for output path
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    full_calendar = ics.Calendar()
    event_calendars = {}

    all_posters = {}
    all_papers = {}
    all_events = {}

    sheet_events = GoogleSheets()
    sheet_events.load_sheet("Events")

    sheet_sessions = GoogleSheets()
    sheet_sessions.load_sheet("Sessions")

    sheet_papers = GoogleSheets()
    sheet_papers.load_sheet("ItemsVISPapers-A")

    sheet_posters = GoogleSheets()
    sheet_posters.load_sheet("Posters")

    # All paper types, full, short, workshop
    sheet_db_papers = GoogleSheets()
    sheet_db_papers.load_sheet("PapersDB")

    db_papers_dict = dict()
    for db_p in sheet_db_papers.data:
        db_papers_dict[db_p["UID"]] = db_p

    # All tracks/rooms of the conference, create dict based on "Track"
    sheet_tracks = GoogleSheets()
    sheet_tracks.load_sheet("Tracks")
    tracks_dict = dict()
    for t in sheet_tracks.data:
        tracks_dict[t["Track"]] = t

    # All broadcasts of the conference, create dict based on "Livestream ID"
    sheet_broadcasts = GoogleSheets()
    sheet_broadcasts.load_sheet("Broadcasts")
    broadcasts_dict = dict()
    for b in sheet_broadcasts.data:
        broadcasts_dict[b["Livestream ID"]] = b

    # ['Event', 'Event Type', 'Event Prefix', 'Event Description',
    #  'Event URL', 'Organizers', 'Organizer Emails']

    for e in sheet_events.data:
        e_data = {
            "event": e["Event"],
            "long_name": e["Event"],
            "event_type": e["Event Type"],
            "event_prefix": e["Event Prefix"],
            "event_description": e["Event Description"],
            "event_url": e["Event URL"],
            "organizers": [o.strip() for o in e["Organizers"].split("|")] if e["Organizers"] else [],
            "sessions": []
        }

        if not e_data["event_prefix"] in all_events:
            all_events[e_data["event_prefix"]] = e_data
        else:
            all_events[e_data["event_prefix"]].append(e_data)

    # ['Session ID', 'Event Prefix', 'Session Title', 'DateTime Start', 'DateTime End',
    # 'Track', 'Livestream ID', 'Session Image', 'Session Chairs', 'Session Chairs EMails',
    # 'Session YouTube URL', 'Session FF Playlist URL', 'Session FF URL', 'Slido URL', 'Discord Channel',
    # 'Discord Channel ID', 'Discord URL', 'Zoom Meeting ID', 'Zoom Password', 'Zoom URL', 'Zoom Host Start URL']

# Thumbnail File Name	Stream Key ID	Captions Enabled	Captions Ingestion URL	Video ID	YouTube URL	Stream Bound

    # Create session data
    for s in sheet_sessions.data:
        t = tracks_dict[s["Track"]] if s["Track"] in tracks_dict else None
        b = broadcasts_dict[s["Livestream ID"]
                            ] if s["Livestream ID"] in broadcasts_dict else None

        s_data = {
            "title": s["Session Title"],
            "session_id": s["Session ID"],
            "event_prefix": s["Event Prefix"],
            "track": s["Track"],
            "livestream_id": s["Livestream ID"],
            "session_image": f'{s["Session ID"]}.png',
            "chair": [c.strip() for c in s["Session Chairs"].split("|")] if s["Session Chairs"] else [],
            "organizers": [],
            "time_start": format_time_iso8601_utc(parse_time(s["DateTime Start"])),
            "time_end": format_time_iso8601_utc(parse_time(s["DateTime End"])),
            "discord_category": "",
            "discord_channel": t["Discord Channel"] if t else "",
            "discord_channel_id": t["Discord Channel ID"] if t else "",
            "discord_link": t["Discord URL"] if t else "",
            "slido_link": t["Slido URL"] if t else "",
            "youtube_url": b["YouTube URL"] if b else "https://youtu.be/_evorVC17Yg",
            "zoom_meeting": s["Zoom Meeting ID"],
            "zoom_password": s["Zoom Password"],
            "zoom_link": s["Zoom URL"],
            "ff_link": s["Session FF URL"],
            "ff_playlist": s["Session FF Playlist URL"],
            "time_slots": [],
        }

        # TODO This only includes papers that are in a session, will need to look for non-overlapping cases
        filtered_papers = list(
            filter(lambda p: p["Session ID"] == s_data["session_id"], sheet_papers.data))

        for p in filtered_papers:
            # Find the corresponding entry by Paper UID in PapersDB

            p_db = db_papers_dict[p["Paper UID"]
                                  ] if p["Paper UID"] in db_papers_dict else None

            p_event_prefix = p_db["Event Prefix"] if p_db else ""

            paper_type = ""
            if p_event_prefix.startswith("v-spotlight"):
                paper_type = "spotlight"
            elif p_event_prefix.startswith("v-panel"):
                paper_type = "panel"
            elif p_event_prefix.startswith("v-short"):
                paper_type = "short"
            elif p_event_prefix.startswith("v-"):
                paper_type = "full"
            elif p_event_prefix.startswith("a-"):
                paper_type = "associated"
            elif p_event_prefix.startswith("w-"):
                paper_type = "workshop"

            p_data = {
                "slot_id": p["Item ID"],
                "session_id": p["Session ID"],
                "type": p["Slot Type"],
                "title": p["Slot Title"],
                "contributors": [c.strip() for c in p["Slot Contributors"].split("|")] if p["Slot Contributors"] else [],
                "authors": [a.strip() for a in p["Authors"].split("|")] if p["Authors"] else [],
                "abstract": p_db["Abstract"] if p_db else "",
                "uid": p["Paper UID"],
                "file_name": p["File Name"],
                "time_stamp": format_time_iso8601_utc(parse_time(p["Slot DateTime Start"])),
                "time_start": format_time_iso8601_utc(parse_time(p["Slot DateTime Start"])),
                "time_end": format_time_iso8601_utc(parse_time(p["Slot DateTime End"])),
                # "youtube_video_id": p["YouTube Video"],
                "paper_type": paper_type,
                "keywords": [k.strip() for k in p_db["Keywords"].split("|")] if p_db and p_db["Keywords"] else [],
                "has_image": p_db["Has Image"] if p_db else False,
                "has_video": p_db["Has Video"] if p_db else False,
                "has_video": p_db["Video Duration"] if p_db else "",
                "paper_award": p_db["Award"] if p_db else "",
                "image_caption": p_db["Image Caption"] if p_db else "",
                "external_paper_link": "",
                "has_pdf": False,
                "ff_link": ""
            }

            s_data["time_slots"].append(p_data)

            # All papers will have a UID
            # Should this be filtered for only full, short, cga, tvcg?
            if p_data["uid"] and not "Q+A" in p_data["type"] and not "Q + A" in p_data["type"]:
                all_papers[p_data["uid"]] = p_data

        if s_data["event_prefix"] in all_events:
            all_events[s_data["event_prefix"]]["sessions"].append(s_data)
        else:
            print("MISSING: event prefix of {} in all_events.".format(
                s_data["event_prefix"]))

    # ['UID', 'Event', 'Event Prefix', 'Title', 'Authors',
    # 'Keywords', 'Abstract', 'Presenting Author (name)',
    # 'Presenting Author (email)', 'ACM Author Affiliations', 'Award', 'PDF Link',
    # 'Has Preview', 'Has Presentation']
    for p in sheet_posters.data:
        p_data = {
            "event": p["Event"],
            "event_prefix": p["Event Prefix"],
            "title": p["Title"],
            "uid": p["UID"],
            "discord_channel": "",
            "has_image": False,
            "authors": [a.strip() for a in p["Authors"].split("|")] if p["Authors"] else [],
            "author_affiliations": [a.strip() for a in p["ACM Author Affiliations"].split(";")] if p["ACM Author Affiliations"] else [],
            "presenting_author": p["Presenting Author (name)"],
            "abstract": p["Abstract"],
            "has_summary_pdf": p["PDF Link"] != "",
            "pdf_link": p["PDF Link"],
        }
        if p_data["uid"]:
            all_posters[p_data["uid"]] = p_data

    with open(os.path.join(output_dir, "session_list.json"), "w", encoding="utf8") as f:
        json.dump(all_events, f, indent=4)

    with open(os.path.join(output_dir, "paper_list.json"), "w", encoding="utf8") as f:
        json.dump(all_papers, f, indent=4)

    with open(os.path.join(output_dir, "poster_list.json"), "w", encoding="utf8") as f:
        json.dump(all_posters, f, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to export json, ics, image, and pdf files for web from Conference Database on Google Sheets.')
    # make it possible to use xlsx file?

    parser.add_argument('--img', help='include image files in data output directory',
                        action='store_true', default=False)
    parser.add_argument('--ics', help='include ICS Calendar files in data output directory',
                        action='store_true', default=False)
    parser.add_argument('--pdf', help='include PDF files in data output directory',
                        action='store_true', default=False)

    parser.add_argument(
        '--output_dir', help='output directory for all the web data', default="./")
    args = parser.parse_args()
    auth = Authentication(email=True)

    if args.output_dir:
        # create output data for web
        create_data_for_web(
            auth=auth, output_dir=args.output_dir,
            export_ics=args.ics, export_img=args.img, export_pdf=args.pdf)
