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
    
    def download_presentation_video(self, uid : str, target_path : str):
        """Downloads presentation video and subtitles to target_path
        """
        pmu_item = self.data_by_index[uid]
        vid_name = "Presentation Video"
        pmu_video = pmu_item[vid_name] if vid_name in pmu_item else None
        pmu_subs = pmu_item[vid_name + " Subtitles"] if (vid_name + " Subtitles") in pmu_item else None
        video_url = pmu_video["url"] if pmu_video else None
        subs_url = pmu_subs["url"] if pmu_subs else None
        if not video_url:
            raise RuntimeError("no video url found for uid " + uid)
        
        print("downloading video " + video_url)
        video_path = os.path.join(target_path, pmu_video["fileName"])
        urllib.request.urlretrieve(video_url, video_path)

        subs_path = None
        if subs_url is not None and len(subs_url) > 0:
            print("downloading subtitles " + subs_url)
            subs_path = os.path.join(target_path, pmu_subs["fileName"])
            urllib.request.urlretrieve(subs_url, subs_path)

        return (video_path, subs_path)

