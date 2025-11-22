# rmbloat
`rmbloat` easily converts your entire, aging video collection to h265. This is useful for size reduction and ensure efficient rendering on modern video players.

While this converter has many potential uses, it is geared towards doing mass conversions on a media server.  Since it is potentially very long running, t makes sense to start `rmbloat` in a tmux window that out-lives a log in session (say on a headless server).

### Easy Installation
To install `rmbloat`, use `pipx rmbloat`. If needed, see [Install and Execute Python Applications Using pipx](https://realpython.com/python-pipx/).

### Bloat Metric
`rmbloat` defines `bloat = 1000 * bitrate / sqrt(height*width)`.  A bloat value of 1000, roughly is an aggressively compressed h265 file. It is common to see bloats of 4000 or more; very bloated files can typically be reduced in size by a factor of 4 or more w/o too much loss of watchability.

## Using `rmbloat`
### Starting `rmbloat` from the CLI
`rmbloat` requires a list of files or directories to scan for conversion candidates.  The full list of options are:
```
usage: rmbloat.py [-h] [-B] [-b BLOAT_THRESH] [-q QUALITY] [-a {x26*,x265,all}] [-F] [-m MIN_SHRINK_PCT] [-S] [-n] [-s] [-L] [files ...]

CLI/curses bulk Video converter for media servers

positional arguments:
  files                 Video files and recursively scanned folders w Video files

options:
  -h, --help            show this help message and exit
  -B, --keep-backup     if true, rename to ORIG.{videofile} rather than recycle [dflt=False]
  -b BLOAT_THRESH, --bloat-thresh BLOAT_THRESH
                        bloat threshold to convert [dflt=1600,min=--save00]
  -q QUALITY, --quality QUALITY
                        output quality (CRF) [dflt=28]
  -a {x26*,x265,all}, --allowed-codecs {x26*,x265,all}
                        allowed codecs [dflt=x265]
  -F, --full-speed      if true, do NOT set nice -n19 and ionice -c3 dflt=False]
  -m MIN_SHRINK_PCT, --min-shrink-pct MIN_SHRINK_PCT
                        minimum conversion reduction percent for replacement [dflt=10]
  -S, --save-defaults   save the -B/-b/-q/-a/-F/-m options as defaults
  -n, --dry-run         Perform a trial run with no changes made.
  -s, --sample          produce 30s samples called SAMPLE.{input-file}
  -L, --logs            view the logs
  ```
  You can customize the defaults by setting the desired options and adding the  `--save-defaults` option. Non-video files in the given files and directories are simply ignored.

  Candidate video files are probed (with `ffprobe`). If not probable, then the candidate is simply ignored. Probing a bunch of files can be time consuming, but `rmbloat` keeps a cache of probes so start-up can be fast if most candidates have been successfully probed.

## The Three Main Screens
The main screens are:
* **Selection Screen** - where you can customize the decisions and scope of the conversions. The Selecition screen is the first screen after start-up.
* **Conversion Screen** - where you can view the conversion progress. When conversions are completed (or manually aborted), it returns to the Selection screen.
* **Help Screen** - where you can see all available keys and meanings. Use the key, '?', to enter and exit the Help screen.

### Selection Screen
After scanning/probing the file and folder arguments, the selection screen will open.  In the example below, we have applied a filter pattern, `anqis.gsk`, to select only certain video files.

```
 [s]etAll [r]setAll [i]nit SP:toggle [g]o ?=help [q]uit /anqis.gsk
      Picked=3/10  GB=5.6(0)  CPU=736/800%
 CVT  NET BLOAT    RES  CODEC  MINS     GB   VIDEO
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
>[X]  ---  2831^  960p   hevc    50  1.342   Anqis.Gsk.Kbnvw.2020.S01E06.1080p.BluRay.10Bit,DDP5.1.H265-d3g.mkv --->
 [X]  ---  2796^  960p   hevc    50  1.321   Anqis.Gsk.Kbnvw.2020.S01E05.1080p.BluRay.10Bit,DDP5.1.H265-d3g.mkv --->
 [X]  ---  2769^  960p   hevc    42  1.116   Anqis.Gsk.Kbnvw.2020.S01E04.1080p.BluRay.10Bit,DDP5.1.H265-d3g.mkv --->
 [ ]  ---   801   960p   hevc    44  0.333   Anqis.Gsk.Kbnvw.2020.s01e02.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsb
 [ ]  ---   762   960p   hevc    48  0.350   Anqis.Gsk.Kbnvw.2020.s01e01.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsb
 [ ]  ---   633   960p   hevc    56  0.338   Anqis.Gsk.Kbnvw.2020.s01e09.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsb
 [ ]  ---   614   960p   hevc    50  0.289   Anqis.Gsk.Kbnvw.2020.s01e08.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsb
 [ ]  ---   608   960p   hevc    43  0.246   Anqis.Gsk.Kbnvw.2020.s01e07.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsb
 [ ]  ---   599   960p   hevc    41  0.234   Anqis.Gsk.Kbnvw.2020.s01e03.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsb
 [ ]  ---    86   960p   hevc    50  0.041   JSTY.Anqis.Gsk.Kbnvw.2020.s01e06.960p.x265.cmf28.recode.mkv ---> /dsqy/
```
**Notes.**
* `[ ]` denotes a video NOT selected for conversion.
* `[X]` denotes a video selected for conversion.
* `^` denotes a value over the threshold for conversion. Besides an excessive bloat, the height could be too large, or the codec unacceptable; all depending on the program options.
* To change whether selected, you can use:
    * the s/r/i keys to affect potentially every select, and
    * SPACE to toggle just one; if one is toggle, the cursor moves to the next line so you can toggle sequences very quickly starting at the top.
* The videos are always sorted by their current bloat score, highest first.
* To start converting the selected videos, hit "go" (i.e., the `g` key), and the Conversion Screen replaces this Selection screen.
### Conversion Screen
The Conversion screen only shows the videos selected for conversion on the Selection screen. There is little that can be done other than monitor progress and abort the conversions (with 'q' key).
```
 ?=help q[uit] /anqis.gsk     ToDo=4/9  GB=11.5(-5.0)  CPU=711/800%
CVT  NET BLOAT    RES  CODEC  MINS     GB   VIDEO
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 OK -74%   762   960p   hevc    48  0.350   Anqis.Gsk.Kbnvw.2020.s01e01.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsbu
 OK -79%   599   960p   hevc    41  0.234   Anqis.Gsk.Kbnvw.2020.s01e03.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsbu
 OK -78%   633   960p   hevc    56  0.338   Anqis.Gsk.Kbnvw.2020.s01e09.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsbu
 OK -79%   614   960p   hevc    50  0.289   Anqis.Gsk.Kbnvw.2020.s01e08.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsbu
 OK -72%   801   960p   hevc    44  0.333   Anqis.Gsk.Kbnvw.2020.s01e02.960p.x265.cmf28.recode.mkv ---> /dsqy/Icwsbu
IP   ---  2870^  960p   hevc    43  1.158   Anqis.Gsk.Kbnvw.2020.S01E07.1080p.BluRay.10Bit,DDP5.1.H265-d3g.mkv --->
-----> 34.6% | 08:41 | -16:22 | 1.7x | At 14:43/42:32
[X]  ---  2831^  960p   hevc    50  1.342   Anqis.Gsk.Kbnvw.2020.S01E06.1080p.BluRay.10Bit,DDP5.1.H265-d3g.mkv --->
[X]  ---  2796^  960p   hevc    50  1.321   Anqis.Gsk.Kbnvw.2020.S01E05.1080p.BluRay.10Bit,DDP5.1.H265-d3g.mkv --->
[X]  ---  2769^  960p   hevc    42  1.116   Anqis.Gsk.Kbnvw.2020.S01E04.1080p.BluRay.10Bit,DDP5.1.H265-d3g.mkv --->
```
**Notes**: You can see:
* the net change in size, `(-5.0)` GB, and the current size, `11.5` GB.
* the CPU consumption which is often quite high as in this example.
* the progress of the singular In Progress conversion including percent complete, time elapsed, time remaining, conversion speed vs viewing speed (1.7x), and the position in the video file.
* for completed conversions, the reduction in size, the new size, and the new file name of the converted video.
### Help Screen
The Help screen is available from the other screens; enter the Help screen with `?` and exit it with another `?`
```
Navigation:      H/M/L:      top/middle/end-of-page
  k, UP:  up one row             0, HOME:  first row
j, DOWN:  down one row           $, END:  last row
  Ctrl-u:  half-page up     Ctrl-b, PPAGE:  page up
  Ctrl-d:  half-page down     Ctrl-f, NPAGE:  page down
────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Type keys to alter choice:
                    ? - help screen:  off ON
               s - set all to "[X]"
             r - reset all to "[ ]"
       i,SP - set all initial state
     SP - toggle current line state
              g - begin conversions
    q - quit converting OR exit app
           p - pause/release screen:  off ON
                  / - search string:  brave.new
                  m - mangle titles:  off ON
```
* Some keys are for navigation (they allow vi-like navigation).
* Some keys are set a state, and the current state is capitalized
* Some keys are to instigate some action (they have no value)
* Finally, `/` is to set the filter. The filter must be a valid python regular expression, and it is always case insensitive.

## TODO (What needs documenting still)
* File renaming. It renames files when resolution (TBD) or codec changes if the names had that info as well as companion files like .srt files.
* NOT DONE (tried and failed):
    * Intel QSV
    * Thread limits
