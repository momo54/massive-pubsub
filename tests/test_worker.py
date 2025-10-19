import types
from worker.worker import process_like



class MockEntity(dict):
    pass

class MockDB:
    def __init__(self):
        self.entities = {}
    def key(self, kind, post_id):
        return (kind, post_id)
    def get(self, key):
        return self.entities.get(key)
    def put(self, entity):
        key = ("Post", entity["id"])
        self.entities[key] = entity

def test_process_like_increments():
    db = MockDB()
    key = db.key("Post", "abc")
    db.entities[key] = {"id": "abc", "likes": 0}
    process_like(db, "abc")
    assert db.entities[key]["likes"] == 1
    process_like(db, "abc")
    assert db.entities[key]["likes"] == 2
