from typing import List
from core.auth import Authentication
from core.templates import load_templates_dict
from core.aws_email import send_aws_email_paper
from core.google_sheets import GoogleSheets
import argparse
import time


def send_emails(auth: Authentication, template: dict, without_slot_contributors: bool = True, event_prefix: str = None, session_id: str = None, ignore_various: bool = True, dow: str = None):
    """send emails to session targets, recipients have to be specified in template as well
    """
    rows = join_session_contributor_rows(
    ) if without_slot_contributors else join_slot_contributors()

    if ignore_various:
        rows = list(filter(lambda r: r["Track"] != "various", rows))
    if event_prefix and len(event_prefix) > 0:
        rows = list(filter(lambda r: r["Event Prefix"] == event_prefix, rows))
    if session_id and len(session_id) > 0:
        rows = list(filter(lambda r: r["Session ID"] == session_id, rows))
    if dow and len(dow) > 0:
        rows = list(filter(lambda r: r["Day of Week"] == dow, rows))
    print(f"sending emails for {len(rows)} rows")
    i = 0
    for row in rows:
        i += 1
        sid = row["Session ID"]
        track = row["Track"]
        print(f"\r\nrow {i}/{len(rows)} Session {sid} - Track {track}")
        response = send_aws_email_paper(auth, row, template)
        print(f"    {response}")
        if i % 4 == 3:
            time.sleep(2)


def join_session_contributor_rows() -> List[dict]:
    """retrieve and join each session row with corresponding event row
    """
    sessions = GoogleSheets()
    sessions.load_sheet("Sessions")
    events = GoogleSheets()
    events.load_sheet("Events")
    tracks = GoogleSheets()
    tracks.load_sheet("Tracks")
    tracks_dict = dict()
    for t in tracks.data:
        tracks_dict[t["Track"]] = t

    events_dict = {}
    for ev in events.data:
        prefix = ev["Event Prefix"]
        if prefix and len(prefix) > 0:
            events_dict[prefix] = ev
    data = sessions.data
    for s in data:
        tr = s["Track"]
        if tr is not None and tr in tracks_dict:
            s.update(tracks_dict[tr])
        prefix = s["Event Prefix"]
        if not prefix or prefix not in events_dict:
            continue
        ev = events_dict[prefix]
        s.update(ev)
    return data


def join_slot_contributors() -> List[dict]:
    """retrieve and join each session row with corresponding event row, but also consolidate
    all presenters/speakers based on the associated slot items into the 'Slot Contributors Emails' column
    """
    sessions = join_session_contributor_rows()
    sessions_dict = {}
    for s in sessions:
        sessions_dict[s["Session ID"]] = s
    items1_sheet = GoogleSheets()
    items1_sheet.load_sheet("ItemsVIS-A")
    items2_sheet = GoogleSheets()
    items2_sheet.load_sheet("ItemsEXT")
    # items3_sheet = GoogleSheets()
    # items3_sheet.load_sheet("ItemsVISSpecial")

    items = []
    items.extend(items1_sheet.data)
    items.extend(items2_sheet.data)
    # items.extend(items3_sheet.data)

    items_by_session: dict[str, List[dict]] = {}

    for item in items:
        s_id = item["Session ID"]
        if type(s_id) != str or len(s_id.strip()) == 0 or s_id not in sessions_dict:
            print(f"WARNING: could not match session id {s_id}")
            continue

        if s_id in items_by_session:
            items_by_session[s_id].append(item)
        else:
            items_by_session[s_id] = [item]

    for s in sessions:
        s_id = s["Session ID"]
        s["Slot Contributors Emails"] = ""
        if type(s_id) != str or len(s_id.strip()) == 0 or s_id not in items_by_session:
            print(f"WARNING: could not match session id {
                  s_id} to any slot item")
            continue
        emails_set = set()
        emails = []
        items = items_by_session[s_id]
        for item in items:
            cont_emails: str = item["Slot Contributors Emails"]
            if type(cont_emails) != str or len(cont_emails) == 0:
                continue
            for em in cont_emails.split('|'):
                email: str = em.strip()
                h = email.lower()
                if h in emails_set:
                    continue
                emails_set.add(h)
                emails.append(email)
        s["Slot Contributors Emails"] = "|".join(emails)
    return sessions


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to send out info to contributors (e.g. session chairs)\r\nIMPORTANT: recipients have to be specified in template, modes only indicate the data that is fetched')

    parser.add_argument('--session', help='send email to session targets such hosts/chairs, event organizers without slot contributors info',
                        action='store_true', default=False)
    parser.add_argument('--speakers', help='send email to session targets such slot contributors, hosts/chairs, event organizers',
                        action='store_true', default=False)
    parser.add_argument('--ignore_various', help='do not send emails to events in various track (default)',
                        action='store_true', default=True)

    parser.add_argument(
        '--email_template', help='template to use for the email', default=None)
    parser.add_argument(
        '--dow', help='filter out sessions based on the dow ["Day of Week"] field (e.g. tue1, wed4)', default=None)
    parser.add_argument(
        '--event_prefix', help='filter sessions that match the event prefix', default=None)
    parser.add_argument(
        '--session_id', help='only send info concerning one session', default=None)

    args = parser.parse_args()
    auth = Authentication(email=True)

    templates = load_templates_dict()
    template_key = args.email_template
    if not template_key or template_key not in templates:
        print(f"could not found template {template_key}")
        exit(-1)
    template: dict = templates[template_key]

    if args.session:
        send_emails(auth, template, True, args.event_prefix,
                    args.session_id, args.ignore_various, args.dow)
    elif args.speakers:
        send_emails(auth, template, False, args.event_prefix,
                    args.session_id, args.ignore_various, args.dow)
