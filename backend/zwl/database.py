# -*- coding: utf8 -*-
"""
    zwl.database
    ============

    Database models.

    :copyright: (c) 2015, Marian Sigler
    :license: GNU GPL 2.0 or later.
"""

from datetime import datetime
from sqlalchemy import TypeDecorator
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.sql.functions import coalesce
from zwl import app, db


class TrainType(db.Model):
    __tablename__ = 'zuege_zuggattungen'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column('zuggattung', db.String(11))
    description = db.Column('bezeichnung', db.String(255))
    category = db.Column('verkehrsart', db.Enum('fv', 'nv', 'gv', 'lz', 'sz'))

class Train(db.Model):
    __tablename__ = 'fahrplan_sessionzuege'

    id = db.Column(db.Integer, primary_key=True)
    nr = db.Column('zugnummer', db.Integer)
    type_id = db.Column('zuggattung_id', db.Integer, db.ForeignKey(TrainType.id))
    vmax = db.Column(db.Integer)
    comment = db.Column('bemerkungen', db.String(255))
    transition_from_id = db.Column('uebergang_von_zug_id', db.Integer, db.ForeignKey(id))
    transition_to_id = db.Column('uebergang_nach_zug_id', db.Integer, db.ForeignKey(id))

    transition_from = db.relationship(lambda: Train, foreign_keys=transition_from_id, primaryjoin=transition_from_id==id, remote_side=id)
    transition_to = db.relationship(lambda: Train, foreign_keys=transition_to_id, primaryjoin=transition_to_id==id, remote_side=id)
    transition_from_nr = association_proxy('transition_from', 'nr')
    transition_to_nr = association_proxy('transition_to', 'nr')
    type_obj = db.relationship(TrainType)
    type = association_proxy('type_obj', 'name')
    category = association_proxy('type_obj', 'category')

    def __repr__(self):
        return '<%s #%s (%s %d)>' \
            % (self.__class__.__name__, self.id, self.type, self.nr)


class TimetableEntry(db.Model):
    __tablename__ = 'fahrplan_sessionfahrplan'

    id = db.Column(db.Integer, primary_key=True)
    train_id = db.Column('zug_id', db.Integer, db.ForeignKey(Train.id))
    loc = db.Column('betriebsstelle', db.String(10))
    arr_plan = db.Column('ankunft_plan', db.Time)
    dep_plan = db.Column('abfahrt_plan', db.Time)
    track_plan = db.Column('gleis_plan', db.Integer)
    min_ridetime = db.Column('min_fahrzeit', db.Integer) # from here to next
    min_stoptime = db.Column('min_haltezeit', db.Integer)
    sorttime = db.Column('sortierzeit', db.Time)

    arr_want = db.Column('ankunft_soll', db.Time)
    arr_real = db.Column('ankunft_ist', db.Time)
    arr_pred = db.Column('ankunft_prognose', db.Time)
    dep_want = db.Column('abfahrt_soll', db.Time)
    dep_real = db.Column('abfahrt_ist', db.Time)
    dep_pred = db.Column('abfahrt_prognose', db.Time)
    track_want = db.Column('gleis_soll', db.Integer)
    track_real = db.Column('gleis_ist', db.Integer)

    train = db.relationship(Train,
        backref=db.backref('timetable_entries', lazy='dynamic'))

    def __repr__(self):
        return '<%s train#%s at %s>' \
            % (self.__class__.__name__, self.train_id, self.loc)


class MinimumStopTime(db.Model):
    __tablename__ = 'fahrplan_mindesthaltezeiten'

    id = db.Column(db.Integer, primary_key=True)
    minimum_stop_time = db.Column('mindesthaltezeit' , db.Integer)
    loc = db.Column('betriebsstelle', db.String(5))
    track = db.Column('gleis', db.Integer)
    traintype_id = db.Column('zuggattung_id', db.Integer,
        db.ForeignKey(TrainType.id))

    traintype = db.relationship(TrainType)

    def __init__(self, minimum_stop_time=None, traintype=None, loc=None, track=None, **kwargs):
        if isinstance(traintype, TrainType):
            traintype = traintype.id
        super(MinimumStopTime, self).__init__(traintype_id=traintype, loc=loc,
                track=track, minimum_stop_time=minimum_stop_time, **kwargs)

    def __repr__(self):
        return '<MinimumStopTime=%s%s%s%s>' % (
                self.minimum_stop_time,
                ' %s' % self.traintype.name if self.traintype else '',
                ' @%s' % self.loc if self.loc else '',
                '[%s]' % self.track if self.track else '',
        )

    @classmethod
    def lookup(cls, traintype, loc, track=None):
        """
        Find the minimum stopping time for a train of type `traintype` at
        `loc` and (optionally) `track`.

        Important: There must be a fallback (None, None, None) entry in the
        database, else incorrect results will be returned by `lookup()`.

        :param traintype: Train object, TrainType object, or TrainType id
        """
        if isinstance(traintype, Train):
            traintype = traintype.type_id
        elif isinstance(traintype, TrainType):
            traintype = traintype.id
        if track is not None and loc is None:
            raise ValueError('loc cannot be None when track is not')

        # rank lines by how good they fit. If the field we look at is NULL,
        # its line is ranked between matching (1) and contradicting (0) lines,
        # by using a ordering value of 0.5. That way default entries can be
        # defined by setting to NULL in some or all columns.
        q = db.session.query(cls.minimum_stop_time)
        if track is not None:
            q = q.order_by(coalesce((cls.loc==loc) & (cls.track==track), 0.5).desc())
        q = q.order_by(coalesce((cls.loc==loc) & cls.track.is_(None), 0.5).desc())
        q = q.order_by(coalesce(cls.traintype_id==traintype, 0.5).desc())

        result = db.session.execute(q).scalar()
        if result is None:
            raise ValueError('No minimum stop time defined')
        return result
