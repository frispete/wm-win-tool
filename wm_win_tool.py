#!/usr/bin/python3
'''
Usage: %(origname)s [-hVvfbr] [-c class][-t title] store
       %(origname)s [-hVvfbr] [-c class][-t title] restore [arg]
       %(origname)s [-hVvb] [-c class][-t title] curlist [max]
       %(origname)s [-hVv] list [max]

       -h, --help           this message
       -V, --version        print version and exit
       -v, --verbose        verbose mode (cumulative)
       -f, --force          force store
       -b, --bracket        use the bracket pattern
       -r, --regexp         class and title pattern are regexp
       -c, --class class    match window class
       -t, --title title    match window title

commands:

store will save the geometry, desktop, and shaded state of selected windows
by class or pattern, unless the previous state is unchanged or the operation
is enforced.

restore will restore the window geometries, matched by class or pattern,
arg is either a timestamp from the store list, or a relative index (eg. -1
for the latest session [default], -2 for the one before...).

Note, that the selection parameters for store and restore should match.

Use the curlist command to test your current selection options.

list shows the available sessions up to an optional maximum number of items
to be restored, sorted by date (descending).

options:

class and title are simple case sensitive wildcard pattern, that can be
supplied multiple times to match a subset of windows. regexp switches them
to regular expression matching. Make sure to properly quote such arguments.

the bracket option just matches the part of the window title in square
brackets, eg.: <[title] long title> will just match <[title]>. This is most
useful in conjunction with Firefox and the Window Titler addon:
https://github.com/tpamula/webextension-window-titler

notes:

The commands store and restore could be triggered, when executed with
symlinks to %(origname)s:

   ln -s %(origname)s.py wm-win-store.py
   ln -s %(origname)s.py wm-win-restore.py

These shortcuts use some hardcoded defaults: --bracket and --verbose.

Homepage: %(homepage)s
Copyright: (c)2020 by %(author)s
License: %(license)s
'''
#
# vim:set et ts=8 sw=4:
#

__version__ = '0.1.6'
__author__ = 'Hans-Peter Jansen <hpj@urpla.net>'
__license__ = 'GNU GPL 2 - see https://www.gnu.org/licenses/gpl2.txt for details'
__homepage__ = 'https://github.com/frispete/wm-win-tool'


import os
import re
import sys
import time
import getopt
import locale
import fnmatch
import logging
import logging.handlers
import datetime
import functools
import subprocess


class gpar:
    '''global parameter class'''
    origname = 'wm-win-tool'
    appdir, appname = os.path.split(sys.argv[0])
    if appdir == '.':
        appdir = os.getcwd()
    if appname.endswith('.py'):
        appname = appname[:-3]
    version = __version__
    author = __author__
    license = __license__
    homepage = __homepage__
    loglevel = logging.WARNING
    force = False
    bracket = False
    regexp = False
    classes = []
    titles = []
    # internals
    storelistdir = os.path.expanduser('~/.local/share/wm-win-tool')
    timestamp = '%Y-%m-%d_%H-%M-%S'


log = logging.getLogger(gpar.appname)

# we need encoding failure tolerant i/o handling
seutf8 = lambda s: s.decode(encoding = 'utf-8',
                            errors = 'surrogateescape')
seopen = lambda fd: open(fd, 'w',
                         encoding = 'utf-8',
                         errors = 'surrogateescape',
                         closefd = False)

sys.stdout = seopen(1)
sys.stderr = seopen(2)

stdout = lambda *s: print(*s, file = sys.stdout, flush = True)
stderr = lambda *s: print(*s, file = sys.stderr, flush = True)


def exit(ret = 0, msg = None, usage = False):
    '''terminate process with optional message and usage'''
    if msg:
        stderr('%s: %s' % (gpar.appname, msg))
    if usage:
        stderr(__doc__ % gpar.__dict__)
    sys.exit(ret)


def setup_logging(loglevel):
    '''setup various aspects of logging facility'''
    logconfig = dict(
        level = loglevel,
        format = '%(asctime)s %(levelname)5s: %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
    )
    logging.basicConfig(**logconfig)


def natural_sort_key(s, case_insensitive = True):
    try:
        for sl in '[]', '()', '{}', '""', "''":
            if s[0] == sl[0] and s[-1] == sl[-1]:
                s = s[1:-1]
    except IndexError:
        pass
    text_case = lambda t: t.lower() if case_insensitive else t
    return [int(text) if text.isdigit() else locale.strxfrm(text_case(text))
            for text in re.split('([0-9]+)', s)]


