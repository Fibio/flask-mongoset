import cProfile
import flask
from flaskext.mongoobject import MongoObject

db = MongoObject()
app = flask.Flask(__name__)
TESTING = True


class SomeModel(db.Model):
    __collection__ = "tests"


db.set_mapper(SomeModel)
db.autoincrement(SomeModel)

app.config['MONGODB_HOST'] = "mongodb://localhost:27017"
app.config['MONGODB_DATABASE'] = "testdb"
app.config['MONGODB_AUTOREF'] = False
app.config['AUTOINCREMENT'] = True
app.config['TESTING'] = True
db.init_app(app)

def create_model(interval):
    for i in interval:
        model = SomeModel({"test": {"name": "testing_{}".format(i)}})
        model.save()

def find_model(interval):
    for i in interval:
        SomeModel.query.find({"test.name": "testing_{}".format(i)})


if __name__ == '__main__':
    interval = range(1000)
    cProfile.run('create_model(interval)')
    #old_version, for interval = 1000: 116059 function calls (114058 primitive calls) in 0.192-0.211 seconds
    #121059 function calls (115058 primitive calls) in 0.199 seconds
    #119059 function calls (113058 primitive calls) in 0.193-0.210 seconds

    cProfile.run('find_model(interval)')
    #old_version, for interval = 1000: 51003 function calls in 0.078-0.086 seconds




    db.clear()