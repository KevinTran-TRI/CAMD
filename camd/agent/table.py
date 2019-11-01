#  Copyright (c) 2019 Toyota Research Institute
"""
This module is intended to create a parameter table associated
with agent testing, e. g. to categorize Agents via numerical
vectors
"""


import numpy as np
import itertools
from indexed import IndexedOrderedDict
from tqdm import tqdm


sklearn_regressor_params = [
        {
            "@class": ["sklearn.linear_model.LinearRegression"],
            "fit_intercept": [True, False],
            "normalize": [True, False]
        },
        {
            "@class": ["sklearn.ensemble.RandomForestRegressor"],
            "n_estimators": [100],
            "max_features": list(np.arange(0.05, 1.01, 0.05)),
            "min_samples_split": list(range(2, 21)),
            "min_samples_leaf": list(range(1, 21)),
            "bootstrap": [True, False]
        },
        {
            "@class": ["sklearn.neural_network.MLPRegressor"],
            "hidden_layer_sizes": [
                # I think there's a better way to support this, but need to think
                (80, 50),
                (84, 55),
                (87, 60),
            ],
            "activation": ["identity", "logistic", "tanh", "relu"],
            "learning_rate": ["constant", "invscaling", "adaptive"]
        },
    ]


agent_params = [
    {
        "@class": ["camd.agent.agents.QBCStabilityAgent"],
        "n_query": [4, 6, 8],
        "n_members": list(range(2, 5)),
        "hull_distance": list(np.arange(0.05, 0.21, 0.05)),
        "training_fraction": [0.4, 0.5, 0.6],
        "regressor": sklearn_regressor_params
    },
    {
        "@class": ["camd.agent.agents.AgentStabilityML5"],
        "n_query": [4, 6, 8],
        "hull_distance": [0.5, 0.1, 0.15, 0.2],
        "exploit_fraction": [0.4, 0.5, 0.6],
        "regressor": sklearn_regressor_params
    },
]


class HashedParameterArray(object):
    def __init__(self, ordering=None):
        # Construct IndexedOrderedDict
        self._iod = IndexedOrderedDict()
        if ordering:
            self.extend(ordering)

    def __getitem__(self, index):
        return self._iod.keys()[index]

    def __contains__(self, item):
        return item in self._iod.keys()

    def __len__(self):
        return len(self._iod)

    # Maybe this should be push or something?
    def append(self, item):
        if item in self._iod.keys():
            return self.get_index(item)
        # Otherwise adds item
        self._iod[item] = len(self._iod)

    def extend(self, items):
        for item in items:
            self.append(item)

    def get_index(self, item):
        return self._iod[item]


class ParameterTable(object):
    def __init__(self, configs=None):
        self._parameter_names = HashedParameterArray()
        self._parameter_values = {}
        self._parameter_table = HashedParameterArray()
        for config in configs:
            self.append(config)

    def append(self, config):
        flattened_params = []
        for parameter_name, value_list in sorted(config.items()):
            # Update the parameter vectors
            if parameter_name not in self._parameter_names:
                self._parameter_names.append(parameter_name)
                if not isinstance(value_list, (list, HashedParameterArray, ParameterTable)):
                    raise ValueError("Values must be a list")
                if isinstance(value_list[0], dict):
                    value_list = ParameterTable(value_list)
                    self._parameter_values[parameter_name] = value_list
                # # Still thinking here,
                # # Just gonna keep tuples for now
                # elif isinstance(value_list[0], list):
                #     pass
                else:
                    self._parameter_values[parameter_name] = HashedParameterArray(value_list)
            else:
                if isinstance(value_list[0], dict):
                    value_list = self._parameter_values[parameter_name].extend(value_list)
                else:
                    self._parameter_values[parameter_name].extend(value_list)
            # I think this lookup could be improved
            flattened_params.append(
                [(self._parameter_names.get_index(parameter_name),
                  self._parameter_values[parameter_name].get_index(value))
                 for value in value_list]
            )
        # Accumulate and extend all_parameter_sets
        all_param_sets = []
        total = np.prod([len(el) for el in flattened_params])
        for param_set in tqdm(itertools.product(*flattened_params), total=total):
            tupled = tuple(itertools.chain.from_iterable(param_set))
            all_param_sets.append(tupled)
            self._parameter_table.append(tupled)
        return all_param_sets

    def __len__(self):
        return len(self._parameter_table)

    def __iter__(self):
        return iter(self._parameter_table)

    def __getitem__(self, item):
        return self._parameter_table[item]

    def get_index(self, value):
        return self._parameter_table._iod[value]

    def hydrate_pair(self, param_index, value_index, construct_object=False):
        name = self._parameter_names[param_index]
        values = self._parameter_values[name]
        if isinstance(values, ParameterTable):
            sub_row = values[value_index]
            return {name: values.hydrate_row(sub_row, construct_object=construct_object)}
        else:
            return {name: values[value_index]}

    def hydrate_row(self, row, construct_object=False):
        hydrated = {}

        # Group into pairs and update sequentially
        for param_index, value_index in zip(row[0::2], row[1::2]):
            hydrated.update(self.hydrate_pair(
                param_index, value_index, construct_object=construct_object))
        if construct_object:
            class_path = hydrated.get("@class")
            if class_path is not None:
                del hydrated['@class']
                constructor = load_class(class_path)
                hydrated = constructor(**hydrated)

        return hydrated

    def hydrate_index(self, index, construct_object=False):
        return self.hydrate_row(self[index], construct_object=construct_object)

    def extend(self, configs):
        all_param_sets = []
        for config in configs:
            all_param_sets.extend(self.append(config))
        return all_param_sets


def load_class(class_path):
    """
    Load and return the class from the given module.

    Args:
        class path (str): full path to class to be loaded, e. g.
            sklearn.linear_model.LinearRegression

    Returns:
        class
    """
    module_path, class_name = class_path.rsplit('.', 1)
    mod = __import__(module_path, globals(), locals(), [class_name], 0)
    return getattr(mod, class_name)


# Some things to test
# Whether prior iteration always has same first row set
# Synchronicity of order and value for parameter lists/tables


if __name__ == "__main__":
    first = ParameterTable(agent_params)
    first.hydrate_index(3)
    first.hydrate_index(3, construct_object=True)
