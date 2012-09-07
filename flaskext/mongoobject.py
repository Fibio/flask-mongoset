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
import trafaret as t
from bson.dbref import DBRef
from pymongo import Connection, ASCENDING
from pymongo.cursor import Cursor
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.son_manipulator import SONManipulator, AutoReference, NamespaceInjector

from flask import abort


inc_collections = set([])

autoref_collections = {}


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
        initial and kwargs.update(initial)
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
        if collection.name in autoref_collections:
            def transform_value(value):

                if isinstance(value, DBRef):
                    return transform_value(self.__database.dereference(value))
                elif isinstance(value, list):
                    return map(transform_value, value)
                elif isinstance(value, dict):
                    if value.get('_ns', None):
                        cls = autoref_collections.get(value['_ns'], None)
                        if cls:
                            return cls(transform_dict(value))
                    return transform_dict(value)
                return value

            def transform_dict(object):
                for (key, value) in object.items():
                    object[key] = transform_value(value)
                return object

            son = transform_dict(son)
        return son


class MongoCursor(Cursor):
    """
    A cursor that will return an instance of :attr:`as_class` with
    provided lang
    """
    def __init__(self, *args, **kwargs):
        self.as_class = kwargs.get('as_class')
        self._lang = kwargs.pop('_lang')
        super(MongoCursor, self).__init__(*args, **kwargs)

    def next(self):
        data = super(MongoCursor, self).next()
        data._lang = self._lang
        return data

    def __getitem__(self, index):
        item = super(MongoCursor, self).__getitem__(index)
        if isinstance(index, slice):
            return item
        else:
            item._lang = self._lang
            return item


class BaseQuery(Collection):
    """
    `BaseQuery` extends :class:`pymongo.Collection` that adds :as_class: parameter
    into parameters of pymongo find method
    """

    def __init__(self, *args, **kwargs):
        self.document_class = kwargs.pop('document_class')
        self.i18n = getattr(self.document_class, 'i18n', None)
        super(BaseQuery, self).__init__(*args, **kwargs)

    def find(self, *args, **kwargs):
        kwargs['as_class'] = self.document_class
        if self.i18n:
            lang = kwargs.get('_lang', self.document_class._fallback_lang)
            for attr in self.i18n:
                value = kwargs.pop(attr, None)
                if value:
                    kwargs['{}.{}'.format(attr, lang)] = value
            kwargs['_lang'] = lang
            return MongoCursor(self, *args, **kwargs)
        return super(BaseQuery, self).find(*args, **kwargs)

    def get_or_404(self, id):
        return self.find_one(id) or abort(404)

    def find_one_or_404(self, *args, **kwargs):
        return self.find_one(*args, **kwargs) or abort(404)

    def find_or_404(self, *args, **kwargs):
        cursor = self.find(*args, **kwargs)
        return not cursor.count() == 0 and cursor or abort(404)


class ModelType(type):
    """ Ghanges validation rules for transleted attrs
    """
    def __new__(cls, name, bases, dct):
        #  change structure:
        structure = dct.get('structure')
        if structure and dct.get('i18n'):
            for key in structure.keys[:]:
                if key.name in dct['i18n']:
                    dct['structure'].keys.remove(key)
                    dct['structure'].keys.append(t.Key(key.name,
                                              trafaret=t.Mapping(t.String, key.trafaret)))

        # inheritance:
        for model in bases:
            if getattr(model, '__abstract__', None) is True:
                dct.update({'__abstract__': False})
                base_attrs = ['i18n', 'indexes']
                for attr in base_attrs:
                    total = list(set(getattr(model, attr, []))|set(dct.get(attr, [])))
                    total and dct.update({attr: total})
                if model.structure and structure is not None:
                    new_structure = list(set(model.structure.keys)|set(structure.keys))
                    dct['structure'].keys = new_structure
                break
        return type.__new__(cls, name, bases, dct)

    def __init__(cls, name, bases, dct):
        # set protected_field_names:
        protected_field_names = set(['_protected_field_names'])
        names = [model.__dict__.keys() for model in cls.__mro__]
        cls._protected_field_names = list(protected_field_names.union(*names))

        if not getattr(cls, '__abstract__', False):
            # add model into DBrefs register:
            cls.use_autorefs and autoref_collections.__setitem__(cls.__collection__, cls)

            # add model into autoincrement_id register:
            cls.inc_id and inc_collections.add(cls.__collection__)

            # add indexes:
            if cls.indexes:
                for index in cls.indexes[:]:
                    if isinstance(index, str):
                        cls.indexes.remove(index)
                        cls.indexes.append((index, ASCENDING))

                cls.db and cls.query.ensure_index(cls.indexes)


