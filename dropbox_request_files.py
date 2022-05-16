from core.auth import Authentication
from core.templates import load_templates_dict
import dropbox
from core.papers_db import PapersDatabase
from dropbox.exceptions import ApiError
from dropbox.files import ListFolderResult, Metadata, FileMetadata, FolderMetadata, GetMetadataError, LookupError
from dropbox.file_requests import FileRequest, FileRequestDeadline
from typing import List
import argparse
import time

root_folder = ""

def folder_exists(dbx : dropbox.Dropbox, path : str) -> bool:
    try:
        m : Metadata = dbx.files_get_metadata(path)
        return isinstance(m, FolderMetadata)
    except ApiError as ex:
        err : GetMetadataError = ex.error
        if err.is_path():
            l_err : LookupError = err.get_path()
            if l_err.is_not_found():
                return False;
        raise ex

def file_exists(dbx : dropbox.Dropbox, path : str) -> bool:
    try:
        m : Metadata = dbx.files_get_metadata(path)
        return isinstance(m, FileMetadata)
    except ApiError as ex:
        err : GetMetadataError = ex.error
        if err.is_path():
            l_err : LookupError = err.get_path()
            if l_err.is_not_found():
                return False;
        raise ex
def create_folder(dbx : dropbox.Dropbox, path : str) -> bool:
    """ Creates folder if it does not yet exist. Returns True if the folder was created."""
    if not folder_exists(dbx, path):
        dbx.files_create_folder(path)
        return True
    return False

def create_folder_requests(dbx : dropbox.Dropbox, title : str,  names : List[str], description : str = None, deadline : FileRequestDeadline = None, create_root_folder : bool = True) -> List[dict]:
    """creates dropbox upload request links for each given name, pointing to <root_folder>/<name>.
    title: title of the request, must be set
    names: list of folder names that should be created
    description: optional description
    deadline: optional FileRequestDeadline, can only be set by pro/business accounts
    create_root_folder: can be set to False to avoid checking availability of root folder
    
    Returns request links and ids: [ { name: ' ', request_link: ' ', id: ' '}, ... ].
    IDs are important as they can be used to get or delete the request."""
    res = []
    
    if create_root_folder and create_folder(dbx, root_folder):
        print("root folder created")
    
    for name in names:
        try:
            p = f"{root_folder}/{name}"
            if create_folder(dbx, p):
                print(f"created folder {p}")
            fr : FileRequest = dbx.file_requests_create(title, p, deadline=deadline, description=description)
            print(f"created request {fr.id} for folder {p}")
            res.append({"name" : name, "request_link": fr.url, "id" : fr.id})
        except Exception as ex:
            print(f"the following exception has occurred: {ex}")
            #return object nonetheless as we may have already created links that we should save somewhere
            return res

    return res

def create_paper_request(dbx : dropbox.Dropbox, paper : dict, template : dict, deadline : FileRequestDeadline = None) -> dict:
    """Creates dropbox upload request link for specified paper (csv row as dict).
    Saves link and id to paper dict.
    Requires 'title' and 'description' template strings in specified template dict, will be formatted
    based on paper dict (i.e., paper dict keys can be used in curly braces as placeholders).

    Returns name, request_link, id as dict.
    """
    title = template['title'].format(**paper)
    description = template['description'].format(**paper)
    names = [ paper['UID'] ]
    res = create_folder_requests(dbx, title, names, description, deadline, False)[0]
    paper['File Request ID'] = res['id']
    paper['File Request Link'] = res['request_link']
    return res

def create_paper_requests(dbx : dropbox.Dropbox, papers_csv_file : str, event_prefix : str = None,
                         deadline : FileRequestDeadline = None):
    """Creates dropbox upload request links for papers.

    papers_csv_file: required CSV file with paper information
    event_prefix: if not None, only papers/items with that event prefix will be handled
    deadline: optional deadline for the file request as FileRequestDeadline object

    Saves respective links and ids to paper dicts and updates papers_csv_file accordingly.
    Requires 'title' and 'description' template strings in specified template dict, will be formatted
    based on paper dict (i.e., paper dict keys can be used in curly braces as placeholders).
    """
    papersDb = PapersDatabase(papers_csv_file)
    templates = load_templates_dict()
    template = templates["paper_dropbox_requests"]
    papers = papersDb.data
    if event_prefix:
        papers = list(filter(lambda p: p["Event Prefix"] == event_prefix, papers))
    print(f"{len(papersDb.data)} papers loaded, of which {len(papers)} will be processed.")

    for i in range(len(papers)):
        paper = papers[i]
        print(f"paper {i+1}/{len(papers)} {paper['UID']}")
        if paper['File Request Link'].startswith("http"):
            print("    skipped since there is already a file request link.")
            continue
        links = create_paper_request(dbx, paper, template)
        print(f"    {links}")
        papersDb.save()
        print(f"    saved. Waiting 10s...")
        time.sleep(10)
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Script to create dropbox file requests automatically.')
    
    parser.add_argument('--create', help='create paper upload requests and update paper db', action='store_true', default=False)
    parser.add_argument('--test', help='test credentials by returning current user account', action='store_true', default=False)

    parser.add_argument('--root_folder', help='parent folder in the dropbox for uploads', default="/ieeevis_uploads")
    parser.add_argument('--papers_csv_file', help='path to papers db CSV file', default="ieeevis_papers_db.json")
    parser.add_argument('--event_prefix', help='filter papers that match the event prefix', default=None)
    FileRequestDeadline()
    

    args = parser.parse_args()
    
    root_folder = args.root_folder

    session = Authentication()
    with dropbox.Dropbox(session.dropbox["access_token"]) as dbx:
        if args.test:
            #test access
            print(f"root folder: {root_folder}")
            acc = dbx.users_get_current_account()
            print(acc)
        elif args.create:
            create_paper_requests(dbx, args.papers_csv_file, args.event_prefix)
        #test folder requests
        #requests = create_folder_requests(dbx, "IEEE VIS Upload", ["v01", "v02"], description="Please upload your video and materials here.")
        #print(requests)
