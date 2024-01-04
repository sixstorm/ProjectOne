import sqlite3
import tvdb_v4_official
import re
import glob
import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

# Variables
tvSourceDir = "/media/ascott/USB/tv"
tvDBFile = "/media/ascott/USB/database/tvshows.db"

# Connect to DB file - This will create the file if it doesn't exist!
conn = sqlite3.connect(tvDBFile)
cursor = conn.cursor()

# Connect to TVDB API
apikey = "21857f0d-16b5-4d5e-8505-f46281ceabdd"
tvdb = tvdb_v4_official.TVDB(apikey)

def CreateTables():
    # Create tables if they don't exist
    cursor.execute("CREATE TABLE IF NOT EXISTS tvshows (id TEXT, showname TEXT, episodename TEXT, season INTEGER, episode INTEGER, overview TEXT, year INTEGER, genre TEXT, duration TEXT, filepath TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS tvshowmaster (id TEXT, name TEXT, year INTEGER, genre TEXT, folderpath TEXT)")

def DownloadEpisodeMetadata(showname, showDBFilePath):
    # Search TVDB for the Show
    searchShowName = showname.replace(" ","-")
    tvObj = tvdb.get_series_by_slug(searchShowName)
    allEpisodes = tvdb.get_series_episodes(tvObj["id"])
    if allEpisodes:
        # Write episode data to 'episodes.json' in the TV show folder
        with open(showDBFilePath, "a+") as file:
            file.write(json.dumps(allEpisodes))

def InsertEpisodeData(id,showname,episodename,season,episode,overview,year,genre,duration,filepath):
    cursor.execute("INSERT INTO tvshows (id,showname,episodename,season,episode,overview,year,genre,duration,filepath) VALUES (?,?,?,?,?,?,?,?,?,?)", (id,showname,episodename,season,episode,overview,year,genre,duration,filepath))
    conn.commit()

def CheckTVShowMasterDB(name):
    searchQuery = "SELECT * from tvshowmaster WHERE name='%s'" % name
    cursor.execute(searchQuery)
    result = cursor.fetchall()

    if result:
        return True
    else:
        return False

def InsertTVShowToMaster(name, year, id, genre, folderpath):
    cursor.execute("INSERT INTO tvshowmaster (id,name,year,genre,folderpath) VALUES (?,?,?,?,?)", (id, name, year, genre, folderpath))
    conn.commit()

def GetGenre(name):
    searchQuery = "SELECT * from tvshowmaster WHERE name='%s'" % name
    cursor.execute(searchQuery)
    result = cursor.fetchall()
    return result[0][3]

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

def ScanTVFolder():
    # Looks at TV root folders, checks to see if TV Series is in Master DB, 
    # downloads episode metadata if it doesn't exist
    for tvRootFolder in next(os.walk(tvSourceDir))[1]:
        showRootFolder = f'{tvSourceDir}/{tvRootFolder}'
        # print(f"{showRootFolder}")
        showName = re.search(".+?(?=\s\()", tvRootFolder)[0]  # Get TV show name from folder name, no year
        searchShowName = showName.replace(" ","-")
        year = re.search("(\d{4})", tvRootFolder)[0]  # Get year of TV show
        # print(f"{showName} - {searchShowName} - {year}")

        # Check to see if TV Series exists in the Master DB
        if not CheckTVShowMasterDB(showName):
            # Call out to TVDB and get metadata, both Series and Episodes
            tvObj = tvdb.get_series_by_slug(searchShowName)
            genre = tvdb.get_series_extended(tvObj["id"])["genres"][0]["name"]
            InsertTVShowToMaster(showName, tvObj["year"], tvObj["id"], genre, showRootFolder)
            
        # Download Episode Metadata
        epiDBFile = f'{showRootFolder}/episodes.json'
        if not Path(epiDBFile).is_file():
            print(f'Cannot find {epiDBFile}')
            DownloadEpisodeMetadata(showName, epiDBFile)

def CheckEpisodes():
    print(f'\nChecking for additions or removals\n')
    
    # Get all episodes from the database
    allEpisodes = cursor.execute("SELECT filepath FROM tvshows")
    results = cursor.fetchall()
    filesToRemove = [f[0] for f in results if not Path(f[0]).is_file()]

    if filesToRemove:
        print(f'Found {len(filesToRemove)} files to remove from the database')
        for f in filesToRemove:
            print(f'Attempting to remove {f}')
            cursor.execute("DELETE FROM tvshows WHERE filepath=?", (f,))
            conn.commit()


def UpdateEpisodeDB():
    for tvRootFolder in next(os.walk(tvSourceDir))[1]:
        showRootFolder = tvSourceDir+"/"+tvRootFolder
        epiDBFile = showRootFolder+"/episodes.json"
        showName = re.search(".+?(?=\s\()", tvRootFolder)[0]  # Get TV show name from folder name, no year

        # Get all TV Show episode files
        globQuery1 = showRootFolder+"/**/*.mkv"
        globQuery2 = showRootFolder+"/**/*.mp4"
        allEpisodes = glob.glob(globQuery1, recursive=True) + glob.glob(globQuery2, recursive=True)
        print(f"Found {len(allEpisodes)}")

        # Loop through each episode and process
        for episode in allEpisodes:
            searchQuery = "SELECT * from tvshows WHERE filepath='%s'" % episode
            cursor.execute(searchQuery)  # Execute SQL Query
            result = cursor.fetchall()

            if not result:
                # If episode is not found, put it into the DB

                # Extract season and episode numbers - Remove leading zeros
                seasonNumber = re.search("S(\d{2})", episode).group(1)
                if seasonNumber.startswith("0"):
                    seasonNumber = seasonNumber.lstrip('0')
                episodeNumber = re.search("E(\d{2})", episode).group(1)
                if episodeNumber.startswith("0"):
                    episodeNumber = episodeNumber.lstrip('0')

                # Find episode in the local 'episodes.json' file
                with open(epiDBFile) as episodeJSONFile:
                    episodesJSONDB = json.load(episodeJSONFile)

                # Check to see if episode exists in the tvshows database table
                print(f'{episode}')
                try:
                    episodeMetadata = [item for item in episodesJSONDB["episodes"] if item["seasonNumber"] == int(seasonNumber) and item["number"] == int(episodeNumber)][0]
                    if episodeMetadata:

                        id = episodeMetadata["id"]
                        episodeName = episodeMetadata["name"]
                        overview = episodeMetadata["overview"]
                        year = re.search("\d{4}", tvRootFolder)[0]  # Get TV show year from folder name
                        genre = GetGenre(showName)
                        duration = GetDuration(episode)
                        filePath = episode

                        InsertEpisodeData(id,showName,episodeName,seasonNumber,episodeNumber,overview,year,genre,duration,filePath)

                except IndexError:
                    pass

ScanTVFolder()
CheckEpisodes()
UpdateEpisodeDB()
