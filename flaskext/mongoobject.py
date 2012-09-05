# -*- coding: utf-8 -*-
"""
flaskext.mongoobject
~~~~~~~~~~~~~~~~~~~~

Add basic MongoDB support to your Flask application.

Inspiration:
https://github.com/slacy/minimongo/
https://github.com/mitsuhiko/flask-sqlalchemy
https://github.com/namlook/mongokit

:copyright: (c) 2011 by Daniel, Dao Quang Minh (dqminh).
:license: MIT, see LICENSE for more details.
"""
from __future__ import absolute_import
import operator
from bson.dbref import DBRef
from pymongo import Connection
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.son_manipulator import SONManipulator, AutoReference, NamespaceInjector

from flask import abort


inc_collections = set([])


class AuthenticationIncorrect(Exception):
    pass


class ClassProperty(property):
    def __init__(self, method, *args, **kwargs):
        method = classmethod(method)
        return super(ClassProperty, self).__init__(method, *args, **kwargs)

    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


classproperty = ClassProperty


def autoincrement(cls):
    inc_collections.add(cls.__collection__)
    return cls


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


class AutoincrementId(SONManipulator):
    """ Creates objects id as integer and autoincrement it,
        if "id" not in son object.
        But not usefull with DBRefs if DBRefs are based on "id" not "id_"
    """
    def transform_incoming(self, son, collection):
        if collection.name in inc_collections:
            son["id"] = son.get('id', self._get_next_id(collection))
        return son

    def _get_next_id(self, collection):
        database = collection.database
        result = database._autoincrement_ids.find_and_modify(
            query={"id": collection.name,},
            update={"$inc": {"next": 1},},
            upsert=True,
            new=True)
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
        self.__database = mongo.session

    def transform_outgoing(self, son, collection):
        def transform_value(value):
            if isinstance(value, DBRef):
                return transform_value(self.__database.dereference(value))
            elif isinstance(value, list):
                return map(transform_value, value)
            elif isinstance(value, dict):
                if value.get('_ns', None):
                    # if the collection has a :class:`Model` mapper
                    cls = self.mongo.mapper.get(value['_ns'], None)
                    if cls:
                        return cls(transform_dict(value))
                return transform_dict(value)
            return value

        def transform_dict(object):
            for (key, value) in object.items():
                object[key] = transform_value(value)
            return object

        value = transform_dict(son)
        return value


class BaseQuery(Collection):
    """
    `BaseQuery` extends :class:`pymongo.Collection` that replaces all results
    coming from database with instance of :class:`Model`
    """

    def __init__(self, *args, **kwargs):
        self.document_class = kwargs.pop('document_class')
        super(BaseQuery, self).__init__(*args, **kwargs)

    def find(self, *args, **kwargs):
        kwargs['as_class'] = self.document_class
        return super(BaseQuery, self).find(*args, **kwargs)

    def get_or_404(self, id):
        return self.find_one(id) or abort(404)

    def find_one_or_404(self, *args, **kwargs):
        return self.find_one(*args, **kwargs) or abort(404)

    def find_or_404(self, *args, **kwargs):
        cursor = self.find(*args, **kwargs)
        return not cursor.count() == 0 and cursor or abort(404)


class Model(AttrDict):
    """
    Base class for custom user models. Provide convenience ActiveRecord
    methods such as :attr:`save`, :attr:`remove`
    """

    query_class = BaseQuery

    __collection__ = None

    @classproperty
    def query(cls):
        return cls.query_class(database=cls.db, name=cls.__collection__,
                               document_class=cls)

    # @property
    # def id(self):
    #     if not getattr(self, "id", None):
    #         return str(self._id)

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

    @classmethod
    def create(cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        return instance.save()

    @classmethod
    def get_or_create(cls, *args, **kwargs):
        instance = cls.query.find_one(*args, **kwargs)
        return instance or instance.create(*args, **kwargs)


    def __repr__(self):
        return "<%s:%s>" % (self.__class__.__name__,
                            getattr(self, 'id', self._id))

    def __unicode__(self):
        return str(self).decode('utf-8')


class MongoObject(object):

    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)
        self.Model = Model
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
        self.Model.db = self.session

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
        [setattr(model, 'db', self.session) for model in models \
        if not getattr(model, 'db', None) or not isinstance(model.db, Database)]
        return len(models) == 1 and models[0] or models

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

    def close_connection(self, response):
        self.connection.end_request()
        return response

    def clear(self):
        self.connection.drop_database(self.app.config['MONGODB_DATABASE'])
        self.connection.end_request()
