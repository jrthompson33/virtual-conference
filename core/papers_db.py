from typing import List
import csv
import os
import json
import uuid

class PapersDatabase:
    """
    Read the stored metadata of papers/sessions from a specified CSV file that was exported from the Google Sheets workbook, for instance.    
    """
    def __init__(self, csv_file : str):
        """ Load and parse the specified csv file. First row must contain headers.
        """
        self.csv_file = csv_file
        data : List[dict] = []        
        self.data = data
        self.data_by_uid : dict = {}
        if not os.path.isfile(csv_file):
            raise RuntimeError(f"Could not find the specified csv_file '{csv_file}'")
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.fieldnames = reader.fieldnames
            for row in reader:
                uid :str = row['UID']
                if not uid:
                    raise RuntimeError(f"each entry in db needs to provide UID")
                if uid in self.data_by_uid:
                    raise RuntimeError(f"each entry in db needs a *unique* UID, '{uid}' appears at least twice")
                data.append(row)
                self.data_by_uid[uid] = row

    def save(self, target_fn : str = None):
        """Saves paper db to .csv file. Overwrites existing db file if no other target filename is specified.
        """
        if not target_fn:
            target_fn = self.csv_file
        temp_fn = target_fn + str(uuid.uuid4())
        with open(temp_fn, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, self.fieldnames)
            writer.writeheader()
            writer.writerows(self.data)
        os.replace(temp_fn, target_fn)
