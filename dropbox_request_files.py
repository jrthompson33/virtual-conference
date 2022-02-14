from core.auth import Authentication
import dropbox
from dropbox.exceptions import ApiError
from dropbox.files import ListFolderResult, Metadata, FileMetadata, FolderMetadata, GetMetadataError, LookupError
from dropbox.file_requests import FileRequest, FileRequestDeadline
from typing import List

#specify root path of uploads etc.
root_folder = "/ieeevis_uploads" 


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
    if not folder_exists(dbx, root_folder):
        dbx.files_create_folder(root_folder)
        return True
    return False

def create_folder_requests(dbx : dropbox.Dropbox, title : str,  names : List[str], description : str = None, deadline : FileRequestDeadline = None) -> List:
    """create dropbox upload request links for each given name, pointing to <root_folder>/<name>.
    title: title of the request, must be set
    names: list of folder names that should be created
    description: optional description
    deadline: optional FileRequestDeadline, can only be set by pro/business accounts
    
    Returns request links and ids: [ { name: ' ', request_link: ' ', id: ' '}, ... ].
    IDs are important as they can be used to get or delete the request."""
    res = []
    
    if create_folder(dbx, root_folder):
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

if __name__ == '__main__':
    session = Authentication()
    with dropbox.Dropbox(session.dropbox["access_token"]) as dbx:
        #test access
        dbx.users_get_current_account()
        #test folder requests
        requests = create_folder_requests(dbx, "IEEE VIS Upload", ["v01", "v02"], description="Please upload your video and materials here.")
        print(requests)
