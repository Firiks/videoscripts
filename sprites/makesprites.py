import time
import subprocess
import shlex
import sys
import logging
import os
import datetime
import math
import glob
import pipes
import argparse
from distutils.spawn import find_executable
##################################
# Generate tooltip thumbnail images & corresponding WebVTT file for a video (e.g MP4).
# Final product is one *_sprite.jpg file and one *_thumbs.vtt file.
#
# DEPENDENCIES: required: ffmpeg & imagemagick
#               optional: sips (comes with MacOSX) - yields slightly smaller sprites
#    download ImageMagick: http://www.imagemagick.org/script/index.php OR http://www.imagemagick.org/script/binary-releases.php (on MacOSX: "sudo port install ImageMagick")
#    download ffmpeg: http://www.ffmpeg.org/download.html
##################################

#TODO determine optimal number of images/segment distance based on length of video? (so longer videos don't have huge sprites)

USE_SIPS = bool(find_executable('sips')) #True to use sips if using MacOSX (creates slightly smaller sprites), else set to False to use ImageMagick
THUMB_RATE_SECONDS= 10 # every Nth second take a snapshot
THUMB_WIDTH= 160 # width in px
SKIP_FIRST= False #True to skip a thumbnail of second 1;
SPRITE_NAME = "sprite.jpg" #jpg is much smaller than png, so using jpg
VTTFILE_NAME = "thumbs.vtt"
THUMB_OUTDIR = "thumbs"
NO_PREFIX_FOLDER = True # output directly to specified folder without any prefix
USE_UNIQUE_OUTDIR = False #true to make a unique timestamped output dir each time, else False to overwrite/replace existing outdir
TIMESYNC_ADJUST = 0 #set to 0 to not adjust time (gets multiplied by thumbRate); On my machine,ffmpeg snapshots show earlier images than expected timestamp by about 1/2 the thumbRate (for one vid, 10s thumbrate->images were 6s earlier than expected;45->22s early,90->44 sec early)
ORIGIN = "" # add custom origin
REFERER = "" # add custom referer
USER_AGENT = "" # add custom user agent

logger = logging.getLogger(sys.argv[0])
logSetup=False

# small wrapper class as convenience accessor for external scripts
class SpriteTask():
    
    def __init__(self,videofile):
        self.remotefile = videofile.startswith("http")
        if not self.remotefile and not os.path.exists(videofile):
            sys.exit("File does not exist: %s" % videofile)
        basefile = os.path.basename(videofile)
        basefile_nospeed = removespeed(basefile) #strip trailing speed suffix from file/dir names, if present
        newoutdir = makeOutDir(basefile_nospeed)
        if NO_PREFIX_FOLDER:
            spritefile = os.path.join(newoutdir,SPRITE_NAME)
            vttfile = os.path.join(newoutdir,VTTFILE_NAME)
        else:
            fileprefix,ext = os.path.splitext(basefile_nospeed)
            spritefile = os.path.join(newoutdir,"%s_%s" % (fileprefix,SPRITE_NAME))
            vttfile = os.path.join(newoutdir,"%s_%s" % (fileprefix,VTTFILE_NAME))
        self.videofile = videofile
        self.vttfile = vttfile
        self.spritefile = spritefile
        self.outdir = newoutdir
    def getVideoFile(self):
        return self.videofile
    def getOutdir(self):
        return self.outdir
    def getSpriteFile(self):
        return self.spritefile
    def getVTTFile(self):
        return self.vttfile

