# -*- coding: utf-8 -*-
"""
flask.ext.mongoset
~~~~~~~~~~~~~~~~~~~~

Add basic MongoDB support to your Flask application.

Inspiration:
https://github.com/slacy/minimongo/
https://github.com/mitsuhiko/flask-sqlalchemy
https://github.com/namlook/mongokit
https://github.com/dqminh/flask-mongoobject

:copyright: (c) 2012 by Fibio, nimnull.
:license: MIT, see LICENSE for more details.
"""

from __future__ import absolute_import
import copy
import operator
import trafaret as t

from bson import DBRef

from flask import abort
from flask.signals import _signals

from pymongo import Connection, ASCENDING
from pymongo.cursor import Cursor
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.son_manipulator import (SONManipulator, AutoReference,
                                     NamespaceInjector)


# list of collections for models witch need autoincrement id
inc_collections = set([])

# list of collections for models witch need auto dbref
autoref_collections = {}

after_insert = 'after_insert'
after_update = 'after_update'
after_delete = 'after_delete'

signal_map = {after_insert: _signals.signal('mongo_after_insert'),
              after_update: _signals.signal('mongo_after_update'),
              after_delete: _signals.signal('mongo_after_delete')}


class AuthenticationError(Exception):
    pass


class InitDataError(Exception):
    pass


class ClassProperty(property):
    """ Implements :@classproperty: decorator, like @property but
        for the class not for the instance of class
    """
    def __init__(self, method, *args, **kwargs):
        method = classmethod(method)
        super(ClassProperty, self).__init__(method, *args, **kwargs)

    def __get__(self, cls, owner):
        return self.fget.__get__(None, owner)()


classproperty = ClassProperty


class AttrDict(dict):
    """
    Base object that represents a MongoDB document. The object will behave both
    like a dict `x['y']` and like an object `x.y`

    :param initial: you can define new instance via dictionary:
                    AttrDict({'a': 'one', 'b': 'two'}) or pass data
                    in kwargs AttrDict(a='one', b='two')
    """
    def __init__(self, initial=None, **kwargs):
        initial and kwargs.update(**initial)
        self._setattrs(**kwargs)

    def __getattr__(self, attr):
        return self._change_method('__getitem__', attr)

    def __setattr__(self, attr, value):
        value = self._make_attr_dict(value)
        return self.__setitem__(attr, value)

    def __delattr__(self, attr):
        return self._change_method('__delitem__', attr)

    def _make_attr_dict(self, value):
        """ Supporting method for self.__setitem__
        """
        if isinstance(value, list):
            value = map(self._make_attr_dict, value)
        elif isinstance(value, dict) and not isinstance(value, AttrDict):
            value = AttrDict(value)
        return value

    def _change_method(self, method, *args, **kwargs):
        """ Changes base dict methods to implemet dot notation
            and sets AttributeError instead KeyError
        """
        try:
            callmethod = operator.methodcaller(method, *args, **kwargs)
            return callmethod(super(AttrDict, self))
        except KeyError as ex:
            raise AttributeError(ex)

    def _setattrs(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)


class AutoincrementId(SONManipulator):
    """ Creates objects id as integer and autoincrement it,
        if "id" not in son object.
        But not usefull with DBRefs, DBRefs could't be based on this "id"
    """
    def transform_incoming(self, son, collection):
        if collection.name in inc_collections:
            son["_int_id"] = son.get('_int_id',
                                        self._get_next_id(collection))
        return son

    def _get_next_id(self, collection):
        database = collection.database
        result = database._autoincrement_ids.find_and_modify(
            query={"id": collection.name},
            update={"$inc": {"next": 1}},
            upsert=True,
            new=True)
        return result["next"]


class AutoReferenceObject(AutoReference):
    """
    Transparently reference and de-reference already saved embedded objects.

    This manipulator should probably only be used when the NamespaceInjector is
    also being used, otherwise it doesn't make too much sense - documents can
    only be auto-referenced if they have an `_ns` field.

    NOTE: this will behave poorly if you have a circular reference.

    TODO: this only works for documents that are in the same database. To fix
    this we'll need to add a DatabaseInjector that adds `_db` and then make
    use of the optional `database` support for DBRefs.
    """

    def __init__(self, mongoset):
        self.__database = mongoset.session

    def transform_outgoing(self, son, collection):
        if collection.name in autoref_collections:
            def transform_value(value):
                if isinstance(value, DBRef):
                    return transform_value(self.__database.dereference(value))
                elif isinstance(value, list):
                    return map(transform_value, value)
                elif isinstance(value, dict):
                    if value.get('_ns'):
                        cls = autoref_collections.get(value['_ns'])
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


