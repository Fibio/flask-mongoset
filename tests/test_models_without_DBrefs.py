from flask.ext.mongoset import Model
from conftest import BaseModelTest, app, mongo


class NewModel(Model):
    __collection__ = 'notdbrefstests'
    inc_id = True
    indexes = ['id', 'name']


class InsideModel(Model):
    __collection__ = 'inside'


class TestModelDecorator(BaseModelTest):

    def setUp(self):
        app.config['MONGODB_HOST'] = "localhost"
        app.config['MONGODB_PORT'] = 27017
        app.config['MONGODB_DATABASE'] = "testdb"
        app.config['MONGODB_AUTOREF'] = False
        app.config['MONGODB_AUTOINCREMENT'] = True
        app.config['TESTING'] = True
        mongo.init_app(app)
        self.app = app
        self.mongo = mongo

        self.model = NewModel
        self.insideModel = InsideModel
        self.mongo.register(self.model)

    def test_autoincrement(self):
        result = self.model.create(name='Hello')
        assert result._int_id == 1

    def test_handle_auto_object_inside_a_list(self):
        parent = self.model.get_or_create({'test': 'hellotest'})
        child = self.model.create(test="testing",
                                         parents=[parent], parent=parent)

        child = self.model.query.find_one({"test": "testing"})
        assert child.parents[0].test == "hellotest"
        assert child.parents[0].__class__.__name__ == self.model.__name__
        assert isinstance(child, self.model)
        assert isinstance(child.parents[0], self.model)

        parent = self.model.create(test="test_two")
        child = child.update_with_reload({
            'parents': [parent]})
        assert child.parents[0].test == "test_two"

    def test_other_object_inside(self):
        child = self.insideModel({'inside': True,
                             '_ns': self.insideModel.__collection__})
        parent = self.model.create({'test': 'hellotest',
                                    'children': [child], 'names': ['ddd']})
        assert isinstance(parent.children[0], self.insideModel)
        assert self.insideModel.query.find_one() is None