# create unique output dir based on video file name and current timestamp
def makeOutDir(videofile):
    base,ext = os.path.splitext(videofile)
    script = sys.argv[0]
    basepath = os.path.dirname(os.path.abspath(script)) #make output dir always relative to this script regardless of shell directory
    if len(THUMB_OUTDIR)>0 and THUMB_OUTDIR[0]=='/':
        outputdir = THUMB_OUTDIR
    else:
        outputdir = os.path.join(basepath,THUMB_OUTDIR)
    if USE_UNIQUE_OUTDIR:
        newoutdir = "%s.%s" % (os.path.join(outputdir,base),datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
    elif NO_PREFIX_FOLDER:
        newoutdir = outputdir
    else:
        newoutdir = "%s_%s" % (os.path.join(outputdir,base),"vtt")
    if not os.path.exists(newoutdir):
        logger.info("Making dir: %s" % newoutdir)
        os.makedirs(newoutdir)
    elif os.path.exists(newoutdir) and not USE_UNIQUE_OUTDIR:
        #remove previous contents if reusing outdir
        files = os.listdir(newoutdir)
        print("Removing previous contents of output directory: %s" % newoutdir)
        for f in files:
            os.unlink(os.path.join(newoutdir,f))
    return newoutdir

def doCmd(cmd,logger):  #execute a shell command and return/print its output
    logger.info( "START [%s] : %s " % (datetime.datetime.now(), cmd))
    args = shlex.split(cmd) #tokenize args
    output = None
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT) #pipe stderr into stdout
    except Exception as e:
        ret = "ERROR   [%s] An exception occurred\n%s\n%s" % (datetime.datetime.now(),output,str(e))
        logger.exception(ret)
        raise e #todo ?
    ret = "END   [%s]\n%s" % (datetime.datetime.now(),output)
    logger.info(ret)
    sys.stdout.flush()
    return output

# take snapshot image of video every Nth second and output to sequence file names and custom directory
# reference: https://trac.ffmpeg.org/wiki/Create%20a%20thumbnail%20image%20every%20X%20seconds%20of%20the%20video
def takesnaps(videofile,newoutdir,thumbRate=None):
    if not thumbRate:
        thumbRate = THUMB_RATE_SECONDS
    rate = "1/%d" % thumbRate # 1/60=1 per minute, 1/120=1 every 2 minutes
    
    referer = 'Referer: ' + REFERER
    origin = 'Origin: ' + ORIGIN
    ua = USER_AGENT 

    cmd = "ffmpeg -headers %s -headers %s -user_agent %s -i %s -f image2 -bt 20M -vf fps=%s -aspect 16:9 %s/tv%%03d.jpg" % (quote_string(referer), quote_string(origin), quote_string(ua), quote_string(videofile), rate, quote_string(newoutdir))

    doCmd(cmd,logger)
    if SKIP_FIRST:
        #remove the first image
        logger.info("Removing first image, unneeded")
        os.unlink("%s/tv001.jpg" % newoutdir)
    count = len(os.listdir(newoutdir))
    logger.info("%d thumbs written in %s" % (count,newoutdir))
    #return the list of generated files
    return count,get_thumb_images(newoutdir)

def get_thumb_images(newdir):
    return glob.glob("%s/tv*.jpg" % newdir)

# change image output size to 100 width (originally matches size of video)
#  - pass a list of files as string rather than use '*' with sips command because
#  subprocess does not treat * as wildcard like shell does
def resize(files):
    if USE_SIPS:
        # HERE IS MAC SPECIFIC PROGRAM THAT YIELDS SLIGHTLY SMALLER JPGs
        doCmd("sips --resampleWidth %d %s" % (THUMB_WIDTH," ".join(map(pipes.quote, files))),logger)
    else:
        # THIS COMMAND WORKS FINE TOO AND COMES WITH IMAGEMAGICK, IF NOT USING A MAC
        doCmd("mogrify -geometry %dx %s" % (THUMB_WIDTH," ".join(map(pipes.quote, files))),logger)

