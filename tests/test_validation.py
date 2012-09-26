import trafaret as t
from conftest import BaseTest
from flask.ext.mongoset import Model


class ValidateModel(Model):
    __collection__ = "validation_tests"
    structure = t.Dict({
    'key': t.String(),
    t.Key('quantity'): t.Int}).allow_extra('_id', '_ns')
    indexes = ["quantity"]


class TestValidation(BaseTest):

    model = ValidateModel

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
