import trafaret as t
from pymongo import DESCENDING
from conftest import BaseTest
from flask.ext.mongoobject import Model


class BaseModel(Model):
    __abstract__ = True
    structure = t.Dict({
        'name': t.String,
        'quantity': t.Int,
        'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
    }).allow_extra('*')
    i18n = ['name', 'attrs']
    indexes = ['id']


class i18nModel(BaseModel):
    __collection__ = "i18ntests"
    inc_id = True
    structure = t.Dict({
        'list_attrs': t.List(t.String),
        'salers': t.List(t.Dict({
            'name': t.String,
            'address': t.String
        })),
        t.Key('list_sku', default=[]): t.List(t.Int)
    }).allow_extra('*')
    i18n = ['list_attrs', 'salers']
    indexes = [('quantity', DESCENDING), 'name']


class TestValidation(BaseTest):

    model = i18nModel

    def setUp(self):
        super(TestValidation, self).setUp()
        self.db.register(self.model)

    def test_validate_translated_attrs(self):
        try:
            self.model.create({'name': 1, 'quantity': 1})
            assert False
        except t.DataError:
            assert True

        try:
            self.model.create({'name': 'Name', 'quantity': 1,
                               'attrs': {'feature': {}, 'revision': 1},
                               'list_attrs': []})
            assert False
        except t.DataError:
            assert True

        result = self.model.create({'name': 'Name', 'quantity': 1,
                                    'attrs': {'feature': 'ice', 'revision': 1},
                                    'list_attrs': ['one', 'two']})

        # try:
        #     result.update(attrs={'featre': [1, 2, 3]})
        #     assert False
        # except t.DataError:
        #     assert True

    def test_translate(self):
        result = self.model.get_or_create({'name': 'Name', 'quantity': 1,
                                    'attrs': {'feature': 'ice', 'revision': 1},
                                    'list_attrs': ['one', 'two']}, _lang='en')
        assert result.name == 'Name'
        result._lang = 'fr'
        result = result.update_with_reload(name='Nom')

        # attr name translated but not feature and list_attrs:
        assert result.name == 'Nom'
        assert result.attrs.feature == 'ice'
        assert result.list_attrs == ['one', 'two']

        result.update(attrs={'feature': 'glace', 'revision': 1},
                      list_attrs=['un', 'deux'])

        result = self.model.query.find_one({'name': 'Nom'}, _lang='fr')
        assert result.attrs.feature == 'glace'

        result = self.model.query.find({'attrs.feature': 'ice'})[0]
        assert result.attrs.feature == 'ice'
        assert result.name == 'Name'
        assert result.list_attrs == ['one', 'two']
        assert not self.model.query.find({
                        'attrs.feature': 'something else'}).count()

        assert self.model.get_or_create({'name': 'Nom', 'quantity': 1,
                                'attrs': {'feature': 'glace', 'revision': 1},
                                'list_attrs': ['un', 'deux']}, _lang='fr')
        assert self.model.query.count() == 1

    def test_update(self):
        result = self.model.get_or_create({'name': 'Name', 'quantity': 1,
                                'attrs': {'feature': 'ice', 'revision': 1},
                                'list_attrs': ['one', 'two'],
                                'salers': [{'name': 'John', 'address': 'NY'},
                                           {'name': 'Jane', 'address': 'CA'}]},
                                _lang='en')
        result._lang = 'fr'
        result = result.update_with_reload(attrs={'feature': 'glace',
                                                  'revision': 1})
        assert result.attrs.feature == 'glace'
        result._lang = 'en'
        assert result.attrs.feature == 'ice'

        result = result.update_with_reload(name='Fridge', quantity=30)
        assert result.name == 'Fridge'
        assert result.quantity == 30

        result = result.update_with_reload({'$set': {
                            'attrs': {'feature': 'no frost', 'revision': 2}}})
        assert result.attrs.feature == 'no frost'
        assert result.attrs.revision == 2

        result = result.update_with_reload({'$push': {'list_attrs': 'three',
                                                      'list_sku': 1},
                                            '$inc': {'quantity': 10}})
        assert result.list_attrs == ['one', 'two', 'three']
        assert result.list_sku == [1]
        assert result.quantity == 40

        result = result.update_with_reload({'$unset': {'quantity': 30},
                                        '$pop': {'list_attrs': 'three'},
                                        '$pull': {'salers': {'name': 'John'}}})
        assert not 'quantity' in result
        assert result.list_attrs == ['one', 'two']
        assert not self.model.query.find_one({'salers.name': 'John'})