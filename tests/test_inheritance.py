import trafaret as t
from pymongo import DESCENDING
from conftest import BaseTest
from flaskext.mongoobject import Model


class BaseModel(Model):
    __abstract__ = True
    structure = t.Dict({
        'name': t.String,
        'quantity': t.Int,
        'attrs': t.Mapping(t.String, t.Or(t.Int, t.Float, t.String)),
    }).allow_extra('*')
    indexes = ['id']

class SubModel(BaseModel):
    __collection__ = "subtests"
    inc_id = True
    structure = t.Dict({
        'list_attrs': t.List(t.String)
    }).allow_extra('*')
    indexes = [('quantity', DESCENDING), 'name']


class TestValidation(BaseTest):

    model = SubModel

    def setUp(self):
        super(TestValidation, self).setUp()
        self.db.register(self.model)

    def test_inheritance(self):
        result = self.model.get_or_create({'name': 'Name', 'quantity': 1,
                                    'attrs':{'feature': 'ice', 'revision': 1},
                                    'list_attrs':['one', 'two']})
        assert result.name == 'Name'
        assert result.attrs.feature == 'ice'
        assert result.list_attrs == ['one', 'two']

        result.update({'attrs': {'feature': 'glace', 'revision': 1}})
        assert result.attrs.feature == 'glace'

        assert not self.model.query.find({'attrs.feature': 'ice'}).count()
        assert self.model.query.find({'name': 'Name'}).count() == 1
        assert self.model.query.count() == 1
