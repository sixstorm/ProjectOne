import random
import glob
import sqlite3
import calendar
import json
import os
import subprocess
import time
from jinja2 import FileSystemLoader, Environment
from datetime import datetime, timedelta

tvDB = '/media/ascott/USB/database/tvshows.db'
movieDB = '/media/ascott/USB/database/movies.db'
channelDB = '/media/ascott/USB/database/channels.db'
collectionsDB = '/media/ascott/USB/database/collections.db'
scheduleDB = '/media/ascott/USB/database/schedule.db'
commercials = glob.glob('/media/ascott/USB/bumpers/*.mp4')
jinjaEnv = Environment(loader=FileSystemLoader('/home/ascott/Project1/templates'))
jinjaTemplate = jinjaEnv.get_template('schedule.html')
dateFormat = datetime.now().strftime('%Y%m%d')

# Web Content
webContent = glob.glob('/media/ascott/USB/web/*.mp4')
while len(webContent) == 0:
    print('Found no content in the web folder, waiting 5 seconds')
    time.sleep(5)
    webContent = glob.glob('/media/ascott/USB/web/*.mp4')

# Initialize Schedule DB
conn = sqlite3.connect(scheduleDB)
cursor = conn.cursor()
# cursor.execute("DROP TABLE schedule")
cursor.execute("CREATE TABLE IF NOT EXISTS schedule (channelNumber TEXT, channelName TEXT, name TEXT, start TEXT, end TEXT, filepath TEXT)")
conn.commit()
conn.close()




class Channel:
    def __init__(self, name, number, logo, ordered, enabled, commercials, mediatypes, template):
        self.name = name
        self.number = number
        self.logo = logo
        self.ordered = ordered
        self.enabled = enabled
        self.commercials = commercials
        self.mediatypes = mediatypes
        self.template = template

class Episode:
    def __init__(self, showname, episodename, season, episode, overview, year, genre, duration, filepath):
        self.showname = showname
        self.episodename = episodename
        self.season = season
        self.episode = episode
        self.overview = overview
        self.year = year
        self.genre = genre
        self.duration = duration
        self.filepath = filepath

class Movie:
    def __init__(self, moviename, year, overview, rating, genre, duration, filepath):
        self.moviename = moviename
        self.year = year
        self.overview = overview
        self.rating = rating
        self.genre = genre
        self.duration = duration
        self.filepath = filepath

class TimeBlock:
    def __init__ (self, start, end, ratingAllowed, mediaType, genres):
        self.start = start
        self.end = end
        self.ratingAllowed = ratingAllowed
        self.mediaType = mediaType
        self.genres = genres

class Collection:
    def __init__(self, name, movies, series):
        self.name = name
        self.movies = movies
        self.series = series

    def GetMovies(self):
        '''
        Retrieves all movies in the collection and returns them in a shuffled state
        '''
        finalMovies = []
        allMovies = ConnectAndQuery(movieDB, 'SELECT * FROM movies')
        collectionMovies = self.movies.split(', ')

        for m in collectionMovies:
            for item in allMovies:
                if m in item[1]:
                    finalMovies.append(item)

        random.shuffle(finalMovies)
        return finalMovies

    def GetEpisodes(self):
        '''
        Retrieves all episodes in the collection and returns them in a shuffled state
        '''
        finalEpisodes = []
        allEpisodes = ConnectAndQuery(tvDB, 'SELECT * FROM tvshows')
        collectionEpisodes = self.series.split(', ')

        # Go through each item in collection episodes and find in the allEpisodes results
        for e in collectionEpisodes:
            for item in allEpisodes:
                if e in allEpisodes[1]:
                    finalEpisodes.append(item)

        random.shuffle(finalEpisodes)
        return finalEpisodes


def ScanChannelFiles():
    '''
    Returns all channel files
    '''
    return glob.glob('/media/ascott/USB/channels/*.json')  # Returns a list of each channel file in list

def GetCollection(channelName):
    '''
    Retreives a Collection from the Collection database if it exists
    '''

    query = f"SELECT * FROM collections WHERE name='{channelName}'"
    results = ConnectAndQuery(collectionsDB, query)  # List
    return Collection(results[0][0], results[0][1], results[0][2])

