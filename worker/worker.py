import os
import json
import time
import os
from typing import Any
from flask import Flask, jsonify, request


try:
    from google.cloud import datastore
    from google.cloud import pubsub_v1
except Exception:
    datastore = None
    pubsub_v1 = None



KIND = "Post"

app = Flask(__name__)



def get_datastore_client():
    if datastore is None:
        raise RuntimeError("google-cloud-datastore non installé ou non disponible.")
    return datastore.Client()


def get_pubsub_subscriber():
    if pubsub_v1 is None:
        raise RuntimeError("google-cloud-pubsub non installé ou non disponible.")
    return pubsub_v1.SubscriberClient()





def process_likes_batch(db: Any, postid_to_count: dict):
    for post_id, count in postid_to_count.items():
        key = db.key(KIND, post_id)
        txn = db.transaction()
        with txn:
            entity = db.get(key, transaction=txn)
            if not entity:
                continue
            entity["likes"] = int(entity.get("likes", 0)) + count
            db.put(entity)


def drain_once(max_batches: int = 5, batch_size: int = 20) -> dict:
    worker_index = int(os.environ.get("WORKER_INDEX", "0"))
    worker_count = int(os.environ.get("WORKER_COUNT", "1"))
    subscriber = get_pubsub_subscriber()
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
    subscription_name = os.environ.get("PUBSUB_SUBSCRIPTION", "post-likes-sub")

    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT non défini")

    subscription_path = subscriber.subscription_path(project_id, subscription_name)
    db = get_datastore_client()

    processed = 0
    acks_total = 0

    for _ in range(max_batches):
        try:
            response = subscriber.pull(
                request={
                    "subscription": subscription_path,
                    "max_messages": batch_size,
                },
                timeout=5,
            )
        except Exception:
            break

        if not response.received_messages:
            break

        ack_ids = []
        postid_to_count = {}
        for received_message in response.received_messages:
            try:
                data = json.loads(received_message.message.data.decode("utf-8"))
                post_id = data.get("post_id")
                if post_id:
                    h = hash(str(post_id))
                    if worker_count > 1:
                        if h % worker_count != worker_index:
                            ack_ids.append(received_message.ack_id)
                            continue
                    postid_to_count[post_id] = postid_to_count.get(post_id, 0) + 1
                ack_ids.append(received_message.ack_id)
                processed += 1
            except Exception:
                ack_ids.append(received_message.ack_id)

        if postid_to_count:
            process_likes_batch(db, postid_to_count)

        if ack_ids:
            subscriber.acknowledge(request={"subscription": subscription_path, "ack_ids": ack_ids})
            acks_total += len(ack_ids)

        time.sleep(0.1)

    return {"processed": processed, "acked": acks_total}



@app.get("/healthz")
def healthz():
    return jsonify({"status": "ok"})

@app.get("/")
def root():
    return "ok", 200

@app.get("/_ah/health")
def gae_health():
    return "ok", 200


@app.route("/tasks/drain", methods=["GET", "POST"])
def tasks_drain():
    # Optionnel: sécuriser via un header X-AppEngine-Cron si nécessaire
    mb = int(request.args.get("max_batches", 5))
    bs = int(request.args.get("batch_size", 20))
    result = drain_once(max_batches=mb, batch_size=bs)
    return jsonify({"status": "ok", **result})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
