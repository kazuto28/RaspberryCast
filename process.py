import youtube_dl
import os, subprocess
import threading, queue
import logging
import json, time
from multiprocessing import Value
logger = logging.getLogger("RaspberryCast")
volume = 0

status = Value("u","0")
omx_cmd = queue.Queue()
video_queue = queue.Queue()

def launchvideo(url, config, sub=False):
    setState("2")

    omx_cmd.queue.clear()
    omx_cmd.put("q")  # Kill previous instance of OMX

    if config["new_log"]:
        subprocess.Popen(["sudo", "fbi", "-T", "1", "-a", "--noverbose", "images/processing.jpg"])

    logger.info('Extracting source video URL...')
    out = return_full_url(url, sub=sub, slow_mode=config["slow_mode"])

    logger.debug("Full video URL fetched.")

    thread = threading.Thread(target=playWithOMX, args=(out, sub,),
            kwargs=dict(width=config["width"], height=config["height"],
                        new_log=config["new_log"]))
    thread.start()

    #os.system("echo . > /tmp/cmd &")  # Start signal for OMXplayer


def queuevideo(url, config, onlyqueue=False):
    logger.info('Extracting source video URL, before adding to queue...')

    out = return_full_url(url, sub=False, slow_mode=config["slow_mode"])

    logger.info("Full video URL fetched.")

    if getState() == "0" and not onlyqueue:
        logger.info('No video currently playing, playing video instead of \
adding to queue.')
        thread = threading.Thread(target=playWithOMX, args=(out, False,),
            kwargs=dict(width=config["width"], height=config["height"],
                        new_log=config["new_log"]))
        thread.start()
        #os.system("echo . > /tmp/cmd &")  # Start signal for OMXplayer
    else:
        if out is not None:
            video_queue.put(out)

def return_full_url(url, sub=False, slow_mode=False):
    logger.debug("Parsing source url for "+url+" with subs :"+str(sub))

    if ((url[-4:] in (".avi", ".mkv", ".mp4", ".mp3")) or
            (sub) or (".googlevideo.com/" in url)):
        logger.debug('Direct video URL, no need to use youtube-dl.')
        return url

    ydl = youtube_dl.YoutubeDL(
        {
            'logger': logger,
            'noplaylist': True,
            'ignoreerrors': True,
        })  # Ignore errors in case of error in long playlists
    with ydl:  # Downloading youtub-dl infos. We just want to extract the info
        result = ydl.extract_info(url, download=False)

    if result is None:
        logger.error(
            "Result is none, returning none. Cancelling following function.")
        return None

    if 'entries' in result:  # Can be a playlist or a list of videos
        video = result['entries'][0]
    else:
        video = result  # Just a video

    if "youtu" in url:
        if slow_mode:
            for i in video['formats']:
                if i['format_id'] == "18":
                    logger.debug(
                        "Youtube link detected, extracting url in 360p")
                    return i['url']
        else:
            logger.debug('''CASTING: Youtube link detected.
Extracting url in maximal quality.''')
            for fid in ('22', '18', '36', '17'):
                for i in video['formats']:
                    if i['format_id'] == fid:
                        logger.debug(
                            'CASTING: Playing highest video quality ' +
                            i['format_note'] + '(' + fid + ').'
                        )
                        return i['url']
    elif "vimeo" in url:
        if slow_mode:
            for i in video['formats']:
                if i['format_id'] == "http-360p":
                    logger.debug("Vimeo link detected, extracting url in 360p")
                    return i['url']
        else:
            logger.debug(
                'Vimeo link detected, extracting url in maximal quality.')
            return video['url']
    else:
        logger.debug('''Video not from Youtube or Vimeo.
Extracting url in maximal quality.''')
        return video['url']


def playlist(url, cast_now, config):
    logger.info("Processing playlist.")

    if cast_now:
        logger.info("Playing first video of playlist")
        launchvideo(url, config)  # Launch first video
    else:
        queuevideo(url, config)

    thread = threading.Thread(target=playlistToQueue, args=(url, config))
    thread.start()


def playlistToQueue(url, config):
    logger.info("Adding every videos from playlist to queue.")
    ydl = youtube_dl.YoutubeDL(
        {
            'logger': logger,
            'extract_flat': 'in_playlist',
            'ignoreerrors': True,
        })
    with ydl:  # Downloading youtub-dl infos
        result = ydl.extract_info(url, download=False)
        for i in result['entries']:
            logger.info("queuing video")
            if i != result['entries'][0]:
                queuevideo(i['url'], config)


def playWithOMX(url, sub, width="", height="", new_log=False):
    logger.info("Starting OMXPlayer now.")

    logger.info("Attempting to read resolution from configuration file.")

    resolution = ""

    if width or height:
        resolution = " --win '0 0 {0} {1}'".format(width, height)

    setState("1")
    if sub:
        proc=subprocess.Popen([
            "omxplayer", "-b", "-r", "-o", "both", url, resolution,
            "--vol", str(volume), "--subtitles", "subtitle.srt"], stdin = subprocess.PIPE
        )
        while not proc.poll() == 0:
            if not omx_cmd.empty():
                proc.stdin.write(omx_cmd.get(False).encode("utf-8"))
                proc.stdin.flush()
            time.sleep(0.1)
    elif url is None:
        pass
    else:
        proc=subprocess.Popen([
            "omxplayer", "-b", "-r", "-o", "both", url, resolution, "--vol", str(volume)
        ],stdin=subprocess.PIPE)
        while not proc.poll() == 0:
            if not omx_cmd.empty():
                proc.stdin.write(omx_cmd.get(False).encode("utf-8"))
                proc.stdin.flush()
            time.sleep(0.1)

    if getState() != "2":  # In case we are again in the launchvideo function
        setState("0")
        # Check if there is videos in queue
        first_line = video_queue.get()
        logger.info("Starting next video in playlist.")
        thread = threading.Thread(
        target=playWithOMX, args=(first_line, False,),
                kwargs=dict(width=width, height=height,
                            new_log=new_log),
        )
        thread.start()
        #os.system("echo . > /tmp/cmd &")  # Start signal for OMXplayer
    else:
        logger.info("Playlist empty, skipping.")
        if new_log:
            subprocess.Popen(["sudo", "fbi", "-T", "1", "-a", "--noverbose", "images/ready.jpg"])


def setState(state):
    # Write to file so it can be accessed from everywhere
    status.value=state


def getState():
    return status.value


def setVolume(vol):
    global volume
    if vol == "more":
        volume += 300
    if vol == "less":
        volume -= 300
