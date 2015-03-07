#!/usr/bin/env python2
# -*- coding: utf8 -*-
import itertools
import os
import tempfile
import unittest
import warnings
from datetime import timedelta, time
from zwl import app, db, trains
from zwl.database import *
from zwl.lines import get_line
from zwl.utils import MidnightWarning, timeadd, timediff

class ZWLTestCase(unittest.TestCase):
    def _setup_database(self):
        self.db_fd, self.db = tempfile.mkstemp()
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///%s' % self.db
        app.config['TESTING'] = True
        self.app = app.test_client()
        db.metadata.create_all(bind=db.engine)

    def _teardown_database(self):
        os.close(self.db_fd)
        #TODO: unlinking breaks everything?!
        #os.unlink(self.db)

class TestTrains(ZWLTestCase):
    def setUp(self):
        self._setup_database()

        ice = TrainType(name='ICE')
        re = TrainType(name='RE')
        self.t1 = Train(nr=700, type_obj=ice)
        self.t2 = Train(nr=2342, type_obj=re)
        db.session.add_all([ice, re, self.t1, self.t2])
        db.session.commit()

        t1 = self.t1.id
        db.session.add_all([
            TimetableEntry(train_id=t1, loc='XWF', arr_plan=None,        dep_plan=time(15,30), sorttime=time(15,30)),
            TimetableEntry(train_id=t1, loc='XLG', arr_plan=time(15,34), dep_plan=time(15,34), sorttime=time(15,34)),
            TimetableEntry(train_id=t1, loc='XBG', arr_plan=time(15,35), dep_plan=time(15,36), sorttime=time(15,36)),
            TimetableEntry(train_id=t1, loc='XDE', arr_plan=time(15,39), dep_plan=time(15,40), sorttime=time(15,40)),
            TimetableEntry(train_id=t1, loc='XCE', arr_plan=time(15,43), dep_plan=None,        sorttime=time(15,43)),
        ])

        t2 = self.t2.id
        db.session.add_all([
            TimetableEntry(train_id=t2, loc='XPN', arr_plan=None,        dep_plan=time(16,21), sorttime=time(16,21)),
            TimetableEntry(train_id=t2, loc='XLG', arr_plan=time(16,23), dep_plan=time(16,23), sorttime=time(16,23)),
            TimetableEntry(train_id=t2, loc='XWF', arr_plan=time(16,27), dep_plan=time(16,30), sorttime=time(16,30)),
            TimetableEntry(train_id=t2, loc='XCE', arr_plan=time(16,32), dep_plan=time(16,33), sorttime=time(16,33)),
            TimetableEntry(train_id=t2, loc='XDE', arr_plan=time(16,36), dep_plan=None,        sorttime=time(16,36)),
        ])
        db.session.commit()

    def test_get_train_ids_within_timeframe(self):
        ids = trains.get_train_ids_within_timeframe(time(15,40), time(16,00), get_line('sample'))
        assert self.t1.id in ids
        assert self.t2.id not in ids

        ids = trains.get_train_ids_within_timeframe(time(15,00), time(15,36), get_line('sample'), startpos=0, endpos=.2)
        assert ids == []

    def test_get_train_information(self):
        res = list(trains.get_train_information([self.t1], get_line('sample')))

        assert len(res) == 1
        inf = res[0]
        assert inf['nr'] == 700
        assert inf['type'] == 'ICE'
        assert len(inf['segments']) == 2

        assert sorted([['XDE#1', 'XCE#1'], ['XLG#1', 'XBG#2', 'XDE#2']]) == \
            sorted([[e['loc'] for e in seg['timetable']] for seg in inf['segments']])

        allelemsd = {e['loc']: e for e in
            itertools.chain.from_iterable(seg['timetable'] for seg in inf['segments'])}
        #TODO activate when implemented
        #assert allelemsd['XDE#2']['succ'] == 'XCE'
        #assert allelemsd['XLG#1']['pred'] == 'XWF'

    def test_locations_extended_between(self):
        line = get_line('sample')
        locs = list(line.locations_extended_between())
        assert locs == line.locations

        locs = line.locations_extended_between(.4, .4)
        assert [l.id for l in locs] == ['XCE#1', 'XLG#1']

        locs = line.locations_extended_between(.31, .55)
        assert [l.id for l in locs] == ['XCE#1', 'XLG#1', 'XBG#2']

        # simulate floating point errors in javascript
        locs = line.locations_extended_between(.2999999999999, .6000000000001)
        assert [l.id for l in locs] == ['XCE#1', 'XLG#1', 'XBG#2']

    def tearDown(self):
        self._teardown_database()


class TestDatabase(ZWLTestCase):
    def setUp(self):
        self._setup_database()

        self.ic = TrainType(name='IC')
        self.re = TrainType(name='RE')
        db.session.add_all([self.ic, self.re])
        db.session.commit()
        db.session.add_all([
            MinimumStopTime(999, None, None, None),
            MinimumStopTime(200, self.ic.id, None, None),
            MinimumStopTime(100, None, 'XPN', None),
            MinimumStopTime(101, None, 'XPN', 1),
            MinimumStopTime(103, None, 'XPN', 3),
            MinimumStopTime(203, self.ic.id, 'XPN', 3),
        ])
        db.session.commit()

    def test_minimum_stop_time(self):
        self.assertEquals(MinimumStopTime.lookup(self.ic, None), 200)
        self.assertEquals(MinimumStopTime.lookup(self.re, None), 999)
        self.assertEquals(MinimumStopTime.lookup(self.ic, 'XPN'), 100)
        self.assertEquals(MinimumStopTime.lookup(self.re, 'XPN'), 100)
        self.assertEquals(MinimumStopTime.lookup(self.ic, 'XPN', 2), 100)
        self.assertEquals(MinimumStopTime.lookup(self.re, 'XPN', 2), 100)
        self.assertEquals(MinimumStopTime.lookup(self.ic, 'XPN', 3), 203)
        self.assertEquals(MinimumStopTime.lookup(self.re, 'XPN', 3), 103)
        self.assertEquals(MinimumStopTime.lookup(self.ic, 'XDE'), 200)
        self.assertEquals(MinimumStopTime.lookup(self.ic, 'XDE', 1), 200)
        self.assertEquals(MinimumStopTime.lookup(self.re, 'XDE'), 999)
        self.assertEquals(MinimumStopTime.lookup(self.re, 'XDE', 1), 999)

    def tearDown(self):
        self._teardown_database()

class TestUtils(ZWLTestCase):
    def test_timediff(self):
        self.assertEqual(timediff(time(19,20), time(17,40)),
                         timedelta(minutes=100))
        with self.assertRaises(ValueError):
            timediff(time(19,20), time(20,30))
        with self.assertRaises(ValueError):
            timediff(time(19,20), time(10,30))

        # not implemented yet
        #self.assertEqual(timediff(time(1,15), time(22,45)),
        #                 timedelta(minutes=150))

    def test_timeadd(self):
        self.assertEqual(timeadd(time(10,20), timedelta(minutes=80)),
                         time(11,40))
        with warnings.catch_warnings(record=True) as w:
            self.assertEqual(timeadd(time(22,20), timedelta(minutes=120)),
                             time(0,20))
            assert len(w) == 1
            assert issubclass(w[-1].category, MidnightWarning)

        with self.assertRaises(ValueError):
            timeadd(time(10,20), timedelta(hours=9))


if __name__ == '__main__':
    unittest.main()
