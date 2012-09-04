import flask
from flaskext.mongoobject import AttrDict, MongoObject

db = MongoObject()
app = flask.Flask(__name__)
TESTING = True


class TestModel(db.Model):
    __collection__ = "tests"


db.set_mapper(TestModel)

class TestFoo(object):
    def setUp(self):
        app.config['MONGODB_HOST'] = "mongodb://localhost:27017"
        app.config['MONGODB_DATABASE'] = "testdb"
        app.config['MONGODB_AUTOREF'] = True
        app.config['TESTING'] = True
        db.init_app(app)

    def teardown(self):
        db.clear()

    def test_convert_dict_to_obj(self):
        test = AttrDict({"a": "b"})
        assert test.a == "b"

    def test_convert_nested_dict_to_object(self):
        test = AttrDict({"a": {"b": "c"}})
        assert test.a.b == "c"

    def test_convert_list_with_nested_dict(self):
        test = AttrDict(a=[{"b": {"c": "d"}}])
        assert test.a[0].b.c == "d"

    def test_convert_list(self):
        test = AttrDict(a=["test", "hello"])
        assert test.a[0] == "test"

    def test_setup_database_properly(self):
        assert db.app
        assert db.connection
        assert db.session.name == "testdb"

    def test_find_one(self):
        id = db.session.tests.insert({"test": "hello world"})
        result = TestModel.query.find_one({"test": "hello world"})
        assert result._id == id
        assert result.test == "hello world"

    def test_find(self):
        db.session.tests.insert({"test": "hello world"})
        db.session.tests.insert({"test": "testing"})
        db.session.tests.insert({"test": "testing", "hello": "world"})
        result = TestModel.query.find({"test": "testing"})
        result[0].test = "testing"
        assert result.count() == 2

    def test_save_return_a_class(self):
        test = TestModel({"test": "hello"})
        test.save()
        assert test.test == "hello"

    def test_not_override_default_variables(self):
        try:
            TestModel({"query_class": "Hello"})
            assert False
        except AssertionError:
            assert True

        try:
            TestModel({"query": "Hello"})
            assert False
        except AssertionError:
            assert True

        try:
            TestModel({"__collection__": "Hello"})
            assert False
        except AssertionError:
            assert True

    def test_handle_auto_dbref(self):
        parent = TestModel(test="hello")
        parent.save()
        child = TestModel(test="test", parent=parent)
        child.save()

        child = TestModel.query.find_one({"test": "test"})
        assert child.parent.test == "hello"
        assert child.parent.__class__.__name__ == "TestModel"
        assert type(child.parent) == TestModel

    def test_handle_auto_dbref_inside_a_list(self):
        parent = TestModel(test="hellotest")
        parent.save()
        child = TestModel(test="testing", parents=[parent], parent=parent)
        child.save()

        child = TestModel.query.find_one({"test": "testing"})
        print child.parents[0]
        assert child.parents[0].test == "hellotest"
        assert child.parents[0].__class__.__name__ == "TestModel"
        assert type(child.parents[0]) == TestModel

    def test_update(self):
        parent = TestModel(test="hellotest")
        parent.save()

        parent.hello = "test"
        parent.test = 'Hello'
        parent.save()

        assert TestModel.query.count() == 1
        parent = TestModel.query.find()[0]
        assert parent.hello == "test"
        assert parent.test == "Hello"