def rstrip(line, lst = ' \t\r\n'):
    '''strip whitespace and line breaks from line end'''
    items = list(lst)
    while line and line[-1] in items:
        line = line[:-1]
    return line


def unexpanduser(path):
    '''reverse of os.path.expanduser()'''
    homedir = os.path.expanduser('~')
    if path.startswith(homedir):
        path = '~' + path[len(homedir):]
    return path


def new_timestamp_filename(path, ext):
    '''return unique filename with timestamp.ext in path'''
    while True:
        fn = os.path.join(path,
             datetime.datetime.now().strftime(gpar.timestamp) + ext)
        if not os.path.exists(fn):
            return fn
        time.sleep(1)


def fdict(dct):
    '''format a dict in a easy to read presentation
       keys, starting with underscore are suppressed
       Note: only string types are allowed as keys
    '''
    ret = []
    keys = [key for key in dct.keys() if not key.startswith('_')]
    maxkeylen = len(keys) and max([len(key) for key in keys]) or 0
    for key in keys:
        ret.append('%*s: %r' % (maxkeylen, key, dct[key]))
    return '\n'.join(ret)


class WinNotFound(Exception):
    '''WinNotFound is raised from an attempt to remove a non
       existing window from WinList
    '''
    def __init__(self, win):
        self.win = win


class WinDuplicate(WinNotFound):
    '''WinDuplicate is raised from an attempt to add a window
       with identical title and class to WinList
    '''


# https://docs.python.org/dev/library/functools.html#functools.total_ordering
@functools.total_ordering
class Win:
    '''a window, as fetched from wmctrl, with an additional shaded attribute'''
    # active window attributes
    _fields = 'winid, desktop, pid, x, y, w, h, cls, host, title, shaded'.split(', ')
    # default values for _fields
    _defaults = '0, -1, 0, 0, 0, 0, 0, , , , N'.split(', ')
    # storage format is a subset of active fields
    _storefields = 'desktop, shaded, x, y, w, h, cls, title'.split(', ')

    def __init__(self, *args, **kwargs):
        '''setup a window instance dynamically from positional and keyword
           parameters while factoring in default values
        '''
        for idx, key in enumerate(self._fields):
            try:
                val = args[idx]
            except IndexError:
                val = self._defaults[idx]
            self.__dict__[key] = val
        # apply overrides from kwargs
        self.__dict__.update(**kwargs)

    @classmethod
    def _fromstr(cls, line):
        '''create instance from string'''
        # we parse the output of wnctrl -lGpx here (10 columns, space separated)
        # the shaded attribute is not taken into account
        return Win(*line.split(maxsplit = len(cls._fields) - 2))

    @classmethod
    def _fromfile(cls, line):
        '''create instance from file representation'''
        # on disk format (8 columns, ', ' separated) is missing a couple of fields
        return Win(**dict(zip(cls._storefields,
                              line.split(', ', maxsplit = len(cls._storefields)-1))))

    def _tofile(self):
        '''convert instance to file representation'''
        return ', '.join(self._stored_tuple())

    def _stored_tuple(self):
        '''create a tuple from stored values of this instance'''
        return tuple(getattr(self, f) for f in self._storefields)

    def cmp_all(self, other):
        '''compare all stored attributes'''
        if other:
            return self._stored_tuple() == other._stored_tuple()
        return False

    def cmp_desktop(self, other):
        '''desktop changed?'''
        if other:
            return self.desktop == other.desktop
        return False

    def cmp_shaded(self, other):
        '''shade state changed?'''
        if other:
            return self.shaded == other.shaded
        return False

    def cmp_geometry(self, other):
        '''geometry changed?'''
        if other:
            return self.x == other.x \
                and self.y == other.y \
                and self.w == other.w \
                and self.h == other.h
        return False

    @property
    def geostr(self):
        '''generate a geometry value including gravity'''
        return '0,%s,%s,%s,%s' % (self.x, self.y, self.w, self.h)

    # thanks to functools.total_ordering, implementing two special methods
    # are enough to be fully sortable
    def __eq__(self, other):
        '''we define two windows equal, if title and class match'''
        if other:
            return self.title == other.title \
                and self.cls == other.cls
        return False

    def __lt__(self, other):
        '''allow sorting in natural (human) sort order'''
        if other:
            if self.title != other.title:
                return natural_sort_key(self.title) < natural_sort_key(other.title)
            if self.cls != other.cls:
                return natural_sort_key(self.cls) < natural_sort_key(other.cls)
        return False

    def __hash__(self):
        '''hash corresponding with the other sorting methods'''
        return hash((self.title, self.cls))

    def __repr__(self):
        '''runtime representation'''
        return '%s(\n%s\n)' % (self.__class__.__name__, fdict(self.__dict__))


