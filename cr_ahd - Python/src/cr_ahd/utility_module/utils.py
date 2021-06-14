import functools
import itertools
import json
import math
import random
import time
import datetime as dt
from collections import namedtuple
from pathlib import Path
from typing import List, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

Coordinates = namedtuple('Coords', ['x', 'y'])


class TimeWindow:
    def __init__(self, open: dt.datetime, close: dt.datetime):
        self.open: dt.datetime = open
        self.close: dt.datetime = close

    def __str__(self):
        return f'[D{self.open.day} {self.open.strftime("%H:%M:%S")} - D{self.close.day} {self.close.strftime("%H:%M:%S")}]'

    def __repr__(self):
        return f'[D{self.open.day} {self.open.strftime("%H:%M:%S")} - D{self.close.day} {self.close.strftime("%H:%M:%S")}]'


opts = {
    'verbose': 0,
    'plot_level': 1,
    'max_tour_length': 850,  # pretty arbitrary for now
    'alpha_1': 0.5,
    'mu': 1,
    'lambda': 2,
    'ccycler': plt.cycler(color=plt.get_cmap('Set1').colors)(),
}

working_dir = Path()
data_dir = working_dir.absolute().parent.parent.parent.joinpath('data')
input_dir = data_dir.joinpath('Input')

output_dir = data_dir.joinpath('Output')
output_dir_GH = output_dir.joinpath('Gansterer_Hartl')

# alpha 100%
univie_colors_100 = [
    '#0063A6',  # universitätsblau
    '#666666',  # universtitätsgrau
    '#A71C49',  # weinrot
    '#DD4814',  # orangerot
    '#F6A800',  # goldgelb
    '#94C154',  # hellgrün
    '#11897A',  # mintgrün
]


def map_to_univie_colors(categories: Sequence):
    colormap = {}
    for cat, color in zip(categories, itertools.cycle(univie_colors_100)):
        colormap[cat] = color
    return colormap


# alpha 80%
univie_colors_60 = [
    '#6899CA',  # universitätsblau
    '#B5B4B4',  # universtitätsgrau
    '#C26F76',  # weinrot
    '#F49C6A',  # orangerot
    '#FCCB78',  # goldgelb
    '#C3DC9F',  # hellgrün
    '#85B6AE',  # mintgrün
]
# paired
univie_colors_paired = list(itertools.chain(*zip(univie_colors_100, univie_colors_60)))

univie_cmap = LinearSegmentedColormap.from_list('univie', univie_colors_100, N=len(univie_colors_100))
univie_cmap_paired = LinearSegmentedColormap.from_list('univie_paired', univie_colors_paired,
                                                       N=len(univie_colors_100) + len(univie_colors_60))