def CheckForCollection(channelName):
    '''
    Checks to see if a Collection exists in the database
    '''
    
    query = f"SELECT * FROM collections WHERE name='{channelName}'"
    results = ConnectAndQuery(collectionsDB, query)
    if results:
        return True
    else:
        return False

def ConnectAndQuery(DB, query):
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute(query)
    items = cursor.fetchall()
    conn.close()
    return items

def CreateHTMLSchedule(masterSchedule, masterChannelList):
    if os.path.exists('/media/ascott/USB/schedule.html'):
        os.remove('/media/ascott/USB/schedule.html')

    for channel in sorted(masterChannelList, key=lambda d: d.number):
        jinjaList = []
        tempSchedule = sorted([i for i in masterSchedule if i['channelNumber'] == channel.number], key=lambda d: d['start'])
        for item in tempSchedule:
            jinjaList.append(item)

        # print(jinjaList)

        outputJinja = jinjaTemplate.render(channelQueue=jinjaList, channelName=channel.name, channelNumber=channel.number)
        with open('/media/ascott/USB/schedule.html', 'a') as s:
            s.write(outputJinja)

def NextTimeBlock(itemEndTime):
    '''
    Returns the next available timeblock based on 15 minute increments
    '''
    try:
        if itemEndTime.minute >= 0 and itemEndTime.minute < 15:
            nextTimeBlock = itemEndTime.replace(minute=15, second=0)
        elif itemEndTime.minute >= 15 and itemEndTime.minute < 30:
            nextTimeBlock = itemEndTime.replace(minute=30, second=0)
        elif itemEndTime.minute >= 30 and itemEndTime.minute < 45:
            nextTimeBlock = itemEndTime.replace(minute=45, second=0)
        elif itemEndTime.minute >= 45 and itemEndTime.minute <= 59:
            if itemEndTime.hour == 23:
                nextTimeBlock = itemEndTime.replace(hour=0, minute=00, second=0) + timedelta(1)
            else:
                nextTimeBlock = itemEndTime.replace(hour=(itemEndTime.hour + 1), minute=00, second=0)
        return nextTimeBlock
    except:
        print('NextTimeBlock Error')

def GetDuration(file):
    '''
    Returns the duration of a media file in seconds using FFProbe
    '''
    command = [
        'ffprobe',
         '-v',
        'error',
        '-show_entries',
        'format=duration',
        '-of',
        'default=noprint_wrappers=1:nokey=1',
        '-sexagesimal',
        file
    ]

    durationStripList = ['\\n', "b'", "'"]
    duration = str(subprocess.check_output(command))
    for char in durationStripList:
        duration = duration.replace(char, '')
    return duration

def FillPPVChannel(ppvMovie, channelObj, blockStart, blockEnd):
    marker = blockStart
    schedule = []
    while marker < blockEnd:
        # Create dictionary for each instance
        tempMovieDuration = datetime.strptime(ppvMovie.duration, '%H:%M:%S.%f')
        movieDuration = timedelta(hours=tempMovieDuration.hour, minutes=tempMovieDuration.minute, seconds=tempMovieDuration.second)
        scheduleDict = {
                'channelNumber': channelObj.number,
                'channelName': channelObj.name,
                'name': ppvMovie.moviename,
                'start': marker,
                'end': (marker + movieDuration),
                'filepath': ppvMovie.filepath
                }

        schedule.append(scheduleDict)

        marker = marker + movieDuration

    return schedule

