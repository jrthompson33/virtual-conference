from pydoc import describe
import os
import time
import uuid
import argparse
from typing import Any, List
from datetime import timezone, datetime, timedelta
import csv
import urllib.request

import core.auth as conf_auth


class GoogleSheets:
    def __init__(self):
        """Google Sheets helper class to retrieve csv data
        """
        self.auth = conf_auth.Authentication()
        self._link = self.auth.gsheets['db_link']
        self.data : List[dict[str, Any]] = []
        self.data_by_index : dict = {}
        self.sheet_name = ""
        if not self._link or not self._link.startswith("http"):
            raise RuntimeError("auth file needs to define sheet url via gsheets->db_link")

    def load_sheet(self, sheet_name : str):
        """Load data from sheet with the name sheet_name.
            First column is used as index if field name ends with ID (self.data_by_index)
        """
        url = self._link + "/gviz/tq?tqx=out:csv&sheet=" + sheet_name
        resp = urllib.request.urlopen(url)
        lines = [ l.decode('utf-8') for l in resp.readlines() ]
        cr = csv.DictReader(lines)
        self.fieldnames = cr.fieldnames
        self.sheet_name = sheet_name        
        self.data = []
        self.data_by_index : dict = {}

        index_key = None
        if self.fieldnames[0].lower().endswith("id"):
            index_key = self.fieldnames[0]

        for row in cr:            
            uid :str = row[index_key] if index_key else None            
            self.data.append(row)
            self.data_by_index[uid] = row

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
