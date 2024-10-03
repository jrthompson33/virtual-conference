import argparse
import time
import json

import eventbrite_helper
import asn_registration_helper
import cvent_scraper

from enum import Enum

from auth0_helper import create_user, retrieve_users_via_export
from core.auth import Authentication

# Get eventbrite list


class Vendor(Enum):
    ASN = "asn"
    CVENT = "cvent"
    EVENTBRITE = "eventbrite"

    def __str__(self):
        return self.value


def get_eventbrite_attendees(auth: Authentication) -> list:
    eventbrite_attendees = eventbrite_helper.get_attendees(auth)
    return eventbrite_attendees


def get_asn_attendees(auth: Authentication) -> list:
    asn_attendees = asn_registration_helper.get_attendees(auth)
    return asn_attendees


def get_cvent_attendees(auth: Authentication) -> list:
    cvent_attendees = json.loads(cvent_scraper.get_attendees_json(auth))
    return cvent_attendees['Data']


def get_auth0_users(auth: Authentication) -> list:
    auth0_users = retrieve_users_via_export(auth, auth.get_auth0_token())
    return auth0_users


def sync_attendees(auth: Authentication, vendor: Vendor):
    attendees = []
    if vendor == Vendor.ASN:
        attendees = get_asn_attendees(auth)
    elif vendor == Vendor.CVENT:
        attendees = get_cvent_attendees(auth)
    elif vendor == Vendor.EVENTBRITE:
        attendees = get_eventbrite_attendees(auth)
    else:
        print(f"Unknown vendor of type = {vendor}")
        return

    auth0_users = get_auth0_users(auth)

    print(f"Found {len(attendees)} attendees from {vendor}")

    # Loop through and print attendees
    # for a in attendees:
    #     print(a)

    # # Loop through and print auth0 users
    # for au in auth0_users:
    #     print(au)

    auth_count = 0

    for a in attendees:
        name = None
        email = None
        isValid = False

        if vendor == Vendor.ASN:
            name = a['Name']
            email = a['Email']
            isValid = a['Item Name'] != 'Cancelled Registration - No Fee'
        elif vendor == Vendor.CVENT:
            name = a['FullName']
            email = a['EmailAddress']
            isValid = a['InviteeStatus'] == 'Accepted'
        elif vendor == Vendor.EVENTBRITE:
            name = a['profile']['name']
            email = a['profile']['email']
            isValid = a['cancelled'] == False
        else:
            print(f"Unknown vendor of type = {vendor}")
            return

        if name and email and isValid:
            # Check if user is already in auth0
            au = next((a for a in auth0_users if a['email'].strip(
            ).lower() == email.strip().lower()), None)
            if au == None:
                create_user(auth, auth.get_auth0_token(), email,
                            name, {'invite_email_sent': False})
                auth_count += 1
    print(f"{auth_count} attendees authorized in Auth0")


def monitor_sync_attendees(auth: Authentication, vendor: Vendor):
    """
    """
    print("monitoring started...")
    while True:
        try:
            sync_attendees(auth, vendor)
        except Exception as e:
            print(f"\r\nERROR OCCURRED: {e}\r\n")
        time.sleep(20*60)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Sync registered attendees from [EventBrite, ASN, or CVENT] with Auth0')
    parser.add_argument('--monitoring', help='monitor registered attendees and send to auth0',
                        action='store_true', default=False)
    parser.add_argument(
        '--sync', help='One time, sync registered attendees and send to auth0', action='store_true', default=True)

    parser.add_argument('--vendor', help='which vendor to pull registered attendees from',
                        type=Vendor, choices=list(Vendor), default=Vendor.ASN)
    args = parser.parse_args()

    auth = Authentication(auth0_api=True)
    args = parser.parse_args()

    if args.monitoring:
        monitor_sync_attendees(auth, args.vendor)
    elif args.sync:
        sync_attendees(auth, args.vendor)
