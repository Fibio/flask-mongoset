from operator import methodcaller, attrgetter
import flask
from bson.dbref import DBRef
from werkzeug.exceptions import NotFound
from flaskext.mongoobject import MongoObject, Model


db = MongoObject()
app = flask.Flask(__name__)
TESTING = True


class SomeModel(Model):
    __collection__ = "tests"


class SomedbModel(db.Model):
    __collection__ = "dbtests"
    use_autorefs = True


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
        collection = attrgetter('db.session.{}'.format(
                                self.model.__collection__))
        return insert(collection(self))

    def test_find_one(self):
        id = self.insert({"test": "hello world"})
        result = self.model.query.find_one({"test": "hello world"})
        assert result._id == id
        assert result.test == "hello world"
        assert isinstance(result, self.model)

        assert not self.model.query.find_one({"test": "something else"})

    def test_find(self):
        self.insert({"test": "hello world"})
        self.insert({"test": "testing"})
        self.insert({"test": "testing", "hello": "world"})
        result = self.model.query.find({"test": "testing"})
        assert result.count() == 2
        result = result[0]
        result.test = "testing"
        assert isinstance(result, self.model)

        assert not self.model.query.find({"test": "not test"}).count()

    def test_create(self):
        result = self.model.create(name='Hello')
        assert result == self.model.query.find_one(name='Hello')
        assert self.model.query.find({"name": "Hello"}).count() == 1

        result = self.model.get_or_create(name='Hello')
        assert result == self.model.query.find_one(name='Hello')
        assert self.model.query.find({"name": "Hello"}).count() == 1
        assert isinstance(result, self.model)

        result = self.model.get_or_create(test='test')
        assert result == self.model.query.find_one(test='test')

    def test_save_return_a_class(self):
        test = self.model.create({"test": "hello"})
        assert test.test == "hello"
        assert isinstance(test, self.model)

    def test_update(self):
        result = self.model.create(test="hellotest")
        result.update(test='Hello', hello='test')

        assert self.model.query.count() == 1
        result = self.model.query.find()[0]
        assert result.hello == "test"
        assert result.test == "Hello"
        assert isinstance(result, self.model)

    def test_not_override_default_variables(self):
        try:
            self.model({"query_class": "Hello"})
            assert False
        except AttributeError:
            assert True

        try:
            self.model({"query": "Hello"})
            assert False
        except AttributeError:
            assert True

        try:
            self.model({"__collection__": "Hello"})
            assert False
        except AttributeError:
            assert True

    def test_handle_auto_object(self):
        parent = self.model.create(test="hello")
        child = self.model.create(test="test", parent=parent)

        child = self.model.query.find_one({"test": "test"})
        assert child.parent.test == "hello"
        assert child.parent.__class__.__name__ == self.model.__name__
        assert isinstance(child, self.model)
        assert isinstance(child.parent, self.model)

    def test_handle_auto_object_after_create(self):
        parent = self.model.create(test="hello")
        child = self.model.create(test="test", parent=parent)
        assert child.parent.test == "hello"

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
            'parents': [DBRef(parent.__collection__, parent._id)]})
        assert child.parents[0].test == "test_two"

    def test_404(self):
        try:
            self.model.query.get_or_404('4879453489')
            assert False
        except NotFound:
            assert True

        try:
            self.model.query.find_one_or_404(name='wrong_name')
            assert False
        except NotFound:
            assert True

        try:
            self.model.query.find_or_404(name='wrong_name')
            assert False
        except NotFound:
            assert True
