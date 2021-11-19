"""
QED celery instance
"""

from __future__ import absolute_import
import os
import logging
import json
import uuid
from datetime import datetime

from flask import request, Response
from flask_restful import Resource

import pymongo as pymongo
from dask.distributed import Client, LocalCluster, fire_and_forget


logging.getLogger('celery.task.default').setLevel(logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

if __name__ == "pram_flask.tasks":
    from pram_flask.ubertool.ubertool.sam import sam_exe as sam
    from pram_flask.REST_UBER import rest_model_caller
else:
    logging.info("SAM Task except import attempt..")
    from .ubertool.ubertool.sam import sam_exe as sam
    from .REST_UBER import rest_model_caller

    logging.info("SAM Task except import complete!")

IN_DOCKER = os.environ.get("IN_DOCKER")
USE_DASK = os.getenv("DASK", "True") == "True"


def connect_to_mongoDB():
    if IN_DOCKER == "False":
        # Dev env mongoDB
        mongo = pymongo.MongoClient(host='mongodb://localhost:27017/0')
        print("MONGODB: mongodb://localhost:27017/0")
    else:
        # Production env mongoDB
        mongo = pymongo.MongoClient(host='mongodb://mongodb:27017/0')
        print("MONGODB: mongodb://mongodb:27017/0")
    mongo_db = mongo['pram_tasks']
    mongo.pram_tasks.Collection.create_index([("date", pymongo.DESCENDING)], expireAfterSeconds=86400)
    # ALL entries into mongo.flask_hms must have datetime.utcnow() timestamp, which is used to delete the record after 86400
    # seconds, 24 hours.
    return mongo_db


def get_dask_client():
    if not USE_DASK:
        return None
    if IN_DOCKER == "True":
        scheduler_name = os.getenv('DASK_SCHEDULER', "pram-dask-scheduler:8786")
        logging.info(f"Dask Scheduler: {scheduler_name}")
        dask_client = Client(scheduler_name)
    else:
        logging.info("Dask Scheduler: Local Cluster")
        scheduler = LocalCluster(processes=False)
        dask_client = Client(scheduler)
    return dask_client


class SamStatus(Resource):
    def get(self, task_id):
        """
        SAM task status
        :param jobId:
        :return:
        """
        # logging.info("SAM task status request received for task: {}".format(str(task_id)))
        task = {}
        try:
            task = sam_status(task_id)
            # logging.info("SAM task id: " + task_id + " status: " + task['status'])
            resp_body = json.dumps({'task_id': task_id, 'task_status': task['status'], 'task_data': task['data']})
        except Exception as ex:
            task['status'] = 'Error fetching status'
            task['error'] = repr(ex)
            task['data'] = {}
            logging.info("SAM task status request error: " + str(ex))
            resp_body = json.dumps(
                {'task_id': task_id, 'task_status': task['status'], 'task_data': task['data'], 'error': task['error']})
        response = Response(resp_body, mimetype='application/json')
        return response


class SamRun(Resource):
    def post(self, jobId="000000100000011"):
        """
        SAM post handler.
        :param jobId:
        :return:
        """
        logging.info("SAM task start request with inputs: {}".format(str(request.form)))
        indexed_inputs = {}
        for k, v in request.form.items():
            indexed_inputs[k] = {"0": v}
        valid_input = {"inputs": indexed_inputs, "run_type": "single"}
        if USE_DASK:
            try:
                dask_client = get_dask_client()
                task_id = uuid.uuid4()
                sam_task = dask_client.submit(sam_run, task_id, valid_input["inputs"])
                fire_and_forget(sam_task)
                resp_body = json.dumps({'task_id': str(task_id)})
            except Exception as ex:
                logging.info("SAM celery task failed: " + str(ex))
                resp_body = json.dumps({'task_id': "1234567890"})
        else:
            # SAM Run without Dask
            task_id = uuid.uuid4()
            sam_run(task_id, valid_input["inputs"])
            logging.info("SAM flask task completed with task id:{}".format(task_id))
            resp_body = json.dumps({'task_id': str(task_id)})
        response = Response(resp_body, mimetype='application/json')
        return response


class SamData(Resource):
    def get(self, task_id):
        logging.info("SAM data request for task id: {}".format(task_id))
        status = sam_status(task_id)
        if status['status'] == 'SUCCESS':
            data_json = json.dumps(status['data'])
            logging.info("SAM data found, data request successful.")
        else:
            data_json = ""
            logging.info("SAM data not available for requested task id.")
        return Response(data_json, mimetype='application/json')


class SamSummaryHUC8(Resource):
    def get(self, task_id):
        logging.info("SAM HUC8 summary request for task id: {}".format(task_id))
        status = sam_status(task_id)
        if status['status'] == 'SUCCESS':
            if any(status['huc8_summary']):
                data_json = json.dumps(status['huc8_summary'])
            else:
                data_json = json.dumps({'Error': 'No acute human drinking water toxicity threshold specified'})
            logging.info("SAM HUC8 summary found, data request successful.")
        else:
            data_json = ""
            logging.info("SAM data not available for requested task id.")
        return Response(data_json, mimetype='application/json')


class SamSummaryHUC12(Resource):
    def get(self, task_id):
        logging.info("SAM HUC12 summary request for task id: {}".format(task_id))
        status = sam_status(task_id)
        if status['status'] == 'SUCCESS':
            if any(status['huc12_summary']):
                data_json = json.dumps(status['huc12_summary'])
            else:
                data_json = json.dumps({'Error': 'No acute human drinking water toxicity threshold specified'})
            logging.info("SAM HUC12 summary found, data request successful.")
        else:
            data_json = ""
            logging.info("SAM data not available for requested task id.")
        return Response(data_json, mimetype='application/json')


def sam_run(task_id, inputs):
    logging.info("SAM CELERY task id: {}".format(task_id))
    logging.info("SAM CELERY task starting...")
    mongo_db = connect_to_mongoDB()
    posts = mongo_db.posts
    time_stamp = datetime.utcnow()
    data = {'_id': task_id, 'date': time_stamp, 'data': {}, 'status': "STARTED"}
    posts.insert_one(data)
    inputs["csrfmiddlewaretoken"] = {"0": task_id}
    try:
        result_data = rest_model_caller.model_run("sam", task_id, inputs, module=sam)
        result_data = json.dumps(result_data['outputs'])
        status = "SUCCESS"
        logging.info("SAM CELERY task completed.")
    except Exception as e:
        result_data = f"Error running sam, message: {e}"
        logging.info(f"Error running sam, message: {e}")
        status = "FAILED"
    logging.info("Dumping SAM data into database...")
    time_stamp = datetime.utcnow()
    data = {'date': time_stamp, 'data': result_data, 'status': status}
    posts.update_one({'_id': task_id}, data)
    logging.info("Completed SAM data db dump.")


def sam_status(task_id):
    mongo_db = connect_to_mongoDB()
    posts = mongo_db.posts
    db_record = dict(posts.find_one({'_id': task_id}))
    if db_record["status"] == "SUCCESS":
        data = json.loads(db_record.get("data", ""))
        return {"status": db_record["status"], "data": data}
    else:
        return {"status": db_record["status"], "data": {}}
