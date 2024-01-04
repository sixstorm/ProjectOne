import bender
import time
import mpv
import re
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

breakloop = False

def my_log(loglevel, component, message):
    print('[{}] {}: {}'.format(loglevel, component, message))

# MPV Instance
mpvPlayer = mpv.MPV(log_handler=my_log, input_default_bindings=True, input_vo_keyboard=True)
# mpvPlayer.deinterlace = 'yes'
mpvPlayer.hwdec = 'drm-copy'
mpvPlayer.sub = 'no'
mpvPlayer.vo = 'gpu'
mpvPlayer.fullscreen = True


@mpvPlayer.on_key_press('s')
def StopPlayback():
    global mpvPlayer
    mpvPlayer.stop()
    mpvPlayer.quit()

@mpvPlayer.on_key_press('w')
def ChannelUp():
    global mpvPlayer, channelList, breakloop
    channelList = channelList[1:] + channelList[:1]
    nowPlaying = GetNowPlaying(channelList[0])
    nextPlaying = GetNextPlaying(channelList[0])
    mpvPlayer.start = f'+{GetPlaybackPosition(nowPlaying)}'
    print(f'Now Playing {nowPlaying["name"]}')
    print(f'Next Up: {nextPlaying["name"]}')
    mpvPlayer.loadfile(nowPlaying['filepath'], mode='replace')
    ChannelOverlay(nowPlaying)
    # mpvPlayer.wait_until_playing()

@mpvPlayer.on_key_press('q')
def ChannelDown():
    global mpvPlayer, channelList, breakloop
    channelList = channelList[-1:] + channelList[:-1]
    nowPlaying = GetNowPlaying(channelList[0])
    nextPlaying = GetNextPlaying(channelList[0])
    mpvPlayer.start = f'+{GetPlaybackPosition(nowPlaying)}'
    print(f'Now Playing {nowPlaying["name"]}')
    print(f'Next Up: {nextPlaying["name"]}')
    mpvPlayer.loadfile(nowPlaying['filepath'], mode='replace')
    ChannelOverlay(nowPlaying)
    # mpvPlayer.wait_until_playing()

@mpvPlayer.on_key_press('i')
def ShowCurrentlyPlayingInfo():
    global mpvPlayer
    font = ImageFont.truetype('/home/ascott/Downloads/Roboto-Regular.ttf', 40)
    overlay = mpvPlayer.create_image_overlay()
    img = Image.new('RGBA', (1000, 150), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    nowPlaying = GetNowPlaying(channelList[0])
    text = f'{mpvPlayer.media_title}'
    print(f'Show: {text}')
    d.text((10, 10), text, font=font, fill=(255, 255, 255, 128), stroke_width=3, stroke_fill='black')
    overlay.update(img)
    time.sleep(2)
    overlay.remove()

@mpvPlayer.on_key_press('m')
def Mute():
    global mpvPlayer
    mpvPlayer.mute

def GetNowPlaying(channelNumber):
    global masterSchedule
    now = datetime.now()

    nowPlaying = [item for item in masterSchedule if item['channelNumber'] == str(channelNumber) and item['start'] <= now and item['end'] >= now][0]

    print(f'Now Playing: {nowPlaying}')
    return nowPlaying

def GetNextPlaying(channelNumber):
    global masterSchedule
    
    # Get everything from channel
    channelItems = [item for item in masterSchedule if item['channelNumber'] == str(channelNumber)]
    # Sort everything by start time
    channelItems = sorted(channelItems, key=lambda i: i['start'])
    # Get currently playing item and next item
    nowPlaying = GetNowPlaying(channelNumber)
    nextItem = channelItems[(channelItems.index(nowPlaying)+1)]
    return nextItem

def GetPlaybackPosition(nowPlaying):
    now = datetime.now()
    return (now - nowPlaying['start']).total_seconds()

def ChannelOverlay(nowPlaying):
    global mpvPlayer

    font = ImageFont.truetype('/home/ascott/Downloads/Roboto-Regular.ttf', 60)
    overlay = mpvPlayer.create_image_overlay()
    img = Image.new('RGBA', (800, 150), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    text = f'{nowPlaying["channelNumber"]}'
    d.text((10, 10), text, font=font, fill=(255, 255, 255, 128), stroke_width=3, stroke_fill='black')
    overlay.update(img)
    time.sleep(2)
    overlay.remove()
    
def ChannelOverlayUpNext(nextPlaying):
    global mpvPlayer

    npStart = datetime.strftime(nextPlaying['start'], "%H:%M")

    if 'movie' in nextPlaying['filepath']:
        someText = nextPlaying['name']
    if 'tv' in nextPlaying['filepath']:
        someText = nextPlaying['series']
    if 'bumper' in nextPlaying['filepath']:
        rePattern = '\/bumpers\/(.*).mp4'
        someText = f'Playing Next: {re.findall(rePattern, nextPlaying["name"])[0]} at {npStart}'
    finalText = f'Playing Next: {someText}'

    font = ImageFont.truetype('/home/ascott/Downloads/static/Oswald-Regular.ttf', 40)
    overlay = mpvPlayer.create_image_overlay()
    img = Image.new('RGBA', (1920, 1050), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.text((10, 900), finalText, font=font, fill=(255, 255, 255, 128), stroke_width=3, stroke_fill='black')
    overlay.update(img)
    time.sleep(10)
    overlay.remove()


# Variables
b = bender
masterSchedule = b.CreateSchedule()
channelList = sorted(list(set([n['channelNumber'] for n in masterSchedule])))

# Main playback loop
while True:
    breakloop = False

    nowPlaying = GetNowPlaying(channelList[0])
    print(f'Now Playing {nowPlaying["name"]}')
    nextPlaying = GetNextPlaying(channelList[0])
    print(f'Next Up: {nextPlaying["name"]}')
    mpvPlayer.start = f'+{GetPlaybackPosition(nowPlaying)}'
    mpvPlayer.loadfile(nowPlaying['filepath'], mode='replace')
    mpvPlayer.wait_until_playing()
    ChannelOverlay(nowPlaying)

    # Check to see if video is playing
    while breakloop is False:
        # If video is playing
        if mpvPlayer.core_idle is False:
            posCounter = int(mpvPlayer.percent_pos)
            print(f'Current percent: {posCounter}')
            mpvPP = int(mpvPlayer.percent_pos)
            if mpvPP > posCounter:
                if 'tv' in mpvPlayer.path:
                    print('This is a TV show')
                    if (mpvPP % 50) == 0 or (mpvPP % 75) == 0 or (mpvPP % 90) == 0:
                        ChannelOverlayUpNext(nextPlaying)
                elif 'movie' in mpvPlayer.path:
                    print('This is a movie')
                    if (mpvPP % 25) == 0 or (mpvPP % 50) == 0 or (mpvPP % 75) == 0 or (mpvPP % 95) == 0:
                        ChannelOverlayUpNext(nextPlaying)
                elif 'bumper' in mpvPlayer.path:
                    print('This is a commercial')
                    if (mpvPP % 2) == 0:
                        ChannelOverlayUpNext(nextPlaying)
                print(mpvPP)
                posCounter = mpvPP

            # Break loop if it's time to play the next thing
            if datetime.now() > nowPlaying['end']:
                breakloop = False
                break
                
            time.sleep(1)

