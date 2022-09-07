import argparse
from core.papers_db import PapersDatabase
from core.cvent_attendee import CventAttendee
from typing import List

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to perform various Cvent actions.')

    
    parser.add_argument('--stats', help='retrieve statistics',
                        action='store_true', default=False)
    
    parser.add_argument('--cvent_path', help='path to cvent attendees json file', default=None)

    
    args = parser.parse_args()
    
    if args.stats:
        attendees = CventAttendee.attendees_from_file(args.cvent_path)
        print(f"{len(attendees)} attendees parsed")
        speakers : List[CventAttendee] = list(filter(lambda it: it.is_speaker, attendees))
        print(f"{len(speakers)} speaker regs")
        num_authors_v = 0
        num_authors_o = 0
        for reg in attendees:
            num_authors_v += reg.num_papers_virtual
            num_authors_o += reg.num_papers_onsite
        print(f"{num_authors_v} virtual / {num_authors_o} on-site author regs, total = {num_authors_v + num_authors_o}")
        for speaker in speakers:
            if speaker.num_onsite > 0 and speaker.num_virtual > 0:
                print(f"{speaker} has on-site and virtual bookings")