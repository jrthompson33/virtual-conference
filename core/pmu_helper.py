import json
from pydoc import describe
import os
import time
import uuid
import argparse
from typing import Any, Dict, List, Tuple
from datetime import timezone, datetime, timedelta
import csv
import urllib.request

import core.auth as conf_auth


class PmuHelper:
    def __init__(self):
        """Helper class to retrieve URLs from the PMU system
        """
        self.auth = conf_auth.Authentication()
        self._link = self.auth.pmu["items_url"]
        pmu_items_json = urllib.request.urlopen(self._link).read()
        self.data = json.loads(pmu_items_json)
        self.data_by_index : Dict[str, Dict[str, Dict[str, Any]]] = {}
        for o in self.data:
            uid = o["uid"]
            it = o["items"]
            dct = {}
            self.data_by_index[uid] = dct
            for uit in it:
                dct[uit["name"]] = uit
                

    def get_video_urls(self, uid : str, is_ff : bool = False) -> Tuple[str, str]:
        """return download links of video and subtitles for provided uid (set to None if not available)
        """
        
        pmu_item = self.data_by_index[uid]
        vid_name = "Video Preview" if is_ff else "Presentation Video"
        pmu_video = pmu_item[vid_name] if vid_name in pmu_item else None
        pmu_subs = pmu_item[vid_name + " Subtitles"] if (vid_name + " Subtitles") in pmu_item else None
        video_url = pmu_video["url"] if pmu_video else None
        subs_url = pmu_subs["url"] if pmu_subs else None
        return (video_url, subs_url)

    def save(self, target_fn : str = None):
        """Saves sheet to .csv file. Target path is './tmp/<sheet name>.csv' if none is specified. Overwrites existing file.
        """
        if not self.sheet_name or len(self.sheet_name) == 0:
            raise RuntimeError("no sheet loaded that could be saved")
        if not target_fn:
            if not os.path.exists("./tmp"):
                os.mkdir("./tmp")
            target_fn = "./tmp/" + self.sheet_name + ".csv"
        temp_fn = target_fn + str(uuid.uuid4())
        with open(temp_fn, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, self.fieldnames)
            writer.writeheader()
            writer.writerows(self.data)
        try:
            os.replace(temp_fn, target_fn)
        except PermissionError:
            time.sleep(5)
            os.replace(temp_fn, target_fn)