def FillWebChannel(webContent, channelObj, blockStart, blockEnd):
    marker = blockStart
    webDB = '/media/ascott/USB/database/web.db'
    schedule = []

    print(f'Block ends at {blockEnd}')

    while marker < blockEnd:
        # Randomize MP4s
        random.shuffle(webContent)

        for webItem in webContent:
            # Search Web DB to get duration
            searchQuery = """SELECT duration FROM web WHERE filepath=?"""
            conn = sqlite3.connect(webDB)
            cursor = conn.cursor()
            cursor.execute(searchQuery, (webItem,))
            results = cursor.fetchall()
            conn.close()

            if results:
                tempWebDuration = datetime.strptime(results[0][0], '%H:%M:%S.%f')  # Str to Datetime
                webItemDuration = timedelta(hours=tempWebDuration.hour, minutes=tempWebDuration.minute, seconds=tempWebDuration.second)
                print(f'File {webItem} - {webItemDuration}')
                scheduleDict = {
                    'channelNumber': channelObj.number,
                    'channelName': channelObj.name,
                    'name': webItem,
                    'start': marker,
                    'end': (marker + webItemDuration),
                    'filepath': webItem
                }
                # print(f'\n{scheduleDict}\n')
            else:            
                webItemDuration = GetDuration(webItem)
                tempWebDuration = datetime.strptime(webItemDuration, '%H:%M:%S.%f')
                webItemDuration = timedelta(hours=tempWebDuration.hour, minutes=tempWebDuration.minute, seconds=tempWebDuration.second)
                print('Getting duration')
                print(f'File {webItem} - {webItemDuration}')
                scheduleDict = {
                    'channelNumber': channelObj.number,
                    'channelName': channelObj.name,
                    'name': webItem,
                    'start': marker,
                    'end': (marker + webItemDuration),
                    'filepath': webItem
                }
                # print(f'\n{scheduleDict}\n')
            
            marker = marker + webItemDuration
            # print(f'Marker: {marker}')
            schedule.append(scheduleDict)

    
    return schedule

def FillJWChannel(movies, channelObj, blockStart, blockEnd):
    marker = blockStart
    movieList = []
    schedule = []

    for movie in movies:
        movieList.append(Movie(movie[1], movie[2], movie[3], movie[5], movie[4], movie[6], movie[7]))
    movieList = sorted(movieList, key=lambda d: d.year)
    randNum = random.choice([1, 2, 3, 4])
    for _ in range(randNum):
        movieList = movieList[1:] + movieList[:1]
        
    while marker < blockEnd:
        for movie in movieList:
            tempMovieDuration = datetime.strptime(movie.duration, '%H:%M:%S.%f')
            movieDuration = timedelta(hours=tempMovieDuration.hour, minutes=tempMovieDuration.minute, seconds=tempMovieDuration.second)
            scheduleDict = {
                    'channelNumber': channelObj.number,
                    'channelName': channelObj.name,
                    'name': movie.moviename,
                    'start': marker,
                    'end': (marker + movieDuration),
                    'filepath': movie.filepath
                    }

            schedule.append(scheduleDict)

            marker = marker + movieDuration
            if marker >= blockEnd:
                break

    return schedule


def FillMovieChannel(movies, channelObj, blockStart, blockEnd):
    marker = blockStart
    schedule = []

    while marker < blockEnd:
        randomMovie = random.choice(movies)
        # Check to make sure that movies are played back to back
        dupFound = [m for m in schedule if randomMovie[7] in m['filepath']]
        if dupFound:
            print(f'Duplicate movie: {randomMovie[1]}')
            randomMovie = random.choice(movies)

        randomMovie = Movie(randomMovie[1], randomMovie[2], randomMovie[3], randomMovie[5], randomMovie[4], randomMovie[6], randomMovie[7])
        print(f'Chose {randomMovie.moviename}')
        tempMovieDuration = datetime.strptime(randomMovie.duration, '%H:%M:%S.%f')
        movieDuration = timedelta(hours=tempMovieDuration.hour, minutes=tempMovieDuration.minute, seconds=tempMovieDuration.second)
        scheduleDict = {
                'channelNumber': channelObj.number,
                'channelName': channelObj.name,
                'name': randomMovie.moviename,
                'start': marker,
                'end': (marker + movieDuration),
                'filepath': randomMovie.filepath
                }
        schedule.append(scheduleDict)
        marker = marker + movieDuration

        # Commercials
        if channelObj.commercials == "True":
            # If less than 90 minutes left, fill with commercials
            if (blockEnd - marker) < timedelta(minutes=90):
                while marker < blockEnd:
                    comm = random.choice(commercials)
                    commDuration = datetime.strptime(GetDuration(comm), '%H:%M:%S.%f')
                    commStart = marker
                    commEnd = (marker + timedelta(hours=commDuration.hour, minutes=commDuration.minute, seconds=commDuration.second))
                    scheduleDict = {
                            'channelNumber': channelObj.number,
                            'channelName': channelObj.name,
                            'name': comm,
                            'start': commStart,
                            'end': commEnd,
                            'filepath': comm
                            }
                    schedule.append(scheduleDict)
                    marker = marker + timedelta(hours=commDuration.hour, minutes=commDuration.minute, seconds=commDuration.second)
            else:
                NTB = NextTimeBlock(marker)
                if NTB > blockEnd:
                    NTB = blockEnd
                # print(f'NTB: {NTB}')
                while marker < NTB:
                    comm = random.choice(commercials)
                    commDuration = datetime.strptime(GetDuration(comm), '%H:%M:%S.%f')
                    commStart = marker
                    if (marker + timedelta(hours=commDuration.hour, minutes=commDuration.minute, seconds=commDuration.second)) > NTB:
                        commEnd = NTB
                    else:
                        commEnd = (marker + timedelta(hours=commDuration.hour, minutes=commDuration.minute, seconds=commDuration.second))

                    scheduleDict = {
                            'channelNumber': channelObj.number,
                            'channelName': channelObj.name,
                            'name': comm,
                            'start': commStart,
                            'end': commEnd,
                            'filepath': comm
                            }
                    schedule.append(scheduleDict)
                    newMarker = marker + timedelta(hours=commDuration.hour, minutes=commDuration.minute, seconds=commDuration.second)
                    if newMarker > NTB:
                        marker = NTB
                    else:
                        marker = newMarker
                    # print(f'Added commercial - Start {commStart} - End {commEnd}')
                    # print(f'Marker now at {marker}')

    return schedule

