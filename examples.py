import flask
import trafaret as t
from flask.ext.mongoset import MongoSet, Model


app = flask.Flask(__name__)

app.config['MONGODB_HOST'] = "localhost"
app.config['MONGODB_PORT'] = 27017
app.config['MONGODB_DATABASE'] = "testdb"
app.config['MONGODB_AUTOREF'] = True
app.config['TESTING'] = True

mongo = MongoSet(app)


class BaseProduct(Model):
    __abstract__ = True
    structure = t.Dict({
        'name': t.String,
        'quantity': t.Int,
        'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
    }).allow_extra('*')
    i18n = ['name', 'attrs']
    indexes = ['id']


@mongo.register
class Product(Model):
    __collection__ = "products"
    inc_id = True
    structure = t.Dict({
        'list_attrs': t.List(t.String)
    }).allow_extra('*')
    i18n = ['list_attrs']
    indexes = [('quantity', -1), 'name']

    def as_dict(self, api_fields=None, exclude=None):
        """ Returns instance as dict in selected language
        """
        keys = api_fields or self.keys()
        if exclude:
            keys = list(set(keys) | set(exclude))
        result = dict(map(lambda key: (key, getattr(self, key)), keys))
        '_id' in result and result.__setitem__('_id', str(result['_id']))
        return result


@app.route("/")
def index():
    product = Product.get_or_create({'name': 'Name', 'quantity': 1,
                                    'attrs': {'feature': 'ice', 'revision': 1},
                                    'list_attrs': ['one', 'two']}, _lang='en')
    product._lang = 'fr'
    product.update({'name': 'Nom'})

    product.update({'attrs': {'feature': 'glace', 'revision': 1}})

    Product.get_or_create({'name': 'Nom', 'quantity': 1,
                           'attrs': {'feature': 'glace', 'revision': 1}},
                            _lang='fr')
    product_fr = product
    product._lang = 'en'
    product_en = product
    total = Product.query.count()

    return "Total: %d. <br> product en is: %s <br> product fr is: %s" % (total,
                    product_en.as_dict(), product_fr.as_dict())


if __name__ == "__main__":
    app.run()
