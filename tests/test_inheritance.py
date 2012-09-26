import trafaret as t
from pymongo import DESCENDING
from conftest import BaseTest
from flask.ext.mongoset import Model


class BaseModel(Model):
    __abstract__ = True
    inc_id = True
    structure = t.Dict({
        'name': t.String,
        'quantity': t.Int,
        'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
    }).allow_extra('_id', '_ns', 'id').ignore_extra('wrong_attr')
    indexes = ['id']
    required_fields = ['name', 'quantity']


class SubAbstractModel(BaseModel):
    __abstract__ = True
    structure = t.Dict({
        'list_attrs': t.List(t.String)
    }).allow_extra('wrong_attr')
    indexes = [('quantity', DESCENDING), 'name']
    required_fields = ['list_attrs']


class SubModel(SubAbstractModel):
    __collection__ = "subtests"


class SimpleModel(Model):
    __collection__ = "simpletests"
    required_fields = ['name', 'quantity']


class TestValidation(BaseTest):

    model = SubModel

    def setUp(self):
        super(TestValidation, self).setUp()
        self.db.register(self.model)

    def test_inheritance(self):
        result = self.model.get_or_create({'name': 'Name', 'quantity': 1,
                                'attrs': {'feature': 'ice', 'revision': 1},
                                'list_attrs': ['one', 'two']})
        assert result.name == 'Name'
        assert result.attrs.feature == 'ice'
        assert result.list_attrs == ['one', 'two']
        result.update({'attrs': {'feature': 'glace', 'revision': 1}})
        assert result.attrs.feature == 'glace'

        assert not self.model.query.find({'attrs.feature': 'ice'}).count()
        assert self.model.query.find({'name': 'Name'}).count() == 1
        assert self.model.query.count() == 1

    def test_required_fields_with_structure(self):
        try:
            self.model.create({'quantity': '1',
                               'attrs': {'feature': 'ice', 'revision': 1}})
            assert False
        except t.DataError:
            assert True
        assert self.model.create({'name': 'Name',
                                  'quantity': 1, 'list_attrs': ['one', 'two']})

    def test_required_fields_without_structure(self):
        self.db.register(SimpleModel)
        try:
            SimpleModel.create({'quantity': '1'})
            assert False
        except t.DataError:
            assert True

        assert SimpleModel.create({'name': 'Name', 'quantity': 1,
                                   'list_attrs': ['one', 'two']})

    def test_structure_inheritance(self):
        self.model.create({'name': 'NewName', 'quantity': 1, 'wrong_attr': 1,
                           'attrs': {'feature': 'ice', 'revision': 1},
                           'list_attrs': ['one', 'two']})
        assert not self.model.query.find_one({'wrong_attr': 1})
        assert self.model.query.find_one({'name': 'NewName'})

    def test_has_id(self):
        self.model.create({'name': 'Name', 'quantity': 1,
                    'attrs': {'feature': 'ice', 'revision': 1},
                    'list_attrs': ['one', 'two']})
        result = self.model.query.find_one({'name': 'Name'})
        assert result.id


