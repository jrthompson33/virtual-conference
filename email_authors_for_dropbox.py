from core.auth import Authentication
from core.templates import load_templates_dict
from core.papers_db import PapersDatabase
from core.aws_email import send_aws_email_paper

import argparse
import time


def send_emails_to_authors(auth: Authentication, papers_csv_file: str, event_prefix: str):
    """send email for papers .
    authentication: Authentication instance in which aws ses client was authenticated
    papers_csv_file: path to papers db file
    event_prefix: event prefix to send to, can only do one at a time

    """
    papersDb = PapersDatabase(papers_csv_file)
    templates = load_templates_dict()
    template = templates["upload_request"]
    papers = list(filter(lambda p: p["Event Prefix"] == event_prefix, papersDb.data))
    
    print(f"{len(papersDb.data)} total papers loaded, filtered for {event_prefix}, for which {len(papers)} papers will be processed.")

    for i in range(len(papers)):
        paper = papers[i]
        print(f"paper {i+1}/{len(papers)} {paper['UID']}")
        response = send_aws_email_paper(auth, paper, template)
        print(f"    {response}")
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
        '--papers_csv_file', help='path to papers db CSV file', default="ieeevis_papers_db.csv")
    parser.add_argument(
        '--event_prefix', help='filter papers that match the event prefix', default=None)

    args = parser.parse_args()
    auth = Authentication(email=True)

    if args.verify:
        # verify an email account
        acc = auth.email.verify_email_identity(
            EmailAddress='no-reply@ieeevis.org')
        print(acc)
    elif args.send:
        # send emails only if event_prefix provided, never send all db
        if args.event_prefix is not None:
            send_emails_to_authors(
                auth, args.papers_csv_file, args.event_prefix)
