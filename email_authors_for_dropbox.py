from core.auth import Authentication
from core.templates import load_templates_dict
from core.papers_db import PapersDatabase
from core.aws_email import send_aws_email_paper

import argparse
import time


def send_emails_to_authors(auth: Authentication, papers_csv_file: str):
    print(papers_csv_file)
    papersDb = PapersDatabase(papers_csv_file)
    templates = load_templates_dict()
    template = templates["upload_request"]
    papers = papersDb.data
    print(f"{len(papersDb.data)} papers loaded, of which {len(papers)} will be processed.")

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

    parser.add_argument('--test', help='test credentials by returning current user account',
                        action='store_true', default=False)

    parser.add_argument(
        '--papers_csv_file', help='path to papers db CSV file', default="ieeevis_papers_db.csv")

    args = parser.parse_args()

    auth = Authentication(email=True)

    if args.test:
        # test access
        acc = auth.email.verify_email_identity(
            EmailAddress='publications@ieeevis.org')
        print(acc)
    else:
        send_emails_to_authors(auth, args.papers_csv_file)
