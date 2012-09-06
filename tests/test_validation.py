import trafaret as t
from conftest import BaseTest
from flaskext.mongoobject import Model


class SomeModel(Model):
    __collection__ = "tests"
    structure = t.Dict({
    'key': t.String(),
    t.Key('quantity'): t.Int}).allow_extra('_id', '_ns')


class TestValidation(BaseTest):

    model = SomeModel

    def setUp(self):
        super(TestValidation, self).setUp()
        self.db.register(self.model)

    def test_validate(self):
        try:
            self.model.create({'key': 'foo', 'quantity': 'one'})
            assert False
        except t.DataError:
            assert True

        result = self.model.create({'key': 'foo', 'quantity': 1})
        try:
            result.update(quantity='two')
            assert False
        except t.DataError:
            assert True
