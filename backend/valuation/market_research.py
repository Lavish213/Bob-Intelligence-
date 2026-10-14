from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

from backend.valuation.engine import day, integer, token


NUMERIC = ('Lot Frontage', 'Lot Area', 'Overall Qual', 'Overall Cond', 'Year Built', 'Year Remod/Add', 'Mas Vnr Area', 'BsmtFin SF 1', 'BsmtFin SF 2', 'Bsmt Unf SF', 'Total Bsmt SF', '1st Flr SF', '2nd Flr SF', 'Low Qual Fin SF', 'Gr Liv Area', 'Bsmt Full Bath', 'Bsmt Half Bath', 'Full Bath', 'Half Bath', 'Bedroom AbvGr', 'Kitchen AbvGr', 'TotRms AbvGrd', 'Fireplaces', 'Garage Yr Blt', 'Garage Cars', 'Garage Area', 'Wood Deck SF', 'Open Porch SF', 'Enclosed Porch', '3Ssn Porch', 'Screen Porch', 'Pool Area')
CATEGORICAL = ('MS SubClass', 'MS Zoning', 'Street', 'Alley', 'Lot Shape', 'Land Contour', 'Utilities', 'Lot Config', 'Land Slope', 'Neighborhood', 'Condition 1', 'Condition 2', 'Bldg Type', 'House Style', 'Roof Style', 'Roof Matl', 'Exterior 1st', 'Exterior 2nd', 'Mas Vnr Type', 'Exter Qual', 'Exter Cond', 'Foundation', 'Bsmt Qual', 'Bsmt Cond', 'Bsmt Exposure', 'BsmtFin Type 1', 'BsmtFin Type 2', 'Heating', 'Heating QC', 'Central Air', 'Electrical', 'Kitchen Qual', 'Functional', 'Fireplace Qu', 'Garage Type', 'Garage Finish', 'Garage Qual', 'Garage Cond', 'Paved Drive', 'Pool QC', 'Fence', 'Misc Feature')
CRITICAL = ('Lot Area', 'Overall Qual', 'Overall Cond', 'Year Built', 'Year Remod/Add', 'Gr Liv Area', 'Total Bsmt SF', 'Full Bath', 'Half Bath', 'Bedroom AbvGr', 'Garage Cars', 'Neighborhood', 'Bldg Type', 'House Style', 'Exter Qual', 'Functional')
FEATURES = NUMERIC + CATEGORICAL
MODEL_NAMES = ('ridge', 'lightgbm', 'catboost', 'ensemble')


def feature_values(row):
    if not isinstance(row, dict):
        raise ValueError('Features must be an object')
    result = {}
    for key in NUMERIC:
        value = row.get(key)
        if value in (None, '', 'NA'):
            result[key] = None
        else:
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                raise ValueError('Numeric source fields must be integers or source strings')
            try:
                parsed = Decimal(str(value))
            except InvalidOperation as error:
                raise ValueError('Invalid numeric source field') from error
            if not parsed.is_finite() or not 0 <= parsed <= 10**7:
                raise ValueError('Out-of-bounds physical feature')
            result[key] = float(parsed)
            if key in ('Overall Qual', 'Overall Cond') and not 1 <= parsed <= 10:
                raise ValueError('Condition and quality ratings must be within the source scale')
    for key in CATEGORICAL:
        value = row.get(key)
        if value is None or value == '':
            result[key] = '__MISSING__'
        elif not isinstance(value, str) or len(value) > 80 or any(ord(c) < 32 for c in value):
            raise ValueError('Invalid categorical source field')
        else:
            result[key] = value
    return result


def log_to_cents(log_price):
    if type(log_price) not in (int, float) or not math.isfinite(log_price) or not 0 <= log_price <= math.log(10**12):
        raise ValueError('Invalid model indication')
    return integer(int((Decimal(str(math.exp(log_price))) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)), 1)


def calibration_radius(scores, alpha_bps=1000):
    integer(alpha_bps, 1, 5000)
    if not isinstance(scores, list) or len(scores) < 20 or any(type(s) not in (int, float) or not math.isfinite(s) or s < 0 for s in scores):
        raise ValueError('At least twenty finite calibration residuals are required')
    rank = ((len(scores) + 1) * (10000 - alpha_bps) + 9999) // 10000
    if rank > len(scores):
        raise ValueError('Calibration set cannot support the requested quantile')
    return sorted(scores)[rank - 1]


