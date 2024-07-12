import argparse
import json
import csv
import os

import core.auth as auth
from core.google_sheets import GoogleSheets

event_prefix_dict = {
    "v-short": {
        "event": "VIS Short Papers",
        "event_type": "Short Paper Presentation",
        "event_prefix": "v-short",
    },
    "v-full": {

    }
}


def tidy_up_string(s):
    return s.replace(r"[\n\r\t]", " ").strip()


def id_to_uid(id: str, event_prefix: str):
    return "{0}-{1}".format(event_prefix, id.split("-")[1])


def format_author_name(a: any):
    if a["middle_initial"].strip() != "":
        return "{first_name} {middle_initial} {last_name} {name_suffix}".format(**a).strip()
    else:
        return "{first_name} {last_name} {name_suffix}".format(**a).strip()


def format_affiliation(a):
    """
    Format the affiliation of an author based on available fields.
    """
    aff_list = [a["institution"], a["city"], a["country"]]
    return ", ".join(filter(lambda x: x.strip() != "", aff_list))


def format_author_affiliations(affiliations):
    """
    Format the affiliations of an author. Use a tab to separate multiple affiliations for one author.
    """
    return "\t".join([format_affiliation(a) for a in affiliations])


def convert_pcs_data(event_prefix: str, pcs_path: str, output_path: str):
    """
    Convert PCS data in JSON format to CSV format that can be used in Google Sheets.
    """
    with open(pcs_path, "r", encoding="utf8") as pcs_file:
        pcs_data = json.load(pcs_file)

        rows = []
        if 'subs' in pcs_data:
            for p in pcs_data['subs']:
                authors = "|".join([format_author_name(a["author"])
                                   for a in p['authors']])
                affiliations = "|".join([format_author_affiliations(
                    a["affiliations"]) for a in p["authors"]])
                rows.append({'id': id_to_uid(p['id']), 'event': 'VIS Short Papers', 'event_type': 'Short Paper Presentation',
                             'event_prefix': 'v-short', 'title': tidy_up_string(p['title']), 'contributors': format_author_name(p['contact']),
                             'contributor_emails':  p['contact']['email'], 'authors': authors, 'author_affiliations': affiliations,
                             'abstract': tidy_up_string(p['abstract'])})

            with open(output_path, 'w', encoding='utf-8') as output_file:
                writer = csv.DictWriter(output_file, fieldnames=[
                                        "id", "event", "event_type", "event_prefix", "title", "contributors", "contributor_emails", "authors", "author_affiliations", "abstract"])
                writer.writerows(rows)
                return True

        else:
            print("Error: PCS JSON data not in correct format. Missing 'subs' key.")

        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to perform various actions on metadata from PCS. Needed to prepare data for Google Sheets.')

    parser.add_argument('--convert', help='convert PCS json data to flattened CSV file for Google Sheets.',
                        action='store_true', default=True)
    parser.add_argument(
        '--pcs_path', help='path to PCS json file', default="vis_papers.json")
    parser.add_argument(
        '--output_path', help='path to google forms respones csv file', default="vis_papers_compact.csv")
    parser.add_argument(
        '--event_prefix', help='event prefix (e.g., v-full, v-short)', required=True)

    args = parser.parse_args()

    if args.convert and args.event_prefix:
        result = convert_pcs_data(
            args.even_prefix, args.pcs_path, args.output_path)
        if result:
            print(
                f"Converted {args.event_prefix} PCS data to {args.output_path}")
        else:
            print(f"Error converting PCS data.")
