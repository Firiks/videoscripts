videoscripts
============


sprites
============
Python scripts to generate tooltip thumbnail images for videos (e.g. mp4,m4v)  & associated WebVTT files.

makesprites.py
--------------
Python script to generate thumbnail images for a video, put them into an grid-style sprite,
and create a Web VTT file that maps the sprite images to the video segments.

Required dependencies (expected in PATH):
* ffmpeg [download here](http://www.ffmpeg.org/download.html)
* imagemagick [download here](http://www.imagemagick.org/script/index.php) or [here](http://www.imagemagick.org/script/index.php) or on Mac, use Macports: <pre>sudo port install ImageMagick</pre>

Optional dependencies for better image compression:
* sips (part of MAC OSX)

Reference Articles:
* http://www.longtailvideo.com/support/jw-player/31804/basic-tooltip-thumbs
* http://www.longtailvideo.com/support/jw-player/31778/adding-tooltip-thumbnails/

Sample Usage:

    python makesprites.py /path/to/myvideofile.mp4

You may want to customize the the following variables in makesprites.py:

    USE_SIPS = True         # True if using MacOSX (creates slightly smaller sprites), else set to False to use ImageMagick resizing
    THUMB_RATE_SECONDS=45   # every Nth second take a snapshot of the video (tested with 30,45,60)
    THUMB_WIDTH=100         # thhumb width in px

A sample of a generated WebVTT file.

<pre>
WEBVTT

Img 1
00:00:22.000 --> 00:01:07.000
myvideofile_sprite.jpg#xywh=0,0,100,56

Img 2
00:01:07.000 --> 00:01:52.000
myvideofile_sprite.jpg#xywh=100,0,100,56

Img 3
00:01:52.000 --> 00:02:37.000
myvideofile_sprite.jpg#xywh=200,0,100,56

Img 4
00:02:37.000 --> 00:03:22.000
myvideofile_sprite.jpg#xywh=300,0,100,56

Img 5
00:03:22.000 --> 00:04:07.000
myvideofile_sprite.jpg#xywh=400,0,100,56

Img 6
00:04:07.000 --> 00:04:52.000
myvideofile_sprite.jpg#xywh=500,0,100,56
</pre>

    
batchsprites.py
--------------

Expects a file name as input. File should be simple text file containing a list of video files (with fully qualified paths or relative paths from script directory).
It generates thumbnails/sprites for each video, then copies the sprite & vtt file to a destination folder defined in the `OUTPUT_FOLDER` variable.

Usage:

    python batchsprites.py filelist.txt
    python batchsprites.py filelist.txt 20  #override default THUMB_RATE_SECONDS to take snapshot every 20 seconds

Sample filelist.txt contents:

    /Users/vlanard/biz/video/video1_circ5.mp4
    ../../archive/an/video1_circ1n2_wc_1500.m4v
    ../../archive/an/video1_circ1n4_wc_1500.m4v
    ../../archive/an/video1_circ2n3_wc_1500.m4v
    ../../archive/an/video1_circ3n4_wc_1500.m4v
