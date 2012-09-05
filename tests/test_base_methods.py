# from flaskext.mongoobject import AttrDict
# from conftest import BaseTest


# class TestAttrDict(BaseTest):

#     def test_convert_dict_to_obj(self):
#         test = AttrDict({"a": "b"})
#         assert test.a == "b"

#     def test_convert_nested_dict_to_object(self):
#         test = AttrDict({"a": {"b": "c"}})
#         assert test.a.b == "c"

#     def test_convert_list_with_nested_dict(self):
#         test = AttrDict(a=[{"b": {"c": "d"}}])
#         assert test.a[0].b.c == "d"

#     def test_convert_list(self):
#         test = AttrDict(a=["test", "hello"])
#         assert test.a[0] == "test"

#     def test_setup_database_properly(self):
#         assert self.db.app
#         assert self.db.connection
#         assert self.db.session.name == "testdb"
