Flask-MongoSet
===============================

.. module:: flask.ext.mongoset

Flask-MongoSet is an extension for `Flask`_ that adds support for `MongoDB`_
in your application. It's based on the excellent `pymongo`_ library and add a
few more features such as retrieving objects, auto-refenrence and dereference
objects, internationalization, quering, id_autoincrementing, inheritance.
The extensions is based on `Flask_MongoObject`_
but added/removed a few features on its own.

Installing Flask-MongoSet
-------------------------------

Install with **pip** and **easy_install**::

    pip install Flask-MongoSet

If you are using **virtualenv**, it is assumed that you are installing **Flask-MongoSet**
in the same virtualenv as your Flask application(s).

Quickstart: A Sample Application
--------------------------------

For most cases, all you have to do is create your Flask application, loading
your configuration and then create :class:`MongoSet` object by passing the
application to it.
It also provides a :class:`Model` that can be used to declare your Model object::

        from flask import Flask
        import trafaret as t
        from flask.ext.mongoset import MongoSet

        app = Flask(__name__)
        app.config['MONGODB_HOST'] = "mongodb://localhost:27017"
        app.config['DEBUG'] = True
        app.config['MONGODB_DATABASE'] = "hello"

        mongo = MongoSet(app)

        class Product(mongo.Model):
            structure = t.Dict({
            'title': t.String,
            'quantity': t.Int,
            'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
        }).allow_extra('*')
        indexes = ['_id']
        required_fields = ['title']
        i18n = ['title']

You can also register your models via register method::

        from flask.ext.mongoset import Model


        class Post(Model):
            inc_id = True
            structure = t.Dict({
                'title': t.String,
                'content': t.String})
            indexes = ['id', '_int_id', 'title']
            i18n = ['title', 'content']

        mongo.register(Post)

or via decorator::

        @mongo.register
        class Product(Model):
            pass

Make sure that your MongoDB database is running. To create a new post:

>>> from yourapplication import Post
>>> post = Post.create(title="test", content="hello")
>>> product = Product.create({'name': 'Name', 'quantity': 1, 'attrs':{'feature': 'ice', 'revision': 1}})

Then, when you want to access the saved objects use can use find or find_one methods.
All of them can work with mongo modifiers:

>>> Post.query.find({"title": "test"})

>>> Product.query.find({'quantity': {'$gte': 2}})

>>> Product.query.find({'attrs.feature': 'ice', 'attrs.revision': {'$in': [1, 2]}})

find with translation language:

>>> Product.query.find({"title": "Name"}, _lang='en')

add data with new language:

>>> product = Product.query.find_one({"title": "Name"}, _lang='en')
>>> product._lang = 'fr'
>>> result.update({'$set': {'title': 'Nom'}})

create with language:

