from flaskext.mongoobject import Model
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

            self.db.set_mapper(NewModel)
            self.db.autoincrement(NewModel)

            self.model = NewModel