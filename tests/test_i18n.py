import trafaret as t
from conftest import BaseTest
from flaskext.mongoobject import Model


class SomeModel(Model):
    __collection__ = "tests"
    structure = t.Dict({
        'name': t.String,
        'quantity': t.Int,
        'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String))
    }).allow_extra('*')
    i18n = ['name', 'attrs']


class TestValidation(BaseTest):

    model = SomeModel

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
                               'attrs':{'feature': {}, 'revision': 1}})
            assert False
        except t.DataError:
            assert True

        result = self.model.create({'name': 'Name', 'quantity': 1,
                                    'attrs':{'feature': 'ice', 'revision': 1}})

        try:
            result.update(attrs={'featre':[1, 2, 3]})
            assert False
        except t.DataError:
            assert True

    def test_translate(self):
        result = self.model.get_or_create(**{'name': 'Name', 'quantity': 1,
                                    'attrs':{'feature': 'ice', 'revision': 1}, '_lang':'en'})
        assert result.name == 'Name'
        result._lang = 'fr'
        result.update({'name': 'Nom'})
        assert result.name == 'Nom'
        assert result.attrs.feature == 'ice'

        result = self.model.query.find_one(**{'name': 'Nom', '_lang': 'fr'})
        assert result.name == 'Name'
        result._lang = 'fr'
        assert result.name == 'Nom'
        result.update({'attrs': {'feature': 'glace', 'revision': 1}})
        assert result.attrs.feature == 'glace'

        result = self.model.query.find(_lang='en', **{'attrs.feature': 'ice'})[0]
        assert result.attrs.feature == 'ice'