class WinList:
    '''a list of windows
       - creates list of windows from string (output of wmctrl)
       - stores list to file
       - loads list from file
    '''
    def __init__(self, **kwargs):
        '''setup empty window list, and call fromstr or fromfile, if requested'''
        self._fn = None
        self._wl = []
        # KeyErrors are programming errors
        for key, val in kwargs.items():
            self.funcdisp[key](self, val)

    def fromstr(self, buf):
        '''load window list from string (output of wmctrl)'''
        if buf:
            lnnr = 0
            for line in buf.split('\n'):
                lnnr += 1
                if line:
                    try:
                        self._wl.append(Win._fromstr(line))
                    except TypeError:
                        log.exception('line %s malformed: %s',
                                      lnnr, line)
        return len(self._wl)

    def fromfile(self, fn):
        '''load window list from file'''
        self._fn = fn
        lnnr = 0
        try:
            with open(fn, 'r', encoding = 'utf-8') as fd:
                for line in fd:
                    line = rstrip(line)
                    lnnr += 1
                    if line:
                        try:
                            self._wl.append(Win._fromfile(line))
                        except TypeError:
                            log.exception('line %s in file %s malformed: %s',
                                          lnnr, fn, line)
        except OSError:
            log.exception('failed to read %s:', fn)
            return 0
        return len(self._wl)

    # ctor kwargs dispatcher
    funcdisp = {
        'fromstr': fromstr,
        'fromfile': fromfile,
    }

    def tofile(self, fn):
        '''save window list to file'''
        self._fn = fn
        lnnr = 0
        if self._wl:
            try:
                with open(fn, 'w', encoding = 'utf-8') as fd:
                    for win in sorted(self._wl):
                        lnnr += 1
                        line = win._tofile()
                        fd.write(line + '\n')
            except OSError:
                log.exception('failed to write %s:', fd)
                return 0
        return len(self._wl)

    def match(self, win):
        '''match a window in the list'''
        try:
            cur = self._wl[self._wl.index(win)]
        except (IndexError, ValueError):
            cur = None
        else:
            log.debug('match other win:\n%r\nwith current:\n%r', win, cur)
        return cur

    def __eq__(self, other):
        '''compare for equality of both window lists'''
        if other:
            for win in self._wl:
                if not win.cmp_all(other.match(win)):
                    return False
            for oth in other._wl:
                if not oth.cmp_all(self.match(oth)):
                    return False
            # all windows in both lists are identical
            return True
        return False

    def __iadd__(self, win):
        '''add window to list with +='''
        if win in self._wl:
            raise WinDuplicate(win)
        self._wl.append(win)
        return self

    def __isub__(self, win):
        '''remove window from list with -='''
        try:
            del self._wl[self._wl.index(win)]
        except IndexError:
            raise WinNotFound(win)
        return self

    def __iter__(self):
        '''iterate over all windows'''
        for win in sorted(self._wl):
            yield win

    def __len__(self):
        '''list length'''
        return len(self._wl)

    def __bool__(self):
        '''list empty'''
        return bool(self._wl)


def command(cmd, *args):
    '''run command, check result and collect stdout/stderr output'''
    cmd = [cmd]
    cmd.extend(args)
    log.debug('run: %s', ' '.join(cmd))
    # in order to handle encoding errors correctly,
    # we convert with surrogateescape manually
    try:
        res = subprocess.run(cmd,
                             check = True,
                             capture_output = True)
    except subprocess.CalledProcessError as e:
        log.debug('error: command returned %s:\n%s',
                  e.returncode, seutf8(e.stderr))
        return e.returncode, None
    else:
        if res.stdout:
            res.stdout = seutf8(res.stdout)
            log.debug('\n' + res.stdout)
        return res.returncode, res.stdout


def test_command(cmd, *args):
    cmdstr = '%s %s' % (cmd, ' '.join(args))
    try:
        rc, buf = command(cmd, *args)
    except OSError as e:
        log.debug('%s: %s' % (cmdstr, e))
        return -1, '%s: program not found' % cmdstr
    else:
        return rc, '%s: failed with error: %s' % (cmdstr, buf)


