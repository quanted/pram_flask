from flask_restful import Resource
from ubertool.ubertool.earthworm import earthworm
from flask import request
import pandas as pd


class EarthwormHandler(Resource):
    def __init__(self):
        self.name = "earthworm"

    def get(self, jid):
        """
        Earthworm get handler.
        :param jid:
        :return:
        """
        return {
            'result': {
                'model: ' + self.name,
                'jid: %s' % jid
            }
        }

    def post(self, jid):
        """
        Earthworm post handler.
        :param jid:
        :return:
        """
        pd_obj = pd.DataFrame.from_dict(request.json["inputs"], dtype='float64')
        earthworm_obj = earthworm.Earthworm(pd_obj, None)
        earthworm_obj.execute_model()
        inputs_json, outputs_json, exp_out_json = earthworm_obj.get_dict_rep(earthworm_obj)

        return {
            'user_id': 'admin',
            'inputs': inputs_json,
            'outputs': outputs_json,
            'exp_out': exp_out_json,
            '_id': jid,
            'run_type': "single"
        }

    @staticmethod
    def get_model_inputs():
        """
        Return model's input class.
        :return:
        """
        return earthworm.EarthwormInputs()

    @staticmethod
    def get_model_outputs():
        """
        Return model's output class.
        :return:
        """
        return earthworm.EarthwormOutputs()