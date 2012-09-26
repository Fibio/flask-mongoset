from flaskext.mongoobject import Model
from conftest import BaseModelTest, app, db


class TestModelDecorator(BaseModelTest):

    def setUp(self):
        app.config['MONGODB_HOST'] = "localhost"
        app.config['MONGODB_PORT'] = 27017
        app.config['MONGODB_DATABASE'] = "testdb"
        app.config['MONGODB_AUTOREF'] = False
        app.config['TESTING'] = True
        db.init_app(app)
        self.app = app
        self.db = db

        @self.db.register
        class NewModel(Model):
            __collection__ = 'notdbrefstests'
            inc_id = True
            indexes = ['id', 'name']
        self.model = NewModel

    def test_autoincrement(self):
        result = self.model.create(name='Hello')
        assert result.id == 1

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
