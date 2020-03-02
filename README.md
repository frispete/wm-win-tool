wm-win-tool
===========

Store desktops, geometries, and shades state of X11 windows, selected by title
and class patterns, in order to restore this layout later on.

The primary reason for this program to exist is Firefox, that fails to restore
its session properly under usual X11 window managers (KF5 in my case).

Note, that the problem is well known, but unfortunately, little has been done
in the last 13 years to [solve this issue](https://bugzilla.mozilla.org/show_bug.cgi?id=372650).

This is an attempt to solve it manually/externally, but might prove useful for
other constellations as well.

Usage:
------
```
wm-win-tool [-hVvfbr] [-c class][-t title] store
wm-win-tool [-hVvfbr] [-c class][-t title] restore [arg]
wm-win-tool [-hVvb][-c class][-t title] winlist [max]
wm-win-tool [-hVv] storelist [max]
       -h, --help           this message
       -V, --version        print version and exit
       -v, --verbose        verbose mode (cumulative)
       -f, --force          force store
       -b, --bracket        use the bracket pattern
       -r, --regexp         class and title pattern are regexp
       -c, --class class    match window class
       -t, --title title    match window title
```

class and title are simple case sensitive wildcard pattern by default, that
can be supplied multiple times to match a certain subset of windows. The regexp
option switches to regular expression matching. Make sure to properly quote
such arguments.

Note, that the selection parameters for store and restore should match.

restore will restore the window positions, matched by class or pattern, and
arg is either a timestamp from store list, or a relative index (eg. -1 for
the latest session store [default], -2 for the second latest...).

The bracket option just matches the part of the window title in square
brackets. This is most useful in conjunction with Firefox and the
[Window Titler addon](https://github.com/tpamula/webextension-window-titler).

Example Usage
-------------

Save Firefox session: install the `Window Titler addon` and supply all windows
with a **unique** name, that should appear in square brackets in front of the
window title.

Now saving a session is as easy as:
```
wm-win-tool -vb store
```

You can run this command as many times, as you want. As long as the session
wasn't changed, it won't store a new session (or `--force` option is given).

After reboot, you may wish to restore this session:
```
wm-win-tool -vb restore
```
é voila, the windows move to their original desktops, resize, and have their
shaded state applied.

The session data is saved in `~/local/share/wm-win-tool`.

Install
-------

with pip:
```
$ pip install wm-win-tool
```

from source:
```
$ wget https://files.pythonhosted.org/packages/source/w/wm-win-tool/wm-win-tool-0.1.tar.gz
$ tar xvf wm-win-tool-0.1.tar.gz
$ cd wm-win-tool-0.1
$ python3 setup.py install
```

Dependencies
------------
You need to make sure, that the command line programs `wmctrl` and `xprop` are installed.
Check with your distributions package manager..

Final notes
-----------
The commands store and restore could be implicitly triggered, when executed via symlinks
to wm-win-tool, eg:
```
$ ln -s wm-win-tool wm-win-store
$ ln -s wm-win-tool wm-win-restore
```

Some things are pretty `oldschool`, eg. command line handling, but until the
command line interface gets significant more complex, I prefer to do it this
way.

If you have other ideas, interesting applications, what ever, let me know.

Feedback welcome.
