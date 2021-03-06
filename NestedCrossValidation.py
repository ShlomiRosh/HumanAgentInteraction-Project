import random

import numpy as np
import pandas as pd

import ExperimentSettings as es
import Runner as r
from Models import Model, evaluate_params


class NestedCrossValidationProcess:

    def __init__(self, params, timer_params):
        self.timers_params = timer_params
        self.loops_params = {}
        self.seeds_params = {}
        self.__run_nested_cross_validation(params)

    def __run_nested_cross_validation(self, params):
        print('\n [INFO]    Start running nested cross-validation...\n')
        self.__outer_folds_loop(params)
        print('\n [INFO]    Running nested cross-validation completed!\n')

    def __outer_folds_loop(self, params):
        self.loops_params.update({'params_list': None, 'loop_modes': [True, False]})
        for seed_idx, seed in enumerate(params['seeds']):
            self.seeds_params.update({'seed_idx': seed_idx, 'seed': seed})
            if self.__check_if_seed_done(params):
                continue
            self.loops_params.update({'hists_seed_by_user': {}, 'hist_train_and_valid_ranges': {}})
            self.loops_params['h2_train_and_valid'] = pd.DataFrame(columns=params['all_columns'], dtype=np.float32)
            self.__split_test_sets_by_user_history(params)
            self.__inner_folds_loop(params)
            self.__test_models(params)

    def __check_if_seed_done(self, params):
        # check if seed was already done
        if self.seeds_params['seed'] in params['done_by_seed']:
            self.loops_params.update({'done_by_inner_seed': params['done_by_seed'][self.seeds_params['seed']]})
            seed_is_done = len(self.loops_params['done_by_inner_seed']) == len(params['inner_seeds']) and all(
                [done_users == len(params['hists_by_user']) for i, done_users in
                 self.loops_params['done_by_inner_seed'].items()])
        else:
            self.loops_params.update({'done_by_inner_seed': {}})
            seed_is_done = False
        if seed_is_done:
            self.timers_params['timer_evaluating_params'].curr_iteration += len(params['inner_seeds']) * len(
                params['hists_by_user'])
            self.timers_params['timer_validation_results'].curr_iteration += len(params['inner_seeds']) * len(
                params['hists_by_user'])
            self.timers_params['timer_test_results'].curr_iteration += len(params['hists_by_user'])
        return seed_is_done

    def __split_test_sets_by_user_history(self, params):
        for user_idx, item in enumerate(params['hists_by_user'].items()):
            user_id, hist = item
            valid_len, test_len = int(len(hist) * es.valid_frac), int(len(hist) * es.test_frac)
            min_idx = 3 * valid_len  # |train set| >= 2|valid set|
            delta = len(hist) - test_len - min_idx  # space between min_idx and test_start_idx
            delta_frac = list(np.linspace(1, 0, len(params['seeds'])))
            random.seed(user_idx), random.shuffle(delta_frac)
            test_start_idx = min_idx + int(delta * delta_frac[self.seeds_params['seed']])
            hist_train_and_valid = hist.iloc[0: test_start_idx]
            hist_test = hist.iloc[test_start_idx: test_start_idx + test_len + 1]
            self.loops_params['hist_train_and_valid_ranges'][user_id] = [
                len(self.loops_params['h2_train_and_valid']),
                len(self.loops_params['h2_train_and_valid']) + len(hist_train_and_valid)]
            self.loops_params['h2_train_and_valid'] = self.loops_params['h2_train_and_valid'].append(
                hist_train_and_valid, ignore_index=True, sort=False)
            hist_test_x = hist_test.drop(columns=[params['target_col']])
            hist_test_y = params['labelizer'].transform(hist_test[[params['target_col']]]).ravel()
            self.loops_params['hists_seed_by_user'][user_id] = [hist_train_and_valid, hist_test_x, hist_test_y]
        self.loops_params['h2_train_and_valid_x'] = self.loops_params['h2_train_and_valid'].drop(columns=[
            params['target_col']])
        self.loops_params['h2_train_and_valid_y'] = params['labelizer'].transform(
            self.loops_params['h2_train_and_valid'][[params['target_col']]]).ravel()

    def __inner_folds_loop(self, params):
        for evaluating_params in self.loops_params['loop_modes']:
            self.loops_params.update({'done_last_users': 0, 'best_params_per_user': {}})
            if evaluating_params:
                self.loops_params['scores_per_user'] = {u: {m: [] for m in es.model_names} for u in params['user_ids']}
            else:
                self.loops_params['best_params_per_user'] = {
                    u: {m: self.loops_params['params_list'][
                        np.argmax(np.mean(self.loops_params['scores_per_user'][u][m], axis=0))]
                        for m in es.model_names} for u in params['user_ids']}
            for inner_seed_idx, inner_seed in enumerate(params['inner_seeds']):
                self.seeds_params.update({'inner_seed_idx': inner_seed_idx, 'inner_seed': inner_seed})
                if not evaluating_params:
                    # check if inner seed was already done
                    if inner_seed in self.loops_params['done_by_inner_seed']:
                        self.loops_params['done_last_users'] = self.loops_params['done_by_inner_seed'][inner_seed]
                        inner_seed_is_done = self.loops_params['done_last_users'] == len(params['hists_by_user'])
                    else:
                        self.loops_params['done_last_users'] = 0
                        inner_seed_is_done = False
                    if inner_seed_is_done:
                        self.timers_params['timer_validation_results'].curr_iteration += len(params['hists_by_user'])
                        continue
                self.__split_to_train_and_validation(params)
                self.__user_loop(params, evaluating_params)

    def __split_to_train_and_validation(self, params):
        # split to train and validation sets
        self.loops_params.update({'hists_inner_seed_by_user': {}})
        h1_train = pd.DataFrame(columns=params['all_columns'], dtype=np.float32)
        self.loops_params['h2_train'] = pd.DataFrame(columns=params['all_columns'], dtype=np.float32)
        h2_valid = pd.DataFrame(columns=params['all_columns'], dtype=np.float32)
        for user_idx, entry in enumerate(self.loops_params['hists_seed_by_user'].items()):
            user_id, item = entry
            hist_train_and_valid, hist_test_x, hist_test_y = item
            hist_len = params['hist_train_ranges'][user_id][1]
            valid_len = int(hist_len * es.valid_frac)
            delta = len(hist_train_and_valid) - 2 * valid_len  # space between min_idx and valid_start
            delta_frac = list(np.linspace(1, 0, len(params['inner_seeds'])))
            random.seed(user_idx)
            random.shuffle(delta_frac)
            valid_start_idx = valid_len + int(delta * delta_frac[self.seeds_params['inner_seed']])
            hist_train = hist_train_and_valid.iloc[0: valid_start_idx]
            hist_valid = hist_train_and_valid.iloc[valid_start_idx:]
            params['hist_train_ranges'][user_id][0] = [len(self.loops_params['h2_train']),
                                                       len(self.loops_params['h2_train']) + len(hist_train)]
            h1_hist_train = hist_train[:max(int(len(hist_train_and_valid) * es.h1_frac), 1)]
            h1_train = h1_train.append(h1_hist_train, ignore_index=True, sort=False)
            self.loops_params['h2_train'] = self.loops_params['h2_train'].append(hist_train, ignore_index=True,
                                                                                 sort=False)
            h2_valid = h2_valid.append(hist_valid, ignore_index=True, sort=False)
            self.loops_params['hists_inner_seed_by_user'][user_id] = [hist_train, hist_valid, hist_test_x, hist_test_y]
            h1_train_x = h1_train.drop(columns=[params['target_col']])
        self.loops_params['h2_train_x'] = self.loops_params['h2_train'].drop(columns=[params['target_col']])
        h2_valid_x = h2_valid.drop(columns=[params['target_col']])
        self.loops_params['h2_train_y'] = params['labelizer'].transform(
            self.loops_params['h2_train'][[params['target_col']]]).ravel()
        h2_valid_y = params['labelizer'].transform(h2_valid[[params['target_col']]]).ravel()
        h1_train_y = params['labelizer'].transform(h1_train[[params['target_col']]]).ravel()
        tuning_x, tuning_y = h2_valid_x, h2_valid_y
        scores, evaluated_params = evaluate_params(
            params['model_type'], h1_train_x, h1_train_y, tuning_x, tuning_y, es.metrics[0],
            params['chosen_params'], get_autc=es.autotune_autc, verbose=es.verbose)
        if self.loops_params['params_list'] is None:
            self.loops_params['params_list'] = evaluated_params
        self.loops_params['h1'] = Model(params['model_type'], 'h1',
                                        params=self.loops_params['params_list'][np.argmax(scores)])
        self.loops_params['h1'].fit(h1_train_x, h1_train_y)

    def __user_loop(self, params, evaluating_params):
        self.loops_params['user_count'] = 0
        for user_id, item in self.loops_params['hists_inner_seed_by_user'].items():
            self.loops_params['hist_train'], self.loops_params['hist_valid'], hist_test_x, hist_test_y = item
            self.loops_params['hist_train_range'] = np.zeros(len(self.loops_params['h2_train']))
            start_idx, end_idx = params['hist_train_ranges'][user_id][0]
            self.loops_params['hist_train_range'][start_idx:end_idx] = 1
            self.loops_params['hist_len'] = len(self.loops_params['hist_train'])
            self.loops_params['user_count'] += 1
            if not evaluating_params:
                if self.loops_params['user_count'] <= self.loops_params['done_last_users']:
                    self.timers_params['timer_validation_results'].curr_iteration += 1
                    continue
                self.timers_params['timer_validation_results'].start_iteration()
            else:
                self.timers_params['timer_evaluating_params'].start_iteration()
            self.__train_all_models(params, evaluating_params, user_id)
            self.loops_params['runtime'] = self.timers_params['timer_evaluating_params'].end_iteration() if \
                evaluating_params else self.timers_params['timer_validation_results'].end_iteration()
            self.loops_params['mod_str'] = 'params' if evaluating_params else 'valid'
            r.log_progress(params, self.loops_params, self.timers_params, self.seeds_params)

    def __train_all_models(self, params, evaluating_params, user_id):
        self.loops_params['hist_train_x'] = self.loops_params['hist_train'].drop(columns=[params['target_col']])
        self.loops_params['hist_valid_x'] = self.loops_params['hist_valid'].drop(columns=[params['target_col']])
        self.loops_params['hist_train_y'] = params['labelizer'].transform(
            self.loops_params['hist_train'][[params['target_col']]]).ravel()
        self.loops_params['hist_valid_y'] = params['labelizer'].transform(
            self.loops_params['hist_valid'][[params['target_col']]]).ravel()
        tuning_x, tuning_y = self.loops_params['hist_valid_x'], self.loops_params['hist_valid_y']
        # train all models
        if evaluating_params:
            scores_per_model = {}
            for model_name in es.model_names:
                found = False
                if not es.autotune_autc:  # look for best params to steal from other models
                    for member in params['no_compat_equality_groups_per_model'][model_name]:
                        if member in scores_per_model:
                            scores_per_model[model_name] = scores_per_model[member]
                            found = True
                            break
                if not found:
                    subset_weights = es.models_to_test[model_name]
                    scores = evaluate_params(
                        params['model_type'], self.loops_params['h2_train_x'], self.loops_params['h2_train_y'],
                        tuning_x, tuning_y, es.metrics[0],
                        params['chosen_params'], subset_weights, self.loops_params['h1'],
                        self.loops_params['hist_train_range'],
                        get_autc=es.autotune_autc, verbose=es.verbose)[0]
                    scores_per_model[model_name] = scores
                scores = scores_per_model[model_name]
                self.loops_params['scores_per_user'][user_id][model_name].append(scores)
        else:
            if not es.only_test:
                best_params_per_model = self.loops_params['best_params_per_user'][user_id]
                self.loops_params['models_by_weight'] = []
                for weight_idx, weight in enumerate(params['diss_weights']):
                    self.loops_params['models'] = []
                    self.loops_params['models_by_weight'].append(self.loops_params['models'])
                    for model_name in es.model_names:
                        subset_weights = es.models_to_test[model_name]
                        best_params = best_params_per_model.get(model_name, params['chosen_params'])
                        model = Model(params['model_type'], model_name, self.loops_params['h1'], weight,
                                      subset_weights, self.loops_params['hist_train_range'], params=best_params)
                        model.fit(self.loops_params['h2_train_x'], self.loops_params['h2_train_y'])
                        self.loops_params['models'].append(model)
                self.__test_inner_loop_models_on_validation(params, user_id)
                r.write_rows_to_all_logs(params, self.loops_params)

    def __test_inner_loop_models_on_validation(self, params, user_id):
        # test all models on validation set
        self.loops_params['rows_by_metric'] = []
        for metric in es.metrics:
            rows_by_subset = []
            self.loops_params['rows_by_metric'].append(rows_by_subset)
            for subset in ['train', 'valid']:
                x, y = eval("self.loops_params['hist_%s_x']" % subset), eval("self.loops_params['hist_%s_y']" % subset)
                rows = []
                rows_by_subset.append(rows)
                h1_y = self.loops_params['h1'].score(x, y, metric)['y']
                for weight_idx, weight in enumerate(params['diss_weights']):
                    self.loops_params['models'] = self.loops_params['models_by_weight'][weight_idx]
                    row = [user_id, self.loops_params['hist_len'], self.seeds_params['seed'],
                           self.seeds_params['inner_seed'], h1_y, weight]
                    for i, model in enumerate(self.loops_params['models']):
                        result = model.score(x, y, metric)
                        com, acc = result['x'], result['y']
                        row.extend([com, acc])
                    rows.append(row)

    def __test_models(self, params):
        user_count = 0
        for user_idx, entry in enumerate(self.loops_params['hists_seed_by_user'].items()):
            self.timers_params['timer_test_results'].start_iteration()
            user_count += 1
            user_id, item = entry
            hist_train_and_valid, hist_test_x, hist_test_y = item
            hist_train_and_valid_range = np.zeros(len(self.loops_params['h2_train_and_valid']))
            start_idx, end_idx = self.loops_params['hist_train_and_valid_ranges'][user_id]
            hist_train_and_valid_range[start_idx:end_idx] = 1
            hist_len = len(hist_train_and_valid)
            best_params_per_model = self.loops_params['best_params_per_user'][user_id]
            models_by_weight = []
            for weight_idx, weight in enumerate(params['diss_weights']):
                models = []
                models_by_weight.append(models)
                for model_name in es.model_names:
                    subset_weights = es.models_to_test[model_name]
                    best_params = best_params_per_model.get(model_name, params['chosen_params'])
                    model = Model(params['model_type'], model_name, self.loops_params['h1'], weight, subset_weights,
                                  hist_train_and_valid_range, params=best_params)
                    model.fit(self.loops_params['h2_train_and_valid_x'], self.loops_params['h2_train_and_valid_y'])
                    models.append(model)
            # test all models on validation set
            rows_by_metric = []
            for metric in es.metrics:
                rows = []
                rows_by_metric.append(rows)
                h1_y = self.loops_params['h1'].score(hist_test_x, hist_test_y, metric)['y']
                for weight_idx, weight in enumerate(params['diss_weights']):
                    models = models_by_weight[weight_idx]
                    row = [user_id, hist_len, self.seeds_params['seed'], self.seeds_params['inner_seed'], h1_y, weight]
                    for i, model in enumerate(models):
                        result = model.score(hist_test_x, hist_test_y, metric)
                        com, acc = result['x'], result['y']
                        row.extend([com, acc])
                    rows.append(row)
            r.write_test_log(params, rows_by_metric)
            # end iteration
            self.loops_params['runtime'] = self.timers_params['timer_test_results'].end_iteration()
            self.loops_params['mod_str'] = 'test'
            r.log_progress(params, self.loops_params, self.timers_params, self.seeds_params)