def split_iterable(iterable, num_chunks):
    """ splits an iterable, e.g. a list into num_chunks parts of roughly the same length. If no exact split is
    possible the first chunk(s) will be longer. """
    k, m = divmod(len(iterable), num_chunks)
    return (iterable[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(num_chunks))


def _euclidean_distance(a: Coordinates, b: Coordinates):
    raise DeprecationWarning(f'Use new _euclidean_distance function!')
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def euclidean_distance(x1, y1, x2, y2):
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def make_travel_duration_matrix(vertices: List):
    """
    :param vertices: List of vertices each of class Vertex
    :return: pd.DataFrame travel time matrix
    """
    index = [i.id_ for i in vertices]
    travel_duration_matrix: pd.DataFrame = pd.DataFrame(index=index, columns=index, dtype='timedelta64[ns]')

    for i in vertices:
        for j in vertices:
            travel_duration_matrix.loc[i.id_, j.id_] = travel_time(_euclidean_distance(i.coords, j.coords))
    assert travel_duration_matrix.index.is_unique, f"Duration matrix must have unique row id's"
    return travel_duration_matrix


def travel_time(dist):
    return dt.timedelta(hours=dist / SPEED_KMH)  # compute timedelta


class InsertionError(Exception):
    """Exception raised for errors in the insertion of a request into a tour.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, expression, message):
        self.expression = expression
        self.message = message


class ConstraintViolationError(Exception):
    def __init__(self, expression='', message=''):
        self.expression = expression
        self.message = message


def timer(func):
    """Print the runtime of the decorated function"""

    @functools.wraps(func)
    def wrapper_timer(*args, **kwargs):
        start_time = time.perf_counter()  # 1
        value = func(*args, **kwargs)
        end_time = time.perf_counter()  # 2
        run_time = end_time - start_time  # 3
        if opts['verbose'] > 0:
            print(f"Finished {func.__name__!r} in {run_time:.4f} secs")
        return value, run_time

    return wrapper_timer


def unique_path(directory, name_pattern) -> Path:
    """
    construct a unique numbered file name based on a template.
    Example template: file_name + '_#{:03d}' + '.json'

    :param directory: directory which shall be the parent dir of the file
    :param name_pattern: pattern for the file name, with room for a counter
    :return: file path that is unique in the specified directory
    """
    counter = 0
    while True:
        counter += 1
        path = directory / name_pattern.format(counter)
        if not path.exists():
            return path


def ask_for_overwrite_permission(path: Path):
    if path.exists():
        permission = input(f'Should files and directories that exist at {path} be overwritten?\n[y/n]: ')
        if permission == 'y':
            return True
        else:
            raise FileExistsError
    else:
        return True


def get_carrier_by_id(carriers, id_):
    for c in carriers:
        if c.id_ == id_:
            return c
    raise ValueError


def power_set(iterable, include_empty_set=True):
    """power_set([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"""
    s = list(iterable)
    if include_empty_set:
        rng = range(len(s) + 1)
    else:
        rng = range(1, len(s) + 1)
    return itertools.chain.from_iterable(itertools.combinations(s, r) for r in rng)


def flatten(sequence: Sequence):
    if not sequence:
        return sequence
    if isinstance(sequence[0], Sequence):
        return flatten(sequence[0]) + flatten(sequence[1:])
    return sequence[:1] + flatten(sequence[1:])


def random_partition(li):
    min_chunk = 1
    max_chunk = len(li)
    it = iter(li)
    while True:
        randint = np.random.randint(min_chunk, max_chunk)
        nxt = list(itertools.islice(it, randint))
        if nxt:
            yield nxt
        else:
            break


def random_max_k_partition_idx(ls, max_k) -> List[int]:
    if max_k < 1:
        return []
    # randomly determine the actual k
    k = random.randint(1, min(max_k, len(ls)))
    # We require that this list contains k different values, so we start by adding each possible different value.
    indices = list(range(k))
    # now we add random values from range(k) to indices to fill it up to the length of ls
    indices.extend([random.choice(list(range(k))) for _ in range(len(ls) - k)])
    # shuffle the indices into a random order
    random.shuffle(indices)
    return indices


def random_max_k_partition(ls, max_k) -> Sequence[Sequence[int]]:
    """partition ls in at most k randomly sized disjoint subsets

    """
    # https://stackoverflow.com/a/45880095
    # we need to know the length of ls, so convert it into a list
    ls = list(ls)
    # sanity check
    if max_k < 1:
        return []
    # randomly determine the actual k
    k = random.randint(1, min(max_k, len(ls)))
    # Create a list of length ls, where each element is the index of
    # the subset that the corresponding member of ls will be assigned
    # to.
    #
    # We require that this list contains k different values, so we
    # start by adding each possible different value.
    indices = list(range(k))
    # now we add random values from range(k) to indices to fill it up
    # to the length of ls
    indices.extend([random.choice(list(range(k))) for _ in range(len(ls) - k)])
    # shuffle the indices into a random order
    random.shuffle(indices)
    # construct and return the random subset: sort the elements by
    # which subset they will be assigned to, and group them into sets
    partitions = []
    sorted_ = sorted(zip(indices, ls), key=lambda x: x[0])
    for index, subset in itertools.groupby(sorted_, key=lambda x: x[0]):
        partitions.append([x[1] for x in subset])
    return partitions


class MyJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, dt.datetime):
            return obj.isoformat()
        if isinstance(obj, dt.timedelta):
            return obj.total_seconds()
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super().default(obj)


def argmin(a):
    return min(range(len(a)), key=lambda x: a[x])


def argmax(a):
    return max(range(len(a)), key=lambda x: a[x])


def argsmin(a, k: int):
    """
    returns the indices of the k min arguments in a
    """
    assert k > 0
    a_sorted = sorted(range(len(a)), key=lambda x: a[x])  # indices in increasing order of values
    return a_sorted[:k]


def argsmax(a, k: int):
    """
    returns the indices of the k max arguments in a
    """
    assert k > 0
    a_sorted = sorted(range(len(a)), key=lambda x: a[x], reverse=True)  # indices in decreasing order of values
    return a_sorted[:k]


def midpoint(instance, pickup_vertex, delivery_vertex):
    pickup_x, pickup_y = instance.x_coords[pickup_vertex], instance.y_coords[delivery_vertex]
    delivery_x, delivery_y = instance.x_coords[pickup_vertex], instance.y_coords[delivery_vertex]
    return (pickup_x + delivery_x) / 2, (pickup_y + delivery_y) / 2


def midpoint_(x1, y1, x2, y2):
    return (x1 + x2) / 2, (y1 + y2) / 2


def linear_interpolation(iterable: Sequence, new_min: float, new_max: float, old_min=None, old_max=None):
    """
    return the iterable re-scaled to the range between new_min and new_max.
    https://gamedev.stackexchange.com/questions/33441/how-to-convert-a-number-from-one-min-max-set-to-another-min-max-set/33445

    """
    if old_min is None and old_max is None:
        old_min = min(iterable)
        old_max = max(iterable)
    return [((x - old_min) / (old_max - old_min)) * (new_max - new_min) + new_min for x in iterable]


def n_points_on_a_circle(n: int, radius, origin_x=0, origin_y=0):
    """create coordinates for n points that are evenly spaced on the circumference of  a circle of the given radius"""
    points = []
    for i in range(1, n + 1):
        x = radius * math.cos(2 * math.pi * i / n - math.pi / 2)
        y = radius * math.sin(2 * math.pi * i / n - math.pi / 2)
        points.append((origin_x + x, origin_y + y))
    return points


def datetime_range(start: dt.datetime, end: dt.datetime, freq: dt.timedelta, include_end=True):
    """
    returns a generator object that yields datetime objects in the range from start to end in steps of freq.
    :param include_end: determines whether the specified end is included in the range
    :return:
    """
    return (start + x * freq for x in range(((end - start) // freq) + include_end))


random.seed(0)
START_TIME = dt.datetime.min
END_TIME = dt.datetime.min + dt.timedelta(minutes=3390)
# END_TIME = dt.datetime.min + dt.timedelta(days=1)
TW_LENGTH = dt.timedelta(hours=2)
ALL_TW = [TimeWindow(e, min(e + TW_LENGTH, END_TIME)) for e in datetime_range(START_TIME, END_TIME, freq=TW_LENGTH)]
TIME_HORIZON = TimeWindow(START_TIME, END_TIME)
SPEED_KMH = 60  # vehicle speed (set to 60 to treat distance = time)
NUM_REQUESTS_TO_SUBMIT = 4  # either relative (between 0 and 1) OR an absolute number <= DYNAMIC_CYCLE_TIME
AUCTION_POOL_SIZE = 100  # 50, 100, 200, 300, 500
