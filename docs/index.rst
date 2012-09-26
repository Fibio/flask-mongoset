.. Flask-MongoObject documentation master file, created by
   sphinx-quickstart on Thu Jun 16 12:51:22 2011.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Flask-MongoSet
=================

.. module:: flask.ext.mongoset

Flask-MongoSet is an extension for `Flask`_ that adds support for `MongoDB`_
in your application. It's based on the excellent `pymongo`_ library and add a
few more features such as retrieving objects, auto-refenrence and dereference
objects, internationalization, quering, id_autoincrementing, inheritance.
The extensions is based on `Flas-MongoObject`_
but added/removed a few features on its own.


Quickstart: A Sample Application
--------------------------------

For most cases, all you have to do is create your Flask application, loading
your configuration and then create :class:`MongoSet` object by passing the
application to it

Once create, that object will contain all the functions and helpers you need to
access your MongoDB database. It also provides a :class:`Model` that can be
used to declare your Model object::



    from flask import Flask
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
        indexes = ['id']
        required_fields = ['title']
        i18n = ['title']

You can also register model via register method:
        from flask.ext.mongoset import Model
        class Post(Model):
            inc_id = True
            structure = t.Dict({
                'title': t.String,
                'content': t.String})
            indexes = ['id', 'title']
            i18n = ['title', 'content']

        mongo.register(Post)

or via decorator:

        @mongo.register
        class Product(Model):
            pass

Make sure that your MongoDB database is running. To create a new post:

>>> from yourapplication import Post
>>> first = Post.create(title="test", content="hello")
>>> second = Post.create({"title": "hello", "content": "second post"})

Then, when you want to access the saved objects:

>>> Post.query.find({"title": "test"})

find with translation language:
>>> Product.query.find({"title": "Name"}, _lang='en')

add data with new language:
>>> product = Product.query.find_one({"title": "Name"}, _lang='en')
>>> product._lang = 'fr'
>>> result.update({'title': 'Nom'})

create with language:
>>>> Product.create({'name': 'Name', 'quantity': 1, 'attrs':{'feature': 'ice', 'revision': 1}}, _lang='en)

create with default _lang (defined in app.config)
>>> Product.create({'name': 'Name', 'quantity': 1,
                                    'attrs':{'feature': 'ice', 'revision': 1}})

get_or_create:
>>> Product.query.get_or_create({'name': 'Name', 'quantity': 1,
                                    'attrs':{'feature': 'ice', 'revision': 1}}, _lang='en')

get_or_404
>>> Product.query.get_or_404("some product _id")
>>> Product.query.find_one_or_404(name='wrong_name')
>>> Product.query.find_or_404(name='wrong_name')

The :class:`Model` has a `query` attribute similar to `Flask-SQLAlchemy` that
can be used to query the collections. In fact, it's only a very thin layer to
`pymongo.Collection`, so it supports all pymongo.Collection methods, but you can
define custom query to implement some changes into returned data or add
some new methods:

        from flask.ext.mongoset import BaseQuery, Model

        class CustomQuery(BaseQuery):

        def update(self, spec, document, upsert=False, manipulate=False,
                safe=None, multi=False, _check_keys=False, **kwargs):
            #some new functionality ...

        def all(self):
            return self.find()

        @mongo.register
        class Product(Model):
            query_class = CustomQuery

Also your model can be abstract:

    class BaseModel(Model):
        __abstract__ = True
        structure = t.Dict({
            'name': t.String,
            'quantity': t.Int,
            'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
        }).allow_extra('*')
        required_fields = ['name']
        i18n = ['name', 'attrs']
        indexes = ['id']

    class i18nModel(BaseModel):
        __collection__ = "i18ntests"
        inc_id = True
        structure = t.Dict({
            'list_attrs': t.List(t.String)
        }).allow_extra('*')
        i18n = ['list_attrs']
        indexes = [('quantity', -1), 'name']


>>> i18nModel.i18n
Out: ['list_attrs', 'name', 'attrs']

>>> i18nModel.indexes
Out: [('quantity', -1), ('id', 1), ('name', 1)]

>>> i18nModel.required_fields
Out: ['name']

Model structure also inherits



Configuration
-------------

A list of configuration keys of the extensions

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

=============================== =========================================
``MONGODB_HOST``                mongo host name default = "localhost"
``MONGODB_PORT``                mongo port, default = 27017
``MONGODB_DATABASE``            database that we are going to connect to
                                default = ""
``MONGODB_AUTOREF``             parametr to use Dbrefs for save nested
                                objects, if it is False nested objects
                                will be saved like dictionaries, and
                                converted in instances after query
                                else - nested objects will be saved
                                like Dbrefs, default =  False
``AUTOINCREMENT``               parametr to use autoincrement ids in
                                models, default =  True, for usage your model
                                should have :param inc_id:
``FALLBACK_LANG``               fallback language, default = 'en'
=============================== =========================================


.. _Flask: http://flask.pocoo.org
.. _MongoDB: http://mongodb.org
.. _pymongo: http://apy.mongodb.org/python/current
.. _minimongo: http://github.com/slacy/minimongo
.. _Flas-MongoObject: https://github.com/dqminh/flask-mongoobject
.. _example:
    https://github.com/dqminh/flask-mongoobject/blob/master/examples_hello.py