# execute command to give geometry HxW+X+Y of each file matching command
#  identify -format "%g - %f\n" *         #all files
#  identify -format "%g - %f\n" onefile.jpg  #one file
# SAMPLE OUTPUT
#  100x66+0+0 - _tv001.jpg
#  100x2772+0+0 - sprite2.jpg
#  4200x66+0+0 - sprite2h.jpg
def get_geometry(file):
    geom = doCmd("""identify -format "%%g - %%f\n" %s""" % quote_string(file),logger)
    parts = geom.decode().split("-",1)
    return parts[0].strip() #return just the geometry prefix of the line, sans extra whitespace

# generate & write vtt file mapping video time to each image's coordinates in our spritemap
def makevtt(spritefile,numsegments,coords,gridsize,writefile,thumbRate=None):
    #split geometry string into individual parts
    ##4200x66+0+0     ===  WxH+X+Y
    if not thumbRate:
        thumbRate = THUMB_RATE_SECONDS
    wh,xy = coords.split("+",1)
    w,h = wh.split("x")
    w = int(w)
    h = int(h)
    #x,y = xy.split("+")
#======= SAMPLE WEBVTT FILE=====
#WEBVTT
#
#00:00.000 --> 00:05.000
#/assets/thumbnails.jpg#xywh=0,0,160,90
#
#00:05.000 --> 00:10.000
#/assets/preview2.jpg#xywh=160,0,320,90
#
#00:10.000 --> 00:15.000
#/assets/preview3.jpg#xywh=0,90,160,180
#
#00:15.000 --> 00:20.000
#/assets/preview4.jpg#xywh=160,90,320,180
#==== END SAMPLE ========
    basefile = os.path.basename(spritefile)
    vtt = ["WEBVTT",""] #line buffer for file contents
    if SKIP_FIRST:
        clipstart = thumbRate  #offset time to skip the first image
    else:
        clipstart = 0

    clipend = clipstart + thumbRate
    adjust = 0

    if TIMESYNC_ADJUST > 0:
        adjust = thumbRate * TIMESYNC_ADJUST

    for imgnum in range(1,numsegments+1):
        # print('imgnum',imgnum,'clipstart',clipstart,'clipend',clipend)
        xywh = get_grid_coordinates(imgnum,gridsize,w,h)
        start = get_time_str(clipstart,adjust=adjust)
        end  = get_time_str(clipend,adjust=adjust)
        clipstart = clipend
        clipend += thumbRate
        print('start -->',start,'end',end)
        # vtt.append("Img %d" % imgnum)
        vtt.append("%s --> %s" % (start,end)) #00:00.000 --> 00:05.000
        vtt.append("%s#xywh=%s" % (basefile,xywh))
        vtt.append("") #Linebreak
    vtt =  "\n".join(vtt)
    #output to file
    writevtt(writefile,vtt)

# convert time in seconds to VTT format time (HH:)MM:SS.ddd
def get_time_str(numseconds,adjust=None):
    if adjust > 0: #offset the time by the adjust amount, if applicable
        seconds = max(numseconds + adjust, 0) #don't go below 0! can't have a negative timestamp
    else:
        seconds = numseconds
    return str(time.strftime('%H:%M:%S', time.gmtime(seconds))) + ".000"

# given an image number in our sprite, map the coordinates to it in X,Y,W,H format
def get_grid_coordinates(imgnum,gridsize,w,h):
    y = int((imgnum - 1) / gridsize)
    x = int((imgnum -1) - (y * gridsize))
    imgx = x * w
    imgy =y * h
    return "%s,%s,%s,%s" % (imgx,imgy,w,h)

# montage _tv*.jpg -tile 8x8 -geometry 100x66+0+0 montage.jpg  #GRID of images
# NOT USING: convert tv*.jpg -append sprite.jpg     #SINGLE VERTICAL LINE of images
# NOT USING: convert tv*.jpg +append sprite.jpg     #SINGLE HORIZONTAL LINE of images
# base the sprite size on the number of thumbs we need to make into a grid.
def makesprite(outdir,spritefile,coords,gridsize):
    grid = "%dx%d" % (gridsize,gridsize)
    cmd = "montage %s/tv*.jpg -tile %s -geometry %s %s" % (quote_string(outdir), grid, coords, quote_string(spritefile))#if video had more than 144 thumbs, would need to be bigger grid, making it big to cover all our case
    doCmd(cmd,logger)