def xprop(winid, prop):
    '''run xprop for winid, return value of property'''
    rc, res = command('xprop', '-id', winid)
    if rc == 0 and res:
        for line in res.split('\n'):
            if not line:
                continue
            m = re.match('%s\(.*\) = (.*)' % prop, line)
            if m:
                return m.group(1)


def wmctrl_move_to_desktop(winid, desktop):
    '''run wmctrl -ir winid -t desktop'''
    return command('wmctrl', '-ir', winid, '-t', desktop)[0]


def wmctrl_adjust_geometry(winid, geostr):
    '''run wmctrl -ir winid -e geostr'''
    return command('wmctrl', '-ir', winid, '-e', geostr)[0]


def wmctrl_toggle_shaded(winid):
    '''run wmctrl -ir winid -b toggle,shaded'''
    return command('wmctrl', '-ir', winid, '-b', 'toggle,shaded')[0]


def fetch_winlist():
    '''run wmctrl -lGpx, filter selected, return WinList'''
    log.info('fetch window list')
    curlist = WinList()
    rc, buf = command('wmctrl', '-lGpx')
    if rc == 0:
        # load from buffer
        if curlist.fromstr(buf):
            # and filter list
            curlist = filter_winlist(curlist)
    return curlist


def filter_winlist(srclist):
    '''filter/qualify list of windows according supplied options'''
    dstlist = WinList()

    def match(patlist, win):
        for pat in patlist:
            if gpar.regexp:
                try:
                    if re.match(pat, win):
                        return True
                except re.error:
                    exit(2, 'error in regexp: <%s>' % pat)
            elif fnmatch.fnmatch(win, pat):
                return True
        return False

    try:
        for win in srclist:
            if gpar.bracket:
                m = re.match('\[.*?\]', win.title)
                if m:
                    win.title = m.group(0)
                    dstlist += win
                continue
            elif gpar.classes:
                if match(gpar.classes, win.cls):
                    dstlist += win
                    continue
            elif gpar.titles:
                if match(gpar.titles, win.title):
                    dstlist += win
                    continue
            else:
                # no filter parameter specified
                dstlist += win
    except WinDuplicate as e:
        log.error('duplicate window ignored:\n%s', e.win)

    # update shaded state
    for win in dstlist:
        if xprop(win.winid, '_NET_WM_STATE') == '_NET_WM_STATE_SHADED':
            win.shaded = 'S'
        else:
            win.shaded = 'N'

    log.info('%s windows passed filter (from %s)', len(dstlist), len(srclist))
    return dstlist


def store_filelist(maxcnt = None):
    '''fetch list of saved window lists, optional limit # of items'''
    log.info('collect store list from %s', unexpanduser(gpar.storelistdir))
    storelist = []
    for fn in os.listdir(gpar.storelistdir):
        if fnmatch.fnmatch(fn, '*.wmlst'):
            storelist.append(fn)
    if not maxcnt:
        maxcnt = len(storelist)
    return sorted(storelist)[-maxcnt:]


def store(args):
    '''store geometry of selected windows'''
    curlist = fetch_winlist()
    if not curlist:
        log.debug('no match for selected windows')
        exit(3)
    # check duplicate list
    try:
        wmlstfn = store_filelist(1).pop()
    except IndexError:
        pass
    else:
        stolist = WinList(fromfile = os.path.join(gpar.storelistdir, wmlstfn))
        if curlist == stolist:
            msg = gpar.force and '' or ': not saved'
            log.info("%s hasn't changed%s", wmlstfn, msg)
            if not gpar.force:
                return 0

    if curlist:
        for win in curlist:
            log.debug(repr(win))
        # save window list
        fn = new_timestamp_filename(gpar.storelistdir, '.wmlst')
        curlist.tofile(fn)
        log.info('%s stored [%s matches]', unexpanduser(fn), len(curlist))
    else:
        log.warning('no match')
    return 0