class Model(AttrDict):
    """
    Base class for custom user models. Provide convenience ActiveRecord
    methods such as :attr:`save`, :attr:`remove`
    """
    __metaclass__ = ModelType

    __collection__ = None

    __abstract__ = False

    _protected_field_names = None

    _lang = None

    _fallback_lang = None

    i18n = []

    db = None

    indexes = None

    query_class = BaseQuery

    structure = t.Dict().allow_extra('*')

    use_autorefs = True

    inc_id = False

    def __init__(self, doc=None, **kwargs):
        doc and kwargs.update(doc)
        self._lang = kwargs.pop('_lang', self._fallback_lang)
        for field in self._protected_field_names:
            if field in kwargs:
                raise AttributeError("Forbidden attribute name %s for model %s" % (field, self.__class__.__name__ ))
        return super(Model, self).__init__(**kwargs)

    def __setattr__(self, attr, value):
        if attr in self._protected_field_names:
            return dict.__setattr__(self, attr, value)
        if attr in self.i18n:
            if attr not in self:
                value = {self._lang: value}
            else:
                attrs = self[attr].copy()
                attrs.update({self._lang: value})
                value = attrs
        return super(Model, self).__setattr__(attr, value)

    def __getattr__(self, attr):
        value = super(Model, self).__getattr__(attr)
        if attr in self.i18n:
            value = value.get(self._lang, value.get(self._fallback_lang, value))
        return value

    @classproperty
    def query(cls):
        return cls.query_class(database=cls.db, name=cls.__collection__,
                               document_class=cls)

    def save(self, *args, **kwargs):
        self.structure.check(self)
        self.query.save(self, *args, **kwargs)
        return self

    def update(self, spec=None, **kwargs):
        update_options = set(['upsert', 'manipulate', 'safe', 'multi', '_check_keys'])
        spec = spec or {}
        new_attrs = list(kwargs.viewkeys() - update_options)
        for k in new_attrs:
            spec[k] = kwargs.pop(k)
        self._setattrs(**spec)
        self.structure.check(self)
        return self.query.update({"_id": self._id}, self, **kwargs)

    def delete(self):
        return self.query.remove(self._id)

    @classmethod
    def create(cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        return instance.save()

    @classmethod
    def get_or_create(cls, *args, **kwargs):
        instance = cls.query.find_one(*args, **kwargs)
        return instance or kwargs.pop('_lang', True) and cls.create(*args, **kwargs)

    def __repr__(self):
        return "<%s:%s>" % (self.__class__.__name__,
                            super(Model, self).__repr__())
                            # getattr(self, 'id', self._id))

    def __unicode__(self):
        return str(self).decode('utf-8')


class MongoObject(object):

    def __init__(self, app=None):
        self.Model = Model
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.config.setdefault('MONGODB_HOST', "localhost")
        app.config.setdefault('MONGODB_PORT', 27017)
        app.config.setdefault('MONGODB_DATABASE', "")
        app.config.setdefault('MONGODB_AUTOREF', True)
        app.config.setdefault('AUTOINCREMENT', True)
        app.config.setdefault('FALLBACK_LANG', 'en')
        self.app = app
        self.connect()
        self.app.after_request(self.close_connection)
        self.Model.db = self.session
        self.Model._fallback_lang = app.config.get('FALLBACK_LANG')

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
                raise AuthenticationIncorrect("can't connect to data base, wrong user_name or password")

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

        for model in models:
            if not getattr(model, 'db', None) or not isinstance(model.db, Database):
                setattr(model, 'db', self.session)
            setattr(model, '_fallback_lang', self.app.config.get('FALLBACK_LANG'))
            model.indexes and model.query.ensure_index(model.indexes)
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

    def close_connection(self, response):
        self.connection.end_request()
        return response

    def clear(self):
        self.connection.drop_database(self.app.config['MONGODB_DATABASE'])
        self.connection.end_request()