def FillEpisodeChannel(episodes, channelObj, blockStart, blockEnd):
    marker = blockStart
    schedule = []
    while marker < blockEnd:
        randomEpisode = random.choice(episodes)
        randomEpisode = Episode(randomEpisode[1], randomEpisode[2], randomEpisode[3], randomEpisode[4], randomEpisode[5], randomEpisode[6], randomEpisode[7], randomEpisode[8], randomEpisode[9])
        tempEpiDuration= datetime.strptime(randomEpisode.duration, '%H:%M:%S.%f')
        epiDuration = timedelta(hours=tempEpiDuration.hour, minutes=tempEpiDuration.minute, seconds=tempEpiDuration.second)
        scheduleDict = {
                'channelNumber': channelObj.number,
                'channelName': channelObj.name,
                'series': randomEpisode.showname,
                'name': randomEpisode.episodename,
                'start': marker,
                'end': (marker + epiDuration),
                'filepath': randomEpisode.filepath
                }
        schedule.append(scheduleDict)
        marker = marker + epiDuration
        
        # Commercials
        if channelObj.commercials == "True":
            NTB = NextTimeBlock(marker)
            if NTB > blockEnd:
                NTB = blockEnd
            # print(f'NTB: {NTB}')
            while marker < NTB:
                comm = random.choice(commercials)
                commDuration = datetime.strptime(GetDuration(comm), '%H:%M:%S.%f')
                # commStart = marker + timedelta(minutes=random.randint(0,commDuration.minute), seconds=random.randint(0,commDuration.second))
                commStart = marker
                if (marker + timedelta(hours=commDuration.hour, minutes=commDuration.minute, seconds=commDuration.second)) > NTB:
                    commEnd = NTB
                else:
                    commEnd = (marker + timedelta(hours=commDuration.hour, minutes=commDuration.minute, seconds=commDuration.second))

                scheduleDict = {
                        'channelNumber': channelObj.number,
                        'channelName': channelObj.name,
                        'name': comm,
                        'start': commStart,
                        'end': commEnd,
                        'filepath': comm
                        }
                schedule.append(scheduleDict)
                newMarker = (marker + timedelta(hours=commDuration.hour, minutes=commDuration.minute, seconds=commDuration.second))
                if newMarker > NTB:
                    marker = NTB
                else:
                    marker = newMarker
                # print(f'Added commercial - Start {commStart} - End {commEnd}')
                # print(f'Marker now at {marker}')

    return schedule
        

