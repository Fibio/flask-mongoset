from flask.ext.mongoset import Model
from conftest import BaseModelTest, SomeModel, SomedbModel


class TestdbModel(BaseModelTest):
    model = SomedbModel


class TestModelRegistration(BaseModelTest):
    model = SomeModel

    def setUp(self):
        super(TestModelRegistration, self).setUp()
        self.db.register(self.model)


class TestModelDecorator(BaseModelTest):

    def setUp(self):
        super(TestModelDecorator, self).setUp()

        @self.db.register
        class NewModel(Model):
            __collection__ = 'decotests'
            inc_id = True
            indexes = ['id', 'name']
        self.model = NewModel

    def test_autoincrement(self):
        result = self.model.create(name='Hello')
        assert result._int_id == 1
