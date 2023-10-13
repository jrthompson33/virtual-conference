from core.auth import Authentication

import argparse
import datetime
import json
import os
import requests
from lxml import html
import time
import pandas as pd


def format_time_iso8601_utc(dt: datetime):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def get_attendees(auth: Authentication):
    login_url = "https://members.asnevents.com.au/login"
    export_url = f"https://members.asnevents.com.au/event/{auth.asn['event_id']}/committee/report?Organisation=&EventAddon=&Export=Export"
    s = requests.Session()
    r = s.get(login_url)
    tree = html.fromstring(r.content)
    csrf_token = tree.xpath('//input[@name="csrf_token"]/@value')[0]

    time.sleep(1)

    login_data = {"Email": auth.asn['username'],
                  "Password": auth.asn['password'],
                  "Login": "Login",
                  "csrf_token": csrf_token,
                  }

    print("\r\nLogging in...\r\n")
    r = s.post("https://members.asnevents.com.au/login/do", data=login_data)

    if (r.status_code != 200):
        print("Error: " + str(r.status_code))
        return None

    tree = html.fromstring(r.content)

    # http get the export url - this should return an bit excel file
    # TODO: might need to add Headers to this request
    r = s.get(export_url)

    if (r.status_code != 200):
        print("Error: " + str(r.status_code))
        return None

    # Only use the columns we need, there are a lot more in the excel file
    columns_to_use = [
        "ID", "Email", "Title", "Name", "First Name", "Last Name",
        "Name Tag", "Gender", "Position", "Department", "Organisation",
        "Date Added", "Date Modified", "Checked", "Completed At", "Class Name",
        "App Login Token Create Date", "Student", "Trade",
        "Head Shot File", "Dietary Requirements", "Special Requirements",
        "App Login Token", "App Login Short URL", "Item Name"
    ]

    # Read in the excel file using pandas
    df = pd.read_excel(r.content, sheet_name="Worksheet",
                       header=0, usecols=columns_to_use)
    # convert all columns with Timestamp to string

    # loop through all columns
    for col in df.columns:
        # check if column is of timestamp type
        if df[col].dtype == "datetime64[ns]":
            # convert to string
            df[col] = df[col].apply(lambda x: format_time_iso8601_utc(
                x) if not pd.isnull(x) else None)

    # Return as json
    return df.to_dict(orient="records")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Eventbrite helper script')
    parser.add_argument('--list', action="store_true",
                        help='retrieve all attendees')
    parser.add_argument('--stats', action="store_true",
                        help='get stats about attendees')
    parser.add_argument('--save', action="store_true",
                        help='save all attendees')

    parser.add_argument(
        '--output_file', help='output file location to save asn_attendees', default="asn_attendees.json")
    parser.add_argument(
        '--output_dir', help='output directory location to save', default=".")

    args = parser.parse_args()
    auth = Authentication()
    attendees = get_attendees(auth)

    if args.list:
        print(json.dumps(attendees))
    if args.stats:
        count_dict = {}
        tot_count = 0
        for at in attendees:

            tot_count += 1
            # TODO: how to tell if they have cancelled?

            if "Class Name" in at:
                ticket_class = at["Class Name"]
                if ticket_class not in count_dict:
                    count_dict[ticket_class] = 1
                else:
                    count_dict[ticket_class] += 1
        print(count_dict)
        print(f"total num attendees: {tot_count}")
    if args.save:
        # Check for output path
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir, exist_ok=True)

        with open(os.path.join(args.output_dir, args.output_file), "w", encoding="utf8") as out_file:
            json.dump(attendees, out_file, indent=4)
