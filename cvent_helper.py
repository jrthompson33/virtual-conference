import argparse
from core.papers_db import PapersDatabase
from core.cvent_attendee import CventAttendee
from typing import List
from fuzzywuzzy import fuzz
import csv

def find_match(papers : PapersDatabase, attendee : CventAttendee, title : str, p_id : str) -> dict:
    """try to match registration to paper and return matched paper
    """
    best_score = -1
    best_paper = None
    num_best_scores = 0
    for paper in papers.data:
        score = 0
        if p_id is not None and len(p_id) > 1 and (paper['UID'].lower() == p_id.lower() or paper['UID'].lower().endswith("-" + p_id.lower())):
            score += 200
        if title is not None:
            fuzz_s = fuzz.ratio(title, paper['Title'])
            if fuzz_s > 60:
                score += int(fuzz_s)
        authors = paper['Authors'].split("|")
        name = ""
        if attendee:
            name = attendee.first_name + " " + attendee.last_name
            author_fuzz_s = 0
            for author in authors:
                if author.lower().startswith(attendee.first_name.lower()) and author.lower().endswith(attendee.last_name.lower()):
                    author_fuzz_s = 100
                    break;
                s = fuzz.ratio(author, name)
                if s > 80 and s > author_fuzz_s:
                    author_fuzz_s = s
            score += int(author_fuzz_s/2)
        if score <= 0:
            continue
        if score > best_score:
            best_score = score
            best_paper = paper
            num_best_scores = 1
        elif score == best_score:
            num_best_scores += 1
    if best_score > 75 and num_best_scores == 1:
        if best_score < 100:
            print(f"WARNING: score of {best_score} for paper {best_paper['UID']} '{best_paper['Title']}' and attendee {attendee} with hint {title}, {p_id}")
        return best_paper
    return None
        

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Script to perform various Cvent actions and synching cvent and google forms inputs to the papers db.')

    
    parser.add_argument('--stats', help='retrieve statistics',
                        action='store_true', default=False)
    parser.add_argument('--sync_speaker_mode', help='try to infer speaker mode (virtal/onsite) for papers based on cvent registrations and google forms responses',
                        action='store_true', default=False)
    
    parser.add_argument('--cvent_path', help='path to cvent attendees json file', default="cvent_attendees.json")
    parser.add_argument('--forms_path', help='path to google forms respones csv file', default="VIS 2022 Paper General Information .csv")
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
        #first clear columns in case the new data is missing some of the previously present rows
        for paper in papers.data:
            paper['Speaker Registration'] = ""
            paper['Speaker Registration Name'] = ""
            paper['Google Forms Speaker Mode'] = ""
            paper['Google Forms Speaker Name'] = ""
            paper['Speaker E-Mail'] = ""
            paper['Speaker Name'] = ""
            paper['Presentation Mode'] = ""
            paper['Preprint URL'] = ""
        #sync cvent stuff
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

        #sync google forms responses
        num_matched_google = 0
        with open(args.forms_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row['Your unique submission ID'].strip()
                g_email = row['Email address of the presenter.'].strip()
                if len(uid) == 0:
                    print("WARNING: there is a google forms response with no UID specified")
                    continue
                if uid.count('-') < 2:
                    print("WARNING: there is a google forms response with a non-conforming UID: " + uid)
                if not uid in papers.data_by_uid:
                    print("WARNING: could not find paper with uid: " + uid)
                    #try matching
                    paper = find_match(papers, None, row['Your paper title.'], uid)
                    if paper is None or (not paper['UID'].endswith(uid) and paper['Contributor Email(s)'] != g_email):
                        print("ERROR: fuzzy search did not succeed, uid: " + uid)
                        continue
                    print("fuzzy search found a match.")
                else:
                    paper = papers.data_by_uid[uid]
                mode = ""
                mode_input = row['Is the presenter planning to attend the conference virtually?']
                if mode_input.startswith("No"):
                    mode = "onsite"
                elif mode_input.startswith("Yes"):
                    mode = "virtual"
                
                paper['Google Forms Speaker Mode'] = mode
                paper['Google Forms Speaker Name'] = row['Name of the presenter.']
                paper['Speaker E-Mail'] = g_email
                preprint = row["Please provide the link to your paper pre-print (e.g. https://arxiv.org/abs/####.#####)?"].strip()
                if ' ' in preprint:
                    preprint = preprint.split(' ')[0]
                if preprint.startswith("http"):
                    paper['Preprint URL'] = preprint
                paper['Practitioners'] = row['What type of practitioners would be interested in reading this paper and/or attending your presentation (e.g. simulation scientists, data journalists, data scientists, biologists etc.)?  How could practitioners apply what they learn from this paper to their work?']
                num_matched_google += 1
        for paper in papers.data:
            mode = paper['Google Forms Speaker Mode']
            final_mode = ""
            cvent_reg_type = paper['Speaker Registration']
            if mode and len(mode) != 0:
                final_mode = mode
                paper['Speaker Name'] = paper['Google Forms Speaker Name']
            elif cvent_reg_type and len(cvent_reg_type) != 0 and cvent_reg_type != "both":
                final_mode = cvent_reg_type
                paper['Speaker Name'] = paper['Speaker Registration Name']
            paper['Presentation Mode'] = final_mode

        print(f"{num_matched} papers matched with cvent, {num_not_matched} could not be matched.")
        print(f"{num_matched_google} papers matched with google forms responses")
        papers.save()
        print("saved.")