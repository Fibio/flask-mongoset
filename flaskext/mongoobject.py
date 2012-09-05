# -*- coding: utf-8 -*-
"""
flaskext.mongoobject
~~~~~~~~~~~~~~~~~~~~

Add basic MongoDB support to your Flask application.

Inspiration:
https://github.com/slacy/minimongo/
https://github.com/mitsuhiko/flask-sqlalchemy

:copyright: (c) 2011 by Daniel, Dao Quang Minh (dqminh).
:license: MIT, see LICENSE for more details.
"""
from __future__ import absolute_import
import operator
from bson.dbref import DBRef
from bson.son import SON
from pymongo import Connection
from pymongo.collection import Collection
from pymongo.cursor import Cursor
from pymongo.son_manipulator import SONManipulator, AutoReference, NamespaceInjector

from flask import abort


autoincrement_models = []


class AuthenticationIncorrect(Exception):
    pass


class ClassProperty(property):
    def __init__(self, method, *args, **kwargs):
        method = classmethod(method)
        return super(ClassProperty, self).__init__(method, *args, **kwargs)

    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


classproperty = ClassProperty


class AttrDict(dict):
    """
    Base object that represents a MongoDB document. The object will behave both
    like a dict `x['y']` and like an object `x.y`
    """
    def __init__(self, initial=None, **kwargs):
        initial and self._setattrs(**initial)
        self._setattrs(**kwargs)

    def __getattr__(self, attr):
        return self._change_method('__getitem__', attr)

    def __setattr__(self, attr, value):
        value = self._make_attr_dict(value)
        return self.__setitem__(attr, value)

    def __delattr__(self, attr):
        return self._change_method('__delitem__', attr)

    def _make_attr_dict(self, value):
        # Supporting method for self.__setitem__
        if isinstance(value, list):
            value = map(self._make_attr_dict, value)
        elif isinstance(value, dict) and not isinstance(value, AttrDict):
            value = AttrDict(value)
        return value

    def _change_method(self, method, *args, **kwargs):
        try:
            callmethod = operator.methodcaller(method, *args, **kwargs)
            return callmethod(super(AttrDict, self))
        except KeyError as excn:
            raise AttributeError(excn)

    def _setattrs(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)


class MongoCursor(Cursor):
    """
    A cursor that will return an instance of :attr:`as_class` instead of
    `dict`
    """
    def __init__(self, *args, **kwargs):
        self.as_class = kwargs.pop('as_class')
        super(MongoCursor, self).__init__(*args, **kwargs)

    def next(self):
        data = super(MongoCursor, self).next()
        return self.as_class(data)

    def __getitem__(self, index):
        item = super(MongoCursor, self).__getitem__(index)
        if isinstance(index, slice):
            return item
        else:
            return self.as_class(item)


class AutoincrementId(SONManipulator):
    """ Creates objects id as integer and autoincrement it,
        if "id" not in son object, but not usefull with DBRefs
    """
    def transform_incoming(self, son, collection):
        son["id"] = son.get('id', self._get_next_id(collection))
        return son

    def _get_next_id(self, collection):
        database = collection.database
        result = database._autoincrement_ids.find_and_modify(
            query={"id": collection.name,},
            update={"$inc": {"next": 1},},
            upsert=True,
            new=True,)
        return result["next"]


class AutoReferenceObject(AutoReference):
    """
    Transparently reference and de-reference already saved embedded objects.

    This manipulator should probably only be used when the NamespaceInjector is
    also being used, otherwise it doesn't make too much sense - documents can
    only be auto-referenced if they have an `_ns` field.

    If the document should be an instance of a :class:`flaskext.mongoobject.Model`
    then we will transform it into a model's instance too.

    NOTE: this will behave poorly if you have a circular reference.

    TODO: this only works for documents that are in the same database. To fix
    this we'll need to add a DatabaseInjector that adds `_db` and then make
    use of the optional `database` support for DBRefs.
    """

    def __init__(self, mongo):
        self.mongo = mongo
        self.db = mongo.session

    def transform_outgoing(self, son, collection):
        def transform_value(value):
            if isinstance(value, DBRef):
                return transform_value(self.__database.dereference(value))
            elif isinstance(value, list):
                return [transform_value(v) for v in value]
            elif isinstance(value, dict):
                if value.get('_ns', None):
                    # if the collection has a :class:`Model` mapper
                    cls = self.mongo.mapper.get(value['_ns'], None)
                    if cls:
                        return cls(transform_dict(SON(value)))
                return transform_dict(SON(value))
            return value

        def transform_dict(object):
            for (key, value) in object.items():
                object[key] = transform_value(value)
            return object

        value = transform_dict(SON(son))
        return value


