import argparse
from core.papers_db import PapersDatabase
from core.cvent_attendee import CventAttendee
from typing import List
from fuzzywuzzy import fuzz
import csv
import eventbrite_helper
import core.auth as auth
from core.google_sheets import GoogleSheets

def find_match(papers : PapersDatabase, attendee_name : str, attendee_email : str, title : str, p_id : str) -> dict:
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
        emails = paper['Contributor Email(s)'].split("|")
        
        if attendee_name:
            attendee_name = attendee_name.lower()
            author_fuzz_s = 0
            for author in authors:               
                s = fuzz.ratio(author.lower(), attendee_name)
                if s > 80 and s > author_fuzz_s:
                    author_fuzz_s = s
            score += int(author_fuzz_s/2)
        if attendee_email:
            attendee_email = attendee_email.lower().strip()
            for email in emails:
                if email.lower().strip() == attendee_email:
                    score += 100
                    break
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
        overrides = GoogleSheets()
        overrides.load_sheet("PresentationModes")
        mail_to_attendee = { at.email.lower() : at for at in attendees }
        num_matched = 0
        num_matched_ev = 0
        num_not_matched = 0
        num_not_matched_ev = 0
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
            paper['Practitioners'] = ""
        #sync cvent stuff
        for speaker in speakers:
            for paper_hint in speaker.papers:
                title = paper_hint[0]
                p_id = paper_hint[1]
                matched_paper = find_match(papers, speaker.first_name + " " + speaker.last_name, speaker.email, title, p_id)
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
                matched_paper['Speaker Registration'] = mode
                matched_paper['Speaker Registration Name'] = f"{speaker.first_name} {speaker.last_name}";

        #sync eventbrite registrations
        print("retrieving eventbrite registrations...")
        ev_attendees = eventbrite_helper.get_attendees(auth.Authentication())
        print(f"{len(ev_attendees)} attendees retrieved.")
        for at in ev_attendees:
            if at["cancelled"] or at["status"] != "Attending":
                continue
            answers = at["answers"]
            if answers and len(answers) > 0:
                for an in answers:
                    if an["question_id"] == "95219869":
                        paper_title = an["answer"] if "answer" in an else None
                        if paper_title and len(paper_title) > 0:
                            full_name = at["profile"]["name"]
                            email = at["profile"]["email"]
                            matched_paper = find_match(papers, full_name, email, paper_title, "")
                            if matched_paper is None:
                                print(f"could not match paper {paper_title} of speaker {full_name}")
                                num_not_matched_ev += 1
                                continue
                            ex_name = matched_paper['Speaker Registration Name']
                            if len(ex_name) > 0:
                                print(f"cannot set attendee {full_name}, cvent registration of {ex_name} already set")
                                continue
                            matched_paper['Speaker Registration'] = "virtual"
                            matched_paper['Speaker Registration Name'] = full_name
                            num_matched_ev += 1
                        break
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
                    paper = find_match(papers, None, g_email, row['Your paper title.'], uid)
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
                pract : str = row['What type of practitioners would be interested in reading this paper and/or attending your presentation (e.g. simulation scientists, data journalists, data scientists, biologists etc.)?  How could practitioners apply what they learn from this paper to their work?']
                if pract and len(pract.strip()) > 0:
                    paper['Practitioners'] = pract.strip()
                num_matched_google += 1
        num_matched_email = 0
        #collect final data
        for paper in papers.data:
            uid = paper['UID']
            if uid in overrides.data_by_index:
                override = overrides.data_by_index[uid]
                paper['Speaker Name'] = override['Speaker Name']
                paper['Speaker E-Mail'] = override['Speaker E-Mail']
                paper['Presentation Mode'] = override['Presentation Mode']
                continue
            mode = paper['Google Forms Speaker Mode']
            final_mode = ""
            cvent_reg_type = paper['Speaker Registration']
            if mode and len(mode) != 0:
                final_mode = mode
                paper['Speaker Name'] = paper['Google Forms Speaker Name']
            elif cvent_reg_type and len(cvent_reg_type) != 0 and cvent_reg_type != "both":
                final_mode = cvent_reg_type
                paper['Speaker Name'] = paper['Speaker Registration Name']
            if final_mode == "" and not cvent_reg_type or len(cvent_reg_type) == 0:
                #try to match with cvent list via email
                emails = paper['Contributor Email(s)'].split('|')
                for email in emails:
                    if email.strip().lower() in mail_to_attendee:
                        speaker = mail_to_attendee[email.strip().lower()]
                        mode = ""
                        if speaker.num_onsite > 0 and speaker.num_virtual > 0:
                            mode = ""
                        elif speaker.num_onsite > 0:
                            mode = "onsite"
                            final_mode = "onsite"
                        elif speaker.num_virtual > 0:
                            mode = "virtual"
                            final_mode = "virtual"
                        if mode != "":
                            paper['Speaker Registration'] = mode;
                            paper['Speaker Registration Name'] = f"{speaker.first_name} {speaker.last_name}";
                            paper['Speaker Name'] = paper['Speaker Registration Name']
                            num_matched_email += 1
                        break
            paper['Presentation Mode'] = final_mode

        print(f"{num_matched} papers matched with cvent, {num_not_matched} could not be matched.")
        print(f"{num_matched_ev} papers matched with eventbrite, {num_not_matched_ev} could not be matched.")
        print(f"{num_matched_google} papers matched with google forms responses")
        print(f"{num_matched_email} papers matched via email address and cvent")
        papers.save()
        print("saved.")