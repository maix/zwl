# -*- coding: utf8 -*-
from datetime import datetime
from sqlalchemy import TypeDecorator
from sqlalchemy.ext.associationproxy import association_proxy
from zwl import app, db

#TODO add relations

class StringTime(TypeDecorator):
    # By http://stackoverflow.com/a/28143787/196244
    impl = db.String

    def __init__(self, length=None, format='%H:%M', **kwargs):
        super(StringTime, self).__init__(length, **kwargs)
        self.format = format

    def process_literal_param(self, value, dialect):
        if value is None or value == '':
            return ''
        # allow passing string or time to column
        if isinstance(value, basestring):
            value = datetime.strptime(value, self.format).time()

        # convert python time to sql string
        return value.strftime(self.format)

    process_bind_param = process_literal_param

    def process_result_value(self, value, dialect):
        if value is None or value == '':
            return None
        return datetime.strptime(value, self.format).time()

class TimetableEntry(db.Model):
    __tablename__ = 'fahrplan_sessionfahrplan' if app.config['USE_SESSION_TIMETABLE'] else 'fzm'

    id = db.Column(db.Integer, primary_key=True)
    train_id = db.Column('zug_id', db.Integer)
    loc = db.Column('betriebsstelle', db.String(10))
    arr = db.Column('ankunft', StringTime(7))
    dep = db.Column('abfahrt', StringTime(7))
    track = db.Column('gleis', db.String(5))
    direction_code = db.Column('fahrtrichtung', db.Integer)
    sorttime = db.Column('sortierzeit', db.Time)

    if app.config['USE_SESSION_TIMETABLE']:
        arr_want = db.Column('ankunft_soll', StringTime(7))
        arr_real = db.Column('ankunft_ist', StringTime(7))
        dep_want = db.Column('abfahrt_soll', StringTime(7))
        dep_real = db.Column('abfahrt_ist', StringTime(7))
        track_want = db.Column('gleis_soll', db.String(5))
        track_real = db.Column('gleis_ist', db.String(5))
    else:
        arr_want = arr_real = property(arr)
        dep_want = dep_real = property(dep)
        track_want = track_real = property(track)

    def __repr__(self):
        return '<%s zug_id=%d at %r>' \
            % (self.__class__.__name__, self.train_id, self.loc)

    @property #TODO: use TypeDecorator
    def direction(self):
        return {0: 'left', 1: 'right', 10: 'left', 11: 'right'}[self.direction_code]

class TrainType(db.Model):
    __tablename__ = 'zuege_zuggattungen'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column('zuggattung', db.String(11))
    description = db.Column('bezeichnung', db.String(255))
    category = db.Column('verkehrsart', db.Enum('fv', 'nv', 'gv', 'lz', 'sz'))

class Train(db.Model):
    __tablename__ = 'fahrplan_sessionzuege' if app.config['USE_SESSION_TIMETABLE'] else 'fahrplan_zuege'

    id = db.Column(db.Integer, primary_key=True)
    nr = db.Column('zugnummer', db.Integer)
    type_id = db.Column('zuggattung_id', db.Integer, db.ForeignKey(TrainType.id))
    vmax = db.Column(db.Integer)
    comment = db.Column('bemerkungen', db.String(255))

    type_obj = db.relationship(TrainType)
    type = association_proxy('type_obj', 'name')