class BaseQuery(Collection):
    """
    `BaseQuery` extends :class:`pymongo.Collection` that replaces all results
    coming from database with instance of :class:`Model`
    """

    def __init__(self, *args, **kwargs):
        self.document_class = kwargs.pop('document_class')
        super(BaseQuery, self).__init__(*args, **kwargs)

    def find_one(self, *args, **kwargs):
        kwargs['as_class'] = self.document_class
        return super(BaseQuery, self).find_one(*args, **kwargs)

    def find(self, *args, **kwargs):
        kwargs['as_class'] = self.document_class
        return MongoCursor(self, *args, **kwargs)

    def find_and_modify(self, *args, **kwargs):
        kwargs['as_class'] = self.document_class
        return super(BaseQuery, self).find_and_modify(*args, **kwargs)

    def get_or_404(self, id):
        item = self.find_one(id, as_class=self.document_class)
        if not item:
            abort(404)
        return item


class _QueryProperty(object):
    """
    Represent :attr:`Model.query` that dynamically instantiate
    :attr:`Model.query_class` so that we can do things like
    `Model.query.find_one`
    """
    def __init__(self, mongo):
        self.mongo = mongo

    def __get__(self, instance, owner):
        return owner.query_class(database=self.mongo.session,
                                 name=owner.__collection__,
                                 document_class=owner)


class Model(AttrDict):
    """
    Base class for custom user models. Provide convenience ActiveRecord
    methods such as :attr:`save`, :attr:`remove`
    """
    #: Query class
    query_class = BaseQuery
    #: instance of :attr:`query_class`
    query = None
    #: name of this model collection
    __collection__ = None

    @property
    def id(self):
        if getattr(self, "id", None):
            return str(self._id)

    def __init__(self, *args, **kwargs):
        assert 'query_class' not in kwargs
        assert 'query' not in kwargs
        assert '__collection__' not in kwargs
        super(Model, self).__init__(*args, **kwargs)

    def save(self, *args, **kwargs):
        self.query.save(self, *args, **kwargs)
        return self

    def update(self, *args, **kwargs):
        self.query.update({"_id": self._id}, self, *args, **kwargs)
        return self

    def remove(self):
        return self.query.remove(self._id)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           super(Model, self).__str__())

    def __unicode__(self):
        return str(self).decode('utf-8')


class MongoObject(object):
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)
        self.Model = self.make_model()
        self.mapper = {}

    def init_app(self, app):
        app.config.setdefault('MONGODB_HOST', "localhost")
        app.config.setdefault('MONGODB_PORT', 27017)
        app.config.setdefault('MONGODB_DATABASE', "")
        app.config.setdefault('MONGODB_AUTOREF', True)
        app.config.setdefault('AUTOINCREMENT', True)
        # initialize connection and Model properties
        self.app = app
        self.connect()
        self.app.after_request(self.close_connection)

    def connect(self):
        """Connect to the MongoDB server and register the documents from
        :attr:`registered_documents`. If you set ``MONGODB_USERNAME`` and
        ``MONGODB_PASSWORD`` then you will be authenticated at the
        ``MONGODB_DATABASE``.
        """
        if not getattr(self, 'app', None):
            raise RuntimeError('The mongoobject extension was not init to '
                               'the current application.  Please make sure '
                               'to call init_app() first.')
        if not getattr(self, 'connection', None):
            self.connection = Connection(
                host=self.app.config.get('MONGODB_HOST'),
                port=self.app.config.get('MONGODB_PORT'),
                slave_okay=self.app.config.get('MONGODB_SLAVE_OKAY', False))

            # ctx.mongokit_connection.register(self.registered_documents)

        if self.app.config.get('MONGODB_USERNAME') is not None:
            auth_success = self.session.authenticate(
                self.app.config.get('MONGODB_USERNAME'),
                self.app.config.get('MONGODB_PASSWORD'))
            if not auth_success:
                raise AuthenticationIncorrect

    def register(self, *models):
        """Register one or more :class:`mongoobject.Model` instances to the
        connection.

        Can be also used as a decorator on Model:

        .. code-block:: python

            db = MongoObject(app)

            @db.register
            class Task(Model):
                structure = {
                   'title': unicode,
                   'text': unicode,
                   'creation': datetime,
                }

        :param documents: A :class:`list` of :class:`mongoobject.Model`.
        """
        [setattr(model, 'query', _QueryProperty(self)) for model in models \
        if not getattr(model, 'query', None) or not isinstance(model.query, _QueryProperty)]
        return len(models) == 1 and models[0] or models

    def make_model(self):
        model = Model
        model.query = _QueryProperty(self)
        return model

    @property
    def session(self):
        if not getattr(self, "db", None):
            self.db = self.connection[self.app.config['MONGODB_DATABASE']]
            if self.app.config['MONGODB_AUTOREF']:
                self.db.add_son_manipulator(NamespaceInjector())
                self.db.add_son_manipulator(AutoReferenceObject(self))
            if self.app.config['AUTOINCREMENT']:
                self.db.add_son_manipulator(AutoincrementId())
        return self.db

    def set_mapper(self, model):
        # Set up mapper for model, so when ew retrieve documents from database,
        # we will know how to map them to model object based on `_ns` fields
        self.mapper[model.__collection__] = model

    def autoincrement(self, cls):
        autoincrement_models.append(cls.__collection__)

    def close_connection(self, response):
        self.connection.end_request()
        return response

    def clear(self):
        self.connection.drop_database(self.app.config['MONGODB_DATABASE'])
        self.connection.end_request()
