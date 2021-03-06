# -*- coding: utf8 -*-
"""
    zwl.views
    =========

    The application's views.

    :copyright: (c) 2015, Marian Sigler
    :license: GNU GPL 2.0 or later.
"""

import os
from datetime import datetime, time
from flask import abort, send_from_directory, Response, json, request, jsonify
from time import sleep, time as ttime
from werkzeug.exceptions import NotFound
from zwl import app, db
from zwl.database import Train
from zwl.lines import lineconfigs, get_lineconfig
from zwl.predict import Manager
from zwl.trains import get_train_ids_within_timeframe, get_train_information
from zwl.utils import js2time, time2js, get_time


@app.route('/lines/')
@app.route('/lines/<key>.json')
def get_line(key=None):
    sleep(app.config['RESPONSE_DELAY'])
    if key is None:
        return Response('\n'.join(lineconfigs.keys()), mimetype='text/plain')

    if key not in lineconfigs:
        abort(404)

    return jsonify(lineconfigs[key].serialize())


@app.route('/lines/info')
def line_info():
    # sort '-foo' immediately after 'foo' (the former being reversion of the latter)
    ids = sorted(lineconfigs, key=lambda k: (k.lstrip('-'), k.startswith('-')))
    return Response(u'\n\n\n'.join(get_lineconfig(l).info() for l in ids),
            mimetype='text/plain')


@app.route('/predict')
def predict():
    start = ttime()

    Manager.from_timestamp(time(14,10)).run()
    db.session.commit()

    end = ttime()

    return Response('done (%fs)' % (end - start), mimetype='text/plain')


@app.route('/graphdata/<line>.json')
def get_graph_data(line):
    sleep(app.config['RESPONSE_DELAY'])

    if line == 'sample':
        return jsonify(trains=[
            {'type': 'ICE',
             'nr': 407,
             'category': 'fv',
             'segments': [
               {
                 'timetable': [
                   {'loc':'XDE#1', 'arr_plan':None, 'dep_plan':13099020, 'track_plan':4},
                   {'line':'XDE#1_XCE#1'},
                   {'loc':'XCE#1', 'arr_plan':13099200, 'dep_plan':13099260, 'track_plan':3},
                   {'line':'XCE#1_XLG#1'},
                   {'loc':'XLG#1', 'arr_plan':13099500, 'dep_plan':13099500},
                   {'line':'XLG#1_XDE#2'},
                   {'loc':'XDE#2', 'arr_plan':13099800, 'dep_plan':None, 'track_plan':3},
                 ],
                 'direction': 'right',
               },
             ],
             'comment': u'',
            },
            {'type': 'IRE',
             'nr': 2342,
             'category': 'nv',
             'segments': [
               {
                 'timetable': [
                   {'loc':'XDE#2', 'arr_plan':None, 'dep_plan':13099440, 'track_plan':1},
                   {'line':'XLG#1_XDE#2'},
                   {'loc':'XLG#1', 'arr_plan':13099740, 'dep_plan':13099740},
                 ],
                 'direction': 'left',
               },
             ],
            },
            {'type': 'RB',
             'nr': 12345,
             'category': 'nv',
             'segments': [
               {
                 'timetable': [
                   {'loc':'XDE#1', 'arr_plan':None, 'dep_plan':13099000, 'track_plan':2},
                   {'line':'XDE#1_XCE#1', 'opposite':True},
                   {'loc':'XCE#1', 'arr_plan':13099140, 'dep_plan':13099140, 'track_plan':2},
                   {'line':'XCE#1_XLG#1'},
                   {'loc':'XDE#2', 'arr_plan':13099460, 'dep_plan':None, 'track_plan':3},
                 ],
                 'direction': 'right',
               },
             ],
            },
        ])

    try:
        line = get_lineconfig(line)
    except KeyError:
        abort(404)

    starttime = js2time(request.args['starttime'])
    endtime = js2time(request.args['endtime'])

    startpos = request.args.get('startpos', 0, float)
    endpos = request.args.get('endpos', 1, float)

    train_ids = list(get_train_ids_within_timeframe(
        starttime, endtime, line, startpos=startpos, endpos=endpos))
    trains = Train.query.filter(Train.id.in_(train_ids)).all() if train_ids else []

    return jsonify(
        trains=list(get_train_information(trains, line)),
        line=line.id,
        starttime=time2js(starttime),
        endtime=time2js(endtime),
    )


@app.route('/time')
def time_plain():
    state, time = get_time()
    timestr = time.strftime('%F %T')

    return Response('state: %s\ntime:  %s' % (state, timestr),
                    mimetype='text/plain')


@app.route('/clock.json')
def clock():
    sleep(app.config['RESPONSE_DELAY'])
    state, timestamp = get_time()
    return jsonify(
        state=state,
        time=time2js(timestamp.time()),
        timestr=timestamp.strftime('%F %T'), # debugging only
    )


@app.route('/')
@app.route('/frontend/<filename>')
@app.route('/frontend/<subdir>/<filename>')
def frontend(subdir='', filename=None):
    if filename == 'zwl.html':
        # if accessed this way the js files wouldn't be found, so just forbid it
        abort(404)
    if filename is None:
        filename = 'zwl.html'

    # as an additional security measure, prevent arbitrary path traversal
    if subdir not in ('', 'src'):
        abort(403)

    # flask would use safe_join if we supplied a relative path
    frontend_dir = app.config.get('FRONTEND_DIR',
        os.path.join(app.root_path, os.pardir, os.pardir, 'frontend'))
    return send_from_directory(os.path.join(frontend_dir, subdir), filename)


@app.route('/favicon.ico')
def favicon():
    return frontend(filename='favicon.ico')


@app.route('/_variables.js')
def js_variables():
    vars = {
        'SCRIPT_ROOT': request.script_root,
        'DEFAULT_VIEWCONFIG': 'gt/ring-xwf,.01,.99',
        'ALL_LINECONFIGS': {l.id: l.name for l in lineconfigs.values()},
        'REFRESH_INTERVAL': app.config['REFRESH_INTERVAL']*1000, # milliseconds
        'EPOCH': time2js(time(4,0,0)),
    }

    for v in ('TIMETABLE_URL_TEMPLATE',):
        vars[v] = app.config[v]

    return Response(('%s = %s;\n' % (k, json.htmlsafe_dumps(v))
                     for (k,v) in vars.items()),
                    mimetype='text/javascript')


@app.route('/_style.css')
def stylesheet():
    _colormap_prefix = 'TRAIN_COLOR_MAP_'

    def _rules():
        for name in app.config:
            if not name.startswith(_colormap_prefix):
                continue
            theme = name[len(_colormap_prefix):].lower()
            colormap = app.config[name]

            for cat, color in colormap.items():
                if cat is None:
                    catstring = ''
                else:
                    catstring = '.category_%s' % cat

                yield '.theme_%s %s .trainpath line { stroke: %s; }' \
                    % (theme, catstring, color)
                yield '.theme_%s %s text { fill: %s; }' \
                    % (theme, catstring, color)

            yield ''

    return Response('\n'.join(_rules()), mimetype='text/css')


@app.route('/debug')
def debug():
    raise Exception