class SavedObject(SONManipulator):
    """
    Takes document from db as class instance.

    This manipulator should probably only be used when the NamespaceInjector is
    also being used, otherwise it doesn't make too much sense - nested
    documents can only be taken from db as instace if they have an `_ns` field.
    """

    def transform_outgoing(self, son, collection):
        if collection.name in autoref_collections:
            def transform_value(value):
                if isinstance(value, list):
                    return map(transform_value, value)
                elif isinstance(value, dict):
                    if value.get('_ns'):
                        cls = autoref_collections.get(value['_ns'])
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
    A cursor that will return an instance of :param as_class: with
    provided :param _lang: instead of dict
    """
    def __init__(self, *args, **kwargs):
        self._lang = kwargs.pop('_lang')
        self.as_class = kwargs.pop('as_class')
        super(MongoCursor, self).__init__(*args, **kwargs)

    def next(self):
        data = super(MongoCursor, self).next()
        return self.as_class(data, _lang=self._lang, from_db=True)

    def __getitem__(self, index):
        item = super(MongoCursor, self).__getitem__(index)
        if isinstance(index, slice):
            return item
        else:
            return self.as_class(item, _lang=self._lang, from_db=True)


class BaseQuery(Collection):
    """
    `BaseQuery` extends :class:`pymongo.Collection` that adds :_lang: parameter
    to response instance via MongoCursor.
    If attr i18n not in model, so model doesn't need translation,
    pymongo.Collection will use

    :param document_class: to return data from db as instance of this class

    :param i18n: to change translatable attributes in the search query
    """

    def __init__(self, *args, **kwargs):
        self.document_class = kwargs.pop('document_class')
        self.i18n = getattr(self.document_class, 'i18n', None)
        super(BaseQuery, self).__init__(*args, **kwargs)

    def find(self, *args, **kwargs):
        spec = args and args[0]
        kwargs['as_class'] = self.document_class
        kwargs['_lang'] = lang = kwargs.pop('_lang',
                                            self.document_class._fallback_lang)

        # defines the fields that should be translated
        if self.i18n and spec:
            if not isinstance(spec, dict):
                raise TypeError("The first argument must be an instance of "
                                "dict")

            spec = self._insert_lang(spec, lang)

        return MongoCursor(self, *args, **kwargs)

    def insert(self, doc_or_docs, manipulate=True,
               safe=None, check_keys=True, continue_on_error=False, **kwargs):
        """ Overrided method for sending :after_insert: signal
        """
        _id = super(BaseQuery, self).insert(doc_or_docs, manipulate, safe,
                                            check_keys, continue_on_error,
                                            **kwargs)
        signal_map[after_insert].send(self.document_class.__name__, _id=_id,
                                      collection=self, signal=after_insert)
        return _id

    def update(self, spec, document, **kwargs):
        if self.i18n:
            lang = kwargs.pop('_lang')
            for attr, value in document.items():
                if attr.startswith('$'):
                    document[attr] = self._insert_lang(value, lang)
                else:
                    document[attr] = {lang: value}

        _id = spec.get('_id')
        result = super(BaseQuery, self).update(spec, document, **kwargs)
        signal_map[after_update].send(self.document_class.__name__, _id=_id,
                                      collection=self, signal=after_update)
        return result

    def remove(self, spec_or_id=None, safe=None, **kwargs):
        signal_map[after_delete].send(self.document_class.__name__,
                                      _id=spec_or_id, collection=self,
                                      signal=after_delete)
        return super(BaseQuery, self).remove(spec_or_id, safe, **kwargs)

    def get(self, id):
        return self.find_one({'_id': id}) or self.find_one({'_int_id': id})

    def get_or_404(self, id):
        return self.get(id) or abort(404)

    def find_one_or_404(self, *args, **kwargs):
        return self.find_one(*args, **kwargs) or abort(404)

    def find_or_404(self, *args, **kwargs):
        cursor = self.find(*args, **kwargs)
        return not cursor.count() == 0 and cursor or abort(404)

    def _insert_lang(self, document, lang):
        for attr in document.copy():
            if attr.startswith('$') and attr != '$where':
                document[attr] = map(lambda a: self._insert_lang(a, lang),
                                     document[attr])
            else:
                attrs = attr.split('.')
                if attrs[0] in self.i18n and '$' not in attr:
                    attrs.insert(1, lang)
                    document['.'.join(attrs)] = document.pop(attr)
        return document

    def delete(self):
        return self.drop()

    def all(self):
        return self.find()


class ModelType(type):
    """ Changes validation rules for transleted attrs.
        Implements inheritance for attrs :i18n:, :indexes:
        and :structure: from __abstract__ model
        Adds :_protected_field_names: into class and :indexes: into Mondodb
    """
    def __new__(cls, name, bases, dct):
        structure = dct.get('structure')

        # inheritance from abstract models:
        for model in bases:

            if getattr(model, '__abstract__', None) is True:
                if '__abstract__' not in dct:
                    dct['__abstract__'] = False
                key_attrs = ['i18n', 'indexes', 'required_fields']

                for attr in key_attrs:
                    base_attrs = set(getattr(model, attr, []))
                    child_attrs = set(dct.get(attr, []))
                    dct.update({attr: list(base_attrs | child_attrs)})

                if model.structure and structure is not None:
                    base_structure = set(model.structure.keys)
                    child_structure = set(structure.keys)
                    structure.keys = list(base_structure | child_structure)

                    structure.allow_any = structure.allow_any \
                                                 or model.structure.allow_any
                    structure.ignore_any = structure.ignore_any \
                                                 or model.structure.ignore_any
                    if not structure.allow_any:
                        structure.extras = list(set(model.structure.extras) |
                                                set(structure.extras))

                    if not structure.ignore_any:
                        structure.ignore = list(set(model.structure.ignore) |
                                                set(structure.ignore))
                elif model.structure:
                    dct['structure'] = model.structure

                break

        #  change structure for translated fields:
        if not dct.get('__abstract__') and structure and dct.get('i18n'):
            for key in structure.keys[:]:
                if key.name in dct['i18n']:
                    dct['structure'].keys.remove(key)
                    dct['structure'].keys.append(t.Key(key.name,
                                    trafaret=t.Mapping(t.String, key.trafaret),
                                    default=key.default, optional=key.optional,
                                    to_name=key.to_name))
        # add required_fields:
        if 'required_fields' in dct:
            required_fields = dct.get('required_fields')
            if dct.get('structure') is not None:
                optional = filter(lambda key: key.name not in dct['required_fields'],
                                  dct['structure'].keys)
                optional = map(operator.attrgetter('name'), optional)
                dct['structure'] = dct['structure'].make_optional(*optional)
            else:
                struct = dict.fromkeys(required_fields, t.Any)
                dct['structure'] = t.Dict(struct).allow_extra('*')

        return type.__new__(cls, name, bases, dct)

    def __init__(cls, name, bases, dct):
        # set protected_field_names:
        protected_field_names = set(['_protected_field_names'])
        names = [model.__dict__.keys() for model in cls.__mro__]
        cls._protected_field_names = list(protected_field_names.union(*names))

        if not cls.__abstract__:
            # add model into DBrefs register:
            if cls.use_autorefs:
                autoref_collections.__setitem__(cls.__collection__, cls)

            # add model into autoincrement_id register:
            if cls.inc_id:
                inc_collections.add(cls.__collection__)

            # add indexes:
            if cls.indexes:
                for index in cls.indexes[:]:
                    if isinstance(index, str):
                        cls.indexes.remove(index)
                        cls.indexes.append((index, ASCENDING))

                if cls.db:
                    cls.query.ensure_index(cls.indexes)


class Model(AttrDict):
    """ Base class for custom user models. Provide convenience ActiveRecord
        methods such as :attr:`save`, :attr:`create`, :attr:`update`,
        :attr:`delete`.

        :param __collection__: name of mongo collection

        :param __abstract__: if True - there is an abstract Model,
                    so :param i18n:, :param structure: and
                    :param indexes: shall be added for submodels

        :param _protected_field_names: fields names that can be added like
                    dict items, generate automatically by ModelType metaclass

        :param _lang: optional, language for model, by default it is
                    the same as :param _fallback_lang:

        :param _fallback_lang: fallback model language, by default it is
                    app.config.MONGODB_FALLBACK_LANG

        :param i18n: optional, list of fields that need to translate

        :param db: Mondodb, it is defining by MongoSet

        :param indexes: optional, list of fields that need to index

        :param query_class: class makes query to MongoDB,
                    by default it is :BaseQuery:

        :param structure: optional, a structure of mongo document, will be
                    validate by trafaret https://github.com/nimnull/trafaret

        :param required_fields: optional, list of required fields

        :param use_autorefs: optional, if it is True - AutoReferenceObject
                    will be use for query, by default is True

        :param inc_id: optional, if it if True - AutoincrementId
                    will be use for query, by default is False

        :param from_db: attr to get object from db as instance,
                    sets automatically
    """
    __metaclass__ = ModelType

    __collection__ = None

    __abstract__ = False

    _protected_field_names = None

    _lang = None

    _fallback_lang = None

    i18n = []

    db = None

    indexes = []

    query_class = BaseQuery

    structure = None

    required_fields = []

    use_autorefs = True

    inc_id = False

    from_db = False

    def __init__(self, initial=None, **kwargs):
        self.from_db = kwargs.pop('from_db', False)
        self._lang = kwargs.pop('_lang', self._fallback_lang)
        dct = kwargs.copy()

        if initial and isinstance(initial, dict):
            dct.update(**initial)

        for field in self._protected_field_names:
            if field in dct and not isinstance(getattr(self.__class__,
                                                       field, None), property):
                raise AttributeError("Forbidden attribute name {} for"
                            " model {}".format(field, self.__class__.__name__))
        super(Model, self).__init__(initial, **kwargs)

    def __setattr__(self, attr, value):
        if attr in self._protected_field_names:
            return dict.__setattr__(self, attr, value)

        if attr in self.i18n and not self.from_db:
            if attr not in self:
                if not isinstance(value, dict) or self._lang not in value:
                    value = {self._lang: value}
            else:
                attrs = self[attr].copy()
                attrs.update({self._lang: value})
                value = attrs
        return super(Model, self).__setattr__(attr, value)

    def __getattr__(self, attr):
        value = super(Model, self).__getattr__(attr)
        if attr in self.i18n:
            value = value.get(self._lang,
                              value.get(self._fallback_lang, value))
        return value

    @classproperty
    def query(cls):
        return cls.query_class(database=cls.db, name=cls.__collection__,
                               document_class=cls)

    def save(self, *args, **kwargs):
        data = self.structure and self.structure.check(self) or self
        return self.query.save(data, *args, **kwargs)

    def save_with_reload(self, *args, **kwargs):
        """ returns self with autorefs after save
        """
        _id = self.save(*args, **kwargs)
        return self.query.find_one({'_id': _id}, _lang=self._lang)

    def update(self, data=None, **kwargs):
        if data is None:
            data = {}
            update_options = set(['upsert', 'manipulate', 'safe', 'multi',
                                  '_check_keys'])
            new_attrs = list(kwargs.viewkeys() - update_options)
            data = {'$set': dict((k, kwargs.pop(k)) for k in new_attrs)}

        if self.i18n:
            kwargs['_lang'] = self._lang

        return self.query.update({"_id": self._id}, data, **kwargs)

    def update_with_reload(self, data=None, **kwargs):
        """ returns self with autorefs after update
        """
        self.update(data, **kwargs)
        result = self.query.find_one({'_id': self._id})
        if self.i18n:
            result._lang = self._lang
        return result

    def delete(self):
        return self.query.remove(self._id)

    @classmethod
    def create(cls, *args, **kwargs):
        instance = cls(*args, **kwargs)
        return instance.save_with_reload()

    @classmethod
    def get_or_create(cls, *args, **kwargs):
        spec = copy.deepcopy(args)
        instance = cls.query.find_one(*args, **kwargs)
        if not instance:
            if not spec or not isinstance(spec[0], dict):
                raise InitDataError("first argument must be an instance of "
                                    "dict with init data")
            instance = cls.create(spec[0], **kwargs)

        return instance

    def __repr__(self):
        return "<%s:%s>" % (self.__class__.__name__,
                            super(Model, self).__repr__())

    def __unicode__(self):
        return str(self).decode('utf-8')


def get_state(app):
    """Gets the state for the application"""
    assert 'mongoset' in app.extensions, \
        'The mongoset extension was not registered to the current ' \
        'application.  Please make sure to call init_app() first.'
    return app.extensions['mongoset']


class MongoSet(object):
    """ This class is used to control the MongoSet integration
        to Flask application.
        Adds :param db: and :param _fallback_lang: into Model

    Usage:

        app = Flask(__name__)
        mongo = MongoSet(app)

    This class also provides access to mongo Model:

        class Product(mongo.Model):
            structure = t.Dict({
            'title': t.String,
            'quantity': t.Int,
            'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
        }).allow_extra('*')
        indexes = ['id']

    via register method:
        mongo = MongoSet(app)
        mongo.register(Product, OtherModel)

    or via decorator:
        from flask.ext.mongoset import Model

        @mongo.register
        class Product(Model):
            pass
    """
    def __init__(self, app=None):
        self.Model = Model

        if app is not None:
            self.init_app(app)
        else:
            self.app = None

    def init_app(self, app):
        app.config.setdefault('MONGODB_HOST', "localhost")
        app.config.setdefault('MONGODB_PORT', 27017)
        app.config.setdefault('MONGODB_USERNAME', '')
        app.config.setdefault('MONGODB_PASSWORD', '')
        app.config.setdefault('MONGODB_DATABASE', "")
        app.config.setdefault('MONGODB_AUTOREF', False)
        app.config.setdefault('MONGODB_AUTOINCREMENT', False)
        app.config.setdefault('MONGODB_FALLBACK_LANG', 'en')
        app.config.setdefault('MONGODB_SLAVE_OKAY', False)
        self.app = app
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['mongoset'] = self
        self.connect()

        @app.teardown_appcontext
        def close_connection(response):
            state = get_state(app)
            if state.connection is not None:
                state.connection.end_request()
            return response

        self.Model.db = self.session
        self.Model._fallback_lang = app.config.get('MONGODB_FALLBACK_LANG')

    def connect(self):
        """Connect to the MongoDB server and register the documents from
        :attr:`registered_documents`. If you set ``MONGODB_USERNAME`` and
        ``MONGODB_PASSWORD`` then you will be authenticated at the
        ``MONGODB_DATABASE``.
        """
        if not hasattr(self, 'app'):
            raise RuntimeError('The mongoset extension was not init to '
                               'the current application.  Please make sure '
                               'to call init_app() first.')
        if not hasattr(self, 'connection'):
            self.connection = Connection(
                host=self.app.config.get('MONGODB_HOST'),
                port=self.app.config.get('MONGODB_PORT'),
                slave_okay=self.app.config.get('MONGODB_SLAVE_OKAY', False))

        if self.app.config.get('MONGODB_USERNAME') is not '':
            auth_success = self.session.authenticate(
                self.app.config.get('MONGODB_USERNAME'),
                self.app.config.get('MONGODB_PASSWORD'))
            if not auth_success:
                raise AuthenticationError("can't connect to data base,"
                                          " wrong user_name or password")

    def register(self, *models):
        """Register one or more :class:`mongoset.Model` instances to the
        connection.
        """
        for model in models:
            if not model.db or not isinstance(model.db, Database):
                setattr(model, 'db', self.session)

            model.indexes and model.query.ensure_index(model.indexes)

            setattr(model, '_fallback_lang',
                    self.app.config['MONGODB_FALLBACK_LANG'])

        return len(models) == 1 and models[0] or models

    @property
    def session(self):
        """ Returns MongoDB
        """
        if not hasattr(self, "db"):
            self.db = self.connection[self.app.config['MONGODB_DATABASE']]
            if self.app.config['MONGODB_AUTOREF']:
                self.db.add_son_manipulator(NamespaceInjector())
                self.db.add_son_manipulator(AutoReferenceObject(self))
            else:
                self.db.add_son_manipulator(NamespaceInjector())
                self.db.add_son_manipulator(SavedObject())
            if self.app.config['MONGODB_AUTOINCREMENT']:
                self.db.add_son_manipulator(AutoincrementId())
        return self.db

    def clear(self):
        self.connection.drop_database(self.app.config['MONGODB_DATABASE'])
        self.connection.end_request()
