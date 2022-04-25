"""
QED celery instance
"""

from __future__ import absolute_import
import os
import logging
import json
import uuid
import io
from datetime import datetime
import pandas as pd

from flask import request, Response
from flask_restful import Resource

import pymongo as pymongo

# from flask_qed.celery_cgi import celery
from celery_cgi import celery

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
        # TODO: set based on env variable
        use_celery = True
        # index the input dictionary
        for k, v in request.form.items():
            indexed_inputs[k] = {"0": v}
        valid_input = {"inputs": indexed_inputs, "run_type": "single"}
        if use_celery:
            # SAM Run with celery
            try:
                # task_id = sam_run.apply_async(args=(jobId, valid_input["inputs"]), queue="sam", taskset_id=jobId)
                task_id = sam_run.apply_async(args=(jobId, valid_input["inputs"]), queue="qed", taskset_id=jobId)
                logging.info("SAM celery task initiated with task id:{}".format(task_id))
                resp_body = json.dumps({'task_id': str(task_id.id)})
            except Exception as ex:
                logging.info("SAM celery task failed: " + str(ex))
                resp_body = json.dumps({'task_id': "1234567890"})
        else:
            # SAM Run without celery
            task_id = uuid.uuid4()
            sam_run(task_id, valid_input["inputs"])
            logging.info("SAM flask task completed with task id:{}".format(task_id))
            resp_body = json.dumps({'task_id': str(task_id)})
        response = Response(resp_body, mimetype='application/json')
        return response


class SamJsonData(Resource):
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

class SamMapData(Resource):
    def get(self, task_id):
        logging.info("SAM mapping data request for task id: {}".format(task_id))
        status = sam_status(task_id, map_data_only = True)
        if status['status'] == 'SUCCESS':
            data_json = json.dumps(status['data'])
            logging.info("SAM data found, data request successful.")
        else:
            data_json = ""
            logging.info("SAM data not available for requested task id.")
        return Response(data_json, mimetype='application/json')

class SamDataExcel(Resource):
    def get(self, task_id):
        logging.info("SAM all zipped data request for task id: {}".format(task_id))
        response = sam_output_xlsx(task_id)
        return response
        
        
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


@celery.task(name='pram_sam', bind=True)
def sam_run(self, jobID, inputs):
    if sam_run.request.id is not None:
        task_id = sam_run.request.id
    else:
        task_id = jobID
    logging.info("SAM CELERY task id: {}".format(task_id))
    logging.info("SAM CELERY task starting...")
    inputs["csrfmiddlewaretoken"] = {"0": task_id}
    data = rest_model_caller.model_run("sam", task_id, inputs, module=sam)
    logging.info("SAM CELERY task completed.")
    logging.info("Dumping SAM data into database...")
    mongo_db = connect_to_mongoDB()
    posts = mongo_db.posts
    save_sam_outputs(posts, task_id, data['outputs'])
    logging.info("Completed SAM data db dump.")


def save_sam_outputs(mongodb_posts, task_id, output_dict):
    time_stamp = datetime.utcnow()
    for  key, value in output_dict.items():
        logging.info('storing {}'.format(task_id+'_'+key))
        data = {'_id': task_id+'_'+key, 'date': time_stamp, 'data': json.dumps(value)}
        mongodb_posts.insert_one(data)

def sam_status(task_id, map_data_only=False):
    task = celery.AsyncResult(task_id)
    if task.status == "SUCCESS":
        mongo_db = connect_to_mongoDB()
        posts = mongo_db.posts
        intakes_db_record = dict(posts.find_one({'_id': task_id+'_intakes'}))
        intakes_data =  json.loads(intakes_db_record.get("data", ""))
        watersheds_db_record = dict(posts.find_one({'_id': task_id+'_watersheds'}))
        watersheds_data =  json.loads(watersheds_db_record.get("data", ""))
        if map_data_only:
            data_return = {'intakes': intakes_data, 'watersheds': watersheds_data}
            return {"status": task.status, 'data': data_return}
        intake_time_series_db_record = dict(posts.find_one({'_id': task_id+'_intake_time_series'}))
        intake_time_series_data = json.loads(intake_time_series_db_record.get("data", ""))
        data_return = {'intakes': intakes_data, 'watersheds': watersheds_data, 'intake_time_series': intake_time_series_data}
        return {"status": task.status, 'data': data_return}
    else:
        return {"status": task.status, 'data': {}}
        
def sam_output_xlsx(task_id):
    data_json = sam_status(task_id)
    intakes_df = pd.read_json(data_json['data']['intakes'])
    watersheds_df = pd.read_json(data_json['data']['watersheds'])
    intake_time_series_df = pd.read_json(data_json['data']['intake_time_series'])
    output = io.BytesIO()
    #workbook = Workbook(output, {'in_memory': True})
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    intakes_df.to_excel(writer, sheet_name='intakes')
    watersheds_df.to_excel(writer, sheet_name='watersheds')
    intake_time_series_df.to_excel(writer, sheet_name='intake_time_series')
    #writer.book.use_zip64()
    writer.save()
    #workbook.close()
    output.seek(0)
    response = HttpResponse(output.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = "attachment; filename='sam_output_{}_.xlsx".format(task_id)
    output.close()
    return response

    



    