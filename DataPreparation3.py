import csv
import os.path
import shutil

import category_encoders as ce
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelBinarizer
from sklearn.preprocessing import MinMaxScaler

import ExperimentSettings3 as es


class DataPreparations:

    def __init__(self):
        self.__prepared_params = {}
        data_config = es.data_sets[es.dataset_name]
        self.target_col = data_config['target_col']
        self.original_categ_cols = data_config['original_categ_cols']
        self.user_cols = data_config['user_cols']
        self.skip_cols = data_config['skip_cols']
        self.hists_already_determined = data_config['hists_already_determined']
        self.df_max_size = es.df_max_size
        self.train_frac = es.train_frac
        self.valid_frac = es.valid_frac
        self.h1_frac = es.h1_frac
        self.h2_len = es.h2_len
        self.seeds = data_config['seeds']
        self.inner_seeds = data_config['inner_seeds']
        self.weights_num = data_config['weights_num']
        self.weights_range = es.weights_range
        self.model_params = es.model_params
        self.min_hist_len = es.min_hist_len
        self.max_hist_len = es.max_hist_len
        self.metrics = es.metrics
        self.min_hist_len_to_test = es.min_hist_len_to_test
        self.__run_prepartion()

        # weights_num, weights_range, model_params, min_hist_len, \
        # max_hist_len, metrics, min_hist_len_to_test

    def get_experiment_parameters(self):
        return self.__prepared_params

    def __run_prepartion(self):

        no_compat_equality_groups = [['no hist', 'm4', 'm6'], ['m1', 'm2', 'm3'], ['m5', 'm7', 'm8']]
        no_compat_equality_groups_per_model = {}
        for group in no_compat_equality_groups:
            for member in group:
                no_compat_equality_groups_per_model[member] = group

        # TODO SKIP cols
        # skip cols
        # user_cols_not_skipped = []
        # for user_col in self.user_cols:
        #     if user_col not in self.skip_cols:
        #         user_cols_not_skipped.append(user_col)
        # original_categs_not_skipped = []
        # for categ in self.original_categ_cols:
        #     if categ not in self.skip_cols:
        #         original_categs_not_skipped.append(categ)
        # user_cols = user_cols_not_skipped
        # original_categ_cols = original_categs_not_skipped

        # create results dir
        # TODO TODAY
        # dataset_path = '%s/%s.csv' % (dataset_dir, dataset_name)
        # if overwrite_result_folder and os.path.exists(result_dir):
        #     shutil.rmtree(result_dir)
        # if not os.path.exists(result_dir):
        #     os.makedirs(result_dir)
        #     with open('%s/parameters.csv' % result_dir, 'w', newline='') as file_out:
        #         writer = csv.writer(file_out)
        #         writer.writerow(['train_frac', 'valid_frac', 'dataset_max_size', 'h1_frac', 'h2_len', 'seeds',
        #                          'inner_seeds', 'weights_num', 'weights_range', 'min_hist_len', 'max_hist_len',
        #                          'skip_cols', 'model_type', 'params'])
        #         writer.writerow(
        #             [self.train_frac, self.valid_frac, self.df_max_size, self.h1_frac, self.h2_len, len(self.seeds), len(self.inner_seeds),
        #              self.weights_num, str(self.weights_range), self.min_hist_len, self.max_hist_len,
        #              str(self.skip_cols), model_type, chosen_params])
        # header = ['user', 'len', 'seed', 'inner_seed', 'h1_acc', 'weight']
        # for model_name in model_names:
        #     header.extend(['%s x' % model_name, '%s y' % model_name])

        self.__create_params_file()

        # run whole experiment for each user column selection
        self.__load_user_prepared_params(no_compat_equality_groups_per_model)

    def __load_user_prepared_params(self, no_compat_equality_groups_per_model):
        diss_weights = list(np.linspace(0, 1, self.weights_num))
        user_col = es.data_sets[es.dataset_name]['user_cols'][0]

        print('user column = %s' % user_col)

        result_type_dir = '%s/%s' % (es.result_dir, user_col)
        done_by_seed = self.__write_result(result_type_dir)

        cache_dir = '%s/caches/%s skip_%s max_len_%d min_hist_%d max_hist_%d balance_%s' % (
            es.dataset_dir, user_col, len(self.skip_cols), self.df_max_size, self.min_hist_len, self.max_hist_len,
            False)
        if es.reset_cache and os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
        safe_make_dir(cache_dir)

        self.__load_seeds_in_cache(cache_dir, user_col)

        self.__prepared_params = self.__get_prepared_params(cache_dir, user_col, diss_weights, result_type_dir,
                                                            no_compat_equality_groups_per_model, done_by_seed)

        # TODO groups_by_user
        # print("determine experiment's users...")
        # min_max_col_values = pd.read_csv('%s/all_columns.csv' % cache_dir, dtype=np.int64)
        # all_columns = min_max_col_values.columns
        #
        # dataset = pd.read_csv('%s/0.csv' % cache_dir)
        #
        # groups_by_user = dataset.groupby(user_col, sort=False)
        # hists_by_user = {}
        # hist_train_ranges = {}
        # curr_h2_len = 0
        # num_users_to_test = 0
        # user_ids = []
        #
        # for user_id, hist in groups_by_user:
        #     user_ids.append(user_id)
        #     hist = hist.drop(columns=[user_col])
        #
        #     hist_train_len = len(hist) * self.train_frac
        #     if self.hists_already_determined or (
        #             self.min_hist_len <= hist_train_len and curr_h2_len + hist_train_len <= self.h2_len):
        #         if len(hist) >= self.min_hist_len_to_test:
        #             num_users_to_test += 1
        #         if len(hist) > self.max_hist_len:
        #             hist = hist[:self.max_hist_len]
        #         hists_by_user[user_id] = hist
        #         min_max_col_values = min_max_col_values.append(hist.apply(min_and_max), sort=False)
        #
        #         hist_train_ranges[user_id] = [curr_h2_len, len(hist)]
        #         curr_h2_len += len(hist)
        #
        # del groups_by_user
        #
        # print('cols=%d data_len=%d h1_frac=%s users=%d diss_weights=%d model_type=%s auto_tune_params=%s' % (
        #     len(all_columns) - 1, curr_h2_len, self.h1_frac, len(hists_by_user), len(diss_weights), model_type,
        #     True))
        #
        # # hists_by_user
        #
        # min_max_col_values = min_max_col_values.reset_index(drop=True)
        # scaler, labelizer = MinMaxScaler(), LabelBinarizer()
        # labelizer.fit(min_max_col_values[[self.target_col]])
        # del min_max_col_values
        #
        # self.__prepared_params = {
        #     'seeds': self.seeds, 'inner_seeds': self.inner_seeds, 'num_users_to_test': num_users_to_test,
        #     'done_by_seed': done_by_seed, 'hists_by_user': hists_by_user, 'target_col': self.target_col,
        #     'scaler': scaler, 'labelizer': labelizer, 'user_ids': user_ids, 'all_columns': all_columns,
        #     'hist_train_ranges': hist_train_ranges, 'chosen_params': es.model_params['params'],
        #     'model_type': model_type,
        #     'diss_weights': diss_weights, 'no_compat_equality_groups_per_model': no_compat_equality_groups_per_model,
        #     'result_type_dir': result_type_dir
        # }

    def __get_prepared_params(self, cache_dir, user_col, diss_weights, result_type_dir,
                              no_compat_equality_groups_per_model, done_by_seed):
        model_type = es.model_params['name']
        hists_by_user = {}
        hist_train_ranges = {}
        curr_h2_len = 0
        num_users_to_test = 0
        user_ids = []
        # done_by_seed = {}

        print("determine experiment's users...")
        min_max_col_values = pd.read_csv('%s/all_columns.csv' % cache_dir, dtype=np.int64)
        all_columns = min_max_col_values.columns
        dataset = pd.read_csv('%s/0.csv' % cache_dir)
        groups_by_user = dataset.groupby(user_col, sort=False)

        for user_id, hist in groups_by_user:
            user_ids.append(user_id)
            hist = hist.drop(columns=[user_col])

            hist_train_len = len(hist) * self.train_frac
            if self.hists_already_determined or (
                    self.min_hist_len <= hist_train_len and curr_h2_len + hist_train_len <= self.h2_len):
                if len(hist) >= self.min_hist_len_to_test:
                    num_users_to_test += 1
                if len(hist) > self.max_hist_len:
                    hist = hist[:self.max_hist_len]
                hists_by_user[user_id] = hist
                min_max_col_values = min_max_col_values.append(hist.apply(min_and_max), sort=False)

                hist_train_ranges[user_id] = [curr_h2_len, len(hist)]
                curr_h2_len += len(hist)
        del groups_by_user

        print('cols=%d data_len=%d h1_frac=%s users=%d diss_weights=%d model_type=%s auto_tune_params=%s' % (
            len(all_columns) - 1, curr_h2_len, self.h1_frac, len(hists_by_user), len(diss_weights), model_type, True))

        # hists_by_user
        min_max_col_values = min_max_col_values.reset_index(drop=True)
        scaler, labelizer = MinMaxScaler(), LabelBinarizer()
        labelizer.fit(min_max_col_values[[self.target_col]])
        del min_max_col_values

        prepared_params = {
            'seeds': self.seeds, 'inner_seeds': self.inner_seeds, 'num_users_to_test': num_users_to_test,
            'done_by_seed': done_by_seed, 'hists_by_user': hists_by_user, 'target_col': self.target_col,
            'scaler': scaler, 'labelizer': labelizer, 'user_ids': user_ids, 'all_columns': all_columns,
            'hist_train_ranges': hist_train_ranges, 'chosen_params': es.model_params['params'],
            'model_type': model_type,
            'diss_weights': diss_weights, 'no_compat_equality_groups_per_model': no_compat_equality_groups_per_model,
            'result_type_dir': result_type_dir
        }
        return prepared_params

    def __load_seeds_in_cache(self, cache_dir, user_col):
        all_seeds_in_cache = True
        if not os.path.exists('%s/0.csv' % cache_dir):
            all_seeds_in_cache = False

        print('loading %s dataset...' % es.dataset_name)
        if all_seeds_in_cache:
            return
        categ_cols = es.data_sets[es.dataset_name]['original_categ_cols']
        try:  # dont one hot encode the user_col
            categ_cols.remove(user_col)
        except ValueError:
            pass

        dataset_full = self.__load_data(user_col, categ_cols)

        if self.hists_already_determined:  # todo: handle multiple seeds when balancing
            dataset_full.to_csv('%s/0.csv' % cache_dir, index=False)
            if not os.path.exists('%s/all_columns.csv' % cache_dir):
                pd.DataFrame(columns=list(dataset_full.drop(columns=[user_col]).columns)).to_csv(
                    '%s/all_columns.csv' % cache_dir, index=False)
        else:
            self.__sort_user_histories(dataset_full, user_col, cache_dir)
        del dataset_full

    def __load_data(self, user_col, categ_cols):

        dataset_full = pd.read_csv(es.dataset_path).drop(columns=self.skip_cols)
        if 'timestamp' in dataset_full.columns:
            dataset_full = dataset_full.drop(columns='timestamp')
        if self.df_max_size > 1:
            dataset_full = dataset_full[:self.df_max_size]
        elif self.df_max_size > 0:  # is a fraction
            dataset_full = dataset_full[:int(len(dataset_full) * self.df_max_size)]

        print('one-hot encoding the data... ')
        col_groups_dict = {}
        categs_unique_values = dataset_full[categ_cols].nunique()
        i = 0
        for col in dataset_full.columns:
            if col in [user_col, self.target_col]:
                continue
            unique_count = 1
            if col in categ_cols:
                unique_count = categs_unique_values[col]
            col_groups_dict[col] = range(i, i + unique_count)
            i = i + unique_count

        dataset_full = ce.OneHotEncoder(cols=categ_cols, use_cat_names=True).fit_transform(dataset_full)

        return dataset_full

    def __sort_user_histories(self, dataset_full, user_col, cache_dir):

        print('sorting histories...')
        groups_by_user = dataset_full.groupby(user_col, sort=False)
        dataset_full = dataset_full.drop(columns=[user_col])
        all_columns = list(dataset_full.columns)
        if not os.path.exists('%s/all_columns.csv' % cache_dir):
            pd.DataFrame(columns=all_columns).to_csv('%s/all_columns.csv' % cache_dir, index=False)

        # get user histories
        for seed in self.seeds:
            if not os.path.exists('%s/%d.csv' % (cache_dir, seed)):
                hists = {}
                for user_id in groups_by_user.groups.keys():
                    hist = groups_by_user.get_group(user_id).drop(columns=[user_col])
                    if len(hist) < self.min_hist_len:
                        continue

                    hists[user_id] = hist
                sorted_hists = [[k, v] for k, v in reversed(sorted(hists.items(), key=lambda n: len(n[1])))]
                seed_df = pd.DataFrame(columns=[user_col] + all_columns, dtype=np.int64)
                for user_id, hist in sorted_hists:
                    hist[user_col] = [user_id] * len(hist)
                    seed_df = seed_df.append(hist, sort=False)
                seed_df.to_csv('%s/0.csv' % cache_dir, index=False)
            # if not balance_histories:
            break
        del groups_by_user
        del hists

    def __write_result(self, result_type_dir):

        done_by_seed = {}
        header = get_results_header()

        # create all folders
        if not os.path.exists(result_type_dir):
            for metric in self.metrics:
                os.makedirs('%s/%s' % (result_type_dir, metric))
                for subset in ['train', 'valid', 'test']:
                    with open('%s/%s/%s_log.csv' % (result_type_dir, metric, subset), 'w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(header)
        else:  # load what is already done
            df_done = pd.read_csv('%s/%s/test_log.csv' % (result_type_dir, self.metrics[-1]))
            groups_by_seed = df_done.groupby('seed')
            for seed, seed_group in groups_by_seed:
                done_by_inner_seed = {}
                done_by_seed[seed] = done_by_inner_seed
                groups_by_inner_seed = seed_group.groupby('inner_seed')
                for inner_seed, inner_seed_group in groups_by_inner_seed:
                    done_by_inner_seed[inner_seed] = len(pd.unique(inner_seed_group['user']))
            del df_done

        return done_by_seed

    def __create_params_file(self):
        if es.overwrite_result_folder and os.path.exists(es.result_dir):
            shutil.rmtree(es.result_dir)
        if not os.path.exists(es.result_dir):
            os.makedirs(es.result_dir)
            with open('%s/parameters.csv' % es.result_dir, 'w', newline='') as file_out:
                writer = csv.writer(file_out)
                writer.writerow(['train_frac', 'valid_frac', 'dataset_max_size', 'h1_frac', 'h2_len', 'seeds',
                                 'inner_seeds', 'weights_num', 'weights_range', 'min_hist_len', 'max_hist_len',
                                 'skip_cols', 'model_type', 'params'])
                writer.writerow(
                    [self.train_frac, self.valid_frac, self.df_max_size, self.h1_frac, self.h2_len, len(self.seeds),
                     len(self.inner_seeds),
                     self.weights_num, str(self.weights_range), self.min_hist_len, self.max_hist_len,
                     str(self.skip_cols), es.model_params['name'], es.model_params['params']])


def safe_make_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def min_and_max(x):
    return pd.Series(index=['min', 'max'], data=[x.min(), x.max()])


def get_results_header():
    header = ['user', 'len', 'seed', 'inner_seed', 'h1_acc', 'weight']
    for model_name in es.model_names:
        header.extend(['%s x' % model_name, '%s y' % model_name])
    return header