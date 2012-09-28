=================
Flask-MongoObject
=================

**Settings:**

:MONGODB_HOST: default = 'localhost', MongoDB host name
:MONGODB_PORT: default = 27017, MongoDB port number
:MONGODB_DATABASE: default = "", MongoDB database name
:MONGODB_USERNAME: default = None. Username to connect with
:MONGODB_PASSWORD: default = None. Password to authenticate if username is provided.
:MONGODB_AUTOREF: default =  False. When set to `True` — nested objects will be saved as DbRef, elsewhere it will be saved as dictionaries.
:MONGODB_AUTOINCREMENT: default =  True. Telling MongoObject to use autoincremented integer for `_id`.
:MONGODB_FALLBACK_LANG: default = 'en'. Fallback language used with i18n definition.

**Access MongoDB from your Flask application.**

Usage:

::

  app = Flask(__name__)
  mongo = MongoObject(app)

This class also provides access to mongo Model:

::

  class Product(mongo.Model):
      structure = t.Dict({
          'title': t.String,
          'quantity': t.Int,
         'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
      }).allow_extra('*')
      indexes = ['id']

via register method:

::

  mongo = MongoObject(app)
  mongo.register(Product, OtherModel)

or via decorator:

::

  from flask.ext.mongoobject import Model

  @mongo.register
  class Product(Model):
      pass


You can define custom query to implement some changes into returned data or add some new methods:

::

  from flask.ext.mongoobject import BaseQuery, Model

  class CustomQuery(BaseQuery):

      def update(self, spec, document, upsert=False, manipulate=False,
                 safe=None, multi=False, _check_keys=False, **kwargs):
            #some new functionality ...

        def all(self):
            return self.find()

        @mongo.register
        class Product(Model):
            query_class = CustomQuery

**Other usage:**

Simple find:

::

  Product.query.find({"title": "Name"})

Find with translation language:

::

  Product.query.find({"title": "Name"}, _lang='en')``

Add data with new language:

::

  product = Product.query.find_one({"title": "Name"}, _lang='en')
  product._lang = 'fr'
  result.update({'title': 'Nom'})

Create:

::

  Product.create({'name': 'Name', 'quantity': 1, 'attrs':{'feature': 'ice', 'revision': 1}}, _lang='en')

Create with default _lang

::

  Product.create({'name': 'Name', 'quantity': 1, 'attrs': {'feature': 'ice', 'revision': 1}})

Get or create:

::

  Product.query.get_or_create({'name': 'Name', 'quantity': 1, 'attrs':{'feature': 'ice', 'revision': 1}}, _lang='en')

And some sugar for usage with Flask:

::

  Product.query.get_or_404("some product _id")
  Product.query.find_one_or_404(name='wrong_name')
  Product.query.find_or_404(name='wrong_name')

The Model.query is derived from the pymongo.Collection so it supports all of pymongo.Collection methods.
