import argparse
import sys
import time
import os
import json
import os.path as path
import string
import time

from urllib.parse import urlsplit
from datetime import datetime
from email.mime.image import MIMEImage
import urllib.request

import core.auth as auth

alphabet = string.ascii_letters + string.digits


def call_get_attendees(session : auth.Authentication, page : int = 1):
    url = f"https://www.eventbriteapi.com/v3/events/{session.eventbrite_event_id}/attendees/?token={session.eventbrite_token}&page={page}"
    req=urllib.request.Request(url,
         headers={"Content-Type":"application/json"}
    )
    with urllib.request.urlopen(req) as u:
        return json.loads(u.read().decode('utf-8'))

def get_attendees(session : auth.Authentication):
    
    # Get the resource URI for the attendee page since we have to do the paginated
    # requests ourselves
    #attendees = session.eventbrite.get_event_attendees(eventbrite_event_id)
    attendees = call_get_attendees(session)
    last_page = attendees["pagination"]["page_count"]

    # Note: Eventbrite's python SDK is half written essentially, and
    # doesn't directly support paging properly. So to load the other
    # pages we need to use the raw get call ourselves instead of 
    # being able to continue calling get_event_attendees
    # It looks like we can also directly request a page by passing page: <number>

    res = []
    # Page indices start at 1 inclusive
    for i in range(1, last_page + 1):
        #print(f"Fetching eventbrite registrations page {i} of {last_page}")        
        attendees = call_get_attendees(session, i)
        if not "attendees" in attendees:
            print("Error fetching eventbrite response?")
            print(attendees)
            break
        res.extend(attendees["attendees"])

    return res


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Eventbrite helper script')
    parser.add_argument('--list', action="store_true", help='retrieve all attendees')
    parser.add_argument('--stats', action="store_true", help='get stats about attendees')
    parser.add_argument('--save', action="store_true", help='save all attendees')

    parser.add_argument(
        '--output_file', help='output file location to save eventbrite_attendees', default="eventbrite_attendees.json")
    parser.add_argument(
        '--output_dir', help='output directory location to save', default=".")
   
    args = parser.parse_args()
    s = auth.Authentication()
    if args.list:
        attendees = get_attendees(s)
        print(json.dumps(attendees))
    if args.stats:
        #"ticket_class_name"
        attendees = get_attendees(s)
        count_dict = {}
        tot_count = 0
        for at in attendees:
            if at["cancelled"]:
                continue

            if "ticket_class_name" in at:
                ticket = at["ticket_class_name"]
                tot_count += 1
                if ticket not in count_dict:
                    count_dict[ticket] = 1
                else:
                    count_dict[ticket] += 1
        print(count_dict)
        print(f"total num attendees: {tot_count}")
    if args.save:
        attendees = get_attendees(s)
        # Check for output path
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir, exist_ok=True)

        with open(os.path.join(args.output_dir, args.output_file), "w", encoding="utf8") as f:
            json.dump(attendees, f, indent=4)

    