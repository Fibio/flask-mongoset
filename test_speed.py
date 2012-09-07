import cProfile
import flask
from flaskext.mongoobject import MongoObject

db = MongoObject()
app = flask.Flask(__name__)
TESTING = True


class SomeModel(db.Model):
    __collection__ = "tests"


app.config['MONGODB_HOST'] = "mongodb://localhost:27017"
app.config['MONGODB_DATABASE'] = "testdb"
app.config['MONGODB_AUTOREF'] = False
app.config['AUTOINCREMENT'] = False
app.config['TESTING'] = True
db.init_app(app)


def create_model(interval):
    for i in interval:
        model = SomeModel({"test": {"name": "testing_{}".format(i)}})
        model.save()


def find_model(interval):
    for i in interval:
        SomeModel.query.find({"test.name": "testing_{}".format(i)})


def update_model(interval):
    instance = SomeModel.query.find_one({"test.name": "testing_5"})
    for i in interval:
        instance.update({'foo': 'bar'})


if __name__ == '__main__':
    interval = range(1000)
    cProfile.run('create_model(interval)')
    #old_version, for interval = 1000: 116059 function calls (114058 primitive calls) in 0.192-0.211 seconds
    #new with translation, for interval = 1000: 151006 function calls (146006 primitive calls) in 0.289-0.302 seconds

    cProfile.run('find_model(interval)')
    #old_version, for interval = 1000: 51003 function calls in 0.078-0.086 seconds
    #new with translation, for interval = 1000:  51003 function calls in 0.079-0.085 seconds

    cProfile.run('update_model(interval)')
    #new : 127161 function calls in 0.285 seconds

    db.clear()