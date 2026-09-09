import json
import unittest
from pathlib import Path

from cados.core.session_analysis import ftp_test_result, measured_max_hr
from cados.core.workout_loader import WorkoutLoader
from cados.core.workout_engine import WorkoutEngine
from fakes import FakeTrainer


def test_session(watts=440):
    return {'workout_name':'FTP Ramp Test (ERG)','ftp_watts':300,
        'workout_payload':{'blocks':[{'type':'steady','label':'Warmup','duration_sec':60,'target_watts':100},
            {'type':'steady','label':'Step 1','duration_sec':120,'target_watts':600}]},
        'samples':[{'duration_sec':1,'elapsed_sec':i+1,'workout_elapsed_sec':i,'watts':watts if i>=60 else 900,'heart_rate':190,'segment':0} for i in range(120)]}


class SessionAnalysisTests(unittest.TestCase):
    def test_ftp_uses_measured_power_not_targets_or_warmup(self):
        result=ftp_test_result(test_session())
        self.assertEqual(result['estimated_ftp'],330)
        self.assertEqual(result['best_minute_watts'],440)
        self.assertEqual(result['old_ftp'],300)
        self.assertEqual(ftp_test_result(test_session(360))['estimated_ftp'],270)

    def test_partial_minutes_and_pauses_do_not_form_a_test_result(self):
        data=test_session();data['samples']=data['samples'][:90]
        self.assertFalse(ftp_test_result(data)['eligible'])
        data=test_session()
        for sample in data['samples'][90:]:sample['segment']=1
        self.assertFalse(ftp_test_result(data)['eligible'])
        self.assertIsNone(ftp_test_result({**data,'workout_name':'FTP 20 minute test'}))

    def test_invalid_hr_values_are_ignored(self):
        self.assertEqual(measured_max_hr([{'heart_rate':v} for v in (None,0,190,195,True,999,float('nan'),'250')]),195)

    def test_ramp_reaches_600w_at_300ftp_and_disallows_adaptive_relief(self):
        path=Path('cados/assets/workouts/FTP Ramp Test (ERG).json')
        workout=WorkoutLoader(path.parent).load_path(path)
        resolved=workout.resolve(300)
        self.assertEqual(max(block.target_watts_at(0) for block in resolved.blocks),600)
        engine=WorkoutEngine(FakeTrainer());engine.load_workout(workout,300)
        self.assertFalse(engine.set_adaptive_erg(True).adaptive_erg)
        self.assertEqual(engine.calculate_ftp_from_ramp(),0)
