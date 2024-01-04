import sqlite3
import glob
import subprocess
from datetime import datetime, timedelta

# Variables
webDB = '/media/ascott/USB/database/web.db'

def ConnectAndQuery(query):
    # Connect to DB File
    conn = sqlite3.connect(webDB)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS web (duration TEXT, filepath TEXT)")
    cursor.execute(query)
    return cursor.fetchall()

def InsertWebData(duration, filepath):
    conn = sqlite3.connect(webDB)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO web (duration,filepath) VALUES (?,?)', (duration,filepath))
    conn.commit()
    conn.close()

def GetDuration(file):
    command = [
        "ffprobe",
         "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        "-sexagesimal",
        file
    ]

    durationStripList = ["\\n", "b'", "'"]
    duration = str(subprocess.check_output(command))
    for char in durationStripList:
        duration = duration.replace(char, '')
    return duration

def UpdateWebContentDB():
    webContent = glob.glob('/media/ascott/USB/web/*.mp4')
    for item in webContent:
        # Check if exist in DB
        searchQuery = f"SELECT * FROM web WHERE filepath='{item}'"
        results = ConnectAndQuery(searchQuery)

        if not results:
            # Insert into DB
            itemDuration = GetDuration(item)
            print(f'Inserting {item} - {itemDuration} into webDB')
            InsertWebData(itemDuration, item)
        else:
            print(f'{item} already in the DB')

UpdateWebContentDB()