>>> Product.create({'name': 'Name', 'quantity': 1, 'attrs':{'feature': 'ice', 'revision': 1}}, _lang='en)

create with default _lang (defined in app.config.MONGODB_FALLBACK_LANG)

>>> Product.create({'name': 'Name', 'quantity': 1, 'attrs':{'feature': 'ice', 'revision': 1}})

get_or_create:

>>> Product.query.get_or_create({'name': 'Name', 'quantity': 1, 'attrs':{'feature': 'ice', 'revision': 1}}, _lang='en')

get_or_404:

>>> Product.query.get_or_404("some product _id")
>>> Product.query.find_one_or_404(name='wrong_name')
>>> Product.query.find_or_404(name='wrong_name')


The :class:`Model` has a `query` attribute similar to  :mod:`Flask-SQLAlchemy` that
can be used to query the collections.

In fact, it's only a very thin layer to :class:`pymongo.Collection`, so it supports
all :class:`Collection` methods, for example 'update' method you have to use with mongodb modifiers,
if you want to get updated instance, you have to use update_with_reload method:

>>> product = Product.create({'name': 'Name', 'attrs':['revision', 'class']})
>>> assert product.name == 'Name'
>>> product = product.update_with_reload({'$set':{'name': 'Fridge'}})
>>> assert product.name == 'Fridge'

>>> product = product.update_with_reload({'$push':{'attrs': 'volume'}})
>>> assert product.attrs = ['revision', 'class', 'volume']

Be carefull with simple update without modifiers:

>>> print product
Out: <Product:{'_id': ObjectId('506ee185312f9113c0000005'), 'name': 'Fridge', 'attrs': ['revision', 'class', 'volume']}>
>>> product = product.update_with_reload({'name': 'Freezer'})
>>> print product
Out: <Product:{'_id': ObjectId('506ee185312f9113c0000005'), 'name': 'Freezer'}>

But you can use update with kwargs:

>>> print product
Out: <Product:{'_id': ObjectId('506ee185312f9113c0000005'), 'name': 'Fridge', 'attrs': ['revision', 'class', 'volume']}>
>>> product = product.update_with_reload(**{'name': 'Freezer'})
>>> print product
Out: <Product:{'_id': ObjectId('506ee185312f9113c0000005'), 'name': 'Freezer', 'attrs': ['revision', 'class', 'volume']}>
>>> product = product.update_with_reload(name='NewFreezer')
>>> print product
Out: <Product:{'_id': ObjectId('506ee185312f9113c0000005'), 'name': 'NewFreezer', 'attrs': ['revision', 'class', 'volume']}>

'update' method is the same, but doesn't reload instance and returns 'None'

>>> product.update(name='NewFridge')
>>> print product
Out: <Product:{'_id': ObjectId('506ee185312f9113c0000005'), 'name': 'NewFreezer', 'attrs': ['revision', 'class', 'volume']}>
>>> product.update(name='NewFridge')
>>> print product
Out: None


You can define custom query to implement some changes into returned data
or add some new methods::

        from flask.ext.mongoset import BaseQuery, Model


        class CustomQuery(BaseQuery):
            def all(self):
                return self.find()


        @mongo.register
        class Product(Model):
            query_class = CustomQuery

Also your model can be abstract::

        class BaseProduct(Model):
            __abstract__ = True
            structure = t.Dict({
                'name': t.String,
                'quantity': t.Int,
                'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
            }).allow_extra('*')
            required_fields = ['name']
            i18n = ['name', 'attrs']
            indexes = ['_id']


        class Product(BaseModel):
            __collection__ = "products"
            inc_id = True
            structure = t.Dict({
                'list_attrs': t.List(t.String)
            }).allow_extra('*')
            i18n = ['list_attrs']
            indexes = [('quantity', -1), 'name']


>>> Product.i18n
Out: ['list_attrs', 'name', 'attrs']

>>> Product.indexes
Out: [('quantity', -1), ('_id', 1), ('name', 1)]

>>> Product.required_fields
Out: ['name']

The attribute :class:`Model.structure` defines structure of mongo collection.
It must be instance of :class:`trafaret.Dict` and
validates via `trafaret`_ before insert.
If this attribute isn't defined your model will be recive any kind of collection structure

:class:`Model.structure` also inherits and the :class:`Dict` methods:
:meth:`Dict.allow_extra` and :meth:`Dict.ignore_extra` too

This is an `example`_


Configuration
-------------

A list of configuration keys of the extensions

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

=============================== =========================================
``MONGODB_HOST``                mongo host name default - "localhost"
``MONGODB_PORT``                mongo port, default - 27017
``MONGODB_DATABASE``            database that we are going to connect to
                                default - ""
``MONGODB_AUTOREF``             parametr to use Dbrefs for save nested
                                objects, if it is False nested objects
                                will be saved like dictionaries, and
                                converted in instances after query
                                else - nested objects will be saved
                                like Dbrefs, default -  False
``MONGODB_AUTOINCREMENT``       parametr to use autoincrement ids in
                                models, default -  False, for usage you
                                should set the model attribute inc_id to True.
                                It adds _int_id attribute into the model
``MONGODB_FALLBACK_LANG``       fallback language, default - 'en'
=============================== =========================================


.. _Flask: http://flask.pocoo.org
.. _MongoDB: http://mongodb.org
.. _pymongo: http://apy.mongodb.org/python/current
.. _minimongo: http://github.com/slacy/minimongo
.. _Flask_MongoObject: https://github.com/dqminh/flask-mongoobject
.. _trafaret: https://github.com/nimnull/trafaret.git
.. _example:
    https://github.com/dqminh/flask-mongoobject/blob/master/examples_hello.py
