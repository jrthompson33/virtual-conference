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
    return datetime.strptime(t, "%Y-%m-%d %H:%M:%SZ")


def format_time_slot(start: datetime, end: datetime):
    return start.strftime("%H%M") + "-" + end.strftime("%H%M")


def format_time(t: datetime):
    return t.strftime("%a %b %d %H:%M %Z")


def format_time_iso8601_utc(t: datetime):
    return t.astimezone(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
            "organizers": e["Organizers"].split("|") if e["Organizers"] else [],
            "sessions": []
        }

        if not e_data["event_prefix"] in all_events:
            all_events[e_data["event_prefix"]] = e_data
        else:
            all_events[e_data["event_prefix"]].append(e_data)

    print(all_events)

    # ['Session ID', 'Event Prefix', 'Session Title', 'DateTime Start', 'DateTime End',
    # 'Track', 'Livestream ID', 'Session Image', 'Session Chairs', 'Session Chairs EMails',
    # 'Session YouTube URL', 'Session FF Playlist URL', 'Session FF URL', 'Slido URL', 'Discord Channel',
    # 'Discord Channel ID', 'Discord URL', 'Zoom Meeting ID', 'Zoom Password', 'Zoom URL', 'Zoom Host Start URL']

    # Create session data
    for s in sheet_sessions.data:
        s_data = {
            "title": s["Session Title"],
            "session_id": s["Session ID"],
            "event_prefix": s["Event Prefix"],
            "track": s["Track"],
            "livestream_id": s["Livestream ID"],
            "session_image": f'{s["Session ID"]}.png',
            "chair": s["Session Chairs"].split("|") if s["Session Chairs"] else [],
            "organizers": [],
            "time_start": format_time_iso8601_utc(parse_time(s["DateTime Start"])),
            "time_end": format_time_iso8601_utc(parse_time(s["DateTime End"])),
            "discord_category": "",
            "discord_channel": s["Discord Channel"],
            "discord_channel_id": s["Discord Channel ID"],
            "discord_link": s["Discord URL"],
            "slido_link": s["Slido URL"],
            "youtube_url": s["Session YouTube URL"],
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

        print(len(filtered_papers))

        for p in filtered_papers:
            p_data = {
                "slot_id": p["Item ID"],
                "session_id": p["Session ID"],
                "type": p["Slot Type"],
                "title": p["Slot Title"],
                "contributors": p["Slot Contributors"].split("|") if p["Slot Contributors"] else [],
                "authors": p["Authors"].split("|") if p["Authors"] else [],
                "abstract": p["Abstract"],
                "uid": p["Paper UID"],
                "file_name": p["File Name"],
                "time_stamp": format_time_iso8601_utc(parse_time(p["Slot DateTime Start"])),
                "time_start": format_time_iso8601_utc(parse_time(p["Slot DateTime Start"])),
                "time_end": format_time_iso8601_utc(parse_time(p["Slot DateTime End"])),
                # "youtube_video_id": p["YouTube Video"],
                "keywords": [""],
                "has_image": False,
                "paper_award": "",
                "image_caption": "",
                "external_paper_link": "",
                "has_pdf": False,
                "ff_link": ""
                # "has_image": image_name != None,
                # "paper_award": paper_award,
                # "image_caption": image_caption if image_caption else "",
                # "external_paper_link": external_pdf_link if external_pdf_link else "",
                # "has_pdf": pdf_file != None,
                # "ff_link": ff_link if ff_link else ""
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
            "authors": p["Authors"].split("|") if p["Authors"] else [],
            "author_affiliations": p["ACM Author Affiliations"].split(";") if p["ACM Author Affiliations"] else [],
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
