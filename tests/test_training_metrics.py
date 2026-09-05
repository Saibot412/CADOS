import unittest

from cados.core.training_metrics import TrainingMetrics


class TrainingMetricsTests(unittest.TestCase):
    def test_metrics_are_independent_of_tick_frequency(self):
        regular, irregular = TrainingMetrics(), TrainingMetrics()
        for watts in [100, 300, 200]:
            for _ in range(240):
                regular.add(0.25, watts, 90, 140, 0, watts)
            for _ in range(60):
                irregular.add(0.1, watts, 90, 140, 0, watts)
                irregular.add(0.9, watts, 90, 140, 0, watts)
        self.assertEqual(regular.summary(250), irregular.summary(250))
        self.assertEqual(regular.summary(250)["avg_watts"], 200)
        self.assertEqual(round(regular.best_minute), 300)

    def test_no_minute_result_before_a_full_minute(self):
        metrics = TrainingMetrics()
        metrics.add(59.5, 400, 90, None, 0, 400)
        self.assertEqual(metrics.best_minute, 0)
        metrics.add(0.5, 400, 90, None, 0, 400)
        self.assertEqual(metrics.best_minute, 400)

    def test_missing_hr_is_excluded_from_average(self):
        metrics = TrainingMetrics()
        metrics.add(10, 200, 90, None, 0, 200)
        metrics.add(10, 200, 90, 150, 10, 200)
        self.assertEqual(metrics.summary(250)["avg_heart_rate"], 150)

    def test_constant_power_has_expected_np_tss_and_energy(self):
        metrics = TrainingMetrics()
        metrics.add(3600, 250, 90, 150, 0, 250)
        result = metrics.summary(250)
        self.assertEqual(result["normalized_power"], 250)
        self.assertEqual(result["intensity_factor"], 1)
        self.assertEqual(result["tss"], 100)
        self.assertEqual(result["calories"], 900)
