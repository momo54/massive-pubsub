
import os
import json
import uuid
import time
from flask import Flask, request, jsonify


try:
    from google.cloud import datastore
    from google.cloud import pubsub_v1
except Exception:
    datastore = None
    pubsub_v1 = None


app = Flask(__name__)



def get_datastore_client():
    if datastore is None:
        raise RuntimeError("google-cloud-datastore non installé ou non disponible.")
    return datastore.Client()



def get_pubsub_publisher():
    if pubsub_v1 is None:
        raise RuntimeError("google-cloud-pubsub non installé ou non disponible.")
    return pubsub_v1.PublisherClient()



KIND = "Post"



@app.post("/posts")
def create_post():
    data = request.get_json(force=True, silent=True) or {}
    title = data.get("title") or "Untitled"
    content = data.get("content") or ""

    client = get_datastore_client()
    doc_id = str(uuid.uuid4())
    key = client.key(KIND, doc_id)
    entity = datastore.Entity(key=key)
    entity.update({
        "id": doc_id,
        "title": title,
        "content": content,
        "likes": 0,
        "createdAt": int(time.time()),
    })
    client.put(entity)
    return jsonify(dict(entity)), 201



@app.get("/posts")
def list_posts():
    client = get_datastore_client()
    query = client.query(kind=KIND)
    query.order = ["-createdAt"]
    posts = []
    for entity in query.fetch(limit=50):
        post = dict(entity)
        post["id"] = entity["id"]
        posts.append(post)
    return jsonify(posts)



@app.post("/posts/<post_id>/like")
def like_post(post_id: str):
    topic = os.environ.get("PUBSUB_TOPIC", "post-likes")
    publisher = get_pubsub_publisher()

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
    if not project_id:
        return jsonify({"error": "GOOGLE_CLOUD_PROJECT non défini"}), 500

    topic_path = publisher.topic_path(project_id, topic)
    payload = {"post_id": post_id}
    data = json.dumps(payload).encode("utf-8")
    future = publisher.publish(topic_path, data, type="like")
    message_id = future.result(timeout=15)
    return jsonify({"status": "enqueued", "messageId": message_id}), 202


@app.get("/")
def root():
    return jsonify({"service": "web", "endpoints": ["GET /posts", "POST /posts", "POST /posts/{id}/like"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