def FillMixedChannel(movies, episodes, channelObj, blockStart, blockEnd):
    schedule = []
    marker = blockStart

    while marker < blockEnd:
        # Choose between TV and Movies
        mediaChoice = random.choice(['tv', 'movie'])
        print(f'{mediaChoice} chosen')

        # Pick random number
        choiceNum = random.choice(range(1, 4, 1))
        print(f'Number: {choiceNum}')

        # Fulfill
        if mediaChoice == 'tv':
            episodeChoice = random.sample(episodes, choiceNum)
            for episode in episodeChoice:
                episode = Episode(episode[1], episode[2], episode[3], episode[4], episode[5], episode[6], episode[7], episode[8], episode[9])
                tempEpiDuration= datetime.strptime(episode.duration, '%H:%M:%S.%f')
                epiDuration = timedelta(hours=tempEpiDuration.hour, minutes=tempEpiDuration.minute, seconds=tempEpiDuration.second)
                scheduleDict = {
                        'channelNumber': channelObj.number,
                        'channelName': channelObj.name,
                        'name': episode.episodename,
                        'series': episode.showname,
                        'start': marker,
                        'end': (marker + epiDuration),
                        'filepath': episode.filepath
                        }
                schedule.append(scheduleDict)
                marker = marker + epiDuration

                if marker > blockEnd:
                    schedule.pop(-1)
                    return schedule

        if mediaChoice == 'movie':
            movieChoice = random.sample(movies, choiceNum)
            for movie in movieChoice:
                movie = Movie(movie[1], movie[2], movie[3], movie[5], movie[4], movie[6], movie[7])
                tempMovieDuration = datetime.strptime(movie.duration, '%H:%M:%S.%f')
                movieDuration = timedelta(hours=tempMovieDuration.hour, minutes=tempMovieDuration.minute, seconds=tempMovieDuration.second)
                scheduleDict = {
                        'channelNumber': channelObj.number,
                        'channelName': channelObj.name,
                        'name': movie.moviename,
                        'start': marker,
                        'end': (marker + movieDuration),
                        'filepath': movie.filepath
                        }
                schedule.append(scheduleDict)
                marker = marker + movieDuration

                if marker > blockEnd:
                    schedule.pop(-1)
                    return schedule

def DumpScheduleToDB(masterSchedule):
    conn = sqlite3.connect(scheduleDB)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE schedule")
    cursor.execute("CREATE TABLE IF NOT EXISTS schedule (channelNumber TEXT, channelName TEXT, name TEXT, start TEXT, end TEXT, filepath TEXT)")

    for item in masterSchedule:
        cursor.execute("INSERT INTO schedule (channelNumber, channelName, name, start, end, filepath) VALUES (?, ?, ?, ?, ?, ?)", (item['channelNumber'], item['channelName'], item['name'], item['start'], item['end'], item['filepath']))
        conn.commit()    
    conn.close()

def CheckSchedule():
    scheduleDB = '/media/ascott/USB/database/schedule.db'
    conn = sqlite3.connect(scheduleDB)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schedule")
    schedule = cursor.fetchall()
    return schedule

