from operator import methodcaller, attrgetter
import flask
from flaskext.mongoobject import MongoObject, Model

db = MongoObject()
app = flask.Flask(__name__)
TESTING = True


class SomeModel(Model):
    __collection__ = "tests"

db.set_mapper(SomeModel)
db.autoincrement(SomeModel)


class SomedbModel(db.Model):
    __collection__ = "dbtests"


db.set_mapper(SomedbModel)
db.autoincrement(SomedbModel)


class BaseTest(object):

    def setUp(self):
        app.config['MONGODB_HOST'] = "localhost"
        app.config['MONGODB_PORT'] = 27017
        app.config['MONGODB_DATABASE'] = "testdb"
        app.config['MONGODB_AUTOREF'] = True
        app.config['TESTING'] = True
        db.init_app(app)
        self.app = app
        self.db = db

    def teardown(self):
        db.clear()


class BaseModelTest(BaseTest):
    model = None

    def insert(self, dct):
        insert = methodcaller("insert", dct)
        collection = attrgetter('db.session.{}'.format(self.model.__collection__))
        return insert(collection(self))

    def test_find_one(self):
        id = self.insert({"test": "hello world"})
        result = self.model.query.find_one({"test": "hello world"})
        assert result._id == id
        assert result.test == "hello world"

    def test_find(self):
        self.insert({"test": "hello world"})
        self.insert({"test": "testing"})
        self.insert({"test": "testing", "hello": "world"})
        result = self.model.query.find({"test": "testing"})
        result[0].test = "testing"
        assert result.count() == 2

    def test_save_return_a_class(self):
        test = self.model({"test": "hello"})
        test.save()
        assert test.test == "hello"
        assert isinstance(test, self.model)

    def test_not_override_default_variables(self):
        try:
            self.model({"query_class": "Hello"})
            assert False
        except AssertionError:
            assert True

        try:
            self.model({"query": "Hello"})
            assert False
        except AssertionError:
            assert True

        try:
            self.model({"__collection__": "Hello"})
            assert False
        except AssertionError:
            assert True

    def test_handle_auto_dbref(self):
        parent = self.model(test="hello")
        parent.save()
        child = self.model(test="test", parent=parent)
        child.save()

        child = self.model.query.find_one({"test": "test"})
        assert child.parent.test == "hello"
        assert child.parent.__class__.__name__ == self.model.__name__
        assert isinstance(child.parent, self.model)

    def test_handle_auto_dbref_inside_a_list(self):
        parent = self.model(test="hellotest")
        parent.save()
        child = self.model(test="testing", parents=[parent], parent=parent)
        child.save()

        child = self.model.query.find_one({"test": "testing"})
        assert child.parents[0].test == "hellotest"
        assert child.parents[0].__class__.__name__ == self.model.__name__
        assert isinstance(child.parents[0], self.model)

    def test_update(self):
        parent = self.model(test="hellotest")
        parent.save()

        parent.hello = "test"
        parent.test = 'Hello'
        parent.save()

        assert self.model.query.count() == 1
        parent = self.model.query.find()[0]
        assert parent.hello == "test"
        assert parent.test == "Hello"