def restore(args):
    '''restore geometry of selected windows'''
    wmlstfn = None
    ts = None
    # check argument (index, filename, or timestamp)
    try:
        which = args.pop(0)
    except IndexError:
        which = -1
    else:
        try:
            which = int(which)
        except ValueError:
            # might be a timestamp
            ts = which
            which = None
    # list of saved window lists
    slist = store_filelist()
    if not slist:
        exit(2, 'no stored sessions (yet), try store')
    # select list
    if which is not None:
        # int is treated as offset
        try:
            wmlstfn = slist[which]
        except IndexError:
            exit(2, 'no such session: %s' % which)
    elif ts:
        # try to match filename and timestamp (filename without extension)
        for fn in slist:
            if ts == fn:
                wmlstfn = fn
                break
            f, ext = os.path.splitext(fn)
            if f == ts:
                wmlstfn = fn
                break

    if wmlstfn is None:
        exit(2, 'no such session: %s' % ts)

    # session to restore located, apply it
    log.info('restore %s', wmlstfn)
    curlist = fetch_winlist()
    # load saved list, compare with current state, and adjust accordingly
    stolist = WinList(fromfile = os.path.join(gpar.storelistdir, wmlstfn))
    for sto in stolist:
        cur = curlist.match(sto)
        if cur:
            log.debug('stored:\n%s', sto)
            log.debug('current:\n%s', cur)
            if not cur.cmp_desktop(sto):
                log.info('move <%s> from desktop %s to desktop %s',
                         cur.title, cur.desktop, sto.desktop)
                wmctrl_move_to_desktop(cur.winid, sto.desktop)
            if not cur.cmp_geometry(sto):
                log.info('adjust geometry of <%s> from %s to %s',
                         cur.title, cur.geostr, sto.geostr)
                wmctrl_adjust_geometry(cur.winid, sto.geostr)
            if not cur.cmp_shaded(sto):
                log.info('adjust shaded state of <%s> from %s to %s',
                         cur.title, cur.shaded, sto.shaded)
                wmctrl_toggle_shaded(cur.winid)
    return 0


def curlist(args):
    '''list selected windows'''
    curlist = fetch_winlist()
    if curlist:
        for cur in curlist:
            log.debug(repr(cur))
        curlist.tofile(1)
    else:
        exit(3, 'no match')
    return 0


def liststore(args):
    '''list available stored session files'''
    try:
        maxcnt = args.pop(0)
    except IndexError:
        maxcnt = None
    else:
        try:
            maxcnt = int(maxcnt)
        except ValueError:
            exit(2, 'invalid list max argument: <%s>' % maxcnt)

    for fn in store_filelist(maxcnt):
        if gpar.loglevel <= logging.INFO:
            stolist = WinList(fromfile = os.path.join(gpar.storelistdir, fn))
            stdout('%s [%s items]' % (fn, len(stolist)))
        else:
            stdout(fn)
    return 0


def main():
    '''Command line interface and console script entry point'''
    try:
        optlist, args = getopt.getopt(sys.argv[1:], 'hVvfbrc:t:',
            ('help', 'version', 'verbose', 'force',
             'bracket', 'regexp', 'class=', 'title=')
        )
    except getopt.error as msg:
        exit(1, msg, True)

    for opt, par in optlist:
        if opt in ('-h', '--help'):
            exit(usage = True)
        elif opt in ('-V', '--version'):
            exit(msg = 'version %s' % gpar.version)
        elif opt in ('-v', '--verbose'):
            if gpar.loglevel > logging.DEBUG:
                gpar.loglevel -= 10
        elif opt in ('-f', '--force'):
            gpar.force = True
        elif opt in ('-b', '--bracket'):
            gpar.bracket = True
        elif opt in ('-r', '--regexp'):
            gpar.regexp = True
        elif opt in ('-c', '--class'):
            gpar.classes.append(par)
        elif opt in ('-t', '--title'):
            gpar.titles.append(par)

    if not args:
        # check symlink names
        if gpar.appname.endswith('restore'):
            args = ['restore']
            gpar.loglevel -= 10
            gpar.bracket = True
        elif gpar.appname.endswith('store'):
            args = ['store']
            gpar.loglevel -= 10
            gpar.bracket = True

    setup_logging(gpar.loglevel)

    for cmd in (('wmctrl', '-h'), ('xprop', '-version')):
        rc, msg = test_command(*cmd)
        if rc:
            exit(2, msg)

    disp = {
        'store': store,
        'restore': restore,
        'curlist': curlist,
        'list': liststore,
    }

    if not args:
        exit(2, 'missing command', True)
    try:
        cmd = args.pop(0).lower()
        func = disp.get(cmd)
        if not func:
            exit(2, 'invalid command: <%s>, check --help' % cmd)
        return func(args)
    except SystemExit as e:
        return e.code
    except KeyboardInterrupt:
        return 5
    except:
        log.exception('internal error:')
        return 8


if __name__ == '__main__':
    exit(main())