# remove the individual thumbs
def cleanup(outdir):
    cmd = ("rm %s" % ' '.join(map(lambda x: ('"%s"'%x), get_thumb_images(outdir))))
    doCmd(cmd,logger)

# output VTT file
def writevtt(vttfile,contents):
    with open(vttfile,mode="w") as h:
        h.write(contents)
    logger.info("Wrote: %s" % vttfile)

# some of my files are suffixed with datarate, e.g. myfile_3200.mp4;
# this trims the speed from the name since it's irrelevant to my sprite names (which apply regardless of speed);
# you won't need this if it's not relevant to your filenames
def removespeed(videofile):
    videofile = videofile.strip()
    speed = videofile.rfind("_")
    speedlast = videofile.rfind(".")
    maybespeed = videofile[speed+1:speedlast]
    try:
        int(maybespeed)
        videofile = videofile[:speed] + videofile[speedlast:]
    except:
        pass
    return videofile

def run(task, thumbRate=None):
    addLogging()
    if not thumbRate:
        thumbRate = THUMB_RATE_SECONDS
    outdir = task.getOutdir()
    spritefile = task.getSpriteFile()

    #create snapshots
    numfiles,thumbfiles = takesnaps(task.getVideoFile(),outdir, thumbRate=thumbRate)
    #resize them to be mini
    resize(thumbfiles)

    #get coordinates from a resized file to use in spritemapping
    gridsize = int(math.ceil(math.sqrt(numfiles)))
    coords = get_geometry(thumbfiles[0]) #use the first file (since they are all same size) to get geometry settings

    #convert small files into a single sprite grid
    makesprite(outdir,spritefile,coords,gridsize)
    cleanup(outdir)

    #generate a vtt with coordinates to each image in sprite
    makevtt(spritefile,numfiles,coords,gridsize,task.getVTTFile(), thumbRate=thumbRate)

def addLogging():
    global logSetup
    if not logSetup:
        if LOG_FILENAME:
            #FILE LOGGING
            print("Writing log to: %s" % LOG_FILENAME)
            logs_dir = os.path.split(LOG_FILENAME)[0]
            if logs_dir and not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
            handler = logging.FileHandler(LOG_FILENAME)
            handler.setLevel(logging.DEBUG)
            logger.addHandler(handler)
        #CONSOLE LOGGING
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        logger.addHandler(ch)
        logger.setLevel(logging.DEBUG)
        logSetup = True #set flag so we don't reset log in same batch

def quote_string(string):
    return '\'' + str(string) + '\''

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='generate sprites.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-r','--thumb_rate', help='every Nth second take a snapshot.',
        default=THUMB_RATE_SECONDS, type=int)
    parser.add_argument('-w', '--width', help='width of thum images.',
        default=THUMB_WIDTH, type=int)
    parser.add_argument('--log_file', help="path to verbose log file.",
        default="")
    parser.add_argument('--referer', help="referer header.",
        default="")
    parser.add_argument('--origin', help="origin header.",
        default="")
    parser.add_argument('--user_agent', help="user agent header.",
        default="")

    parser.add_argument('videofile', help='full path or url to the video file for which to create thumbnails.')
    parser.add_argument('out_dir', help='output directory.', nargs='?', default=THUMB_OUTDIR)
    args = parser.parse_args()

    THUMB_RATE_SECONDS = args.thumb_rate
    THUMB_WIDTH = args.width
    THUMB_OUTDIR = args.out_dir
    LOG_FILENAME = args.log_file
    ORIGIN = args.origin
    REFERER = args.referer
    USER_AGENT = args.user_agent

    videofile = args.videofile

    task = SpriteTask(videofile)
    run(task)