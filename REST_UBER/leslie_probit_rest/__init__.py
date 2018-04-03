from flask_restful import Resource
from pram_flask.ubertool.ubertool.leslie_probit import leslie_probit_exe as leslie_probit
from flask import request
from pram_flask.REST_UBER import rest_validation, rest_schema, rest_model_caller


class LeslieProbitHandler(Resource):
    def __init__(self):
        self.name = "leslie_probit"

    @staticmethod
    def get_model_inputs():
        """
        Return model's input class.
        :return:
        """
        return leslie_probit.LeslieProbitInputs()

    @staticmethod
    def get_model_outputs():
        """
        Return model's output class.
        :return:
        """
        return leslie_probit.LeslieProbitOutputs()


class LeslieProbitGet(LeslieProbitHandler):

    def get(self, jobId="YYYYMMDDHHMMSSuuuuuu"):
        """
        LeslieProbit get handler.
        :param jobId:
        :return:
        """
        return rest_schema.get_schema(self.name, jobId)


class LeslieProbitPost(LeslieProbitHandler):

    def post(self, jobId="000000100000011"):
        """
        LeslieProbit post handler.
        :param jobId:
        :return:
        """
        inputs = rest_validation.parse_inputs(request.json)

        if inputs:
            return rest_model_caller.model_run(self.name, jobId, inputs, module=leslie_probit)
        else:
            return rest_model_caller.error(self.name, jobId, inputs)
