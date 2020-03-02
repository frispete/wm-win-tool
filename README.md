wm-win-tool
===========
Store desktops, geometries, and shade states of X11 windows, selected by
window title and class patterns, in order to restore their layouts later on.

The primary reason for this program to exist is Firefox, that fails to restore
its session properly under usual X11 window managers (KF5 in my case).

Note, that the problem is well known, but unfortunately, little has been done
in the last 13 years to [solve this issue](https://bugzilla.mozilla.org/show_bug.cgi?id=372650).

This program is an humble attempt to solve it manually/externally, but might
prove useful for other constellations as well.

Usage:
------
```
wm-win-tool [-hVvfbr] [-c class][-t title] store
wm-win-tool [-hVvfbr] [-c class][-t title] restore [arg]
wm-win-tool [-hVvb][-c class][-t title] curlist [max]
wm-win-tool [-hVv] list [max]
       -h, --help           this message
       -V, --version        print version and exit
       -v, --verbose        verbose mode (cumulative)
       -f, --force          force store
       -b, --bracket        use the bracket pattern
       -r, --regexp         class and title pattern are regexp
       -c, --class class    match window class
       -t, --title title    match window title
```

Commands
--------
`store` will save the geometry, desktop, and shaded state of selected windows
by class or pattern, unless the previous state is unchanged or the operation
is enforced with `--force`.

`restore` will restore the window geometries, matched by class or pattern,
`arg` is either a timestamp from the store list, or a relative index (eg. -1
for the latest session [default], -2 for the one before...).

Note, that the selection parameters for store and restore *should* match.

Use the `curlist` command to test your current selection options.

`list` shows the available sessions up to an optional maximum number of items
to be restored, sorted by date (descending).

Options
-------
`--class` and `--title` are simple case sensitive wildcard pattern, that can
be supplied multiple times to match a subset of windows. `--regexp` switches
them to regular expression matching. Make sure to properly quote such
arguments.

The `--bracket` option just matches the part of the window title in square
brackets, eg.: `[title] long title` will just match `[title]`. This is most
useful in conjunction with Firefox and the
[Window Titler addon](https://github.com/tpamula/webextension-window-titler).

Example Usage
-------------
In order to save your Firefox sessions: install the `Window Titler addon` and
supply all windows with a **unique** title, that should appear in square
brackets in front of the window title, while the normal window title changes
depending on which tab is actived.

Now saving a session is as easy as:
```
wm-win-tool -vb store
```

You can run this command as many times as you want. As long as the session
wasn't changed meanwhile, it won't store a new session (unless the `--force`
option is supplied).

After reboot, you may wish to restore this session:
```
wm-win-tool -vb restore
```
é voila, the windows move to their original desktops, and have their former
geometry and shaded state applied.

Install
-------
Using pip:
```
$ pip install wm-win-tool
```

From source:
```
$ wget https://files.pythonhosted.org/packages/source/w/wm-win-tool/wm-win-tool-<version>.tar.gz
$ tar xvf wm-win-tool-<version>.tar.gz
$ cd wm-win-tool-<version>
$ python3 setup.py install
```

Dependencies
------------
You need to make sure, that the command line programs `wmctrl` and `xprop` are
installed. Check with your distributions package manager..

Consequently, `wm-win-tool` needs a proper DISPLAY/XAUTHORITY environment
setup.

Final notes
-----------
The commands `store` and `restore` could be implicitly triggered, when executed
via symlinks to `wm-win-tool`, eg.:
```
$ cd <whatever>/bin
$ ln -s wm-win-tool wm-win-store
$ ln -s wm-win-tool wm-win-restore
```
These operation modes come with some hardcoded defaults: `--bracket` and
`--verbose` for the most usual usage pattern. If that's not enough, a config
file option might be useful (TBD).

The session data is saved in `~/local/share/wm-win-tool`.

In pathological cases (where I count in for sure), it might be advantageous
to exclude Firefox from the window manager session restore completely. kwin5
is configurable as such. When executing Firefox after reboot, it will open all
session windows on your **current** desktop then. Run `wm-win-restore` and *be
done*.

If you plan to run `wm-win-store` from `crontab -e`, keep in mind, that most
cron implementations suffer from variable expansion issues. Here is an
example, that should work with Vixie cron:
```
#PATH=$HOME/bin:/bin:/usr/bin	# won't work
#XAUTHORITY=~/.Xauthority	# neither that

# store firefox window list
42 * * * * XAUTHORITY=~/.Xauthority DISPLAY=:0 wm-win-tool -b store
```
`AUTHORITY`is expanded from the shell in this case, which is necessary to
operate properly. Depending on the way, you installed `wm-win-tool`, you might
need to adjust the path as well. We also avoid using the symlink shortcut
here due to its implicit verbosity level.

Some things are realized in a pretty `oldschool` way, eg. command line
handling, but until the command line interface gets **significantly** more
complex, I prefer to do it this way (since ages).

If you have other ideas, interesting applications, what ever, let me know.

Feedback welcome.