def CreateSchedule():
    masterChannelList = []
    masterSchedule = []
    schedule = CheckSchedule()

    # Go through each channel
    channelFiles = glob.glob('/media/ascott/USB/channels/*.json') 
    for channelFile in channelFiles:
        # Read in JSON file
        channelInfo = json.load(open(channelFile))
        channelObj = Channel(channelInfo['channelname'],
                             channelInfo['channelnumber'],
                             channelInfo['channellogo'],
                             channelInfo['ordered'],
                             channelInfo['enabled'],
                             channelInfo['commercials'],
                             channelInfo['mediatypes'],
                             channelInfo['channelTemplate'])
        
        if channelObj.enabled == 'False':
            continue

        print(f'{channelObj.name}')

        # Check to see if a schedule already exist
        # Look in schedule.db for channel number and today's date
        # todayDate = datetime.strftime(datetime.now(), '%Y-%m-%d')
        # print(f'Today\'s date: {todayDate}')
        # scheduleResults = [i for i in schedule if channelObj.number == i[0] and datetime.strptime(i[3], "%Y-%m-%d %H:%M:%S") >= datetime.now()]
        # if scheduleResults:
        #     print(f'Found existing schedule for {channelObj.name}')
        #     # Create dictionary of each item and append to masterSchedule
        #     for channelNumber, channelName, name, start, end, filepath in [i for i in schedule if channelObj.number == i[0]]:
        #         scheduleDict = {
        #                 'channelNumber': channelNumber,
        #                 'channelName': channelName,
        #                 'name': name,
        #                 # 'start': start,
        #                 # 'end': end,
        #                 'start': datetime.strptime(start, "%Y-%m-%d %H:%M:%S"),
        #                 'end': datetime.strptime(end, "%Y-%m-%d %H:%M:%S"),
        #                 'filepath': filepath
        #                 }
        #         masterSchedule.append(scheduleDict)
        # else:
        # Check for Collection
        if CheckForCollection(channelObj.name):
            collection = GetCollection(channelObj.name)
            if collection:
                if collection.movies:
                    movies = collection.GetMovies()
                if collection.series:
                    episodes = collection.GetEpisodes()
        else:
            movies = ConnectAndQuery(movieDB, "SELECT * FROM movies")
            episodes = ConnectAndQuery(tvDB, "SELECT * FROM tvshows")

        # Variables
        now = datetime.now()
        todayName = (calendar.day_name[(datetime.today()).weekday()]).lower()

        for block in [b for b in channelObj.template if b['day'] == todayName]:
            if block['mediaType'][0] == 'offair':
                continue

            # Genre Filtering
            if block['genres']:
                # g = block['genres'][0]
                # print('Filtering on '+g)
                # movies = ConnectAndQuery(movieDB, f"SELECT * FROM movies WHERE genre LIKE '{g}'")
                # print(f'Found {len(movies)}')

                tempMovieList = []
                for g in block['genres']:
                    print(f'Filtering on {g}')
                    filteredMovies = [m for m in movies if g in m[4]]
                movies = filteredMovies

                    # for m in movies:
                    #     if g in m[4]:
                    #         tempMovieList.append(m)
                # movies = tempMovieList
                # print(f'Found {len(movies)} after genre filtering')

            blockStart = datetime.strptime(block['start'], '%H:%M').replace(year=now.year, month=now.month, day=now.day)
            blockEnd = datetime.strptime(block['end'], '%H:%M').replace(year=now.year, month=now.month, day=now.day)
            if blockEnd < blockStart:
                blockEnd = blockEnd + timedelta(1)
            elif blockEnd == blockStart:
                blockEnd = blockEnd + timedelta(1)

            # Speciality Blocks

            if 'PPV' in channelObj.name:
                movie = random.choice(movies)
                ppvMovie = Movie(movie[1], movie[2], movie[3], movie[5], movie[4], movie[6], movie[7])
                # Check to see if other PPV channels have this movie playing
                PPVMovies = list(set([m['name'] for m in masterSchedule if 'PPV' in m['channelName']]))
                print(f'Currently Selected PPV Movies: {PPVMovies}')
                if ppvMovie.moviename in PPVMovies:
                    movie = random.choice(movies)
                    ppvMovie = Movie(movie[1], movie[2], movie[3], movie[5], movie[4], movie[6], movie[7])
                    print(f'Duplicate PPV movie found, selecting {ppvMovie.moviename} instead')

                tempSchedule = FillPPVChannel(ppvMovie, channelObj, blockStart, blockEnd)
                for item in tempSchedule:
                    masterSchedule.append(item)
                break

            if 'John Wick' in channelObj.name:
                tempSchedule = FillJWChannel(movies, channelObj, blockStart, blockEnd)
                for item in tempSchedule:
                    masterSchedule.append(item)
                break

            # Blocks with different schedules
            if 'movie' in block['mediaType'] and 'tv' not in block['mediaType']:
                tempSchedule = FillMovieChannel(movies, channelObj, blockStart, blockEnd)
                for item in tempSchedule:
                    masterSchedule.append(item)

            if 'tv' in block['mediaType'] and 'movie' not in block['mediaType']:
                tempSchedule = FillEpisodeChannel(episodes, channelObj, blockStart, blockEnd)
                for item in tempSchedule:
                    masterSchedule.append(item)

            if 'tv' in block['mediaType'] and 'movie' in block['mediaType']:
                tempSchedule = FillMixedChannel(movies, episodes, channelObj, blockStart, blockEnd)
                for item in tempSchedule:
                    masterSchedule.append(item)

            # Web Content Block
            if 'web' in block['mediaType']:
                print(f'Found {len(webContent)} web videos!')
                tempSchedule = FillWebChannel(webContent, channelObj, blockStart, blockEnd)
                for item in tempSchedule:
                    masterSchedule.append(item)
            
            masterChannelList.append(channelObj)
            

    CreateHTMLSchedule(masterSchedule, masterChannelList)
    DumpScheduleToDB(masterSchedule)


    return masterSchedule




