from core.auth import Authentication
from core.templates import load_templates_dict
from core.google_sheets import GoogleSheets
from core.aws_email import send_aws_email_paper

import argparse
import time


def send_emails_to_authors(auth: Authentication, event_prefix: str, email_template: str, uid: str = None):
    """send email for papers .
    authentication: Authentication instance in which aws ses client was authenticated
    papers_csv_file: path to papers db file
    event_prefix: event prefix to send to, can only do one at a time

    """
    sheet_db_papers = GoogleSheets()
    sheet_db_papers.load_sheet("PapersDB")
    templates = load_templates_dict()

    sheet_events = GoogleSheets()
    sheet_events.load_sheet("Events")
    events_prefix_dict = dict()

    for e in sheet_events.data:
        events_prefix_dict[e["Event Prefix"]] = e["Event"]

    if email_template == "upload_request":
        if event_prefix == "v-spotlights" or event_prefix == "a-biomedchallenge" or event_prefix == "a-scivis-contest" or event_prefix == "w-visxai" or event_prefix == "w-nlviz" or event_prefix == "w-pdav" or event_prefix == "w-future" or event_prefix == "w-firstperson":
            template = templates["upload_request_associated_event_no_xplore"]
        elif event_prefix == "w-test" or event_prefix == "a-test" or event_prefix == "a-visap" or event_prefix == "s-vds" or event_prefix == "a-ldav" or event_prefix == "w-topoinvis" or event_prefix == "w-beliv" or event_prefix == "w-uncertainty" or event_prefix == "w-storygenai" or event_prefix == "w-accessible" or event_prefix == "w-energyvis" or event_prefix == "w-vis4climate" or event_prefix == "w-eduvis":
            template = templates["upload_request_associated_event_xplore"]
        elif event_prefix == "v-tvcg" or event_prefix == "v-cga" or event_prefix == "v-test":
            template = templates["upload_request_tvcg_cga"]
        elif event_prefix == "v-short" or event_prefix == "v-full":
            template = templates["upload_request_full_short"]
    elif email_template == "missing_preview":
        if event_prefix == "v-cga" or event_prefix == "v-tvcg":
            template = templates["missing_preview_tvcg_cga"]
        else:
            template = templates["missing_preview"]
    elif email_template == "missing_urgent":
        if event_prefix == "v-cga" or event_prefix == "v-tvcg" or event_prefix == "v-short" or event_prefix == "v-full":
            template = templates["missing_urgent"]
        else:
            template = templates["missing_urgent_workshop"]
    elif email_template == "presentation_tips":
        template = templates["presentation_tips"]
    elif email_template == "copyright_delay":
        template = templates["copyright_delay"]
    elif email_template == "missing_video":
        template = templates["missing_video"]
    elif email_template == "reminder_survey":
        template = templates["reminder_survey"]

    if uid is not None:
        papers = list(filter(lambda p: p["UID"] == uid, sheet_db_papers.data))
    elif event_prefix is not None:
        papers = list(
            filter(lambda p: p["Event Prefix"] == event_prefix, sheet_db_papers.data))

    print(f"{len(sheet_db_papers.data)} total papers loaded, filtered for {
          event_prefix}, for which {len(papers)} papers will be processed.")

    print(events_prefix_dict)
    for i in range(len(papers)):
        paper = papers[i]
        if paper["Event Prefix"] in events_prefix_dict:
            paper["Event"] = events_prefix_dict[paper["Event Prefix"]]
        else:
            print("event_prefix not found!")
        print(f"paper {i+1}/{len(papers)} {paper['UID']}")
        response = send_aws_email_paper(auth, paper, template)
        print(f"    {response}")
        if i % 4 == 3:
            print(f"    saved. Waiting 2s...")
            time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to email paper authors to request files via dropbox.')

    parser.add_argument('--verify', help='verify email identity for no-reply@ieeevis.org',
                        action='store_true', default=False)
    parser.add_argument('--send', help='send upload request emails for paper db and event-prefix',
                        action='store_true', default=False)

    parser.add_argument(
        '--event_prefix', help='filter papers that match the event prefix', default=None)
    parser.add_argument(
        '--uid', help='filter papers that match this UID', default=None)
    parser.add_argument(
        '--email_template', help='template to use for the email (e.g., \"upload_request\", \"missing_preview\")', default="upload_request")

    args = parser.parse_args()
    auth = Authentication(email=True)

    if args.verify:
        # verify an email account
        acc = auth.email.verify_email_identity(
            EmailAddress='tech@ieeevis.org')
        print(acc)
    elif args.send:
        # send emails only if event_prefix provided, never send all db
        if args.event_prefix is not None:
            send_emails_to_authors(
                auth, args.event_prefix, args.email_template, args.uid)
