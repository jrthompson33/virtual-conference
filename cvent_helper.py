import argparse
from core.papers_db import PapersDatabase
from core.cvent_attendee import CventAttendee
from typing import List
from fuzzywuzzy import fuzz

def find_match(papers : PapersDatabase, attendee : CventAttendee, title : str, p_id : str) -> dict:
    """try to match registration to paper and return matched paper
    """
    best_score = -1
    best_paper = None
    num_best_scores = 0
    for paper in papers.data:
        score = 0
        if p_id is not None and (paper['UID'] == p_id or paper['UID'].endswith("-" + p_id)):
            score += 10
        if title is not None:
            fuzz_s = fuzz.ratio(title, paper['Title'])
            if fuzz_s > 0.5:
                score += int(fuzz_s*10)
        authors = paper['Authors'].split("|")
        name = attendee.first_name + " " + attendee.last_name
        author_fuzz_s = 0
        for author in authors:
            s = fuzz.ratio(author, name)
            if s > 0.8 and s > author_fuzz_s:
                author_fuzz_s = s
        score += author_fuzz_s*5
        if score == 0:
            continue
        if score > best_score:
            best_score = score
            best_paper = paper
            num_best_scores = 1
        elif score == best_score:
            num_best_scores += 1
    if best_score != -1 and num_best_scores == 1:
        if best_score < 10:
            print(f"warning, score of {best_score} for paper {paper['UID']} and attendee {attendee} with hint {title}, {p_id}")
        return best_paper
    return None
        

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to perform various Cvent actions.')

    
    parser.add_argument('--stats', help='retrieve statistics',
                        action='store_true', default=False)
    parser.add_argument('--sync_speaker_mode', help='try to infer speaker mode (virtal/onsite) for papers based on cvent registrations',
                        action='store_true', default=False)
    
    parser.add_argument('--cvent_path', help='path to cvent attendees json file', default="cvent_attendees.json")
    parser.add_argument('--papers_csv_file', help='path to papers db CSV file', default="IEEEVIS_22_Papers_Compact.csv")

    
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
    elif args.sync_speaker_mode:
        attendees = CventAttendee.attendees_from_file(args.cvent_path)
        papers = PapersDatabase(args.papers_csv_file)
        speakers : List[CventAttendee] = list(filter(lambda it: it.is_speaker, attendees))
        num_matched = 0
        num_not_matched = 0
        for paper in papers.data:
            paper['Speaker Registration'] = ""
        for speaker in speakers:
            for paper_hint in speaker.papers:
                title = paper_hint[0]
                p_id = paper_hint[1]
                matched_paper = find_match(papers, speaker, title, p_id)
                if matched_paper is None:
                    print(f"could not match paper {paper_hint} of speaker {speaker}")
                    num_not_matched += 1
                    continue
                num_matched += 1
                mode = "missing"
                if speaker.num_onsite > 0 and speaker.num_virtual > 0:
                    mode = "both"
                elif speaker.num_onsite > 0:
                    mode = "onsite"
                elif speaker.num_virtual > 0:
                    mode = "virtual"
                matched_paper['Speaker Registration'] = mode;
                matched_paper['Speaker Registration Name'] = f"{speaker.first_name} {speaker.last_name}";

        print(f"{num_matched} papers matched, {num_not_matched} could not be matched.")
        papers.save()
        print("saved.")