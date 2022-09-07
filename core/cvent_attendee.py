from __future__ import annotations
import json
from typing import List

def get_survey_item(registration_json : dict, question_text : str) -> dict:
    survey = registration_json["EventSurveyDetail"]
    if not survey or len(survey) == 0:
        return None
    
    for question in survey:
        if question["QuestionText"] == question_text:
            return question

    return None

def get_survey_answer(registration_json : dict, question_text : str) -> str:
    item = get_survey_item(registration_json, question_text)
    if not item:
        return None
    answer = item["AnswerText"]
    if not answer:
        return None
    if type(answer) == str:
        return answer
    if len(answer) > 0:
        return answer[0]
    return None

class CventAttendee:
    """Represents parsed Cvent Registration with most important information
    """
    def __init__(self, registration_json : dict):
        self.registration_json = registration_json
        self.id = registration_json["Id"]
        self.first_name = registration_json["FirstName"]
        self.last_name = registration_json["LastName"]
        self.company = registration_json["Company"]
        self.title = registration_json["Title"]
        self.last_name = registration_json["LastName"]
        self.email = registration_json["EmailAddress"]
        self.is_speaker = get_survey_answer(registration_json, "Are you a pre-recorded or live speaker? (Paper presenter, poster presenter, panelist, session chair, art exhibitor, etc.)") == "Yes, I am a speaker"
        self.paper_or_session_titles = get_survey_answer(registration_json, "List all paper presentations or session titles in which you will present:")
        #array of [paper title : str, paper id : str]
        self.papers = []
        if self.is_speaker:
            for i in range(1, 10):
                title = get_survey_answer(registration_json, f"Paper Title #{i}")
                paper_id = get_survey_answer(registration_json, f"Paper ID #{i}")
                if title is None and paper_id is None:
                    if i == 1:
                        #one old reg item does not have Paper Title question
                        self.papers.append([self.paper_or_session_titles, None])
                    break
                self.papers.append([title, paper_id])
        orders = registration_json["OrderDetail"]
        #numer of on-site admission items
        self.num_onsite = 0
        #number of virtual admission items
        self.num_virtual = 0
        self.num_papers_onsite = 0
        self.num_papers_virtual = 0
        self.amount_due = 0
        if orders is not None and len(orders) > 0:
            for item in orders:
                if item["ProductType"] != "Admission Item":
                    continue
                self.amount_due += item["AmountDue"]
                product_name = item["ProductName"]
                product_code = item["ProductCode"]
                if "Virtual " in product_name:
                    self.num_virtual += 1                    
                elif "On-site " in product_name:
                    self.num_onsite += 1
                if "V-Invited" in product_code or "V-Author" in product_code:
                    self.num_papers_virtual += 1
                elif "O-Invited" in product_code or "O-Author" in product_code:
                    self.num_papers_onsite += 1

    def __str__(self):
        return f"{self.id}: {self.first_name} {self.last_name}"

    @classmethod
    def attendees_from_file(cls, path : str) -> List[CventAttendee]:
        """load json file with Cvent Registrations as array and parse them as list of CventAttendee
        """
        with open(path, 'r', encoding='utf-8') as f:
            reg_list = json.load(f)
            if not isinstance(reg_list, list):
                raise RuntimeError(f"loaded file '{path} is not a JSON array'")
            res = []
            for reg in reg_list:
                res.append(cls(reg))
        return res

