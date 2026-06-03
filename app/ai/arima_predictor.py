import warnings
import numpy as np

class ArimaProcessTimePredictor:
    """
    真 ARIMA：使用 statsmodels ARIMA 對歷史加工時間序列建模。
    若資料太少或套件不存在，會降級成 moving average，避免 Demo 系統直接中斷。
    """
    def __init__(self, order=(1, 1, 1)):
        self.order = order
        self.last_mode = "UNKNOWN"

    def predict_next_minutes(self, series):
        values = [float(v) for v in series if v is not None and float(v) > 0]
        if not values:
            self.last_mode = "FALLBACK_NO_DATA"
            return 30.0

        if len(values) < 6:
            self.last_mode = "FALLBACK_MOVING_AVG_NOT_ENOUGH_DATA"
            return round(float(np.mean(values[-3:])), 2)

        try:
            from statsmodels.tsa.arima.model import ARIMA
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = ARIMA(values, order=self.order)
                fitted = model.fit()
                forecast = fitted.forecast(steps=1)
                predicted = float(forecast[0])
            self.last_mode = "STATS_MODELS_ARIMA"
            return round(max(predicted, 1.0), 2)
        except Exception:
            self.last_mode = "FALLBACK_MOVING_AVG_ARIMA_ERROR"
            return round(float(np.mean(values[-5:])), 2)
