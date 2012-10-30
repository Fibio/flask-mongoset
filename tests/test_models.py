from flask.ext.mongoset import Model
from conftest import BaseModelTest, SomeModel, SomedbModel, app, mongo


app.config['MONGODB_HOST'] = "localhost"
app.config['MONGODB_PORT'] = 27017
app.config['MONGODB_DATABASE'] = "testdb"
app.config['MONGODB_AUTOREF'] = True
app.config['MONGODB_AUTOINCREMENT'] = True
app.config['TESTING'] = True
mongo.init_app(app)


@mongo.register
class NewModel(Model):
    __collection__ = 'decotests'
    inc_id = True
    indexes = ['id', 'name']


class TestModelDecorator(BaseModelTest):

    def setUp(self):
        self.app = app
        self.mongo = mongo
        self.model = NewModel

    def test_autoincrement(self):
        result = self.model.create(name='Hello')
        assert result._int_id == 1


class TestdbModel(BaseModelTest):
    model = SomedbModel


class TestModelRegistration(BaseModelTest):
    model = SomeModel

    def setUp(self):
        super(TestModelRegistration, self).setUp()
        self.mongo.register(self.model)