class MarketResearchModel:
    def __init__(self, seed=3342):
        integer(seed, 0, 2**31 - 1)
        self.seed = seed
        self.models = {}
        self.radii = {}
        self.cutoff = None
        self.region = None
        self.categories = {}
        self.area_bounds = None
        self.feature_bounds = {}
        self.artifact_id = None

    def fit(self, fitting, calibration, cutoff, region):
        self.models, self.radii, self.categories, self.feature_bounds = {}, {}, {}, {}
        self.cutoff, self.region, self.area_bounds, self.artifact_id = None, None, None, None
        import numpy as np
        import pandas as pd
        from catboost import CatBoostRegressor
        from lightgbm import LGBMRegressor
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        effective = day(cutoff)
        if effective > date.today():
            raise ValueError('Future model cutoff is not supported')
        token(region)
        if not isinstance(fitting, list) or not isinstance(calibration, list) or len(fitting) < 100 or len(calibration) < 20 or len(fitting) + len(calibration) > 50000:
            raise ValueError('Bounded, disjoint fitting and calibration sets are required')
        identities = []
        data = []
        for row in fitting + calibration:
            identity = token(row['property_id'])
            if token(row['region']) != region or not day(row['closed_on']) <= day(row['available_on']) <= effective:
                raise ValueError('Training evidence is unavailable or belongs to another region')
            integer(row['sale_price_cents'], 100)
            if row['features'].get('Bldg Type') != '1Fam':
                raise ValueError('This research model is restricted to detached houses')
            values = feature_values(row['features'])
            if any(values[k] is None or values[k] in ('__MISSING__', 'NA') for k in CRITICAL) or values['Gr Liv Area'] <= 0:
                raise ValueError('Missing essential training features')
            if any(values[k] is not None and values[k] > day(row['closed_on']).year for k in ('Year Built', 'Year Remod/Add', 'Garage Yr Blt')):
                raise ValueError('Future construction metadata')
            identities.append(identity)
            data.append(values)
        if len(set(identities)) != len(identities):
            raise ValueError('Duplicate parcel or fitting/calibration overlap')
        count = len(fitting)
        frame = pd.DataFrame(data, columns=FEATURES)
        for key in NUMERIC:
            frame[key] = frame[key].astype(float)
        target = np.log([r['sale_price_cents'] / 100 for r in fitting + calibration])
        def encoder():
            return ColumnTransformer([('num', make_pipeline(SimpleImputer(strategy='median'), StandardScaler()), list(NUMERIC)), ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), list(CATEGORICAL))]).set_output(transform='pandas')
        models = {'ridge': make_pipeline(encoder(), Ridge(alpha=20)), 'lightgbm': make_pipeline(encoder(), LGBMRegressor(n_estimators=900, num_leaves=15, min_child_samples=15, reg_lambda=5, learning_rate=0.03, n_jobs=2, verbosity=-1, random_state=self.seed)), 'catboost': CatBoostRegressor(iterations=900, depth=6, learning_rate=0.04, l2_leaf_reg=8, loss_function='RMSE', random_seed=self.seed, thread_count=2, verbose=False, allow_writing_files=False, cat_features=list(CATEGORICAL))}
        calibrated = {}
        for name, model in models.items():
            model.fit(frame.iloc[:count], target[:count])
            calibrated[name] = model.predict(frame.iloc[count:])
        calibrated['ensemble'] = np.mean(list(calibrated.values()), axis=0)
        self.radii = {name: calibration_radius([float(v) for v in abs(predictions - target[count:])]) for name, predictions in calibrated.items()}
        self.categories = {key: set(row[key] for row in data[:count]) for key in CATEGORICAL}
        areas = [row['Gr Liv Area'] for row in data[:count]]
        self.area_bounds = (min(areas), max(areas))
        self.feature_bounds = {key: (min(row[key] for row in data[:count]), max(row[key] for row in data[:count])) for key in CRITICAL if key in NUMERIC}
        self.cutoff, self.region, self.models = effective, region, models
        bound_data = [{k: r[k] for k in ('property_id', 'region', 'closed_on', 'available_on', 'sale_price_cents')} | {'features': values} for r, values in zip(fitting + calibration, data)]
        payload = {'seed': self.seed, 'cutoff': cutoff, 'region': region, 'fit_count': count, 'algorithm_version': '1.0', 'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'dependencies': {name: importlib.metadata.version(name) for name in ('numpy', 'pandas', 'scikit-learn', 'catboost', 'lightgbm', 'scipy')}, 'data': bound_data}
        self.artifact_id = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        return self

    def numerical_predictions(self, rows):
        import numpy as np
        import pandas as pd

        if not self.models or not isinstance(rows, list) or not 1 <= len(rows) <= 5000:
            raise ValueError('Fitted model and bounded research batch are required')
        frame = pd.DataFrame([feature_values(r['features']) for r in rows], columns=FEATURES)
        for key in NUMERIC:
            frame[key] = frame[key].astype(float)
        predictions = {name: model.predict(frame) for name, model in self.models.items()}
        predictions['ensemble'] = np.mean(list(predictions.values()), axis=0)
        return [{name: log_to_cents(float(values[i])) for name, values in predictions.items()} for i in range(len(rows))]

    def predict_research(self, rows, as_of, region):
        effective = day(as_of)
        if self.cutoff is None or not self.cutoff <= effective <= date.today():
            raise ValueError('Invalid research effective date')
        if not isinstance(rows, list) or not 1 <= len(rows) <= 5000:
            raise ValueError('Bounded research batch is required')
        reasons_by_row = []
        results = []
        for row in rows:
            values = feature_values(row['features'])
            reasons = []
            if region != self.region:
                reasons.append('different_model_region')
            if (effective - self.cutoff).days > 365:
                reasons.append('stale_model_cutoff')
            if row['features'].get('Bldg Type') != '1Fam':
                reasons.append('unsupported_property_type')
            if any(values[k] is None or values[k] in ('__MISSING__', 'NA') for k in CRITICAL):
                reasons.append('missing_essential_features')
            if values['Neighborhood'] not in self.categories['Neighborhood']:
                reasons.append('unseen_neighborhood')
            if values['Gr Liv Area'] is None or not self.area_bounds[0] <= values['Gr Liv Area'] <= self.area_bounds[1]:
                reasons.append('living_area_outside_training_support')
            if any(values[k] is not None and not bounds[0] <= values[k] <= bounds[1] for k, bounds in self.feature_bounds.items()):
                reasons.append('essential_feature_outside_training_support')
            if any(values[k] is not None and values[k] > effective.year for k in ('Year Built', 'Year Remod/Add', 'Garage Yr Blt')):
                reasons.append('future_construction_metadata')
            reasons_by_row.append(reasons)
        eligible = [index for index, reasons in enumerate(reasons_by_row) if not reasons]
        indications = dict(zip(eligible, self.numerical_predictions([rows[i] for i in eligible]))) if eligible else {}
        for index, row in enumerate(rows):
            reasons = reasons_by_row[index]
            point = low = high = None
            if not reasons:
                prices = indications[index]
                point = prices['ensemble']
                if (max(prices.values()) - min(prices.values())) * 10000 > point * 1500:
                    reasons.append('model_disagreement_over_15_percent')
                radius = self.radii['ensemble']
                low = log_to_cents(math.log(point / 100) - radius)
                high = log_to_cents(math.log(point / 100) + radius)
            results.append({'schema_version': '1.0', 'status': 'needs_review' if reasons else 'research_only', 'method': 'experimental_log_price_hedonic_ensemble', 'property_id': token(row['property_id']), 'as_of': as_of, 'model_cutoff': self.cutoff.isoformat(), 'region': self.region, 'artifact_id': self.artifact_id, 'research_point_cents': None if reasons else point, 'research_low_cents': None if reasons else low, 'research_high_cents': None if reasons else high, 'review_reasons': reasons, 'band_meaning': '90_percent_calibration_residual_band_temporal_coverage_must_be_measured_not_guaranteed', 'quote_authorized': False, 'offer_authorized': False, 'production_ready': False})
        return results
